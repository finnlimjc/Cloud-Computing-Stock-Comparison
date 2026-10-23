from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from yfinance.exceptions import YFException

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
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
STOCK_COLORS = {
    "A": plots.STOCK_A_COLOR,
    "B": plots.STOCK_B_COLOR,
}
NEWS_COLUMN_WIDTHS = (1.5, 5.2, 1.5)
METRIC_HELP = {
    "Latest price": "The latest intraday price, or the most recent close when the US market is closed.",
    "Return over period": "The percentage change from the first to the last price in this range.",
    "Max drawdown": (
        "The biggest fall from a peak to a low in the period. If you had bought "
        "at the top, this is your worst loss on paper."
    ),
    "Sharpe ratio": (
        "Return earned per unit of risk. Higher means the return came with less "
        "ups and downs."
    ),
}
METRIC_CAPTIONS = {
    "Latest price": "US dollars",
    "Return over period": "over the selected range",
    "Max drawdown": "worst drop from a peak",
    "Sharpe ratio": "return per unit of risk",
}
COMPARISON_METRICS = [
    "Revenue",
    "Gross Profit",
    "Net Income",
    "Total Assets",
    "Total Liabilities",
    "Cash & Equivalents",
    "Operating Cash Flow",
]


@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_prices(ticker:str, start_date:date, end_date:date) -> pd.Series:
    """Load historical prices for a date range.

    Inputs:
    - ticker: stock symbol
    - start_date: inclusive first date
    - end_date: inclusive last date

    Outputs:
    - Daily closing prices
    """
    # This part delegates the request to the price-history provider.
    return input_data.get_price_history(ticker, start_date, end_date)


@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_company_pair_data(ticker_a: str, ticker_b: str) -> dict:
    """Download and cache the snapshots used by the company metrics comparison."""
    return input_data.get_company_pair_data(ticker_a, ticker_b)


@st.cache_data(ttl=LATEST_PRICE_TTL, show_spinner=False)
def load_latest_price(ticker:str, market_open:bool) -> tuple[float, datetime]:
    """Load the latest available price and its fetch time.

    Inputs:
    - ticker: stock symbol
    - market_open: whether regular US trading is open

    Outputs:
    - Latest price and UTC fetch time
    """
    # This part fetches and timestamps the latest available price.
    price = input_data.get_latest_price(ticker, market_open)
    return price, datetime.now(timezone.utc)


def us_market_is_open(now:datetime | None=None) -> bool:
    """Check weekday US regular trading hours.

    Inputs:
    - now: optional time to check

    Outputs:
    - Whether the US market is open
    """
    # This part converts the supplied time to US Eastern time.
    eastern_now = datetime.now(NEW_YORK) if now is None else now
    if eastern_now.tzinfo is None:
        eastern_now = eastern_now.replace(tzinfo=NEW_YORK)
    else:
        eastern_now = eastern_now.astimezone(NEW_YORK)
    # This part checks weekdays and regular trading hours.
    market_time = (eastern_now.hour, eastern_now.minute)
    return eastern_now.weekday() < 5 and (9, 30) <= market_time < (16, 0)


@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_news(ticker:str) -> list[dict]:
    """Load recent news for a ticker.

    Inputs:
    - ticker: stock symbol

    Outputs:
    - Recent news articles
    """
    # This part uses Alpaca when configured and falls back to Yahoo Finance otherwise.
    return input_data.get_news(ticker, limit=5)


def analyze_ticker(
    role:str,
    ticker_input:str,
    start_date:date,
    end_date:date,
) -> tuple[dict | None, str | None]:
    """Load and summarize one stock's price history.

    Inputs:
    - role: stock's comparison role
    - ticker_input: user-entered symbol
    - start_date: inclusive first date
    - end_date: inclusive last date

    Outputs:
    - Stock analysis and optional warning
    """
    # This part handles an empty optional ticker.
    if not ticker_input.strip():
        if role == "A":
            return None, "Stock A: Please enter a ticker symbol."
        return None, None
    try:
        # This part loads and validates the ticker's price history.
        ticker = input_data.clean_ticker(ticker_input)
        prices = load_prices(ticker, start_date, end_date).dropna()
        if prices.empty:
            raise ValueError("No price history found.")
        # This part assembles the stock's prices and metrics.
        return {
            "role": role,
            "ticker": ticker,
            "prices": prices,
            "metrics": transformation.summarize_prices(prices),
        }, None
    except (ValueError, KeyError) as error:
        # This part reports expected ticker or data lookup errors.
        return None, f"{ticker_input.strip().upper()}: {error}"
    except (YFException, requests.RequestException, OSError) as error:
        # This part reports unexpected provider errors in the dashboard.
        return None, f"{ticker_input.strip().upper()}: data could not be loaded ({error})"


