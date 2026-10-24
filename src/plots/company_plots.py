import pandas as pd
import plotly.graph_objects as go

from src.plots.theme import *

# Core metrics table
COLOR_UP = "#2E8B57"
COLOR_DOWN = "#D95D39"
FILL_UP = "rgba(14,159,110,0.10)"
FILL_DOWN = "rgba(224,36,36,0.10)"

# Business model radar
RADIAL_TICKS = [20, 40, 60, 80, 100]

# Analyst sentiment
COLOR_HOLD = "#D9B36C"
COLOR_SELL = "#C65151"
MIN_LABEL_PERCENT = 6 # Stacked bar chart, too tiny to put the value in the middle
SENTIMENT_BUCKETS = (
    ("buy", "Buy", COLOR_UP, "#ffffff"),
    ("hold", "Hold", COLOR_HOLD, COLOR_INK),
    ("sell", "Sell", COLOR_SELL, "#ffffff")
)

def _format_money(value:float) -> str:
    return "N/A" if pd.isna(value) else f"{value:,.2f}"

def _format_signed(value:float) -> str:
    return "N/A" if pd.isna(value) else f"{value:+,.2f}"

def _format_pct(value:float) -> str:
    if pd.isna(value):
        return "N/A"
    arrow = "▲" if value >= 0 else "▼"
    return f"{arrow}{value:+.1f}%"

def _to_usd_billions(values:list[float], usd_rate:float) -> list[float]:
    USD_PER_BILLION = 1_000_000_000
    return [value * usd_rate / USD_PER_BILLION for value in values]

def _core_metric_rows(metrics:pd.DataFrame, usd_rates:dict[str, float], year_a:str, year_b:str) -> list[tuple]:
    """Build (values, fills, fonts) table rows, with a banner row before each statement."""
    n_cols = 6
    rows = []
    for statement in metrics["Statement"].drop_duplicates():
        banner_values = [statement.upper()] + [""] * (n_cols - 1)
        banner_fonts = [COLOR_B] + [COLOR_MUTED] * (n_cols - 1)
        rows.append((banner_values, [COLOR_SECTION_FILL] * n_cols, banner_fonts))
        
        for _, row in metrics[metrics["Statement"] == statement].iterrows():
            to_usd = _to_usd_billions([row[year_a], row[year_b], row["Abs_Change"]], usd_rates[row["Company"]])
            value_a, value_b, abs_change = to_usd
            is_positive = abs_change >= 0
            diff_fill = FILL_UP if is_positive else FILL_DOWN
            diff_font = COLOR_UP if is_positive else COLOR_DOWN
            
            values = [
                row["Metric"],
                row["Company"],
                _format_money(value_a),
                _format_money(value_b),
                _format_signed(abs_change),
                _format_pct(row["Growth_Pct"])
            ]
            fills = [COLOR_BG] * 4 + [diff_fill] * 2
            fonts = [COLOR_INK] * 4 + [diff_font] * 2
            rows.append((values, fills, fonts))
    return rows

def make_core_metrics_figure(metrics:pd.DataFrame, usd_rates:dict[str, float]) -> go.Figure:
    """
    Create the two-year financial comparison table in USD billions.
    
    Inputs:
    - metrics: output of fundamentals.build_core_metrics_table, one row per company and metric with Statement, Metric, Company, two FY columns, Abs_Change and Growth_Pct, in the reporting currency
    - usd_rates: USD value of one unit of each company's reporting currency, a dictionary with kv pair being ticker:usd_conversion_rate.
    
    Outputs:
    - Plotly table figure, or an empty figure when metrics is empty
    """
    if metrics.empty:
        return go.Figure()
    
    # Inputs
    year_columns = [
        column for column in metrics.columns
        if isinstance(column, str) and column.startswith("FY") and column[2:].isdigit()
    ]
    if len(year_columns) != 2:
        raise ValueError("Core metrics chart requires exactly two selected fiscal years.")
    year_a, year_b = year_columns
    
    # Table content
    rows = _core_metric_rows(metrics, usd_rates, year_a, year_b)
    values, fills, fonts = ([list(column) for column in zip(*part)] for part in zip(*rows))
    header = [
        "Metric",
        "Company",
        year_a,
        year_b,
        f"Abs. Change<br><span style='font-size:9px'>{year_b} - {year_a}</span>",
        f"Growth<br><span style='font-size:9px'>{year_a} → {year_b}</span>"
    ]
    
    # Figure
    fig = go.Figure(
        go.Table(
            columnwidth=[145, 68, 76, 76, 116, 104],
            header=dict(
                values=header,
                fill_color=[COLOR_A] * 4 + [COLOR_B] * 2,
                font=dict(color="#ffffff", size=12, family=FONT_STACK),
                align=["left", "center", "right", "right", "center", "center"],
                height=48,
                line_color=COLOR_A
            ),
            cells=dict(
                values=values,
                fill_color=fills,
                font=dict(color=fonts, size=12.5, family=MONO_STACK),
                align=["left", "center", "right", "right", "right", "center"],
                height=34,
                line_color=COLOR_RULE
            )
        )
    )
    fig.update_layout(
        title=chart_title(f"Core Metrics Comparison — {year_a} vs {year_b}<br>(USD billions · per-company growth)", 15),
        width=760,
        height=700,
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        margin=dict(l=12, r=12, t=78, b=16)
    )
    return fig

