from datetime import date

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis.transformation import normalize_prices
from src.plots.theme import COLOR_BG, COLOR_INK, COLOR_MUTED, COLOR_RULE

# Price dashboard
TRACE_LINE_WIDTH = 2.0
DATE_HOVER_FORMAT = "%a, %b %d %Y"
RECESSION_FILL = "rgba(120, 120, 120, 0.12)"
RECESSION_LABEL_BG = "rgba(255,255,255,0.72)"

def _add_stock_traces(fig:go.Figure, prices:dict[str, pd.Series], volatilities:dict[str, pd.Series], colors:dict[str, str], comparison:bool) -> None:
    """Add price and volatility traces for each stock, normalizing prices when comparing."""
    if comparison:
        price_hover = (
            "$%{y:,.2f} per $100 invested · Actual price: "
            "$%{customdata:,.2f}<extra>%{fullData.name}</extra>"
        )
    else:
        price_hover = "$%{customdata:,.2f}<extra>%{fullData.name}</extra>"
    
    for ticker, series in prices.items():
        actual = series.dropna()
        if actual.empty:
            continue
        display = normalize_prices(actual) if comparison else actual
        line = dict(width=TRACE_LINE_WIDTH, color=colors[ticker])
        
        # Price trace
        fig.add_trace(
            go.Scatter(
                x=actual.index,
                y=display,
                customdata=actual.values,
                mode="lines",
                name=ticker,
                line=line,
                hovertemplate=price_hover
            ),
            row=1,
            col=1
        )
        
        # Volatility trace
        volatility = volatilities[ticker].dropna()
        fig.add_trace(
            go.Scatter(
                x=volatility.index,
                y=volatility.values,
                mode="lines",
                name=ticker,
                showlegend=False,
                line=line,
                hovertemplate="%{y:.1%}<extra>%{fullData.name}</extra>"
            ),
            row=2,
            col=1
        )

def _add_recession_periods(fig:go.Figure, recessions:list[dict], start_date:date, end_date:date) -> None:
    """Add recession bands and labels clipped to the visible date range."""
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
            fillcolor=RECESSION_FILL,
            line_width=0,
            layer="below"
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
                font=dict(size=9, color=COLOR_MUTED),
                bgcolor=RECESSION_LABEL_BG
            )

def plot_dashboard(prices:dict[str, pd.Series], volatilities:dict[str, pd.Series], colors:dict[str, str], recessions:list[dict], comparison:bool, start_date:date, end_date:date) -> go.Figure:
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
    # Subplot titles
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
    
    # Traces and recession bands
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.18,
        subplot_titles=(price_title, volatility_title)
    )
    _add_stock_traces(fig, prices, volatilities, colors, comparison)
    fig.update_xaxes(range=[start_date, end_date])
    _add_recession_periods(fig, recessions, start_date, end_date)
    
    # Styling
    fig.update_layout(
        height=510,
        margin=dict(l=8, r=8, t=65, b=25),
        hovermode="x unified",
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(color=COLOR_INK)
    )
    
    fig.update_yaxes(title_text="Value ($)" if comparison else "Price ($)", tickprefix="$", row=1, col=1, gridcolor=COLOR_RULE) # Price
    fig.update_yaxes(title_text="Volatility", tickformat=".0%", row=2, col=1, gridcolor=COLOR_RULE) # Volatility
    fig.update_xaxes(hoverformat=DATE_HOVER_FORMAT, showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1, gridcolor=COLOR_RULE) # Shared
    return fig
