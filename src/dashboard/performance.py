from datetime import date
from html import escape

import requests
import streamlit as st
from yfinance.exceptions import YFException

from src.analysis import transformation
from src.dashboard.analysis import plain_words
from src.dashboard.config import METRIC_HELP, NEWS_COLUMN_WIDTHS, REFRESH_SECONDS, SINGAPORE, STOCK_COLORS, SUMMARY_PREVIEW_CHARS
from src.dashboard.dates import us_market_is_open
from src.dashboard.loaders import load_latest_price, load_recession_periods
from src.plots import price_plots

def metric_value(name:str, value:float) -> str:
    """Format a dashboard metric as currency, percentage, or ratio."""
    if name == "Latest price":
        return f"${value:,.2f}"
    if name == "Return over period":
        return f"{value:+.1%}"
    if name == "Max drawdown":
        return f"{value:.1%}"
    return f"{value:.2f}"

def render_metric_values(stocks:dict, values:dict[str, str]) -> None:
    """Render each stock's formatted value as a stacked metric."""
    for stock in stocks.values():
        st.metric(stock["ticker"], values[stock["ticker"]])

def render_latest_price_card(result:dict, card_placeholder, status_placeholder, card_height:int) -> None:
    """Render latest stock prices in a card that refreshes while the market is open.
    
    Inputs:
    - result: dashboard analysis result
    - card_placeholder: location reserved for the latest-price card
    - status_placeholder: location reserved for the update and market status
    - card_height: shared height for metric cards
    """
    scheduled_market_open = us_market_is_open()
    
    @st.fragment(run_every=REFRESH_SECONDS if scheduled_market_open else None)
    def render_fragment() -> None:
        market_open = us_market_is_open()
        if scheduled_market_open and not market_open:
            st.rerun(scope="app") #stop the scheduled refresh once the market closes
        
        latest_prices = {}
        for stock in result["stocks"].values():
            try:
                latest_prices[stock["ticker"]] = load_latest_price(stock["ticker"], market_open)
            except (ValueError, KeyError, YFException, requests.RequestException, OSError) as error:
                latest_prices[stock["ticker"]] = error
        
        # Update status
        market_status = "open" if market_open else "closed"
        successful_updates = [value[1] for value in latest_prices.values() if not isinstance(value, Exception)]
        if successful_updates:
            updated_at = max(successful_updates).astimezone(SINGAPORE)
            status_placeholder.caption(f"Last updated: {updated_at:%H:%M} (Singapore time) · US market {market_status}")
        else:
            status_placeholder.caption(f"Last updated: unavailable · US market {market_status}")
        
        # Price card
        card_placeholder.empty()
        with card_placeholder.container():
            with st.container(border=True, height=card_height):
                st.markdown("**Latest price**", help=METRIC_HELP["Latest price"])
                price_values = {}
                for stock in result["stocks"].values():
                    latest = latest_prices[stock["ticker"]]
                    price_values[stock["ticker"]] = "Unavailable" if isinstance(latest, Exception) else metric_value("Latest price", latest[0])
                render_metric_values(result["stocks"], price_values)
    
    render_fragment()

def render_metrics(result:dict) -> None:
    """Render the latest-price card and the three selected-range metric cards."""
    metric_names = ["Return over period", "Max drawdown", "Sharpe ratio"]
    card_height = 230 if result["comparison"] else 170
    status_placeholder = st.empty()
    cards = st.columns(4, gap="small")
    
    latest_card_placeholder = cards[0].empty()
    render_latest_price_card(result, latest_card_placeholder, status_placeholder, card_height)
    
    for card, name in zip(cards[1:], metric_names):
        with card:
            with st.container(border=True, height=card_height):
                st.markdown(f"**{name}**", help=METRIC_HELP[name])
                metric_values = {stock["ticker"]: metric_value(name, stock["metrics"][name]) for stock in result["stocks"].values()}
                render_metric_values(result["stocks"], metric_values)
    
    if result["end_date"] < date.today():
        range_prices = [
            f"{stock['ticker']} ${stock['price_at_end_range']:,.2f} (close {stock['price_at_end_date']:%Y-%m-%d})"
            for stock in result["stocks"].values()
        ]
        st.caption("Price at end of range: " + " · ".join(range_prices))

