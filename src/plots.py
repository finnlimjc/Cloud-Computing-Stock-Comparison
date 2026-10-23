from __future__ import annotations

from datetime import date
from typing import Any, Dict

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf

from src.transformation import normalize_prices

# This section defines the original project styling and the updated company color scheme.
LINE_WIDTH = 1.5
USD_PER_BILLION = 1_000_000_000
CURRENCY_SELECTION_ERROR = "Please select companies with valid currencies or exchange rates."
NEUTRAL_COLOR = "#1f77b4"
NEGATIVE_COLOR = "crimson"
NEGATIVE_FILL_COLOR = "rgba(220, 20, 60, 0.3)"
DATE_HOVER_FORMAT = "%a, %b %d %Y"
STOCK_A_COLOR = "#141C52"
STOCK_B_COLOR = "#B08D5B"


def add_stock_traces(
    fig:go.Figure,
    prices:dict[str, pd.Series],
    volatilities:dict[str, pd.Series],
    colors:dict[str, str],
    comparison:bool,
) -> None:
    """Add price and volatility traces for each stock.

    Inputs:
    - fig: Plotly figure receiving the traces
    - prices: price series keyed by ticker
    - volatilities: volatility series keyed by ticker
    - colors: line colors keyed by ticker
    - comparison: whether prices are normalized for comparison

    Outputs:
    - None
    """
    # This part adds each available price series and its volatility trace.
    for ticker, series in prices.items():
        actual = series.dropna()
        if actual.empty:
            continue
        display = normalize_prices(actual) if comparison else actual
        fig.add_trace(
            go.Scatter(
                x=actual.index,
                y=display,
                customdata=actual.values,
                mode="lines",
                name=ticker,
                line=dict(width=LINE_WIDTH + 0.5, color=colors[ticker]),
                hovertemplate=(
                    "$%{y:,.2f} per $100 invested · Actual price: "
                    "$%{customdata:,.2f}<extra>%{fullData.name}</extra>"
                    if comparison
                    else "$%{customdata:,.2f}<extra>%{fullData.name}</extra>"
                ),
            ),
            row=1,
            col=1,
        )
        volatility = volatilities[ticker].dropna()
        fig.add_trace(
            go.Scatter(
                x=volatility.index,
                y=volatility.values,
                mode="lines",
                name=ticker,
                showlegend=False,
                line=dict(width=LINE_WIDTH + 0.5, color=colors[ticker]),
                hovertemplate="%{y:.1%}<extra>%{fullData.name}</extra>",
            ),
            row=2,
            col=1,
        )


def add_recession_periods(
    fig:go.Figure,
    recessions:list[dict],
    start_date:date,
    end_date:date,
) -> None:
    """Add visible recession bands and labels to a chart.

    Inputs:
    - fig: Plotly figure receiving shapes and annotations
    - recessions: recession date ranges
    - start_date: first visible chart date
    - end_date: last visible chart date

    Outputs:
    - None
    """
    # This part clips each recession period to the visible date range.
    for recession in recessions:
        start = max(pd.Timestamp(start_date), pd.Timestamp(recession["start"]))
        end = min(pd.Timestamp(end_date), pd.Timestamp(recession["end"]))
        if start > end:
            continue
        # This part shades the overlapping recession period.
        fig.add_shape(
            type="rect",
            xref="x",
            yref="paper",
            x0=start,
            x1=end,
            y0=0,
            y1=1,
            fillcolor="rgba(120, 120, 120, 0.12)",
            line_width=0,
            layer="below",
        )
        # This part labels known recessions at the center of each band.
        if recession.get("label"):
            midpoint = start + (end - start) / 2
            fig.add_annotation(
                x=midpoint,
                y=0.99,
                xref="x",
                yref="paper",
                text=recession["label"],
                showarrow=False,
                font=dict(size=9, color="#555555"),
                bgcolor="rgba(255,255,255,0.72)",
            )