def _add_company_bar(fig:go.Figure, years:list[str], values:list[float], name:str, color:str) -> None:
    fig.add_bar(
        x=years,
        y=values,
        name=name,
        marker=dict(color=color, cornerradius=4),
        text=[f"{value:,.2f}" if pd.notna(value) else "" for value in values],
        customdata=years,
        hovertemplate="%{fullData.name}<br>%{customdata}<br>%{y:,.2f} USD billions<extra></extra>",
        textposition="outside",
        textfont=dict(color=color, size=11, family=MONO_STACK),
        width=0.3
    )

def make_grouped_bar_figure(data:dict, usd_rates:dict[str, float], metric:str="Revenue") -> go.Figure:
    """Create the grouped bar chart comparing one metric across two fiscal years in USD billions."""
    series_a = _to_usd_billions(data["series_a"], usd_rates[data["company_a"]])
    series_b = _to_usd_billions(data["series_b"], usd_rates[data["company_b"]])
    
    fig = go.Figure()
    _add_company_bar(fig, data["years"], series_a, data["company_a"], COLOR_A)
    _add_company_bar(fig, data["years"], series_b, data["company_b"], COLOR_B)
    
    fig.update_layout(
        barmode="group",
        bargap=0.42,
        bargroupgap=0.12,
        title=chart_title(
            f"{metric} — Grouped Comparison<br>({' vs '.join(data['years'])}, USD billions · latest FX rates)",
            17
        ),
        legend=dict(orientation="h", x=0.0, y=1.02, xanchor="left", font=legend_font()),
        xaxis=dict(
            title=None,
            tickfont=dict(color=COLOR_INK, size=13, family=FONT_STACK),
            showline=True,
            linecolor=COLOR_RULE,
            ticks=""
        ),
        yaxis=dict(
            title=dict(text="USD billions", font=dict(color=COLOR_MUTED, size=11)),
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=11, family=MONO_STACK)
        ),
        width=1280,
        height=640,
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        margin=dict(l=64, r=24, t=116, b=48)
    )
    return fig

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

def make_business_model_radar_figure(radar_data:dict) -> go.Figure:
    """Create the radar chart of normalized business-model scores for both companies."""
    # Inputs
    labels = radar_data["labels"]
    fiscal_year = radar_data["fiscal_year"]
    axis_labels = [
        label.replace("Safety Ratio", "Safety<br>Ratio").replace("Gross Margin", "Gross<br>Margin")
        for label in labels
    ]
    companies = [
        {
            "name": radar_data.get("name_a", radar_data["company_a"]),
            "values": radar_data["values_a"],
            "actuals": radar_data["actuals_a"],
            "color": COLOR_A,
            "fillcolor": FILL_A,
            "symbol": "circle"
        },
        {
            "name": radar_data.get("name_b", radar_data["company_b"]),
            "values": radar_data["values_b"],
            "actuals": radar_data["actuals_b"],
            "color": COLOR_B,
            "fillcolor": FILL_B,
            "symbol": "diamond"
        }
    ]
    
    # Traces
    fig = go.Figure()
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
                hoverinfo="skip"
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
                    line=dict(color=COLOR_BG, width=1.2)
                ),
                customdata=_radar_customdata(radar_data, company["values"], company["actuals"]),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Formula: %{customdata[3]}<br>"
                    "Normalized score: %{customdata[1]}/100<br>"
                    f"FY{fiscal_year} actual: "
                    "%{customdata[2]}<extra>%{fullData.name}</extra>"
                ),
                showlegend=False
            )
        )
    
    # Layout
    subtitle = (
        f"<span style='font-family:{FONT_STACK};font-size:14px;font-weight:400;color:#4B5563'>"
        "Normalized Business Metric Scores (0-100) | <i>Hover for formulas</i></span>"
    )
    fig.update_layout(
        title=chart_title(f"Normalized Business Model Fingerprint — FY{fiscal_year}<br>{subtitle}", 17, y=0.92, yanchor="top"),
        polar=dict(
            domain=dict(x=[0.10, 0.90], y=[0.03, 0.82]),
            radialaxis=dict(
                range=[0, 105],
                gridcolor=COLOR_RULE,
                tickvals=[0] + RADIAL_TICKS,
                tickangle=0,
                tickfont=dict(color=COLOR_MUTED, size=10),
                showline=False,
                angle=0
            ),
            angularaxis=dict(
                gridcolor=COLOR_RULE,
                tickfont=dict(color=COLOR_INK, size=12.5, family=FONT_STACK)
            ),
            bgcolor=COLOR_BG
        ),
        legend=dict(orientation="h", x=1.0, y=0.80, xanchor="right", font=legend_font()),
        annotations=[],
        width=900,
        height=660,
        paper_bgcolor=COLOR_BG,
        margin=dict(l=48, r=48, t=82, b=30)
    )
    return fig

