from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.transformation import normalize_prices

LINE_WIDTH = 1.5
NEUTRAL_COLOR = "#1f77b4"
NEGATIVE_COLOR = "crimson"
NEGATIVE_FILL_COLOR = "rgba(220, 20, 60, 0.3)"
DATE_HOVER_FORMAT = "%a, %b %d %Y"
STOCK_A_COLOR = "#141C52"
STOCK_B_COLOR = "#B08D5B"

def plot_price_drawdown(prices:pd.Series, drawdown:pd.Series, ticker:str) -> go.Figure:
    """
    Price chart stacked on a drawdown chart, sharing one time axis so zoom, pan and hover stay in sync.
    
    Inputs:
        - prices: closing prices indexed by date
        - drawdown: drawdown fractions indexed by the same dates
        - ticker: symbol used in the title
    
    Outputs:
        - Plotly figure with price (top) and drawdown (bottom)
    """
    PRICE_DOMAIN = [0.35, 1.0]
    DRAWDOWN_DOMAIN = [0.0, 0.3]
    PRICE_HOVER = "%{y:,.2f}<br>Drawdown: %{customdata:.2%}"
    DRAWDOWN_HOVER = "%{y:.2%}<br>Price: %{customdata:,.2f}"
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=prices.index,
        y=prices.values,
        mode="lines",
        name="Price",
        yaxis="y",
        customdata=drawdown.values,
        line=dict(width=LINE_WIDTH, color=NEUTRAL_COLOR),
        hovertemplate=PRICE_HOVER
    ))
    
    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown.values,
        mode="lines",
        name="Drawdown",
        yaxis="y2",
        customdata=prices.values,
        fill="tozeroy",
        fillcolor=NEGATIVE_FILL_COLOR,
        line=dict(width=LINE_WIDTH, color=NEGATIVE_COLOR),
        hovertemplate=DRAWDOWN_HOVER
    ))
    
    # Each figure also carries the other's value in customdata
    fig.update_layout(
        title=f"{ticker} Price and Drawdown",
        hovermode="x unified",
        showlegend=False,
        xaxis=dict(anchor="y2", hoverformat=DATE_HOVER_FORMAT, showspikes=True, # Anchor y2 so the spike line is drawn across both panels
                   spikemode="across", spikesnap="cursor", spikethickness=1), #Spike refers to the dotted line when you hover
        yaxis=dict(domain=PRICE_DOMAIN, title_text="Price"),
        yaxis2=dict(domain=DRAWDOWN_DOMAIN, title_text="Drawdown", tickformat=".0%")
    )
    return fig


def plot_dashboard(
    prices:dict[str, pd.Series],
    volatilities:dict[str, pd.Series],
    colors:dict[str, str],
    recessions:list[dict],
    comparison:bool,
    start_date:date,
    end_date:date,
) -> go.Figure:
    """Plot price and rolling volatility together with a shared date axis."""
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
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.18,
        subplot_titles=(price_title, volatility_title),
    )
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

    fig.update_xaxes(range=[start_date, end_date])
    for recession in recessions:
        start = max(pd.Timestamp(start_date), pd.Timestamp(recession["start"]))
        end = min(pd.Timestamp(end_date), pd.Timestamp(recession["end"]))
        if start > end:
            continue
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