def plot_dashboard(
    prices:dict[str, pd.Series],
    volatilities:dict[str, pd.Series],
    colors:dict[str, str],
    recessions:list[dict],
    comparison:bool,
    start_date:date,
    end_date:date,
) -> go.Figure:
    """Plot price and rolling volatility together with a shared date axis.

    Inputs:
    - prices: price series keyed by ticker
    - volatilities: volatility series keyed by ticker
    - colors: line colors keyed by ticker
    - recessions: recession date ranges
    - comparison: whether to normalize prices for comparison
    - start_date: first visible chart date
    - end_date: last visible chart date

    Outputs:
    - Plotly dashboard figure
    """
    # This part selects titles for single-stock and comparison charts.
    if comparison:
        price_title = (
            "If you had invested $100 …<br>"
            "<sup>Both stocks start at $100 so you can compare growth fairly.</sup>"
        )
    else:
        price_title = "Share price in USD<br><sup>Daily closing price.</sup>"
    volatility_title = (
        "How bumpy is the ride? · Volatility (30-day, annualised)<br>"
        "<sup>Higher = bigger daily price swings = more risk.</sup>"
    )
    # This part creates the stacked price and volatility panels.
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.18,
        subplot_titles=(price_title, volatility_title),
    )
    # This part adds stock data and recession shading to the figure.
    add_stock_traces(fig, prices, volatilities, colors, comparison)
    # This part applies the requested date range and recession bands.
    fig.update_xaxes(range=[start_date, end_date])
    add_recession_periods(fig, recessions, start_date, end_date)
    # This part styles the figure and labels both y-axes.
    fig.update_layout(
        height=510,
        margin=dict(l=8, r=8, t=65, b=25),
        hovermode="x unified",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(color="#141C52"),
    )
    fig.update_yaxes(
        title_text="Value ($)" if comparison else "Price ($)",
        tickprefix="$",
        row=1,
        col=1,
        gridcolor="#ECEEF4",
    )
    fig.update_yaxes(
        title_text="Volatility",
        tickformat=".0%",
        row=2,
        col=1,
        gridcolor="#ECEEF4",
    )
    fig.update_xaxes(
        hoverformat=DATE_HOVER_FORMAT,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        gridcolor="#ECEEF4",
    )
    return fig


# Updated company palette to match the screenshot style:
# Company A is dark blue and Company B is gold.
COLOR_A = "#12264F"
COLOR_B = "#C7A15E"

COLOR_UP = "#2E8B57"
COLOR_DOWN = "#D95D39"
COLOR_INK = "#17233d"
COLOR_MUTED = "#5f6b7f"
COLOR_RULE = "#e2e7ef"
COLOR_BG = "#ffffff"
FONT_STACK = "Work Sans, Helvetica Neue, Arial, sans-serif"
MONO_STACK = "IBM Plex Mono, SF Mono, Menlo, monospace"


def plot_price_drawdown(prices:pd.Series, drawdown:pd.Series, ticker:str) -> go.Figure:
    """Plot price and drawdown on linked time axes.

    Inputs:
    - prices: closing prices indexed by date
    - drawdown: drawdown fractions indexed by date
    - ticker: symbol used in the title

    Outputs:
    - Plotly figure with price and drawdown panels
    """
    # This part creates the original compatible Part 1 price and drawdown figure.
    price_domain = [0.35, 1.0]
    drawdown_domain = [0.0, 0.3]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=prices.index,
            y=prices.values,
            mode="lines",
            name="Price",
            yaxis="y",
            customdata=drawdown.values,
            line=dict(width=LINE_WIDTH, color=NEUTRAL_COLOR),
            hovertemplate="$%{y:,.2f}<br>Drawdown: %{customdata:.2%}",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode="lines",
            name="Drawdown",
            yaxis="y2",
            customdata=prices.values,
            fill="tozeroy",
            fillcolor=NEGATIVE_FILL_COLOR,
            line=dict(width=LINE_WIDTH, color=NEGATIVE_COLOR),
            hovertemplate="%{y:.2%}<br>Price: $%{customdata:,.2f}",
        )
    )
    # This part applies linked hover and the original two-panel layout.
    fig.update_layout(
        title=f"{ticker} Price and Drawdown",
        hovermode="x unified",
        showlegend=False,
        xaxis=dict(
            anchor="y2",
            hoverformat=DATE_HOVER_FORMAT,
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
        ),
        yaxis=dict(domain=price_domain, title_text="Price"),
        yaxis2=dict(domain=drawdown_domain, title_text="Drawdown", tickformat=".0%"),
    )
    return fig


