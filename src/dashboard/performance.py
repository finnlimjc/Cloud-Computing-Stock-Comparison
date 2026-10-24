from datetime import date
from html import escape, unescape

import pandas as pd
import requests
import streamlit as st
from yfinance.exceptions import YFException

from src.analysis import transformation
from src.dashboard.config import CARD_METRICS, METRIC_HELP, NEWS_HEIGHT, NEWS_SUMMARY_STYLE, REFRESH_SECONDS, SINGAPORE, STOCK_COLORS, TABLE_METRICS
from src.dashboard.dates import us_market_is_open
from src.dashboard.loaders import load_latest_price, load_recession_periods
from src.plots import price_plots

def metric_value(name:str, value:float) -> str:
    """Format a dashboard metric as currency, percentage, or ratio."""
    if name == "Latest price":
        return f"${value:,.2f}"
    if name == "Return over period":
        return f"{value:+.1%}"
    if name in ("Max drawdown", "Current drawdown"):
        return f"{value:.1%}"
    return f"{value:.2f}"

def render_latest_price_card(latest_prices:dict, card_height:int) -> None:
    """Render the single-stock latest-price card."""
    with st.container(border=True, height=card_height):
        price = next(iter(latest_prices.values()))
        st.metric("Latest price", "Unavailable" if price is None else metric_value("Latest price", price), help=METRIC_HELP["Latest price"])

def render_metrics_table(result:dict, latest_prices:dict) -> None:
    """Render one row per stock with every headline metric, for comparisons."""
    stocks = list(result["stocks"].values())
    tickers = [stock["ticker"] for stock in stocks]
    columns = {"Latest price": pd.Series([latest_prices[ticker] for ticker in tickers], index=tickers, dtype="float64")}
    for name in TABLE_METRICS:
        columns[name] = pd.Series([stock["metrics"][name] for stock in stocks], index=tickers, dtype="float64")
    column_config = {"_index": st.column_config.TextColumn("Ticker")}
    formatters = {}
    for name in columns:
        column_config[name] = st.column_config.NumberColumn(name, help=METRIC_HELP[name])
        formatters[name] = lambda value, name=name: "Unavailable" if pd.isna(value) else metric_value(name, value)
    styled = pd.DataFrame(columns).style.format(formatters).highlight_max(axis=0, props="font-weight:700")
    st.dataframe(styled, column_config=column_config, width="stretch")

def render_live_prices(result:dict, placeholder, status_placeholder, render_body) -> None:
    """Render latest-price content that refreshes while the market is open.
    
    Inputs:
    - result: dashboard analysis result
    - placeholder: location reserved for the latest-price content
    - status_placeholder: location reserved for the update and market status
    - render_body: callable taking {ticker: latest price, or None when unavailable}
    """
    scheduled_market_open = us_market_is_open()
    
    @st.fragment(run_every=REFRESH_SECONDS if scheduled_market_open else None)
    def render_fragment() -> None:
        market_open = us_market_is_open()
        if scheduled_market_open and not market_open:
            st.rerun(scope="app") #stop the scheduled refresh once the market closes
        
        latest_prices = {}
        update_times = []
        for stock in result["stocks"].values():
            try:
                price, updated = load_latest_price(stock["ticker"], market_open)
                latest_prices[stock["ticker"]] = price
                update_times.append(updated)
            except (ValueError, KeyError, YFException, requests.RequestException, OSError):
                latest_prices[stock["ticker"]] = None
        
        # Update status
        market_status = "open" if market_open else "closed"
        if update_times:
            updated_at = max(update_times).astimezone(SINGAPORE)
            status_placeholder.caption(f"Last updated: {updated_at:%H:%M} (Singapore time) · US market {market_status}")
        else:
            status_placeholder.caption(f"Last updated: unavailable · US market {market_status}")
        
        placeholder.empty()
        with placeholder.container():
            render_body(latest_prices)
    
    render_fragment()

def render_metrics(result:dict) -> None:
    """Render metric cards for one stock, or a comparison table for several."""
    status_placeholder = st.empty()
    if result["comparison"]:
        table_placeholder = st.empty()
        render_live_prices(result, table_placeholder, status_placeholder, lambda latest_prices: render_metrics_table(result, latest_prices))
    else:
        stock = next(iter(result["stocks"].values()))
        card_height = 95
        cards = st.columns(len(CARD_METRICS) + 1, gap="small")
        latest_card_placeholder = cards[0].empty()
        render_live_prices(result, latest_card_placeholder, status_placeholder, lambda latest_prices: render_latest_price_card(latest_prices, card_height))
        
        for card, name in zip(cards[1:], CARD_METRICS):
            with card:
                with st.container(border=True, height=card_height):
                    st.metric(name, metric_value(name, stock["metrics"][name]), help=METRIC_HELP[name])
    
    if result["end_date"] < date.today():
        range_prices = [
            f"{stock['ticker']} ${stock['price_at_end_range']:,.2f} (close {stock['price_at_end_date']:%Y-%m-%d})"
            for stock in result["stocks"].values()
        ]
        st.caption("Price at end of range: " + " · ".join(range_prices))