def render_news_article(article:dict, comparison:bool) -> None:
    """Render one article's ticker, headline, summary, and date."""
    ticker_column, headline_column, when_column = st.columns(NEWS_COLUMN_WIDTHS, gap="small")
    color = STOCK_COLORS[article["role"]]
    ticker_column.markdown(f'<span style="color:{color};font-weight:700">{escape(article["ticker"])}</span>', unsafe_allow_html=True)
    
    headline = escape(article["headline"])
    if article["url"]:
        headline_column.markdown(f"[{headline}]({article['url']})")
    else:
        headline_column.markdown(headline)
    if not comparison and article["summary"]:
        summary = article["summary"].replace("\n", " ").strip()
        ellipsis = "…" if len(summary) > SUMMARY_PREVIEW_CHARS else ""
        headline_column.caption(summary[:SUMMARY_PREVIEW_CHARS] + ellipsis)
    
    try:
        when_column.caption(transformation.relative_time(article["created_at"]))
    except (TypeError, ValueError):
        when_column.caption("Date unavailable")
    st.divider()

def render_news(result:dict) -> None:
    """Render recent news and the comparison ticker filter."""
    st.subheader("Latest news")
    
    # Filter by stock
    articles = result["news"]
    if result["comparison"]:
        selected = st.radio(
            "Filter news",
            ["All", "Stock A", "Stock B"],
            horizontal=True,
            label_visibility="collapsed",
            key="news_filter"
        )
        if selected != "All":
            role = "A" if selected == "Stock A" else "B"
            articles = [article for article in articles if article["role"] == role]
    
    if not articles:
        if result["news_error"]:
            st.info(f"Latest news could not be loaded: {result['news_error']}")
        else:
            st.info("No recent news articles are available for this ticker.")
        return
    
    # Article table
    header = st.columns(NEWS_COLUMN_WIDTHS, gap="small")
    header[0].markdown("**Ticker**")
    header[1].markdown("**Headline**")
    header[2].markdown("**When**")
    with st.container(height=435):
        for article in articles:
            render_news_article(article, result["comparison"])

def render_dashboard_chart(result:dict) -> None:
    """Display the price and volatility chart with recession shading."""
    price_series = {}
    volatility_series = {}
    colors = {}
    for stock in result["stocks"].values():
        ticker = stock["ticker"]
        if ticker in price_series:
            continue
        price_series[ticker] = stock["prices"]
        volatility_series[ticker] = transformation.rolling_volatility(stock["prices"])
        colors[ticker] = STOCK_COLORS[stock["role"]]
    
    chart = price_plots.plot_dashboard(
        price_series,
        volatility_series,
        colors,
        load_recession_periods(),
        result["comparison"],
        result["start_date"],
        result["end_date"]
    )
    st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})

def render_dashboard(result:dict) -> None:
    """Render the main single-stock or comparison dashboard."""
    # Title and legend
    stocks = result["stocks"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    title = " vs ".join(tickers) if result["comparison"] else tickers[0]
    title_column, legend_column = st.columns([3, 2], vertical_alignment="center")
    title_column.title(title)
    legend_items = [
        f'<span style="color:{STOCK_COLORS[stock["role"]]};font-weight:700">● {escape(stock["ticker"])}</span>'
        for stock in stocks.values()
    ]
    legend_column.markdown(" &nbsp; ".join(legend_items), unsafe_allow_html=True)
    
    # Summary
    st.markdown("### In plain words")
    st.info(plain_words(result))
    if len(stocks) == 1 and result["input_stock_b"]:
        st.caption("Only one valid ticker could be loaded; the available stock is shown below.")
    elif not result["comparison"]:
        st.caption("Add a Stock B on the left to compare.")
    
    # Metrics, chart and news
    render_metrics(result)
    chart_column, news_column = st.columns([2, 1], gap="medium")
    with chart_column:
        render_dashboard_chart(result)
    with news_column:
        render_news(result)
