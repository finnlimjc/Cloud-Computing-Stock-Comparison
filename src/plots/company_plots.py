import pandas as pd
import plotly.graph_objects as go

from src.plots.theme import *

# Shared layout
CHART_HEIGHT = 420
SENTIMENT_HEIGHT = 560 #fills the analyst card, which stretches to the taller radar card
TICK_SIZE = 13
AXIS_TITLE_SIZE = 13
CATEGORY_SIZE = 15
CHART_MARGIN = dict(l=8, r=8, t=40, b=8)

# Business model radar
RADIAL_TICKS = [20, 40, 60, 80, 100]
RADAR_FILL_ALPHA = 0.14
RADAR_SYMBOLS = ("circle", "diamond", "square", "triangle-up", "x")

# Analyst sentiment
COLOR_BUY = "#2E8B57"
COLOR_HOLD = "#D9B36C"
COLOR_SELL = "#C65151"
MIN_LABEL_SIZE = 11 #segment labels that would shrink below this are hidden, not rotated
SENTIMENT_BUCKETS = (
    ("buy", "Buy", COLOR_BUY, "#ffffff"),
    ("hold", "Hold", COLOR_HOLD, COLOR_INK),
    ("sell", "Sell", COLOR_SELL, "#ffffff")
)

# Price targets
TARGET_RANGE_ALPHA = 0.35
TARGET_ROW_HEIGHT = 70

def _radar_customdata(radar_data:dict, scores:list, actuals:list) -> list[list[str]]:
    labels = radar_data["labels"]
    customdata = [
        [
            label,
            f"{score:.1f}" if score is not None else "N/A",
            f"{actual:.1f}{radar_data['units'][label]}" if actual is not None else "Unavailable",
            radar_data["definitions"][label]
        ]
        for label, score, actual in zip(labels, scores, actuals)
    ]
    return customdata

def make_business_model_radar_figure(radar_data:dict, colors:dict[str, str]) -> go.Figure:
    """
    Create the radar chart of normalized business-model scores.
    
    Inputs:
    - radar_data: output of fundamentals.build_business_model_radar_data, optionally filtered to the companies to draw
    - colors: line and marker colors keyed by ticker
    
    Outputs:
    - Plotly polar figure with one filled outline per company and hover text showing formulas, scores and actual values
    """
    labels = radar_data["labels"]
    fiscal_year = radar_data["fiscal_year"]
    axis_labels = [
        label.replace("Safety Ratio", "Safety<br>Ratio").replace("Gross Margin", "Gross<br>Margin")
        for label in labels
    ]
    companies = radar_data["companies"]
    
    # Traces
    fig = go.Figure()
    # Draw filled areas first so no company's markers are hidden by another fill.
    for company in reversed(companies):
        color = colors[company["ticker"]]
        fig.add_trace(
            go.Scatterpolar(
                r=company["scores"] + company["scores"][:1], #repeat the first point so the outline closes
                theta=axis_labels + axis_labels[:1],
                name=company["ticker"],
                mode="lines",
                fill="toself",
                line=dict(color=color, width=2.5),
                fillcolor=with_alpha(color, RADAR_FILL_ALPHA),
                connectgaps=False,
                hoverinfo="skip",
                showlegend=False
            )
        )
    
    # Invisible markers along each axis so the formula shows on hover anywhere on the axis.
    fig.add_trace(
        go.Scatterpolar(
            r=RADIAL_TICKS * len(labels),
            theta=[axis_label for axis_label in axis_labels for _ in RADIAL_TICKS],
            mode="markers",
            marker=dict(color="rgba(255,255,255,0.01)", size=16),
            customdata=[[label, radar_data["definitions"][label]] for label in labels for _ in RADIAL_TICKS],
            hovertemplate="<b>%{customdata[0]}</b><br>Formula: %{customdata[1]}<extra></extra>",
            showlegend=False
        )
    )
    
    for company_idx, company in enumerate(companies):
        fig.add_trace(
            go.Scatterpolar(
                r=company["scores"],
                theta=axis_labels,
                name=company["ticker"],
                mode="markers",
                marker=dict(
                    color=colors[company["ticker"]],
                    size=9,
                    symbol=RADAR_SYMBOLS[company_idx % len(RADAR_SYMBOLS)],
                    line=dict(color=COLOR_BG, width=1.2)
                ),
                customdata=_radar_customdata(radar_data, company["scores"], company["actuals"]),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Formula: %{customdata[3]}<br>"
                    "Normalized score: %{customdata[1]}/100<br>"
                    f"FY{fiscal_year} actual: "
                    "%{customdata[2]}<extra>%{fullData.name}</extra>"
                )
            )
        )
    
    # Layout
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                range=[0, 105],
                gridcolor=COLOR_RULE,
                tickvals=[0] + RADIAL_TICKS,
                tickangle=0,
                tickfont=dict(color=COLOR_MUTED, size=TICK_SIZE),
                showline=False,
                angle=0
            ),
            angularaxis=dict(
                gridcolor=COLOR_RULE,
                tickfont=dict(color=COLOR_INK, size=14, family=FONT_STACK)
            ),
            bgcolor=COLOR_BG
        ),
        legend=dict(orientation="v", x=1.0, y=1.0, xanchor="left", yanchor="top", font=legend_font()),
        height=CHART_HEIGHT,
        paper_bgcolor=COLOR_BG,
        hoverlabel=hover_label(),
        margin=dict(l=48, r=24, t=32, b=24)
    )
    return fig

