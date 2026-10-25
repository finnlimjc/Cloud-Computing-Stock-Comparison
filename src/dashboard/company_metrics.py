import pandas as pd
import streamlit as st

from src.analysis import analyst, fundamentals
from src.dashboard.analysis import load_company_snapshots, rated_companies, valuation_text
from src.dashboard.config import COMPARISON_METRICS, STOCK_COLORS, VALUATION_HELP
from src.plots import company_plots

# Layout
VALUATION_CARD_HEIGHT = 95
CHART_CONFIG = {"displayModeBar": False}
ANALYST_VIEWS = ["Latest", "Trend"]

# Financials table
FINANCIALS_FORMAT = "{:,.4f}"
CAGR_FORMAT = "{:+.1f}%"
MISSING_VALUE = "—"

# Radar scoring
RANGE_ROW_WIDTHS = [3, 2, 2]
RANGE_INPUT_KEY = "radar_range_{bound}_{label}"

def _reset_score_ranges() -> None:
    for label, (low, high) in fundamentals.default_score_ranges().items():
        st.session_state[RANGE_INPUT_KEY.format(bound="low", label=label)] = low
        st.session_state[RANGE_INPUT_KEY.format(bound="high", label=label)] = high

def render_score_method() -> dict[str, tuple[float, float]]:
    """
    Explain how each radar ratio is scored and let the user edit the low and high reference values.
    
    Outputs:
    - (low, high) reference values keyed by dimension label; rows where low is not below high keep their defaults
    """
    defaults = fundamentals.default_score_ranges()
    with st.expander("How the score is calculated"):
        st.markdown(
            "Each ratio is placed on a scale between a low and a high reference value:\n\n"
            "**score = (actual - low) / (high - low) x 100**, capped at 0 and 100.\n\n"
            "A company at the low value scores 0, one at the high value scores 100, and anything beyond either end is held at the edge. "
            "The defaults are typical for large listed companies; change **Low** and **High** to score against your own range. "
            "Average balances use the prior and current year-ends."
        )
        # Seeding session state (rather than passing value=) lets the reset callback overwrite the inputs
        for label, (low, high) in defaults.items():
            st.session_state.setdefault(RANGE_INPUT_KEY.format(bound="low", label=label), low)
            st.session_state.setdefault(RANGE_INPUT_KEY.format(bound="high", label=label), high)
        st.button("Reset to defaults", key="radar_ranges_reset", on_click=_reset_score_ranges)
        
        # Create Table
        header = st.columns(RANGE_ROW_WIDTHS)
        header[0].markdown("**Ratio**")
        header[1].markdown("**Low** (scores 0)")
        header[2].markdown("**High** (scores 100)")
        
        ranges = {}
        invalid = []
        for dimension in fundamentals.RADAR_DIMENSIONS:
            # Format
            label = dimension.label
            formula = dimension.definition.format(year="t", prior="t-1") # Mainly for Revenue Growth
            step = 0.1 if dimension.unit == "x" else 1.0
            number_format = "%.2f" if dimension.unit == "x" else "%.1f"
            
            # Inputs
            row = st.columns(RANGE_ROW_WIDTHS, vertical_alignment="center")
            row[0].markdown(f"{label} ({dimension.unit})", help=f"{dimension.meaning}\n\nFormula: {formula}")
            low = row[1].number_input(
                f"{label} low", step=step, format=number_format, label_visibility="collapsed",
                key=RANGE_INPUT_KEY.format(bound="low", label=label)
            )
            high = row[2].number_input(
                f"{label} high", step=step, format=number_format, label_visibility="collapsed",
                key=RANGE_INPUT_KEY.format(bound="high", label=label)
            )
            
            # Check Inputs
            if low >= high:
                invalid.append(label)
                ranges[label] = defaults[label]
            else:
                ranges[label] = (float(low), float(high))
        
        if invalid:
            st.warning(f"Low must be below High, so the default range is used for: {', '.join(invalid)}.")
    return ranges