def collect_news(stocks:dict) -> tuple[list[dict], str]:
    """Collect recent articles for successfully loaded stocks.

    Inputs:
    - stocks: loaded stock analyses keyed by comparison role

    Outputs:
    - Newest-first news articles and a combined error message
    """
    # This part initializes article and error collections.
    articles = []
    errors = []
    # This part collects news for each successfully loaded stock.
    for stock in stocks.values():
        try:
            for article in load_news(stock["ticker"]):
                articles.append(
                    {
                        "role": stock["role"],
                        "ticker": stock["ticker"],
                        "created_at": article.get("created_at", ""),
                        "headline": article.get("headline", "No headline"),
                        "url": article.get("url", ""),
                        "summary": article.get("summary") or "",
                    }
                )
        except (
            requests.RequestException,
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            errors.append(f"{stock['ticker']}: {error}")
    # This part orders articles by timestamp and combines loading errors.
    articles.sort(key=news_timestamp, reverse=True)
    return articles, "; ".join(errors)


def news_timestamp(article:dict) -> int:
    """Return an article timestamp as an integer sort key.

    Inputs:
    - article: normalized news article

    Outputs:
    - UTC timestamp value, or zero when invalid
    """
    # This part parses the timestamp and handles missing or invalid dates.
    timestamp = pd.to_datetime(article["created_at"], utc=True, errors="coerce")
    return int(timestamp.value) if not pd.isna(timestamp) else 0


def load_analysis(
    ticker_a:str,
    ticker_b:str,
    start_date:date,
    end_date:date,
    range_label:str,
) -> tuple[dict, list[str]]:
    """Load available stock analyses and their news.

    Inputs:
    - ticker_a: first user-entered symbol
    - ticker_b: optional second user-entered symbol
    - start_date: inclusive first date
    - end_date: inclusive last date
    - range_label: selected quick-range option

    Outputs:
    - Analysis result and ticker warnings
    """
    # This part loads each requested ticker and records any warning.
    stocks = {}
    warnings = []
    inputs = (("A", ticker_a), ("B", ticker_b))
    for role, ticker_input in inputs:
        stock, warning = analyze_ticker(role, ticker_input, start_date, end_date)
        if stock:
            stocks[role] = stock
        if warning:
            warnings.append(warning)
    if not stocks:
        return {}, warnings

    # This part avoids treating the same ticker as two comparison series.
    if (
        len(stocks) == 2
        and stocks["A"]["ticker"] == stocks["B"]["ticker"]
    ):
        stocks.pop("B")
        warnings.append("Stock A and Stock B are the same ticker; showing one stock.")

    # This part aligns comparison data to dates both stocks share.
    if len(stocks) == 2:
        aligned = transformation.common_start_prices(
            {role: stock["prices"] for role, stock in stocks.items()}
        )
        if any(prices.empty for prices in aligned.values()):
            warnings.append("The selected stocks have no overlapping price history.")
            stocks.pop("B")
        else:
            for role, stock in stocks.items():
                stock["prices"] = aligned[role]
                stock["metrics"] = transformation.summarize_prices(stock["prices"])

    # This part stores the last available close after aligning the series.
    for stock in stocks.values():
        stock["price_at_end_range"] = float(stock["prices"].iloc[-1])
        stock["price_at_end_date"] = stock["prices"].index[-1].date()
    # This part gathers the news and assembles the dashboard result.
    news, news_error = collect_news(stocks)
    result = {
        "stocks": stocks,
        "start_date": start_date,
        "end_date": end_date,
        "range_label": range_label,
        "comparison": len(stocks) == 2,
        "news": news,
        "news_error": news_error,
        "input_stock_b": bool(ticker_b.strip()),
    }
    return result, warnings


def plain_words(result:dict) -> str:
    """Create a plain-language summary of the loaded stock data.

    Inputs:
    - result: dashboard analysis result

    Outputs:
    - Plain-language comparison or single-stock summary
    """
    # This part selects the single-stock or comparison summary path.
    stocks = result["stocks"]
    range_label = result["range_label"]
    if range_label == "Custom":
        range_label = f"{result['start_date']:%Y-%m-%d} to {result['end_date']:%Y-%m-%d}"
    if result["comparison"]:
        ordered = [stocks[role] for role in ("A", "B")]
        tickers = [stock["ticker"] for stock in ordered]
        returns = {
            stock["ticker"]: stock["metrics"]["Return over period"]
            for stock in ordered
        }
        volatilities = {
            stock["ticker"]: stock["metrics"]["Average volatility"]
            for stock in ordered
        }
        drawdowns = {
            stock["ticker"]: stock["metrics"]["Max drawdown"]
            for stock in ordered
        }
        return transformation.plain_words_comparison(
            tickers,
            returns,
            volatilities,
            drawdowns,
            range_label,
        )
    stock = next(iter(stocks.values()))
    return transformation.plain_words_single(
        stock["ticker"],
        stock["prices"],
        range_label,
    )


def metric_value(name:str, value:float) -> str:
    """Format a dashboard metric for display.

    Inputs:
    - name: metric label
    - value: numeric metric value

    Outputs:
    - Formatted metric text
    """
    # This part applies the appropriate currency, percentage, or ratio format.
    if name == "Latest price":
        return f"${value:,.2f}"
    if name == "Return over period":
        return f"{value:+.1%}"
    if name == "Max drawdown":
        return f"{value:.1%}"
    return f"{value:.2f}"


def render_metric_values(stocks:dict, values:dict[str, str]) -> None:
    """Render stock values as vertically stacked metrics.

    Inputs:
    - stocks: analyzed stock records keyed by role
    - values: formatted metric values keyed by ticker

    Outputs:
    - None
    """
    # This part displays each ticker and value on its own line.
    for stock in stocks.values():
        st.metric(stock["ticker"], values[stock["ticker"]])


def make_analysis_markdown(
    result:dict,
    sentence:str,
    created_at:datetime,
) -> str:
    """Build a Markdown report for a dashboard analysis.

    Inputs:
    - result: dashboard analysis result
    - sentence: plain-language summary
    - created_at: report creation time

    Outputs:
    - Complete Markdown report
    """
    # This part derives the report title and analysis type.
    stocks = result["stocks"]
    comparison = result["comparison"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    analysis_type = "overview" if comparison else "single"
    title = " vs ".join(tickers) if comparison else tickers[0]
    # This part creates report metadata and the metrics table header.
    lines = [
        f"# {title}",
        "",
        f"- Analysis type: {analysis_type}",
        f"- Tickers: {', '.join(tickers)}",
        f"- Time range: {result['start_date']:%Y-%m-%d} to "
        f"{result['end_date']:%Y-%m-%d} ({result['range_label']})",
        f"- Created: {created_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
        "## In plain words",
        "",
        sentence,
        "",
        "## Metrics",
        "",
        "| Ticker | Latest price | Return over period | Max drawdown | Sharpe ratio |",
        "|---|---:|---:|---:|---:|",
    ]
    # This part adds one metrics row for each analyzed stock.
    for stock in stocks.values():
        metrics = stock["metrics"]
        lines.append(
            f"| {stock['ticker']} | ${metrics['Latest price']:,.2f} "
            f"({stock['price_at_end_date']:%Y-%m-%d}) | "
            f"{metrics['Return over period']:+.1%} | "
            f"{metrics['Max drawdown']:.1%} | {metrics['Sharpe ratio']:.2f} |"
        )
    # This part appends the available news headlines.
    lines.extend(["", "## Latest news", ""])
    if result["news"]:
        for article in result["news"]:
            lines.append(
                f"- **{article['ticker']}** · [{article['headline']}]"
                f"({article['url']}) ({article['created_at']})"
            )
    else:
        lines.append("No news articles were available when this analysis was saved.")
    return "\n".join(lines) + "\n"


def analysis_label(path:Path) -> str:
    """Create a readable label for a saved analysis path.

    Inputs:
    - path: saved analysis path

    Outputs:
    - Human-readable analysis label
    """
    # This part parses names and timestamp from the saved filename.
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
        readable_names = names.replace("-vs-", " vs ")
        return f"{readable_names} · {created.strftime(date_format)}"
    return path.stem


def saved_analysis_details(markdown:str) -> str:
    """Extract a short details line from saved report metadata.

    Inputs:
    - markdown: saved analysis report

    Outputs:
    - Compact metadata description
    """
    # This part reads metadata fields from the Markdown report.
    metadata = {}
    for line in markdown.splitlines():
        match = re.match(r"^- ([^:]+):\s*(.*)$", line)
        if match:
            metadata[match.group(1)] = match.group(2)
    # This part formats analysis type and range details.
    analysis_type = metadata.get("Analysis type", "Unavailable")
    if analysis_type != "Unavailable":
        analysis_type = analysis_type.title()
    details = [
        f"Tickers: {metadata.get('Tickers', 'Unavailable')}",
        f"Analysis type: {analysis_type}",
        f"Time range: {metadata.get('Time range', 'Unavailable')}",
        f"Created: {metadata.get('Created', 'Unavailable')}",
    ]
    return " · ".join(details)


@st.dialog("Previous analysis", width="large")
def show_saved_analysis(markdown:str) -> None:
    """Display a saved Markdown analysis in a dialog.

    Inputs:
    - markdown: saved report content

    Outputs:
    - None
    """
    # This part makes report tables scrollable in the dialog.
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
    # This part displays the saved report.
    st.markdown(markdown)


def render_metrics(result:dict) -> None:
    """Render the four metric cards for the loaded analysis.

    Inputs:
    - result: dashboard analysis result

    Outputs:
    - None
    """
    # This part prepares a refreshable price card and three historical metrics.
    metric_names = ["Return over period", "Max drawdown", "Sharpe ratio"]
    single_stock = not result["comparison"]
    card_height = 230 if not single_stock else 170
    # This part displays the refresh timestamp and market status above the cards.
    status_placeholder = st.empty()
    cards = st.columns(4, gap="small")
    latest_card_placeholder = cards[0].empty()
    # This part refreshes only the latest-price card during market hours.
    render_latest_price_card(result, latest_card_placeholder, status_placeholder, card_height)
    # This part renders the selected-range metrics in equal-height cards.
    for card, name in zip(cards[1:], metric_names):
        with card:
            with st.container(border=True, height=card_height):
                st.markdown(f"**{name}**", help=METRIC_HELP[name])
                metric_values = {
                    stock["ticker"]: metric_value(name, stock["metrics"][name])
                    for stock in result["stocks"].values()
                }
                render_metric_values(result["stocks"], metric_values)
    # This part labels the selected range's closing price separately from today's price.
    if result["end_date"] < date.today():
        range_prices = [
            f"{stock['ticker']} ${stock['price_at_end_range']:,.2f} (close {stock['price_at_end_date']:%Y-%m-%d})"
            for stock in result["stocks"].values()
        ]
        st.caption("Price at end of range: " + " · ".join(range_prices))


def render_latest_price_card(result:dict, card_placeholder, status_placeholder, card_height:int) -> None:
    """Render latest stock prices in a refreshable metric card.

    Inputs:
    - result: dashboard analysis result
    - card_placeholder: location reserved for the latest-price card
    - status_placeholder: location reserved for the update and market status
    - card_height: shared height for metric cards

    Outputs:
    - None
    """
    # This part sets the refresh schedule from the current market status.
    scheduled_market_open = us_market_is_open()

    @st.fragment(run_every=60 if scheduled_market_open else None)
    def render_fragment() -> None:
        """Render the latest-price card and its update status.

        Inputs:
        - None

        Outputs:
        - None
        """
        # This part stops scheduled refreshes after the market closes.
        market_open = us_market_is_open()
        if scheduled_market_open and not market_open:
            st.rerun(scope="app")
        # This part loads each ticker's cached latest price.
        latest_prices = {}
        for stock in result["stocks"].values():
            try:
                price, fetched_at = load_latest_price(stock["ticker"], market_open)
                latest_prices[stock["ticker"]] = (price, fetched_at)
            except Exception as error:
                latest_prices[stock["ticker"]] = error
        # This part displays the last successful update time and market status.
        successful_updates = [
            value[1] for value in latest_prices.values() if not isinstance(value, Exception)
        ]
        if successful_updates:
            updated_at = max(successful_updates).astimezone(SINGAPORE)
            status_placeholder.caption(
                f"Last updated: {updated_at:%H:%M} (Singapore time) · "
                f"US market {'open' if market_open else 'closed'}"
            )
        else:
            status_placeholder.caption(
                f"Last updated: unavailable · US market {'open' if market_open else 'closed'}"
            )
        # This part renders the latest prices without changing card dimensions.
        card_placeholder.empty()
        with card_placeholder.container():
            with st.container(border=True, height=card_height):
                st.markdown("**Latest price**", help=METRIC_HELP["Latest price"])
                price_values = {}
                for stock in result["stocks"].values():
                    latest = latest_prices[stock["ticker"]]
                    price_values[stock["ticker"]] = (
                        "Unavailable"
                        if isinstance(latest, Exception)
                        else metric_value("Latest price", latest[0])
                    )
                render_metric_values(result["stocks"], price_values)

    render_fragment()


def render_news(result:dict) -> None:
    """Render recent news and the comparison ticker filter.

    Inputs:
    - result: dashboard analysis result

    Outputs:
    - None
    """
    # This part selects the articles requested by the comparison filter.
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
    # This part explains why the news table has no articles.
    if not articles:
        if result["news_error"]:
            st.info(f"Latest news could not be loaded: {result['news_error']}")
        else:
            st.info("No recent news articles are available for this ticker.")
        return
    # This part renders the news table headings and rows.
    header = st.columns(NEWS_COLUMN_WIDTHS, gap="small")
    header[0].markdown("**Ticker**")
    header[1].markdown("**Headline**")
    header[2].markdown("**When**")
    with st.container(height=435):
        for article in articles:
            render_news_article(article, result["comparison"])


def render_news_article(article:dict, comparison:bool) -> None:
    """Render one article's ticker, headline, summary, and date.

    Inputs:
    - article: normalized news article
    - comparison: whether the dashboard compares two stocks

    Outputs:
    - None
    """
    # This part creates columns and displays the ticker and headline.
    ticker_column, headline_column, when_column = st.columns(
        NEWS_COLUMN_WIDTHS,
        gap="small",
    )
    color = STOCK_COLORS[article["role"]]
    ticker_column.markdown(
        f'<span style="color:{color};font-weight:700">'
        f'{escape(article["ticker"])}</span>',
        unsafe_allow_html=True,
    )
    headline = escape(article["headline"])
    if article["url"]:
        headline_column.markdown(f"[{headline}]({article['url']})")
    else:
        headline_column.markdown(headline)
    # This part adds the single-stock summary and relative date.
    if not comparison and article["summary"]:
        summary = article["summary"].replace("\n", " ").strip()
        headline_column.caption(summary[:160] + ("…" if len(summary) > 160 else ""))
    try:
        when_column.caption(transformation.relative_time(article["created_at"]))
    except (TypeError, ValueError):
        when_column.caption("Date unavailable")
    st.divider()


def resolve_month_date(year:int, month:int, day:int, earliest_date:date, today:date) -> tuple[date, bool]:
    """Resolve a selected calendar date within the available history.

    Inputs:
    - year: selected calendar year
    - month: selected calendar month
    - day: selected calendar day
    - earliest_date: earliest available date
    - today: latest available date

    Outputs:
    - Resolved date and whether the selection needed adjustment
    """
    # This part adjusts days that do not exist in the selected month.
    last_day = monthrange(year, month)[1]
    selected_day = min(day, last_day)
    selected_date = date(year, month, selected_day)
    # This part clamps the selected date to the available history.
    resolved_date = min(max(selected_date, earliest_date), today)
    return resolved_date, selected_day != day or resolved_date != selected_date


def render_dashboard_chart(result:dict) -> None:
    """Prepare and display the dashboard's price and volatility chart.

    Inputs:
    - result: dashboard analysis result

    Outputs:
    - None
    """
    # This part builds unique price and volatility series for the chart.
    price_series = {}
    volatility_series = {}
    colors = {}
    for stock in result["stocks"].values():
        ticker = stock["ticker"]
        if ticker in price_series:
            continue
        price_series[ticker] = stock["prices"]
        volatility_series[ticker] = transformation.rolling_volatility(
            stock["prices"]
        )
        colors[ticker] = STOCK_COLORS[stock["role"]]
    # This part creates and displays the chart with recession shading.
    chart = plots.plot_dashboard(
        price_series,
        volatility_series,
        colors,
        input_data.get_recession_periods(),
        result["comparison"],
        result["start_date"],
        result["end_date"],
    )
    st.plotly_chart(chart, use_container_width=True, config={"displayModeBar": False})


def render_dashboard(result:dict) -> None:
    """Render the main single-stock or comparison dashboard.

    Inputs:
    - result: dashboard analysis result

    Outputs:
    - None
    """
    # This part renders the dashboard title and comparison legend.
    stocks = result["stocks"]
    tickers = [stock["ticker"] for stock in stocks.values()]
    title = " vs ".join(tickers) if result["comparison"] else tickers[0]
    title_column, legend_column = st.columns([3, 2], vertical_alignment="center")
    title_column.title(title)
    legend_items = []
    for stock in stocks.values():
        color = STOCK_COLORS[stock["role"]]
        legend_items.append(
            f'<span style="color:{color};font-weight:700">'
            f'● {escape(stock["ticker"])}</span>'
        )
    legend_column.markdown(" &nbsp; ".join(legend_items), unsafe_allow_html=True)
    # This part displays the plain-language summary and metric cards.
    st.markdown("### In plain words")
    st.info(plain_words(result))
    if len(stocks) == 1 and result["input_stock_b"]:
        st.caption("Only one valid ticker could be loaded; the available stock is shown below.")
    elif not result["comparison"]:
        st.caption("Add a Stock B on the left to compare.")
    render_metrics(result)
    # This part places the price and volatility chart beside the news table.
    chart_column, news_column = st.columns([2, 1], gap="medium")
    with chart_column:
        render_dashboard_chart(result)
    with news_column:
        render_news(result)


def render_analysis_form(today:date) -> None:
    """Render the sidebar form and run a quick-range stock analysis.

    Inputs:
    - today: current date used for the selected range

    Outputs:
    - None
    """
    # This part establishes the available years and date boundaries.
    minimum_date:date = (pd.Timestamp(today) - pd.DateOffset(years=20)).date()
    maximum_date:date = today
    available_years = list(range(minimum_date.year, today.year + 1))
    # This part defines defaults matching today's date and the 20-year start date.
    start_month_index = minimum_date.month - 1
    start_day_index = minimum_date.day - 1
    current_month_index = today.month - 1
    current_day_index = today.day - 1
    # This part renders ticker, range, and date inputs in one form.
    with st.form("stock_analysis_form"):
        ticker_a = st.text_input("Stock A", value="AAPL")
        ticker_b = st.text_input(
            "Stock B (optional)",
            value="",
            help="Leave empty to look at one stock.",
        )
        range_label = st.selectbox("Time range", [*RANGE_OPTIONS, "Custom"], index=3)
        # This part renders the Start year, month, and day selectors side by side.
        start_year_column, start_month_column, start_day_column = st.columns(3)
        start_year = start_year_column.selectbox("Start year", available_years, index=0, key="custom_start_year")
        start_month = start_month_column.selectbox("Start month", MONTHS, index=start_month_index, key="custom_start_month")
        start_day = start_day_column.selectbox("Start day", range(1, 32), index=start_day_index, key="custom_start_day")
        # This part renders the End year, month, and day selectors side by side.
        end_year_column, end_month_column, end_day_column = st.columns(3)
        end_year = end_year_column.selectbox("End year", available_years, index=len(available_years) - 1, key="custom_end_year")
        end_month = end_month_column.selectbox("End month", MONTHS, index=current_month_index, key="custom_end_month")
        end_day = end_day_column.selectbox("End day", range(1, 32), index=current_day_index, key="custom_end_day")
        run = st.form_submit_button("Run", type="primary", use_container_width=True)
    # This part derives the dates selected by the custom or quick-range option.
    if run:
        if range_label == "Custom":
            start_date, start_adjusted = resolve_month_date(start_year, MONTHS.index(start_month) + 1, start_day, minimum_date, maximum_date)
            end_date, end_adjusted = resolve_month_date(end_year, MONTHS.index(end_month) + 1, end_day, minimum_date, maximum_date)
            # This part reports calendar-day or date-boundary adjustments.
            if start_adjusted:
                st.info(f"Start date adjusted to {start_date:%Y-%m-%d} to fit the calendar and available date range.")
            if end_adjusted:
                st.info(f"End date adjusted to {end_date:%Y-%m-%d} to fit the calendar and available date range.")
        else:
            years_back = RANGE_OPTIONS[range_label]
            start_date = (pd.Timestamp(today) - pd.DateOffset(years=years_back)).date()
            end_date = today
        # This part rejects invalid custom ranges before requesting market data.
        if start_date >= end_date or (end_date - start_date).days < 60:
            st.warning("Choose a start date before the end date, at least 60 days apart.")
            return
        # This part loads the requested analysis for the selected dates.
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
            st.session_state.analysis_results = result
        else:
            st.error(
                "No valid stock price data was found. Check the ticker symbols and try again."
            )


def render_saved_analyses() -> str | None:
    """Render save and previous-analysis controls.

    Inputs:
    - None

    Outputs:
    - Selected saved report to display, if requested
    """
    # This part saves the current single-stock or comparison analysis.
    result = st.session_state.get("analysis_results")
    if result and st.button("Save Analysis", use_container_width=True):
        try:
            now = datetime.now().astimezone()
            markdown = make_analysis_markdown(result, plain_words(result), now)
            saved_path = storage.save_analysis(
                markdown,
                [stock["ticker"] for stock in result["stocks"].values()],
                "overview" if result["comparison"] else "single",
                now,
            )
            st.success(f"Analysis saved: {saved_path.name}")
        except (OSError, ValueError) as error:
            st.error(f"Could not save this analysis: {error}")

    # This part loads saved reports and reports storage errors.
    st.subheader("Previous Analyses")
    try:
        saved_files = storage.list_analyses()
    except OSError as error:
        saved_files = []
        st.error(f"Could not list saved analyses: {error}")
    # This part displays saved report details and returns the selected report.
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
        if st.button("Show", use_container_width=True):
            try:
                return storage.read_analysis(selected_path)
            except (OSError, ValueError) as error:
                st.error(f"Could not open this analysis: {error}")
    else:
        st.caption("No saved analyses yet. Run an analysis and click Save Analysis to keep it here.")
    return None


def show_comparison_dashboard() -> None:
    st.header("Two-Company Comparison")
    st.write("Compare financial metrics, business models, and analyst sentiment.")

    with st.form("comparison_form"):
        ticker_columns = st.columns(2)
        ticker_a = ticker_columns[0].text_input(
            "First ticker",
            value=st.session_state.get("comparison_ticker_a", "AAPL"),
            placeholder="e.g. AAPL",
        )
        ticker_b = ticker_columns[1].text_input(
            "Second ticker",
            value=st.session_state.get("comparison_ticker_b", "MSFT"),
            placeholder="e.g. MSFT",
        )
        selected_metric = st.session_state.get("comparison_metric", COMPARISON_METRICS[0])
        metric = st.selectbox(
            "Metric for grouped bar chart",
            COMPARISON_METRICS,
            index=COMPARISON_METRICS.index(selected_metric),
        )
        submitted = st.form_submit_button("Compare companies")

    if submitted:
        try:
            clean_a = input_data.clean_ticker(ticker_a)
            clean_b = input_data.clean_ticker(ticker_b)
            if clean_a == clean_b:
                raise ValueError("Please enter two different ticker symbols.")
            st.session_state["comparison_ticker_a"] = clean_a
            st.session_state["comparison_ticker_b"] = clean_b
            st.session_state["comparison_metric"] = metric
        except ValueError as e:
            st.warning(str(e))
            return

    ticker_a = st.session_state.get("comparison_ticker_a")
    ticker_b = st.session_state.get("comparison_ticker_b")
    if not ticker_a or not ticker_b:
        return

    metric = st.session_state.get("comparison_metric", metric)
    try:
        with st.spinner(f"Loading comparison data for {ticker_a} and {ticker_b}..."):
            company_data = load_company_pair_data(ticker_a, ticker_b)
            company_a = company_data[ticker_a]
            company_b = company_data[ticker_b]

        fiscal_years = transformation.get_common_fiscal_years(company_a, company_b)
        if len(fiscal_years) < 2:
            st.warning(
                "At least two common fiscal years are needed for the first two charts."
            )
            return

        control_columns = st.columns([2, 1, 1])
        selected_years = control_columns[0].select_slider(
            "Fiscal years for charts 1–2",
            options=fiscal_years,
            value=(fiscal_years[-2], fiscal_years[-1]),
            format_func=lambda year: f"FY{year}",
            key=f"comparison_years_{ticker_a}_{ticker_b}",
        )
        radar_year = control_columns[1].selectbox(
            "Fiscal year for chart 3",
            options=fiscal_years,
            index=len(fiscal_years) - 1,
            format_func=lambda year: f"FY{year}",
            key=f"radar_year_{ticker_a}_{ticker_b}",
        )
        analyst_periods = transformation.get_common_analyst_periods(company_a, company_b)
        if analyst_periods:
            selected_analyst_period = control_columns[2].selectbox(
                "Snapshot for chart 4",
                options=analyst_periods,
                format_func=transformation.analyst_period_label,
                key=f"analyst_period_{ticker_a}_{ticker_b}",
            )
        else:
            selected_analyst_period = None
            control_columns[2].warning("No common analyst snapshot periods.")

        core_metrics = transformation.build_core_metrics_table(
            company_a,
            company_b,
            years=selected_years,
        )
        grouped_data = transformation.build_grouped_bar_dataset(
            company_a,
            company_b,
            metric,
            years=selected_years,
        )
        radar_data = transformation.build_business_model_radar_data(
            company_a,
            company_b,
            fiscal_year=radar_year,
        )
        sentiment_data = (
            transformation.build_analyst_sentiment_data(
                company_a,
                company_b,
                period=selected_analyst_period,
            )
            if selected_analyst_period
            else None
        )

        first_row = st.columns(2)
        with first_row[0]:
            st.plotly_chart(
                plots.make_core_metrics_figure(core_metrics),
                use_container_width=True,
            )
        with first_row[1]:
            st.plotly_chart(
                plots.make_grouped_bar_figure(grouped_data, metric),
                use_container_width=True,
            )

        second_row = st.columns(2)
        with second_row[0]:
            if radar_data["missing_metrics"]:
                missing = ", ".join(
                    f"{item['company']} — {item['metric']}"
                    for item in radar_data["missing_metrics"]
                )
                st.warning(
                    f"FY{radar_data['fiscal_year']} data unavailable for: {missing}. "
                    "These radar points are omitted, not scored as zero."
                )
            st.plotly_chart(
                plots.make_business_model_radar_figure(radar_data),
                use_container_width=True,
            )
        with second_row[1]:
            if sentiment_data:
                st.plotly_chart(
                    plots.make_analyst_sentiment_figure(sentiment_data),
                    use_container_width=True,
                )
    except ValueError as e:
        st.warning(str(e))
    except Exception as e:
        st.error(f"Unable to load the company comparison: {e}")

def main() -> None:
    """Configure and render the Streamlit dashboard.

    Inputs:
    - None

    Outputs:
    - None
    """
    # This part configures the wide dashboard and its layout styling.
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
    # This part initializes dashboard state and renders the sidebar.
    st.session_state.setdefault("analysis_results", None)
    with st.sidebar:
        st.title("Stock Comparison")
        render_analysis_form(date.today())
        saved_report = render_saved_analyses()
        st.caption("For learning only. Not investment advice.")
    performance_page, metrics_page = st.tabs(
        ["Stock Performance", "Company Metrics"]
    )
    with performance_page:
        if saved_report is not None:
            show_saved_analysis(saved_report)
        result = st.session_state.analysis_results
        if result:
            render_dashboard(result)
    with metrics_page:
        show_comparison_dashboard()

if __name__ == "__main__":
    main()
