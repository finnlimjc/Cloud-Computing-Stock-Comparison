from __future__ import annotations

import re
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from src import input_data, plots, storage, transformation

THIRTY_MINUTES = 1800
LATEST_PRICE_TTL = 60
NEW_YORK = ZoneInfo("America/New_York")
SINGAPORE = ZoneInfo("Asia/Singapore")
RANGE_OPTIONS = {
    "1 year": 1,
    "5 years": 5,
    "10 years": 10,
    "20 years": 20,
}
STOCK_COLORS = {
    "A": plots.STOCK_A_COLOR,
    "B": plots.STOCK_B_COLOR,
}
METRIC_HELP = {
    "Max drawdown": (
        "The biggest fall from a peak to a low in the period. If you had bought "
        "at the top, this is your worst loss on paper."
    ),
    "Sharpe ratio": (
        "Return earned per unit of risk. Higher means the return came with less "
        "ups and downs."
    ),
}


@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_prices(ticker:str, start_date:date, end_date:date) -> pd.Series:
    return input_data.get_price_history(ticker, start_date, end_date)

@st.cache_data(ttl=LATEST_PRICE_TTL, show_spinner=False)
def load_latest_price(ticker:str, market_open:bool) -> tuple[float, datetime]:
    price = input_data.get_latest_price(ticker, market_open)
    return price, datetime.now(timezone.utc)


@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_news(ticker:str) -> list[dict]:
    return input_data.get_alpaca_news(ticker, limit=5)

def us_market_is_open(now:datetime | None=None) -> bool:
    """Check regular US market hours, without accounting for market holidays."""
    eastern_now = (now or datetime.now(NEW_YORK)).astimezone(NEW_YORK)
    return (
        eastern_now.weekday() < 5
        and (eastern_now.hour, eastern_now.minute) >= (9, 30)
        and (eastern_now.hour, eastern_now.minute) < (16, 0)
    )


def analyze_ticker(
    role:str,
    ticker_input:str,
    start_date:date,
    end_date:date,
) -> tuple[dict | None, str | None]:
    if not ticker_input.strip():
        if role == "A":
            return None, "Stock A: Please enter a ticker symbol."
        return None, None
    try:
        ticker = input_data.clean_ticker(ticker_input)
        prices = load_prices(ticker, start_date, end_date)
        prices = prices.dropna()
        if prices.empty:
            raise ValueError("No price history found.")
        return {
            "role": role,
            "ticker": ticker,
            "prices": prices,
            "price_at_end_range": float(prices.iloc[-1]),
            "price_at_end_date": prices.index[-1].date(),
            "metrics": transformation.summarize_prices(prices),
        }, None
    except (ValueError, KeyError) as error:
        return None, f"{ticker_input.strip().upper()}: {error}"
    except Exception as error:
        return None, f"{ticker_input.strip().upper()}: data could not be loaded ({error})"


def load_analysis(
    ticker_a:str,
    ticker_b:str,
    start_date:date,
    end_date:date,
    range_label:str,
) -> tuple[dict, list[str]]:
    stocks = {}
    warnings = []
    for role, ticker_input in (("A", ticker_a), ("B", ticker_b)):
        stock, warning = analyze_ticker(role, ticker_input, start_date, end_date)
        if stock:
            stocks[role] = stock
        if warning:
            warnings.append(warning)

    if not stocks:
        return {}, warnings

    if len(stocks) == 2:
        aligned_prices = transformation.common_start_prices({
            role: stock["prices"] for role, stock in stocks.items()
        })
        for role, stock in stocks.items():
            stock["prices"] = aligned_prices[role]
            stock["metrics"] = transformation.summarize_prices(stock["prices"])

    news = []
    news_errors = []
    for stock in stocks.values():
        try:
            for article in load_news(stock["ticker"]):
                news.append({
                    "role": stock["role"],
                    "ticker": stock["ticker"],
                    "created_at": article.get("created_at", ""),
                    "headline": article.get("headline", "No headline"),
                    "url": article.get("url", ""),
                    "summary": article.get("summary") or "",
                })
        except Exception as error:
            news_errors.append(str(error))
    def news_timestamp(article:dict) -> int:
        timestamp = pd.to_datetime(article["created_at"], utc=True, errors="coerce")
        return int(timestamp.value) if not pd.isna(timestamp) else 0

    news.sort(key=news_timestamp, reverse=True)
    result = {
        "stocks": stocks,
        "start_date": start_date,
        "end_date": end_date,
        "range_label": range_label,
        "range_type": "Custom" if range_label == "Custom" else "quick option",
        "comparison": len(stocks) == 2,
        "news": news,
        "news_error": "; ".join(news_errors),
    }
    return result, warnings


