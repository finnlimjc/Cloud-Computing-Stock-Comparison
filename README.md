# Cloud Computing Stock Comparison

A Streamlit stock research dashboard, plus the AWS architecture designed to host it. Type up to five tickers (press Enter after each), choose a quick time range (or a custom date range), and click **Run**.

The dashboard supports single-stock and comparison modes, with five metric cards (latest price, return, max drawdown, current drawdown, Sharpe ratio) for one stock or a comparison table for several, recent news with summaries and a ticker filter, price/volatility/drawdown charts, and a calendar-year returns chart. Comparison prices are rebased to $100 at the start of their shared history; chart hover text also shows each stock's actual price. US recession periods are shaded using FRED's USREC series, with known recession dates as a fallback.

The **Company Metrics** tab uses the same tickers. It shows valuation (market cap, trailing and forward P/E, EV/EBITDA, dividend yield) and a financials table: pick a metric to see every fiscal year the companies share, in USD billions at the latest exchange rate, with a trend sparkline and CAGR. Below that are a business-model radar (pick the fiscal year and which companies to draw; an expander explains how each ratio is scored 0-100 and lets you edit the low and high reference values), analyst sentiment (latest buy/hold/sell split or the buy-share trend over recent monthly snapshots), and analyst price-target ranges relative to the current price.

The available time ranges are **1 year**, **5 years**, **10 years**, **20 years** (default), and **Custom** (any start and end date within the last 20 years, at least 60 days apart). Charts and metrics use daily closing prices; the **Latest price** card refreshes every 60 seconds while the US market is open.

## Setup

1. Create a virtual environment and install the packages.

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

2. **Set up `secrets.env`** (optional, for news).

   The news analysis calls the Alpaca News API, which needs API credentials. Get a free key pair from [Alpaca](https://alpaca.markets/), then create a file named `secrets.env` in the project root (next to `src/`) containing:

   ```env
   ALPACA_API_KEY=your-alpaca-api-key
   ALPACA_SECRET_KEY=your-alpaca-secret-key
   ```

   - The file is loaded automatically by `src/data/news.py` via `python-dotenv`.
   - `*.env` is listed in `.gitignore`, so it will not be committed. Never commit or share your keys.
   - Without it, news falls back to Yahoo Finance; stock prices and charts work either way.

3. Run the app from the project root.

   ```bash
   python -m streamlit run src/app.py
   ```

   Use `python -m` from the project root: modules import each other as `src.*`, which needs the project root on the import path.

## Save and View Analyses

After running a single-stock or comparison analysis, click **Save Analysis** in the sidebar to save a Markdown report. The report covers both tabs: price metrics and news, plus valuation, financials, business-model ratios, analyst sentiment with the number of analysts in each bucket, and price targets. Saved reports appear under **Previous Analyses**; select one and click **Show** to open it in a pop-up. Reports are stored in `analyses-data/` in the project root, which is ignored by Git.

### How timestamps are shown

- News providers send publication times in ISO 8601 UTC, such as `2026-10-24T07:28:35Z` (`T` separates the date from the time, `Z` means UTC). All timestamps are converted based on your computer's local time.
- **Dashboard news cards** show a relative age such as `9h ago` or `Yesterday`, counted from the current time, so it is the same in any time zone. Articles older than a week show their date.
- **Saved reports** show exact times with the UTC offset, such as `2026-10-24 15:28:35 UTC+08:00`. This applies to the **Created** line and to each news item. A time that cannot be read is saved unchanged.

## Project structure

```text
.
├── src/
│   ├── app.py                  # Streamlit entry point (run this)
│   ├── dashboard/              # Streamlit UI
│   │   ├── config.py           # Constants, cache TTLs, and page CSS
│   │   ├── loaders.py          # Cached data loaders
│   │   ├── dates.py            # Market hours and date-range resolution
│   │   ├── analysis.py         # Builds the stock analysis result and summary
│   │   ├── sidebar.py          # Analysis form and saved analyses
│   │   ├── performance.py      # Stock Performance tab
│   │   └── company_metrics.py  # Company Metrics tab
│   ├── plots/                  # Plotly charts
│   │   ├── theme.py            # Shared palette, fonts, and title helpers
│   │   ├── price_plots.py      # Price, volatility, and recession dashboard
│   │   └── company_plots.py    # Radar, analyst sentiment, and price-target charts
│   ├── data/                   # Loading and saving
│   │   ├── price_ratings.py    # Yahoo Finance prices, statements, ratings, and FX rates
│   │   ├── news.py             # Alpaca and Yahoo Finance news; loads secrets.env
│   │   ├── recessions.py       # FRED recession periods with a known-date fallback
│   │   └── storage.py          # Saved Markdown analyses
│   └── analysis/               # Calculations on loaded data
│       ├── transformation.py   # Price metrics, summaries, and relative time
│       ├── fundamentals.py     # Financial statement comparisons and business-model scores
│       └── analyst.py          # Analyst rating periods and buy/hold/sell sentiment
├── notebooks/              # Original exploratory notebooks (filings, news, stock_price_ratings)
├── documentation/          # AWS architecture write-ups
├── assets/                 # Architecture diagrams
├── scripts/                # CloudFormation template
├── secrets.env             # Your API keys (you create this; git-ignored)
└── requirements.txt        # Python dependencies
```

- `src/dashboard/loaders.py` caches price, news, and company lookups for 30 minutes (recession data for a day); ticker and provider problems are shown in the dashboard.
- The notebooks in `notebooks/` are the starting point the functions in `src/` were taken from. Run them with `jupyter notebook` if you want to explore the raw code.

## AWS architecture

The dashboard is designed to run in its own VPC on AWS. These documents describe the design:

- [AWS IAM access architecture](documentation/aws-iam-access-architecture.md): IAM Identity Center groups and permission sets. This was designed but not built, because the AWS sandbox does not allow IAM Identity Center or AWS Organizations.
- [AWS VPC architecture](documentation/aws-vpc-architecture.md): two-AZ VPC for the Streamlit web servers and S3 uploads. Built from the CloudFormation template [scripts/stock-research-dashboard-vpc.yaml](scripts/stock-research-dashboard-vpc.yaml).