def news_article_html(article:dict) -> str:
    """Build one compact news row: ticker, headline with a clamped summary beneath, and age."""
    color = STOCK_COLORS[article["role"]]
    ticker = f'<span style="color:{color};font-weight:700;min-width:3.5rem">{escape(article["ticker"])}</span>'
    
    summary = unescape(article["summary"]).replace("\n", " ").strip() #feeds send entities such as &#39;
    headline = escape(unescape(article["headline"]))
    if (article["url"] or "").startswith(("http://", "https://")):
        headline = f'<a href="{escape(article["url"], quote=True)}" target="_blank" rel="noopener noreferrer" title="{escape(summary, quote=True)}">{headline}</a>'
    body = f"<div>{headline}</div>"
    if summary:
        body += f'<div style="{NEWS_SUMMARY_STYLE}">{escape(summary)}</div>'
    body = f'<span style="flex:1">{body}</span>'
    
    try:
        age = transformation.relative_time(article["created_at"])
    except (TypeError, ValueError):
        age = "Date unavailable"
    when = f'<span style="color:#6b7280;font-size:0.85rem;white-space:nowrap">{escape(age)}</span>'
    return f'<div style="display:flex;gap:0.75rem;padding:0.3rem 0;line-height:1.3">{ticker}{body}{when}</div>'

def render_news(result:dict) -> None:
    """Render recent news in a card with the comparison ticker filter."""
    with st.container(border=True, key="news_card"):
        title_column, filter_column = st.columns([1, 2], vertical_alignment="center")
        title_column.subheader("Latest news")
        render_news_body(result, filter_column)

def render_news_body(result:dict, filter_column) -> None:
    """Render the ticker filter in filter_column and the matching articles."""
    articles = result["news"]
    tickers = [stock["ticker"] for stock in result["stocks"].values()]
    options = ["All"] + tickers if result["comparison"] else tickers
    with filter_column.container(key="news_filter_box"):
        selected = st.pills(
            "Filter news",
            options,
            selection_mode="single",
            default=options[0],
            label_visibility="collapsed",
            key="news_filter_" + "_".join(tickers) #options change with every analysis
        )
    if selected not in (None, "All"):
        articles = [article for article in articles if article["ticker"] == selected]
    
    if not articles:
        if result["news_error"]:
            st.info(f"Latest news could not be loaded: {result['news_error']}")
        else:
            st.info("No recent news articles are available for this ticker.")
        return
    
    with st.container(height=NEWS_HEIGHT, border=False):
        st.markdown("".join(news_article_html(article) for article in articles), unsafe_allow_html=True)

def render_calendar_returns_chart(result:dict) -> None:
    """Display each stock's return by calendar year."""
    returns = {}
    colors = {}
    for stock in result["stocks"].values():
        returns[stock["ticker"]] = transformation.calendar_year_returns(stock["prices"])
        colors[stock["ticker"]] = STOCK_COLORS[stock["role"]]
    chart = price_plots.plot_calendar_returns(returns, colors)
    st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

def render_dashboard_chart(result:dict) -> None:
    """Display the price and volatility chart with recession shading."""
    price_series = {}
    volatility_series = {}
    drawdown_series = {}
    colors = {}
    for stock in result["stocks"].values():
        ticker = stock["ticker"]
        if ticker in price_series:
            continue
        price_series[ticker] = stock["prices"]
        volatility_series[ticker] = transformation.rolling_volatility(stock["prices"])
        drawdown_series[ticker] = transformation.compute_drawdown(stock["prices"].dropna())
        colors[ticker] = STOCK_COLORS[stock["role"]]
    
    chart = price_plots.plot_dashboard(
        price_series,
        volatility_series,
        drawdown_series,
        colors,
        load_recession_periods(),
        result["comparison"],
        result["start_date"],
        result["end_date"]
    )
    st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

def render_dashboard(result:dict) -> None:
    """Render the main single-stock or comparison dashboard."""
    # Title
    stocks = result["stocks"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    title = " vs ".join(tickers) if result["comparison"] else tickers[0]
    st.title(title)
    if len(stocks) < result["n_requested"]:
        st.caption(f"Only {len(stocks)} of {result['n_requested']} tickers could be loaded; the available stocks are shown below.")
    elif not result["comparison"]:
        st.caption("Add more tickers on the left to compare.")
    
    # Metrics, chart and news
    render_metrics(result)
    render_dashboard_chart(result)
    chart_column, news_column = st.columns([3, 2])
    with chart_column:
        with st.container(border=True, key="chart_card"):
            st.subheader("Return by calendar year")
            render_calendar_returns_chart(result)
            st.caption("\\* = part of the year only (the range starts or ends mid-year).")
    with news_column:
        render_news(result)