def plain_words(result:dict) -> str:
    stocks = result["stocks"]
    range_label = (
        f"{result['start_date']:%Y-%m-%d} to {result['end_date']:%Y-%m-%d}"
    )
    if result["comparison"]:
        ordered = [stocks[role] for role in ("A", "B")]
        tickers = [stock["ticker"] for stock in ordered]
        returns = {stock["ticker"]: stock["metrics"]["Return over period"] for stock in ordered}
        volatilities = {
            stock["ticker"]: stock["metrics"]["Average volatility"] for stock in ordered
        }
        drawdowns = {stock["ticker"]: stock["metrics"]["Max drawdown"] for stock in ordered}
        return transformation.plain_words_comparison(
            tickers, returns, volatilities, drawdowns, range_label
        )
    stock = next(iter(stocks.values()))
    return transformation.plain_words_single(stock["ticker"], stock["prices"], range_label)


def metric_value(name:str, value:float) -> str:
    if name == "Price at end of range":
        return f"${value:,.2f}"
    if name == "Return over period":
        return f"{value:+.1%}"
    if name == "Max drawdown":
        return f"{value:.1%}"
    return f"{value:.2f}"


def make_analysis_markdown(result:dict, sentence:str, created_at:datetime) -> str:
    stocks = result["stocks"]
    comparison = result["comparison"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    analysis_type = "overview" if comparison else "single"
    title = " vs ".join(tickers) if comparison else tickers[0]
    range_description = (
        "Custom"
        if result["range_type"] == "Custom"
        else f"{result['range_label']} quick option"
    )
    latest_prices = result.get("latest_prices", {})
    lines = [
        f"# {title}",
        "",
        f"- Analysis type: {analysis_type}",
        f"- Tickers: {', '.join(tickers)}",
        f"- Time range: {result['start_date']:%Y-%m-%d} to "
        f"{result['end_date']:%Y-%m-%d} ({range_description})",
        f"- Created: {created_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "## In plain words",
        "",
        sentence,
        "",
        "## Metrics",
        "",
        "| Ticker | Latest price (today) | Price at end of range | Return over period | Max drawdown | Sharpe ratio | Average volatility |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for stock in stocks.values():
        metrics = stock["metrics"]
        latest = latest_prices.get(stock["ticker"])
        latest_text = (
            f"${latest['price']:,.2f} "
            f"(fetched {latest['fetched_at'].astimezone(SINGAPORE):%Y-%m-%d %H:%M} SGT)"
            if latest
            else "Unavailable"
        )
        lines.append(
            f"| {stock['ticker']} | {latest_text} | "
            f"${stock['price_at_end_range']:,.2f} "
            f"({stock['price_at_end_date']:%Y-%m-%d}) | "
            f"{metrics['Return over period']:+.1%} | {metrics['Max drawdown']:.1%} | "
            f"{metrics['Sharpe ratio']:.2f} | {metrics['Average volatility']:.1%} |"
        )
    lines.extend(["", "## Latest news", ""])
    if result["news"]:
        for article in result["news"]:
            date_text = article["created_at"]
            lines.append(
                f"- **{article['ticker']}** · [{article['headline']}]({article['url']}) "
                f"({date_text})"
            )
    else:
        lines.append("No news articles were available when this analysis was saved.")
    return "\n".join(lines) + "\n"


def analysis_label(path:Path) -> str:
    match = re.fullmatch(
        r"(.+)_(?:overview|single)_(\d{8}-\d{6})(?:_\d+)?",
        path.stem,
    )
    if match:
        names, timestamp = match.groups()
        created = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
        date_format = (
            "%d %b %H:%M"
            if created.year == datetime.now().year
            else "%d %b %Y %H:%M"
        )
        readable_date = created.strftime(date_format)
        readable_names = names.replace("-vs-", " vs ")
        return f"{readable_names} · {readable_date}"
    return path.stem


def saved_analysis_details(markdown:str) -> str:
    metadata = {}
    for line in markdown.splitlines():
        match = re.match(r"^- ([^:]+):\s*(.*)$", line)
        if match:
            metadata[match.group(1)] = match.group(2)
    analysis_type = metadata.get("Analysis type", "Unavailable")
    if analysis_type != "Unavailable":
        analysis_type = analysis_type.title()
    details = [
        f"Tickers: {metadata.get('Tickers', 'Unavailable')}",
        f"Analysis type: {analysis_type}",
    ]
    time_range = metadata.get(
        "Time range",
        metadata.get("Price time range", "Unavailable"),
    )
    details.append(f"Time range: {time_range}")
    details.append(f"Created: {metadata.get('Created', 'Unavailable')}")
    return " · ".join(details)


@st.dialog("Previous analysis", width="large")
def show_saved_analysis(markdown:str) -> None:
    st.markdown(
        """
        <style>
        div[role="dialog"] [data-testid="stMarkdownContainer"] {
            overflow-wrap: anywhere;
        }
        div[role="dialog"] [data-testid="stMarkdownContainer"] table {
            display: block;
            max-width: 100%;
            overflow-x: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(markdown)


def render_metrics(result:dict) -> None:
    metric_names = ["Return over period", "Max drawdown", "Sharpe ratio"]
    if result["end_date"] < datetime.now().date():
        metric_names.append("Price at end of range")
    cards = st.columns(len(metric_names), gap="small")
    for card, name in zip(cards, metric_names):
        with card:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                stock_columns = st.columns(len(result["stocks"]))
                for column, stock in zip(stock_columns, result["stocks"].values()):
                    with column:
                        st.metric(
                            stock["ticker"],
                            metric_value(
                                name,
                                stock["price_at_end_range"]
                                if name == "Price at end of range"
                                else stock["metrics"][name],
                            ),
                            help=METRIC_HELP.get(name),
                        )
                        if name == "Price at end of range":
                            st.caption(
                                f"Closing price on {stock['price_at_end_date']:%Y-%m-%d}"
                            )

def render_latest_price_card(result:dict) -> None:
    scheduled_market_open = us_market_is_open()

    @st.fragment(
        run_every=60 if scheduled_market_open else None,
        key="latest-price-card",
    )
    def render_fragment() -> None:
        market_open = us_market_is_open()
        if scheduled_market_open and not market_open:
            st.rerun(scope="app")
        latest_prices = st.session_state.setdefault("latest_price_data", {})
        price_columns = st.columns(len(result["stocks"]))
        for column, stock in zip(price_columns, result["stocks"].values()):
            ticker = stock["ticker"]
            try:
                price, fetched_at = load_latest_price(ticker, market_open)
                latest_prices[ticker] = {"price": price, "fetched_at": fetched_at}
                with column:
                    st.metric(f"Latest price (today) · {ticker}", f"${price:,.2f}")
                    singapore_time = fetched_at.astimezone(SINGAPORE)
                    st.caption(
                        f"Last updated {singapore_time:%H:%M} · "
                        f"US market {'open' if market_open else 'closed'} "
                        f"(Singapore time)"
                    )
            except Exception as error:
                with column:
                    st.error(f"{ticker}: latest price unavailable ({error})")

    render_fragment()


def render_news(result:dict) -> None:
    st.subheader("Latest news")
    articles = result["news"]
    if result["comparison"]:
        selected = st.radio(
            "Filter news",
            ["All", "Stock A", "Stock B"],
            horizontal=True,
            label_visibility="collapsed",
            key="news_filter",
        )
        if selected != "All":
            role = "A" if selected == "Stock A" else "B"
            articles = [article for article in articles if article["role"] == role]
    if not articles:
        if "credentials not set" in result["news_error"].lower():
            st.info("Latest news needs Alpaca credentials. Add ALPACA_API_KEY and ALPACA_SECRET_KEY to secrets.env.")
        elif result["news_error"]:
            st.info(f"Latest news could not be loaded: {result['news_error']}")
        else:
            st.info("No recent news articles are available for this ticker.")
        return

    header = st.columns([1.1, 5.2, 1.3], gap="small")
    header[0].markdown("**Ticker**")
    header[1].markdown("**Headline**")
    header[2].markdown("**When**")
    with st.container(height=435):
        for article in articles:
            ticker_column, headline_column, when_column = st.columns(
                [1.1, 5.2, 1.3], gap="small"
            )
            color = STOCK_COLORS[article["role"]]
            ticker_column.markdown(
                f'<span style="color:{color};font-weight:700">{escape(article["ticker"])}</span>',
                unsafe_allow_html=True,
            )
            headline = escape(article["headline"])
            if article["url"]:
                headline_column.markdown(f"[{headline}]({article['url']})")
            else:
                headline_column.markdown(headline)
            if not result["comparison"] and article["summary"]:
                summary = article["summary"].replace("\n", " ").strip()
                headline_column.caption(summary[:160] + ("…" if len(summary) > 160 else ""))
            try:
                when_column.caption(transformation.relative_time(article["created_at"]))
            except (TypeError, ValueError):
                when_column.caption("Date unavailable")
            st.divider()


def render_dashboard(result:dict) -> None:
    stocks = result["stocks"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    title = " vs ".join(tickers) if result["comparison"] else tickers[0]
    title_column, legend_column = st.columns([3, 2], vertical_alignment="center")
    title_column.title(title)
    legend_items = []
    for stock in stocks.values():
        color = STOCK_COLORS[stock["role"]]
        legend_items.append(
            f'<span style="color:{color};font-weight:700">● {escape(stock["ticker"])}</span>'
        )
    legend_column.markdown(" &nbsp; ".join(legend_items), unsafe_allow_html=True)

    st.info(plain_words(result))
    if len(stocks) == 1 and len(tickers) == 1 and result.get("input_stock_b"):
        st.caption("Only one valid ticker could be loaded; the available stock is shown below.")
    elif not result["comparison"]:
        st.caption("Add a Stock B on the left to compare")

    render_latest_price_card(result)
    render_metrics(result)
    chart_column, news_column = st.columns([2, 1], gap="medium")
    with chart_column:
        price_series = {}
        volatility_series = {}
        colors = {}
        for stock in stocks.values():
            ticker = stock["ticker"]
            if ticker in price_series:
                continue
            price_series[ticker] = stock["prices"]
            volatility_series[ticker] = transformation.rolling_volatility(stock["prices"])
            colors[ticker] = STOCK_COLORS[stock["role"]]
        chart = plots.plot_dashboard(
            price_series,
            volatility_series,
            colors,
            input_data.get_recession_periods(),
            result["comparison"],
            result["start_date"],
            result["end_date"],
        )
        st.plotly_chart(chart, width="stretch", config={"displayModeBar": False})
    with news_column:
        render_news(result)


def main() -> None:
    st.set_page_config(page_title="Stock Comparison", page_icon="📈", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background: #F5F6FA; }
        div[data-testid="stMetric"] { padding: 0.15rem 0; }
        [data-testid="stMetricValue"] { font-size: 1.6rem; }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #8A704C; }
        [data-testid="stSidebar"] { background: #FFFFFF; }
        section[data-testid="stSidebar"] { width: 320px !important; }
        @media (max-width: 640px) {
            section[data-testid="stSidebar"] { width: min(320px, 85vw) !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state.setdefault("analysis_results", None)

    dialog_content = None
    today = date.today()
    earliest_start = (pd.Timestamp(today) - pd.DateOffset(years=20)).date()
    st.session_state.setdefault("start_date", earliest_start)
    st.session_state.setdefault("end_date", today)

    with st.sidebar:
        st.title("Stock Comparison")
        with st.form("stock_analysis_form"):
            ticker_a = st.text_input("Stock A", value="AAPL")
            ticker_b = st.text_input(
                "Stock B (optional)",
                value="MSFT",
                help="Leave empty to look at one stock",
            )
            range_label = st.selectbox(
                "Time range",
                ["1 year", "5 years", "10 years", "20 years", "Custom"],
                index=3,
            )
            start_date = st.date_input(
                "Start date",
                min_value=earliest_start,
                max_value=today,
                help="Used only when Time range is Custom",
                key="start_date",
            )
            end_date = st.date_input(
                "End date",
                min_value=earliest_start,
                max_value=today,
                help="Used only when Time range is Custom",
                key="end_date",
            )
            run = st.form_submit_button("Run", type="primary", width="stretch")
        if run:
            if range_label != "Custom":
                years = RANGE_OPTIONS[range_label]
                start_date = (pd.Timestamp(today) - pd.DateOffset(years=years)).date()
                end_date = today
            if start_date is None or end_date is None:
                st.warning("Choose both a start date and an end date.")
            elif start_date >= end_date:
                st.warning("The start date must be before the end date.")
            elif (end_date - start_date).days < 60:
                st.warning("Choose a date range of at least 60 days for the volatility analysis.")
            else:
                with st.spinner("Loading prices and news..."):
                    result, warnings = load_analysis(
                        ticker_a,
                        ticker_b,
                        start_date,
                        end_date,
                        range_label,
                    )
                for warning in warnings:
                    st.warning(warning)
                if result:
                    result["input_stock_b"] = bool(ticker_b.strip())
                    st.session_state.analysis_results = result
                else:
                    st.error("No valid stock price data was found. Check the ticker symbols and try again.")

        result = st.session_state.analysis_results
        if result:
            if st.button("Save Analysis", width="stretch"):
                try:
                    now = datetime.now().astimezone()
                    markdown = make_analysis_markdown(
                        {
                            **result,
                            "latest_prices": st.session_state.get("latest_price_data", {}),
                        },
                        plain_words(result),
                        now,
                    )
                    saved_path = storage.save_analysis(
                        markdown,
                        [stock["ticker"] for stock in result["stocks"].values()],
                        "overview" if result["comparison"] else "single",
                        now,
                    )
                    st.success(f"Analysis saved: {saved_path.name}")
                except (OSError, ValueError) as error:
                    st.error(f"Could not save this analysis: {error}")

        st.subheader("Previous Analyses")
        try:
            saved_files = storage.list_analyses()
        except OSError as error:
            saved_files = []
            st.error(f"Could not list saved analyses: {error}")
        if saved_files:
            selected_path = st.selectbox(
                "Saved analyses",
                saved_files,
                format_func=analysis_label,
                label_visibility="collapsed",
            )
            try:
                st.caption(saved_analysis_details(storage.read_analysis(selected_path)))
            except (OSError, ValueError) as error:
                st.error(f"Could not read saved analysis details: {error}")
            if st.button("Show", width="stretch"):
                try:
                    dialog_content = storage.read_analysis(selected_path)
                except (OSError, ValueError) as error:
                    st.error(f"Could not open this analysis: {error}")
        else:
            st.caption("No saved analyses yet. Run an analysis and click Save Analysis to keep it here.")
        st.caption("For learning only. Not investment advice. Prices delayed ~15 min.")

    if dialog_content is not None:
        show_saved_analysis(dialog_content)
    result = st.session_state.analysis_results
    if result:
        render_dashboard(result)


if __name__ == "__main__":
    main()