def render_valuation(snapshots:list[dict]) -> None:
    """Render valuation cards for one company, or a table with one row per company."""
    if len(snapshots) == 1:
        snapshot = snapshots[0]
        cards = st.columns(len(VALUATION_HELP), gap="small")
        for card, name in zip(cards, VALUATION_HELP):
            with card:
                with st.container(border=True, height=VALUATION_CARD_HEIGHT):
                    value = valuation_text(name, snapshot["valuation"][name], snapshot["valuation"]["Currency"])
                    st.metric(name, value, help=VALUATION_HELP[name])
        return
    
    tickers = [snapshot["ticker"] for snapshot in snapshots]
    columns = {}
    column_config = {"_index": st.column_config.TextColumn("Ticker")}
    for name in VALUATION_HELP:
        values = [valuation_text(name, snapshot["valuation"][name], snapshot["valuation"]["Currency"]) for snapshot in snapshots]
        columns[name] = pd.Series(values, index=tickers, dtype="string")
        column_config[name] = st.column_config.TextColumn(name, help=VALUATION_HELP[name])
    st.dataframe(pd.DataFrame(columns), column_config=column_config, width="stretch")

def render_financials(snapshots:list[dict], key_suffix:str) -> None:
    """Render the metric picker and a table of every common fiscal year with a trend sparkline and CAGR."""
    with st.container(border=True, key="financials_card"):
        st.subheader("Key Financials")
        metric = st.pills(
            "Metric",
            COMPARISON_METRICS,
            selection_mode="single",
            default=COMPARISON_METRICS[0],
            label_visibility="collapsed",
            key=f"financials_metric_{key_suffix}"
        ) or COMPARISON_METRICS[0] #pills can be deselected
        
        history = fundamentals.build_metric_history(snapshots, metric)
        year_columns = [column for column in history.columns if column != fundamentals.CAGR_COLUMN]
        if not year_columns:
            st.info("These companies have no fiscal years in common.")
            return
        
        table = history.copy()
        table["Trend"] = [[value for value in row if not pd.isna(value)] for row in history[year_columns].to_numpy()] #sparklines break on missing years
        styled = table.style.format(FINANCIALS_FORMAT, subset=year_columns, na_rep=MISSING_VALUE).format(
            CAGR_FORMAT, subset=[fundamentals.CAGR_COLUMN], na_rep=MISSING_VALUE
        )
        column_config = {
            "_index": st.column_config.TextColumn("Ticker"),
            "Trend": st.column_config.LineChartColumn("Trend", help=f"{metric} over the years with data, {year_columns[0]} to {year_columns[-1]}."),
            fundamentals.CAGR_COLUMN: st.column_config.NumberColumn(
                "CAGR",
                help="Compound annual growth rate from the first to the last year with data. Blank when either value is zero or negative."
            )
        }
        st.dataframe(
            styled,
            column_config=column_config,
            column_order=[*year_columns, "Trend", fundamentals.CAGR_COLUMN],
            width="stretch"
        )
        caption = "USD billions, converted at the latest exchange rate."
        if history[year_columns].isna().to_numpy().any():
            caption += f" {MISSING_VALUE} means Yahoo Finance has no figure for that year."
        st.caption(caption)

def render_radar(snapshots:list[dict], colors:dict[str, str], key_suffix:str) -> None:
    """Render the business-model radar with a fiscal year picker, a company picker for more than two companies, and the scoring method."""
    with st.container(border=True, height="stretch", key="radar_card"):
        st.subheader("Business model")
        fiscal_years = fundamentals.get_common_fiscal_years(snapshots)
        if not fiscal_years:
            st.info("These companies have no fiscal years in common.")
            return
        
        # Controls
        tickers = [snapshot["ticker"] for snapshot in snapshots]
        control_columns = st.columns([1, 2]) if len(tickers) > 2 else [st.container()]
        fiscal_year = control_columns[0].selectbox(
            "Fiscal year",
            options=fiscal_years,
            index=len(fiscal_years) - 1,
            format_func=lambda year: f"FY{year}",
            key=f"radar_year_{key_suffix}"
        )
        selected = tickers
        if len(tickers) > 2:
            selected = control_columns[1].multiselect("Companies", tickers, default=tickers, key=f"radar_tickers_{key_suffix}")
        if not selected:
            st.info("Pick at least one company to draw.")
            return
        
        # The scoring ranges are edited below the chart but needed to draw it, so the chart fills a slot reserved above
        chart_slot = st.container()
        ranges = render_score_method()
        selected_snapshots = [snapshot for snapshot in snapshots if snapshot["ticker"] in selected]
        radar_data = fundamentals.build_business_model_radar_data(selected_snapshots, fiscal_year, ranges)
        with chart_slot:
            st.plotly_chart(company_plots.make_business_model_radar_figure(radar_data, colors), width="stretch", config=CHART_CONFIG)
            caption = "Each ratio is scored 0-100 against a reference range. Hover for formulas and actual values."
            if ranges != fundamentals.default_score_ranges():
                caption += " Using your custom ranges."
            st.caption(caption)
            if radar_data["missing_metrics"]:
                missing = ", ".join(f"{item['company']} {item['metric']}" for item in radar_data["missing_metrics"])
                st.caption(f"Not available for FY{fiscal_year}, so left off rather than scored as zero: {missing}.")

