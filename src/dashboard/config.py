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
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
)

# Stock performance dashboard
STOCK_COLORS = {"A": theme.COLOR_A, "B": theme.COLOR_B}
NEWS_COLUMN_WIDTHS = (1.5, 5.2, 1.5)
SUMMARY_PREVIEW_CHARS = 160
METRIC_HELP = {
    "Latest price": "The latest intraday price, or the most recent close when the US market is closed.",
    "Return over period": "The percentage change from the first to the last price in this range.",
    "Max drawdown": (
        "The biggest fall from a peak to a low in the period. If you had bought "
        "at the top, this is your worst loss on paper."
    ),
    "Sharpe ratio": "Return earned per unit of risk. Higher means the return came with less ups and downs."
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
[data-testid="stMetricValue"] { font-size: 1.6rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #8A704C; }
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