# This function formats a numeric value as a clean money string.
def _format_money(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:,.2f}"


# This function formats a signed numeric value with a plus sign for positive values.
def _format_signed(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:+,.2f}"


# This function formats a percentage value with a directional arrow.
def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "N/A"
    arrow = "▲" if value >= 0 else "▼"
    return f"{arrow}{value:+.1f}%"


# This function returns the latest USD value of one unit of the company's reporting currency.
def _get_usd_conversion_rate(ticker: str) -> float:
    info = yf.Ticker(ticker).info or {}
    currency = info.get("financialCurrency")
    if not currency:
        raise ValueError(CURRENCY_SELECTION_ERROR)

    currency = str(currency).upper()
    if currency == "USD":
        return 1.0

    def latest_close(pair: str) -> float | None:
        history = yf.Ticker(pair).history(period="5d")
        if history.empty or "Close" not in history:
            return None
        closes = history["Close"].dropna()
        return float(closes.iloc[-1]) if not closes.empty else None

    rate = latest_close(f"{currency}USD=X")
    if rate is None:
        inverse_rate = latest_close(f"USD{currency}=X")
        if inverse_rate is None:
            raise ValueError(CURRENCY_SELECTION_ERROR)
        if pd.isna(inverse_rate) or inverse_rate <= 0:
            raise ValueError(CURRENCY_SELECTION_ERROR)
        rate = 1 / inverse_rate

    if pd.isna(rate) or rate <= 0:
        raise ValueError(CURRENCY_SELECTION_ERROR)
    return rate


