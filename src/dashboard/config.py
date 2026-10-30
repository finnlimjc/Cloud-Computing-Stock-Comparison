from pathlib import Path
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
    "color:#3f4a5c;font-size:0.85rem;display:-webkit-box;-webkit-line-clamp:2;"
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
VALUATION_HELP = {
    "Market cap": "Share price times shares outstanding: what the market values the whole company at, in its listing currency.",
    "Trailing P/E": "Share price divided by the last 12 months of earnings per share. Higher means investors pay more for each dollar of profit.",
    "Forward P/E": "Share price divided by analysts' expected earnings per share for the next 12 months.",
    "EV/EBITDA": "Enterprise value (market cap plus debt minus cash) divided by operating earnings before depreciation. Useful for comparing companies with different debt levels.",
    "Dividend yield": "Yearly dividends as a percentage of the share price."
}

# Storage Settings
MAX_UPLOAD_MB = 20
VISIBILITY_OPTIONS = ["Private", "Public"]
OWNER_FILTERS = {"Anyone": "all", "Me": "mine", "Others": "others"}
UPLOAD_TYPES = {"pdf": "application/pdf", "md": "text/markdown"}
PDF_HEIGHT = 700

# Local Storage
LOCAL_DATA_DIR = Path(__file__).resolve().parents[2] / "local-data"
LOCAL_DB_PATH = LOCAL_DATA_DIR / "app.db"
LOCAL_OBJECTS_DIR = LOCAL_DATA_DIR / "objects"
SEED_CREDENTIALS_PATH = LOCAL_DATA_DIR / "seed-credentials.txt"

# Pages
PAGE_KEY = "active_page"
PAGE_NAMES = ["Stock Performance", "Company Metrics", "Financial Statements"]
STATEMENTS_PAGE = "Financial Statements"

# Financial statements
STATEMENT_UNITS_NOTE = (
    "{currency} millions, except per-share figures; share counts in millions. "
    "Signs follow Yahoo Finance, with negatives in brackets."
)
STATEMENT_OTHER_NOTE = "Mostly breakdowns or restatements of figures already in the totals above; listed for reference, not to be added to them."
STATEMENT_TALLY_NOTES = [
    ("Every figure is the value Yahoo Finance reports. Nothing is calculated or summed here.", []),
    ("Bold totals and subtotals are Yahoo's own totals, not sums of the rows above them", []),
    (
        "Each statement's other line items are the remaining rows Yahoo provides. Adding them to the totals would count them twice. They are usually one of:",
        [
            "Breakdowns of a line shown: Accounts Receivable and Other Receivables make up Receivables; Gross PPE less Accumulated Depreciation gives Property, plant & equipment.",
            "The same figure at another step: Net Income Continuous Operations and Net Income Common Stockholders often equal Net income.",
            "Alternative measures built from the same figures: Normalized Income, Total Unusual Items, Invested Capital, Tangible Book Value."
        ]
    ),
    ("A dash means Yahoo has no figure for that year. Every table shows the fiscal years of all three statements, so a year can be empty in one of them.", [])
]

# Page styling
PAGE_CSS = """
<style>
.stApp { background: #F5F6FA; }
div[data-testid="stMetric"] { padding: 0.15rem 0; }
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #1F2A44; }
[data-testid="stMetricLabel"] { color: #4b5563; font-size: 0.8rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #8A704C; background: #FFFFFF; }
.st-key-news_card, .st-key-chart_card, .st-key-financials_card, .st-key-radar_card, .st-key-analyst_card, .st-key-targets_card { background: #FFFFFF; border-radius: 0.75rem; }
.st-key-analyst_toggle_box { align-items: flex-end; }
.st-key-analyst_toggle_box [data-testid="stButtonGroup"] { justify-content: flex-end; }
.st-key-news_filter_box { align-items: flex-end; }
.st-key-news_filter_box [data-testid="stButtonGroup"] { justify-content: flex-end; }
[data-testid="stSidebar"] { background: #FFFFFF; }
[data-testid="stCaptionContainer"] { color: #4b5563 !important; opacity: 1 !important; } /* Streamlit fades captions with opacity, not color */
section[data-testid="stSidebar"] { width: 320px !important; }
[class*="st-key-statement_card"] { background: #FFFFFF; border-radius: 0.75rem; }
/* Financial statement tables: fixed layout so every statement shares the same column widths */
.fs-scroll { overflow-x: auto; }
.stApp table.fs-table { width: 100%; min-width: 640px; table-layout: fixed; border-collapse: collapse; margin: 0; font-size: 0.9rem; color: #1F2A44; font-variant-numeric: tabular-nums; }
.stApp .fs-table th, .stApp .fs-table td { padding: 0.4rem 0.75rem; border: none; background: transparent; text-align: right; overflow-wrap: anywhere; line-height: 1.35; }
.stApp .fs-table th:first-child, .stApp .fs-table td:first-child { text-align: left; }
.stApp .fs-table thead th { background: #1F2A44; color: #FFFFFF; font-weight: 600; vertical-align: bottom; }
.stApp .fs-table thead th:first-child { border-top-left-radius: 0.4rem; color: #CBD5E1; font-weight: 500; font-size: 0.8rem; }
.stApp .fs-table thead th:last-child { border-top-right-radius: 0.4rem; }
.fs-table .fs-date { display: block; color: #CBD5E1; font-size: 0.72rem; font-weight: 400; }
.stApp .fs-table .fs-section td { padding-top: 0.9rem; color: #8A704C; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; border-bottom: 1px solid #E5E7EB; }
.stApp .fs-table .fs-item td { border-bottom: 1px solid #F0F1F5; }
.stApp .fs-table .fs-item td:first-child { padding-left: 1.75rem; color: #374151; }
.stApp .fs-table .fs-subtotal td { font-weight: 600; border-top: 1px solid #9CA3AF; }
.stApp .fs-table .fs-total td { font-weight: 700; border-top: 1px solid #1F2A44; border-bottom: 3px double #1F2A44; }
.stApp .fs-table tbody tr:not(.fs-section):hover td { background: #FBF7F0; }
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