def _bucket_label(percent:float, count:float) -> str:
    if percent < MIN_LABEL_PERCENT:
        return ""
    return f"{percent:.1f}%<br><span style='font-size:10px'>{int(count)}</span>"

def _tick_text(ticker:str, sentiment:dict, total:float) -> str:
    return (
        f"<b>{ticker}</b><br><span style='font-size:10px;color:{COLOR_MUTED}'>"
        f"Consensus: {sentiment['consensus']} · {int(total)} analysts</span>"
    )

def make_analyst_sentiment_figure(sentiment_data:dict) -> go.Figure:
    """
    Create the 100% stacked buy/hold/sell chart for both companies.
    
    Inputs:
    - sentiment_data: output of analyst.build_analyst_sentiment_data, with company_a and company_b tickers, period_label, and a and b dicts holding buy, hold and sell analyst counts plus the consensus label
    
    Outputs:
    - Plotly stacked bar figure with one bar per company, segments showing percent of covering analysts
    """
    tickers = [sentiment_data["company_a"], sentiment_data["company_b"]]
    sentiments = [sentiment_data["a"], sentiment_data["b"]]
    totals = [sum(sentiment[bucket] for bucket, *_ in SENTIMENT_BUCKETS) for sentiment in sentiments]
    
    # One stacked bar per bucket
    fig = go.Figure()
    for bucket, label, color, text_color in SENTIMENT_BUCKETS:
        counts = [sentiment[bucket] for sentiment in sentiments]
        percents = [count / total * 100 if total else 0.0 for count, total in zip(counts, totals)]
        fig.add_bar(
            x=tickers,
            y=percents,
            name=label,
            marker=dict(color=color),
            text=[_bucket_label(percent, count) for percent, count in zip(percents, counts)],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color=text_color, size=13, family=MONO_STACK),
            customdata=[int(count) for count in counts],
            hovertemplate="<b>%{x}</b> · " + label + ": %{y:.1f}% (%{customdata} analysts)<extra></extra>",
            width=0.42
        )
    
    # Layout
    subtitle = f"<span style='font-size:13px;font-weight:400'>Snapshot: {sentiment_data.get('period_label', 'Latest snapshot')}</span>"
    fig.update_layout(
        barmode="stack",
        title=chart_title(f"Analyst Sentiment — 100% Stacked (Buy / Hold / Sell)<br>{subtitle}", 17, y=0.88, yanchor="top"),
        legend=dict(
            orientation="h",
            x=0.99,
            y=1.01,
            xanchor="right",
            yanchor="bottom",
            traceorder="normal",
            font=legend_font()
        ),
        xaxis=dict(
            tickmode="array",
            tickvals=tickers,
            ticktext=[_tick_text(ticker, sentiment, total) for ticker, sentiment, total in zip(tickers, sentiments, totals)],
            tickfont=dict(color=COLOR_INK, size=14, family=FONT_STACK),
            showline=True,
            linecolor=COLOR_RULE
        ),
        yaxis=dict(
            title=dict(text="% of covering analysts", font=dict(color=COLOR_MUTED, size=11)),
            range=[0, 100],
            ticksuffix="%",
            gridcolor=COLOR_RULE,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED, size=11, family=MONO_STACK)
        ),
        width=1280,
        height=620,
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        margin=dict(l=64, r=24, t=160, b=64)
    )
    return fig