# This function creates the core financial comparison table.
def make_core_metrics_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()

    tickers = list(df["Company"].dropna().unique())
    usd_rates = {ticker: _get_usd_conversion_rate(ticker) for ticker in tickers}
    fiscal_year_columns = [
        column for column in df.columns
        if isinstance(column, str) and column.startswith("FY") and column[2:].isdigit()
    ]
    if len(fiscal_year_columns) != 2:
        raise ValueError("Core metrics chart requires exactly two selected fiscal years.")
    year_a, year_b = fiscal_year_columns

    n_cols = 6
    values = [[] for _ in range(n_cols)]
    fills = [[] for _ in range(n_cols)]
    fonts = [[] for _ in range(n_cols)]

    # This loop adds each statement block to the comparison table.
    for statement in df["Statement"].drop_duplicates():
        values[0].append(statement.upper())
        fills[0].append("#eef2f8")
        fonts[0].append(COLOR_B)

        for col_idx in range(1, n_cols):
            values[col_idx].append("")
            fills[col_idx].append("#eef2f8")
            fonts[col_idx].append(COLOR_MUTED)

        subset = df[df["Statement"] == statement]

        for _, row in subset.iterrows():
            usd_rate = usd_rates[row["Company"]]
            value_a_usd = row[year_a] * usd_rate / USD_PER_BILLION
            value_b_usd = row[year_b] * usd_rate / USD_PER_BILLION
            abs_change_usd = row["Abs_Change"] * usd_rate / USD_PER_BILLION
            growth_pct = row["Growth_Pct"]

            is_positive = abs_change_usd >= 0
            diff_fill = "rgba(14,159,110,0.10)" if is_positive else "rgba(224,36,36,0.10)"
            diff_font = COLOR_UP if is_positive else COLOR_DOWN

            row_data = [
                row["Metric"],
                row["Company"],
                _format_money(value_a_usd),
                _format_money(value_b_usd),
                _format_signed(abs_change_usd),
                _format_pct(growth_pct),
            ]

            for idx, val in enumerate(row_data):
                values[idx].append(val)
                if idx == 0:
                    fills[idx].append(COLOR_BG)
                    fonts[idx].append(COLOR_INK)
                elif idx in (4, 5):
                    fills[idx].append(diff_fill)
                    fonts[idx].append(diff_font)
                else:
                    fills[idx].append(COLOR_BG)
                    fonts[idx].append(COLOR_INK)

    header = [
        "Metric",
        "Company",
        year_a,
        year_b,
        f"Abs. Change<br><span style='font-size:9px'>{year_b} − {year_a}</span>",
        f"Growth<br><span style='font-size:9px'>{year_a} → {year_b}</span>",
    ]

    fig = go.Figure(
        go.Table(
            columnwidth=[145, 68, 76, 76, 116, 104],
            header=dict(
                values=header,
                fill_color=[COLOR_A, COLOR_A, COLOR_A, COLOR_A, COLOR_B, COLOR_B],
                font=dict(color="#ffffff", size=12, family=FONT_STACK),
                align=["left", "center", "right", "right", "center", "center"],
                height=48,
                line_color=COLOR_A,
            ),
            cells=dict(
                values=values,
                fill_color=fills,
                font=dict(color=fonts, size=12.5, family=MONO_STACK),
                align=["left", "center", "right", "right", "right", "center"],
                height=34,
                line_color=COLOR_RULE,
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=(
                f"Core Metrics Comparison — {year_a} vs {year_b}"
                "<br>(USD billions · per-company growth)"
            ),
            font=dict(size=15, color=COLOR_INK, family=FONT_STACK),
            x=0.01,
            xanchor="left",
        ),
        width=760,
        height=700,
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        margin=dict(l=12, r=12, t=78, b=16),
    )

    return fig


# This function creates the grouped bar chart for the selected metric.
def make_grouped_bar_figure(data: Dict[str, Any], metric: str = "Revenue") -> go.Figure:
    fig = go.Figure()
    usd_rate_a = _get_usd_conversion_rate(data["company_a"])
    usd_rate_b = _get_usd_conversion_rate(data["company_b"])
    series_a = [value * usd_rate_a / USD_PER_BILLION for value in data["series_a"]]
    series_b = [value * usd_rate_b / USD_PER_BILLION for value in data["series_b"]]

    fig.add_bar(
        x=data["years"],
        y=series_a,
        name=data["company_a"],
        marker=dict(color=COLOR_A, cornerradius=4),
        text=[f"{v:,.2f}" if pd.notna(v) else "" for v in series_a],
        customdata=data["years"],
        hovertemplate="%{fullData.name}<br>%{customdata}<br>%{y:,.2f} USD billions<extra></extra>",
        textposition="outside",
        textfont=dict(color=COLOR_A, size=11, family=MONO_STACK),
        width=0.3,
    )

    fig.add_bar(
        x=data["years"],
        y=series_b,
        name=data["company_b"],
        marker=dict(color=COLOR_B, cornerradius=4),
        text=[f"{v:,.2f}" if pd.notna(v) else "" for v in series_b],
        customdata=data["years"],
        hovertemplate="%{fullData.name}<br>%{customdata}<br>%{y:,.2f} USD billions<extra></extra>",
        textposition="outside",
        textfont=dict(color=COLOR_B, size=11, family=MONO_STACK),
        width=0.3,
    )

    fig.update_layout(
        barmode="group",
        bargap=0.42,
        bargroupgap=0.12,
        title=dict(
            text=(
                f"{metric} — Grouped Comparison"
                f"<br>({' vs '.join(data['years'])}, USD billions · latest FX rates)"
            ),
            font=dict(size=17, color=COLOR_INK, family=FONT_STACK),
            x=0.01,
            xanchor="left",
        ),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.02,
            xanchor="left",
            font=dict(color=COLOR_INK, size=12, family=FONT_STACK),
        ),
        xaxis=dict(
            title=None,
            tickfont=dict(color=COLOR_INK, size=13, family=FONT_STACK),
            showline=True,
            linecolor=COLOR_RULE,
            ticks="",
        ),
        yaxis=dict(
            title=dict(text="USD billions", font=dict(color=COLOR_MUTED, size=11)),
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=11, family=MONO_STACK),
        ),
        width=1280,
        height=640,
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        margin=dict(l=64, r=24, t=116, b=48),
    )

    return fig


