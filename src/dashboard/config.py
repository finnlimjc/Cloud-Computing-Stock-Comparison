from zoneinfo import ZoneInfo

from src.plots import theme

# Caching and refresh
THIRTY_MINUTES = 1800
ONE_DAY_SECONDS = 86400
LATEST_PRICE_TTL = 60
REFRESH_SECONDS = 60

# Time zones
NEW_YORK = ZoneInfo("America/New_York")
SINGAPORE = ZoneInfo("Asia/Singapore")

# Date range selection
RANGE_OPTIONS = {"1 year": 1, "5 years": 5, "10 years": 10, "20 years": 20}
MIN_RANGE_DAYS = 60
HISTORY_YEARS = 20

# Stock performance dashboard
MAX_STOCKS = 5
# One color per role letter, assigned to tickers by entry position (see load_analysis)
STOCK_COLORS = {
    "A": theme.COLOR_A,
    "B": theme.COLOR_B,
    "C": theme.COLOR_C,
    "D": theme.COLOR_D,
    "E": theme.COLOR_E
}
TABLE_METRICS = ["Return over period", "Max drawdown", "Current drawdown", "Sharpe ratio"]
CARD_METRICS = TABLE_METRICS
NEWS_HEIGHT = 376
NEWS_SUMMARY_STYLE = (
    "color:#5f6b7f;font-size:0.85rem;display:-webkit-box;-webkit-line-clamp:2;"
    "-webkit-box-orient:vertical;overflow:hidden"
)
METRIC_HELP = {
    "Latest price": "The latest intraday price, or the most recent close when the US market is closed.",
    "Return over period": "The percentage change from the first to the last price in this range.",
    "Max drawdown": (
        "The biggest fall from a peak to a low in the period. If you had bought "
        "at the top, this is your worst loss on paper."
    ),
    "Current drawdown": "How far the latest price is below the highest price reached in this period. 0% means at a new high.",
    "Sharpe ratio":"Return earned per unit of risk. Higher means the return came with less ups and downs."
}

# Company metrics comparison
COMPARISON_METRICS = [
    "Revenue",
    "Gross Profit",
    "Net Income",
    "Total Assets",
    "Total Liabilities",
    "Cash & Equivalents",
    "Operating Cash Flow"
]

# Page styling
PAGE_CSS = """
<style>
.stApp { background: #F5F6FA; }
div[data-testid="stMetric"] { padding: 0.15rem 0; }
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #1F2A44; }
[data-testid="stMetricLabel"] { color: #6b7280; font-size: 0.8rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #8A704C; background: #FFFFFF; }
.st-key-news_card, .st-key-chart_card { background: #FFFFFF; border-radius: 0.75rem; }
.st-key-news_filter_box { align-items: flex-end; }
.st-key-news_filter_box [data-testid="stButtonGroup"] { justify-content: flex-end; }
[data-testid="stSidebar"] { background: #FFFFFF; }
section[data-testid="stSidebar"] { width: 320px !important; }
@media (max-width: 640px) {
    section[data-testid="stSidebar"] { width: min(320px, 85vw) !important; }
}
</style>
"""
DIALOG_CSS = """
<style>
div[role="dialog"] [data-testid="stMarkdownContainer"] { overflow-wrap: anywhere; }
div[role="dialog"] [data-testid="stMarkdownContainer"] table { display: block; max-width: 100%; overflow-x: auto; }
</style>
"""