def render_analyst_sentiment(snapshots:list[dict], colors:dict[str, str], key_suffix:str) -> None:
    """Render the latest buy/hold/sell split or the buy-share trend, chosen with a toggle."""
    with st.container(border=True, height="stretch", key="analyst_card"):
        title_column, toggle_column = st.columns([1, 1], vertical_alignment="center")
        title_column.subheader("Analyst sentiment")
        with toggle_column.container(key="analyst_toggle_box"):
            view = st.segmented_control(
                "View",
                ANALYST_VIEWS,
                default=ANALYST_VIEWS[0],
                label_visibility="collapsed",
                key=f"analyst_view_{key_suffix}"
            ) or ANALYST_VIEWS[0]
        
        rated = rated_companies(snapshots)
        if not rated:
            st.info("No analyst ratings are available for these companies.")
            return
        
        if view == "Latest":
            sentiment_data = analyst.build_analyst_sentiment_data(rated)
            st.plotly_chart(company_plots.make_analyst_sentiment_figure(sentiment_data), width="stretch", config=CHART_CONFIG)
            st.caption(f"{sentiment_data['period_label']}. Hover a segment for the number of analysts.")
        else:
            trend = analyst.build_sentiment_trend(rated)
            if trend.empty:
                st.info("These companies have no analyst snapshots in common.")
            else:
                st.plotly_chart(company_plots.make_sentiment_trend_figure(trend, colors), width="stretch", config=CHART_CONFIG)
                st.caption("Share of covering analysts rating the stock buy or strong buy, by monthly snapshot.")
        
        rated_tickers = {snapshot["ticker"] for snapshot in rated}
        unrated = [snapshot["ticker"] for snapshot in snapshots if snapshot["ticker"] not in rated_tickers]
        if unrated:
            st.caption(f"No analyst ratings for {', '.join(unrated)}.")

def render_price_targets(snapshots:list[dict], colors:dict[str, str]) -> None:
    """Render each company's analyst price-target range against its current price."""
    with st.container(border=True, key="targets_card"):
        st.subheader("Analyst price targets")
        targets = analyst.build_price_targets(snapshots)
        if not targets:
            st.info("No analyst price targets are available for these companies.")
            return
        st.plotly_chart(company_plots.make_price_target_figure(targets, colors), width="stretch", config=CHART_CONFIG)
        st.caption(
            "The bar runs from the lowest to the highest analyst target. Only the low, median, mean and high "
            "targets are published, so there are no quartiles. Hover for prices in each listing currency."
        )

def show_comparison_dashboard(result:dict | None) -> None:
    """Render the Company Metrics tab for the tickers analysed in the sidebar."""
    if not result:
        st.info("Run an analysis in the sidebar to see company metrics.")
        return
    
    with st.spinner("Loading company data..."):
        snapshots, warnings = load_company_snapshots(result)
    for warning in warnings:
        st.warning(warning)
    if not snapshots:
        return
    
    # Title
    tickers = [snapshot["ticker"] for snapshot in snapshots]
    colors = {stock["ticker"]: STOCK_COLORS[stock["role"]] for stock in result["stocks"].values()}
    key_suffix = "_".join(tickers) #widget state resets when the tickers change
    st.title(" vs ".join(tickers))
    st.caption("Valuation, analyst data and statement figures are from Yahoo Finance.")
    
    # Sections
    try:
        render_valuation(snapshots)
        render_financials(snapshots, key_suffix)
        with st.container(horizontal=True, gap="medium"): #cards stretch to the taller one's height
            render_radar(snapshots, colors, key_suffix)
            render_analyst_sentiment(snapshots, colors, key_suffix)
        render_price_targets(snapshots, colors)
    except (ValueError, KeyError) as error:
        st.warning(f"Some company metrics could not be shown: {error}")