# This function creates the business model radar chart.
def make_business_model_radar_figure(radar_data: Dict[str, Any]) -> go.Figure:
    labels = radar_data["labels"]
    values_a = radar_data["values_a"]
    values_b = radar_data["values_b"]
    fiscal_year = radar_data["fiscal_year"]
    definitions = radar_data["definitions"]
    axis_labels = [
        label.replace("Safety Ratio", "Safety<br>Ratio").replace(
            "Gross Margin", "Gross<br>Margin"
        )
        for label in labels
    ]
    def trace_customdata(
        scores: list,
        actuals: list,
        units: Dict[str, str],
    ) -> list:
        return [
            [
                label,
                f"{score:.1f}" if score is not None else "N/A",
                f"{actual:.1f}{units[label]}" if actual is not None else "Unavailable",
                definitions[label],
            ]
            for label, score, actual in zip(labels, scores, actuals)
        ]

    fig = go.Figure()

    companies = [
        {
            "name": radar_data.get("name_a", radar_data["company_a"]),
            "values": values_a,
            "actuals": radar_data["actuals_a"],
            "color": COLOR_A,
            "fillcolor": "rgba(18,38,79,0.14)",
            "symbol": "circle",
        },
        {
            "name": radar_data.get("name_b", radar_data["company_b"]),
            "values": values_b,
            "actuals": radar_data["actuals_b"],
            "color": COLOR_B,
            "fillcolor": "rgba(199,161,94,0.18)",
            "symbol": "diamond",
        },
    ]

    # Draw filled areas first so neither company's markers are hidden by the other fill.
    for company in reversed(companies):
        fig.add_trace(
            go.Scatterpolar(
                r=company["values"],
                theta=axis_labels,
                name=company["name"],
                mode="lines",
                fill="toself",
                line=dict(color=company["color"], width=2.5),
                fillcolor=company["fillcolor"],
                connectgaps=False,
                hoverinfo="skip",
            )
        )

    axis_hover_customdata = [
        [label, definitions[label]]
        for label in labels
        for _ in range(5)
    ]
    fig.add_trace(
        go.Scatterpolar(
            r=[20, 40, 60, 80, 100] * len(labels),
            theta=[axis_label for axis_label in axis_labels for _ in range(5)],
            mode="markers",
            marker=dict(color="rgba(255,255,255,0.01)", size=16),
            customdata=axis_hover_customdata,
            hovertemplate="<b>%{customdata[0]}</b><br>Formula: %{customdata[1]}<extra></extra>",
            showlegend=False,
        )
    )

    for company in companies:
        fig.add_trace(
            go.Scatterpolar(
                r=company["values"],
                theta=axis_labels,
                name=company["name"],
                mode="markers",
                marker=dict(
                    color=company["color"],
                    size=9,
                    symbol=company["symbol"],
                    line=dict(color=COLOR_BG, width=1.2),
                ),
                customdata=trace_customdata(
                    company["values"],
                    company["actuals"],
                    radar_data["units"],
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Formula: %{customdata[3]}<br>"
                    "Normalized score: %{customdata[1]}/100<br>"
                    f"FY{fiscal_year} actual: "
                    "%{customdata[2]}<extra>%{fullData.name}</extra>"
                ),
                showlegend=False,
            )
        )

    fig.update_layout(
        title=dict(
            text=(
                f"Normalized Business Model Fingerprint — FY{fiscal_year}"
                "<br><span style='font-family:Work Sans, Helvetica Neue, Arial, sans-serif;"
                "font-size:14px;font-weight:400;color:#4B5563'>"
                "Normalized Business Metric Scores (0-100) | "
                "<i>Hover for formulas</i></span>"
            ),
            font=dict(size=17, color=COLOR_INK, family=FONT_STACK),
            x=0.01,
            xanchor="left",
            y=0.92,
            yanchor="top",
        ),
        polar=dict(
            domain=dict(x=[0.10, 0.90], y=[0.03, 0.82]),
            radialaxis=dict(
                range=[0, 105],
                gridcolor=COLOR_RULE,
                tickvals=[0, 20, 40, 60, 80, 100],
                tickangle=0,
                tickfont=dict(color=COLOR_MUTED, size=10),
                showline=False,
                angle=0,
            ),
            angularaxis=dict(
                gridcolor=COLOR_RULE,
                tickfont=dict(color=COLOR_INK, size=12.5, family=FONT_STACK),
            ),
            bgcolor=COLOR_BG,
        ),
        legend=dict(
            orientation="h",
            x=1.0,
            y=0.80,
            xanchor="right",
            font=dict(color=COLOR_INK, size=12, family=FONT_STACK),
        ),
        annotations=[],
        width=900,
        height=660,
        paper_bgcolor=COLOR_BG,
        margin=dict(l=48, r=48, t=82, b=30),
    )

    return fig