def _tick_text(sentiment:dict) -> str:
    return (
        f"<b>{sentiment['ticker']}</b><br><span style='font-size:12px;color:{COLOR_MUTED}'>"
        f"{sentiment['consensus']} · {int(sentiment['total'])} analysts</span>"
    )

def make_analyst_sentiment_figure(sentiment_data:dict) -> go.Figure:
    """
    Create the 100% stacked buy/hold/sell chart.
    
    Inputs:
    - sentiment_data: output of analyst.build_analyst_sentiment_data, whose companies list holds each ticker's buy, hold and sell counts, total and consensus label
    
    Outputs:
    - Plotly stacked bar figure with one bar per company; segments show the percent of covering analysts and hover adds the count
    """
    sentiments = sentiment_data["companies"]
    tickers = [sentiment["ticker"] for sentiment in sentiments]
    
    # One stacked bar per bucket
    fig = go.Figure()
    for bucket, label, color, text_color in SENTIMENT_BUCKETS:
        counts = [sentiment[bucket] for sentiment in sentiments]
        percents = [
            count / sentiment["total"] * 100 if sentiment["total"] else 0.0
            for count, sentiment in zip(counts, sentiments)
        ]
        fig.add_bar(
            x=tickers,
            y=percents,
            name=label,
            marker=dict(color=color),
            text=[f"{percent:.0f}%" if percent > 0 else "" for percent in percents],
            textposition="inside",
            insidetextanchor="middle",
            textangle=0,
            textfont=dict(color=text_color, size=CATEGORY_SIZE, family=MONO_STACK),
            customdata=[int(count) for count in counts],
            hovertemplate="<b>%{x}</b><br>" + label + ": %{y:.1f}%<br>%{customdata} analysts<extra></extra>",
            width=0.5
        )
    
    # Layout
    fig.update_layout(
        barmode="stack",
        uniformtext=dict(minsize=MIN_LABEL_SIZE, mode="hide"),
        legend=dict(orientation="h", x=1.0, y=1.02, xanchor="right", yanchor="bottom", traceorder="normal", font=legend_font()),
        xaxis=dict(
            tickmode="array",
            tickvals=tickers,
            ticktext=[_tick_text(sentiment) for sentiment in sentiments],
            tickfont=dict(color=COLOR_INK, size=CATEGORY_SIZE, family=FONT_STACK),
            showline=True,
            linecolor=COLOR_RULE
        ),
        yaxis=dict(
            title=dict(text="% of covering analysts", font=dict(color=COLOR_MUTED, size=AXIS_TITLE_SIZE)),
            range=[0, 100],
            ticksuffix="%",
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=TICK_SIZE, family=MONO_STACK)
        ),
        height=SENTIMENT_HEIGHT,
        paper_bgcolor=COLOR_BG,
        hoverlabel=hover_label(),
        plot_bgcolor=COLOR_BG,
        margin=CHART_MARGIN
    )
    return fig

