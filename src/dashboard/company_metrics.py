import streamlit as st

from src.analysis import analyst, fundamentals
from src.dashboard.config import COMPARISON_METRICS
from src.dashboard.loaders import load_company_pair_data
from src.data import price_ratings
from src.plots import company_plots

def render_comparison(ticker_a:str, ticker_b:str, metric:str) -> None:
    """Load both companies and render the four comparison charts."""
    try:
        with st.spinner(f"Loading comparison data for {ticker_a} and {ticker_b}..."):
            company_data = load_company_pair_data(ticker_a, ticker_b)
            company_a = company_data[ticker_a]
            company_b = company_data[ticker_b]
        usd_rates = {company["ticker"]: company["usd_rate"] for company in (company_a, company_b)}
        
        fiscal_years = fundamentals.get_common_fiscal_years(company_a, company_b)
        if len(fiscal_years) < 2:
            st.warning("At least two common fiscal years are needed for the first two charts.")
            return
        
        # Chart controls
        control_columns = st.columns([2, 1, 1])
        selected_years = control_columns[0].select_slider(
            "Fiscal years for charts 1-2",
            options=fiscal_years,
            value=(fiscal_years[-2], fiscal_years[-1]),
            format_func=lambda year: f"FY{year}",
            key=f"comparison_years_{ticker_a}_{ticker_b}"
        )
        radar_year = control_columns[1].selectbox(
            "Fiscal year for chart 3",
            options=fiscal_years,
            index=len(fiscal_years) - 1,
            format_func=lambda year: f"FY{year}",
            key=f"radar_year_{ticker_a}_{ticker_b}"
        )
        analyst_periods = analyst.get_common_analyst_periods(company_a, company_b)
        if analyst_periods:
            analyst_period = control_columns[2].selectbox(
                "Snapshot for chart 4",
                options=analyst_periods,
                format_func=analyst.analyst_period_label,
                key=f"analyst_period_{ticker_a}_{ticker_b}"
            )
        else:
            analyst_period = None
            control_columns[2].warning("No common analyst snapshot periods.")
        
        # Chart data
        core_metrics = fundamentals.build_core_metrics_table(company_a, company_b, years=selected_years)
        grouped_data = fundamentals.build_grouped_bar_dataset(company_a, company_b, metric, years=selected_years)
        radar_data = fundamentals.build_business_model_radar_data(company_a, company_b, fiscal_year=radar_year)
        sentiment_data = analyst.build_analyst_sentiment_data(company_a, company_b, period=analyst_period) if analyst_period else None
        
        # Charts
        first_row = st.columns(2)
        first_row[0].plotly_chart(company_plots.make_core_metrics_figure(core_metrics, usd_rates), use_container_width=True)
        first_row[1].plotly_chart(company_plots.make_grouped_bar_figure(grouped_data, usd_rates, metric), use_container_width=True)
        
        second_row = st.columns(2)
        with second_row[0]:
            if radar_data["missing_metrics"]:
                missing = ", ".join(f"{item['company']} — {item['metric']}" for item in radar_data["missing_metrics"])
                st.warning(
                    f"FY{radar_data['fiscal_year']} data unavailable for: {missing}. "
                    "These radar points are omitted, not scored as zero."
                )
            st.plotly_chart(company_plots.make_business_model_radar_figure(radar_data), use_container_width=True)
        if sentiment_data:
            second_row[1].plotly_chart(company_plots.make_analyst_sentiment_figure(sentiment_data), use_container_width=True)
    except ValueError as error:
        st.warning(str(error))
    except Exception as error:
        st.error(f"Unable to load the company comparison: {error}")

def show_comparison_dashboard() -> None:
    """Render the two-company form, remembering the last valid submission."""
    st.header("Two-Company Comparison")
    st.write("Compare financial metrics, business models, and analyst sentiment.")
    
    # Form inputs
    with st.form("comparison_form"):
        ticker_columns = st.columns(2)
        ticker_a = ticker_columns[0].text_input(
            "First ticker",
            value=st.session_state.get("comparison_ticker_a", "AAPL"),
            placeholder="e.g. AAPL"
        )
        ticker_b = ticker_columns[1].text_input(
            "Second ticker",
            value=st.session_state.get("comparison_ticker_b", "MSFT"),
            placeholder="e.g. MSFT"
        )
        selected_metric = st.session_state.get("comparison_metric", COMPARISON_METRICS[0])
        metric = st.selectbox(
            "Metric for grouped bar chart",
            COMPARISON_METRICS,
            index=COMPARISON_METRICS.index(selected_metric)
        )
        submitted = st.form_submit_button("Compare companies")
    
    # Remember the last valid submission
    if submitted:
        try:
            clean_a = price_ratings.clean_ticker(ticker_a)
            clean_b = price_ratings.clean_ticker(ticker_b)
            if clean_a == clean_b:
                raise ValueError("Please enter two different ticker symbols.")
        except ValueError as error:
            st.warning(str(error))
            return
        st.session_state["comparison_ticker_a"] = clean_a
        st.session_state["comparison_ticker_b"] = clean_b
        st.session_state["comparison_metric"] = metric
    
    ticker_a = st.session_state.get("comparison_ticker_a")
    ticker_b = st.session_state.get("comparison_ticker_b")
    if ticker_a and ticker_b:
        render_comparison(ticker_a, ticker_b, st.session_state.get("comparison_metric", metric))