# This function creates the stacked analyst sentiment bar chart.
def make_analyst_sentiment_figure(sentiment_data: Dict[str, Any]) -> go.Figure:
    a = sentiment_data["a"]
    b = sentiment_data["b"]
    ticker_a = sentiment_data["company_a"]
    ticker_b = sentiment_data["company_b"]

    totals = {
        ticker_a: a["buy"] + a["hold"] + a["sell"],
        ticker_b: b["buy"] + b["hold"] + b["sell"],
    }

    def pct(bucket_value: float, total: float) -> float:
        if total == 0:
            return 0.0
        return bucket_value / total * 100

    fig = go.Figure()

    for bucket, label, color, text_color in [
        ("buy", "Buy", "#2E8B57", "#ffffff"),
        ("hold", "Hold", "#D9B36C", "#17233d"),
        ("sell", "Sell", "#C65151", "#ffffff"),
    ]:
        values = [
            pct(a[bucket], totals[ticker_a]),
            pct(b[bucket], totals[ticker_b]),
        ]

        labels = [
            f"{values[0]:.1f}%<br><span style='font-size:10px'>{int(a[bucket])}</span>" if values[0] >= 6 else "",
            f"{values[1]:.1f}%<br><span style='font-size:10px'>{int(b[bucket])}</span>" if values[1] >= 6 else "",
        ]

        fig.add_bar(
            x=[ticker_a, ticker_b],
            y=values,
            name=label,
            marker=dict(color=color),
            text=labels,
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color=text_color, size=13, family=MONO_STACK),
            customdata=[int(a[bucket]), int(b[bucket])],
            hovertemplate="<b>%{x}</b> · " + label + ": %{y:.1f}% (%{customdata} analysts)<extra></extra>",
            width=0.42,
        )

    fig.update_layout(
        barmode="stack",
        title=dict(
            text=(
                "Analyst Sentiment — 100% Stacked (Buy / Hold / Sell)"
                f"<br><span style='font-size:13px;font-weight:400'>"
                f"Snapshot: {sentiment_data.get('period_label', 'Latest snapshot')}</span>"
            ),
            font=dict(size=17, color=COLOR_INK, family=FONT_STACK),
            x=0.01,
            xanchor="left",
            y=0.88,
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            x=0.99,
            y=1.01,
            xanchor="right",
            yanchor="bottom",
            traceorder="normal",
            font=dict(color=COLOR_INK, size=12, family=FONT_STACK),
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=[ticker_a, ticker_b],
            ticktext=[
                f"<b>{ticker_a}</b><br><span style='font-size:10px;color:#5f6b7f'>"
                f"Consensus: {a['consensus']} · {totals[ticker_a]} analysts</span>",
                f"<b>{ticker_b}</b><br><span style='font-size:10px;color:#5f6b7f'>"
                f"Consensus: {b['consensus']} · {totals[ticker_b]} analysts</span>",
            ],
            tickfont=dict(color=COLOR_INK, size=14, family=FONT_STACK),
            showline=True,
            linecolor=COLOR_RULE,
        ),
        yaxis=dict(
            title=dict(text="% of covering analysts", font=dict(color=COLOR_MUTED, size=11)),
            range=[0, 100],
            ticksuffix="%",
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=11, family=MONO_STACK),
        ),
        width=1280,
        height=620,
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        margin=dict(l=64, r=24, t=160, b=64),
    )

    return fig