import pandas as pd
import plotly.graph_objects as go

LINE_WIDTH = 1.5
NEUTRAL_COLOR = "#1f77b4"
NEGATIVE_COLOR = "crimson"
NEGATIVE_FILL_COLOR = "rgba(220, 20, 60, 0.3)"
DATE_HOVER_FORMAT = "%a, %b %d %Y"

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