def make_sentiment_trend_figure(trend:pd.DataFrame, colors:dict[str, str]) -> go.Figure:
    """
    Plot each company's buy share across analyst snapshots.
    
    Inputs:
    - trend: output of analyst.build_sentiment_trend, one row per period label (oldest first) and one column per ticker
    - colors: line colors keyed by ticker
    
    Outputs:
    - Plotly line figure of buy percentage over time
    """
    fig = go.Figure()
    for ticker in trend.columns:
        fig.add_trace(
            go.Scatter(
                x=trend.index,
                y=trend[ticker],
                name=ticker,
                mode="lines+markers",
                line=dict(color=colors[ticker], width=2.5),
                marker=dict(size=8),
                hovertemplate="%{y:.1f}% buy<extra>%{fullData.name}</extra>"
            )
        )
    
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", x=1.0, y=1.02, xanchor="right", yanchor="bottom", font=legend_font()),
        xaxis=dict(type="category", showline=True, linecolor=COLOR_RULE, tickfont=dict(color=COLOR_INK, size=CATEGORY_SIZE)),
        yaxis=dict(
            title=dict(text="% rating buy", font=dict(color=COLOR_MUTED, size=AXIS_TITLE_SIZE)),
            range=[0, 100],
            ticksuffix="%",
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=TICK_SIZE, family=MONO_STACK)
        ),
        height=SENTIMENT_HEIGHT,
        paper_bgcolor=COLOR_BG,
        hoverlabel=hover_label(),
        plot_bgcolor=COLOR_BG,
        margin=CHART_MARGIN
    )
    return fig

def make_price_target_figure(targets:list[dict], colors:dict[str, str]) -> go.Figure:
    """
    Plot each company's analyst price-target range relative to its current price.
    
    Inputs:
    - targets: output of analyst.build_price_targets, with prices in the listing currency and their percentage distance from the current price
    - colors: colors keyed by ticker
    
    Outputs:
    - Plotly horizontal range figure: a low-to-high bar per ticker, a diamond at the median target, and the current price at 0%
    """
    hover = (
        "<b>%{customdata[0]}</b><br>"
        "Current: %{customdata[1]:,.2f} %{customdata[10]}<br>"
        "Low: %{customdata[2]:,.2f} (%{customdata[6]:+.1f}%)<br>"
        "Median: %{customdata[3]:,.2f} (%{customdata[7]:+.1f}%)<br>"
        "Mean: %{customdata[4]:,.2f} (%{customdata[8]:+.1f}%)<br>"
        "High: %{customdata[5]:,.2f} (%{customdata[9]:+.1f}%)<extra></extra>"
    )
    
    fig = go.Figure()
    for target in targets:
        ticker = target["ticker"]
        color = colors[ticker]
        customdata = [[
            ticker, target["current"], target["low"], target["median"], target["mean"], target["high"],
            target["low_pct"], target["median_pct"], target["mean_pct"], target["high_pct"], target["currency"]
        ]]
        
        # Low-to-high range
        fig.add_trace(
            go.Scatter(
                x=[target["low_pct"], target["high_pct"]],
                y=[ticker, ticker],
                mode="lines",
                line=dict(color=with_alpha(color, TARGET_RANGE_ALPHA), width=14),
                customdata=customdata * 2,
                hovertemplate=hover,
                showlegend=False
            )
        )
        
        # Median target and current price markers
        fig.add_trace(
            go.Scatter(
                x=[target["median_pct"]],
                y=[ticker],
                mode="markers",
                marker=dict(color=color, size=14, symbol="diamond", line=dict(color=COLOR_BG, width=1.5)),
                customdata=customdata,
                hovertemplate=hover,
                showlegend=False
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[0.0],
                y=[ticker],
                mode="markers",
                marker=dict(color=COLOR_BG, size=11, symbol="circle", line=dict(color=COLOR_INK, width=2)),
                customdata=customdata,
                hovertemplate=hover,
                showlegend=False
            )
        )
    
    # Legend entries for the marker meanings
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Median target", marker=dict(color=COLOR_MUTED, size=12, symbol="diamond")))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", name="Current price", marker=dict(color=COLOR_BG, size=10, line=dict(color=COLOR_INK, width=2))))
    fig.add_vline(x=0, line=dict(color=COLOR_MUTED, width=1, dash="dash"))
    
    tickers = [target["ticker"] for target in targets]
    n_targets = len(targets)
    fig.update_layout(
        legend=dict(orientation="h", x=1.0, y=1.02, xanchor="right", yanchor="bottom", font=legend_font()),
        xaxis=dict(
            title=dict(text="Target vs current price", font=dict(color=COLOR_MUTED, size=AXIS_TITLE_SIZE)),
            ticksuffix="%",
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=TICK_SIZE, family=MONO_STACK)
        ),
        yaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=list(reversed(tickers)), #first ticker on top
            tickfont=dict(color=COLOR_INK, size=CATEGORY_SIZE, family=FONT_STACK)
        ),
        height=TARGET_ROW_HEIGHT * n_targets + 130,
        paper_bgcolor=COLOR_BG,
        hoverlabel=hover_label(),
        plot_bgcolor=COLOR_BG,
        margin=CHART_MARGIN
    )
    return fig
