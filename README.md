# Cloud Computing Stock Comparison

A Streamlit stock research dashboard, plus the AWS architecture designed to host it. Type up to five tickers (press Enter after each), choose a quick time range (or a custom date range), and click **Run**.

The dashboard supports single-stock and comparison modes, with five metric cards (latest price, return, max drawdown, current drawdown, Sharpe ratio) for one stock or a comparison table for several, recent news with summaries and a ticker filter, price/volatility/drawdown charts, and a calendar-year returns chart. Comparison prices are rebased to $100 at the start of their shared history; chart hover text also shows each stock's actual price. US recession periods are shaded using FRED's USREC series, with known recession dates as a fallback.

The **Company Metrics** tab uses the same tickers. It shows valuation (market cap, trailing and forward P/E, EV/EBITDA, dividend yield) and a financials table: pick a metric to see every fiscal year the companies share, in USD billions at the latest exchange rate, with a trend sparkline and CAGR. Below that are a business-model radar (pick the fiscal year and which companies to draw; an expander explains how each ratio is scored 0-100 and lets you edit the low and high reference values), analyst sentiment (latest buy/hold/sell split or the buy-share trend over recent monthly snapshots), and analyst price-target ranges relative to the current price.

The **Financial Statements** tab shows the annual income statement, balance sheet, and cash flow statement of one company; when several tickers were run, pick the company with the pills at the top. Figures are Yahoo Finance's reported values in the company's reporting currency, in millions (per-share figures to two decimals, share counts in millions), with negatives in brackets. Each statement follows a standard layout (for example revenue, operating expenses, and net income), with bold subtotals and double-underlined totals, and all three tables share the same fiscal-year columns so they line up. Companies report different items, so a row is shown only when the company has it, and every remaining Yahoo row is listed under **Other line items** below each statement. Those extra rows are mostly breakdowns or restatements of figures already in the totals (for example, Accounts Receivable and Other Receivables make up Receivables), so they should not be added to them.

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
   python -m streamlit run src/app.py -- --local
   ```

   - Use `python -m` from the project root: modules import each other as `src.*`, which needs the project root on the import path.
   - `--local` stores accounts and saved documents on this computer (see [Storage](#storage)). Options for the app go after `--`; anything before it is for Streamlit.
   - Without `--local`, the app expects AWS storage (RDS and S3). That is not implemented yet, so the app only shows an error.

## Save and View Analyses

Anyone can run analyses. To save documents, create an account in the sidebar (**Sign up**) or **Log in**. Usernames are 3 to 32 letters, numbers, `-` or `_` (not case-sensitive), and passwords need at least 8 characters. Refreshing the browser logs you out.

After running a single-stock or comparison analysis, choose **Private** or **Public** under **Save as**, then click **Save Analysis** to save a Markdown report. Private documents are visible only to you. Public documents are visible to every user, including visitors who are not logged in. What is saved depends on the open tab:

- **Stock Performance** or **Company Metrics**: price metrics and news, plus valuation, financials, business-model ratios, analyst sentiment with the number of analysts in each bucket, and price targets. Saved as `TICKERS_overview_<time>.md` (or `_single_` for one stock).
- **Financial Statements**: only the company selected in the pills. The report starts with a short explanation of how the figures tally, then each statement's main table followed by its other line items. Saved as `TICKER_statements_<time>.md`.

To add your own notes, open **Upload document**. Pick a Markdown (`.md`) or PDF file of up to 20 MB, and optionally give it a title (defaults to the file name), tickers, and visibility. It is saved as `Title_upload_<time>.md` or `.pdf`.

**Previous Analyses** lists your own documents and everyone's public ones, newest first. The line under the selector shows the tickers, type, time range, creation time, owner, and visibility. Click **Show** to open the document in a pop-up: Markdown is rendered as formatted text, and PDFs open in a viewer. Both have a **Download** button. On your own documents you can also switch between private and public (**Make public** / **Make private**) or **Delete** them.

### How timestamps are shown

- News providers send publication times in ISO 8601 UTC, such as `2026-10-24T07:28:35Z` (`T` separates the date from the time, `Z` means UTC). All timestamps are converted based on your computer's local time.
- **Dashboard news cards** show a relative age such as `9h ago` or `Yesterday`, counted from the current time, so it is the same in any time zone. Articles older than a week show their date.
- **Saved reports** show exact times with the UTC offset, such as `2026-10-24 15:28:35 UTC+08:00`. This applies to the **Created** line and to each news item. A time that cannot be read is saved unchanged.
- **Saved filenames** use UTC with a trailing `Z`, such as `20261024-072835Z`, so they match the `created_at` value stored in the database whatever the server's time zone.

## Storage

Saved documents are split between a **database** and an **object store**. The database holds small, structured data that the app filters and checks, and the object store holds the file contents. The app always looks up the database row, which decides who may see a document, before it reads the file.

| | Database | Object store |
|---|---|---|
| Holds | Users, document metadata, and access rules | Document contents: Markdown reports and uploaded PDFs, later exported chart PDFs |
| Local (`--local`) | SQLite file `local-data/app.db` | Folder `local-data/objects/` |
| AWS (planned) | Amazon RDS PostgreSQL | Private Amazon S3 bucket, reached through the VPC's S3 gateway endpoint |

`local-data/` is ignored by Git. Market data (prices, news, statements) is not stored: it is fetched again and cached in memory by `src/dashboard/loaders.py`. API keys stay in `secrets.env` locally, and in AWS Secrets Manager on AWS.

### Database tables

- **users**: `user_id`, `username` (unique, lower case), `password_hash`, `created_at`. Passwords are never stored. They are hashed with scrypt, using a random salt per user, and stored as `scrypt$n$r$p$salt$hash` so the cost can be raised later.
- **documents**: `document_id`, `owner_id`, `filename`, `object_key`, `title`, `document_type` (`overview`, `single`, `statements` or `upload`), `visibility` (`private` or `public`), `content_type`, `size_bytes`, `sha256`, `start_date`, `end_date`, `range_label`, `created_at`. Indexed by owner and by visibility, each with creation time, which covers the two queries the app runs: "my documents" and "public documents".
- **document_tickers**: one row per ticker a document covers, with its position, so documents can later be filtered by ticker.

The tables are defined with SQLAlchemy Core in `src/storage/database.py` and use only portable SQL, so moving to RDS means changing the database URL, not the queries.

### Password hashing

Passwords are hashed with [scrypt](https://en.wikipedia.org/wiki/Scrypt), using Python's built-in `hashlib.scrypt`, so there is no extra dependency. The code is in `src/storage/auth.py`.

**Why scrypt**

- If the database leaks, the only way to recover a password from its hash is to guess and re-hash. A fast hash such as SHA-256 lets an attacker try billions of guesses per second on a GPU. scrypt is deliberately slow and needs a large block of memory for every guess, so guessing is expensive and cannot be parallelised cheaply on GPUs or custom chips.
- Each password gets its own random 16-byte salt. Two users with the same password get different hashes, and precomputed tables of common-password hashes are useless.
- Verification compares hashes with `hmac.compare_digest`, which takes the same time whether the first byte or the last byte differs.

**Settings**

| Setting | Value | Meaning |
|---|---|---|
| `N` | 2^14 (16384) | CPU and memory cost. Doubling it doubles both. |
| `r` | 8 | Block size. Together with `N` it sets the memory per hash: 128 × `N` × `r` bytes, about 16 MB. |
| `p` | 1 | Number of independent lanes. 1 means no extra work. |
| Salt | 16 bytes | Random per password. |

These are the commonly used values for interactive logins, and one hash takes roughly 50 to 100 ms. `N`, `r`, `p` and the salt are stored with each hash (`scrypt$n$r$p$salt$hash`), and `verify_password` re-hashes with the values stored in that row. Raising the settings later affects only new passwords. Existing users can still log in, and nothing has to be migrated at once. The hash is not re-hashed with the new settings at login yet.

**Multiple users logging in at the same time**

- Streamlit runs each browser session in its own thread. A hash keeps no shared state: it uses only its own arguments, a fresh salt and its own memory, so logins never need a lock and cannot affect each other.
- `hashlib.scrypt` releases Python's global interpreter lock while it computes, so simultaneous logins run in parallel on separate CPU cores. A login waiting on a hash does not block other users from using the app.
- Each hash needs about 16 MB while it runs, and frees it when done (about 0.1 seconds later). Memory use grows only with logins that overlap in time: 10 overlapping logins use about 160 MB at once, and 100 use about 1.6 GB. Sign-ups and logins are short, so on a small dashboard this overlap is rare.
- Raising `N` to 2^15 or more needs a larger `maxmem` argument in `hashlib.scrypt`, because the default limit is 32 MB.
- Logging in with a username that does not exist still hashes a dummy password, so an unknown username and a wrong password take the same time and cannot be told apart.

**Not covered yet:** there is no limit on login attempts. Because every attempt costs about 16 MB and some CPU time, a script sending many attempts at once could slow down or exhaust a small server, and it could also guess passwords. Add a per-username or per-IP rate limit before exposing the app publicly.

### Filenames and object keys

Each file's name and location are built only from its database row, so a row points to exactly one file, and any file path leads back to its row:

```text
filename:   {tickers or title}_{document_type}_{created_at in UTC}.{md|pdf}
object key: users/{owner_id}/{document_id}/{filename}

example:    users/3/42/AAPL-vs-MSFT_overview_20261026-060500Z.md
```

- The `document_id` folder keeps keys unique, even when two documents are saved in the same second.
- Visibility is **not** part of the key. Making a document public or private only updates its row, never moves the file, so the S3 bucket can stay fully private with the app as the only gatekeeper.
- The row and the file are saved in one database transaction that commits only after the file is written, so a failed save leaves neither behind. Deleting removes the row and the file together.
- Object keys are checked so they cannot point outside the storage folder.

### Moving to AWS

The AWS version needs no changes to the dashboard pages:

- An `S3ObjectStore` with the same `put`, `get` and `delete` methods as `LocalObjectStore` in `src/storage/object_store.py`.
- A PostgreSQL URL for RDS, read from Secrets Manager, passed to `Database`.
- The backend choice in `open_store` in `src/app.py`.

## Project structure

```text
.
├── src/
│   ├── app.py                  # Streamlit entry point (run this); --local picks local storage
│   ├── dashboard/              # Streamlit UI
│   │   ├── config.py           # Constants, cache TTLs, storage paths, and page CSS
│   │   ├── loaders.py          # Cached data loaders
│   │   ├── dates.py            # Market hours and date-range resolution
│   │   ├── analysis.py         # Builds the stock analysis result and summary
│   │   ├── auth.py             # Log in, sign up, and log out controls
│   │   ├── sidebar.py          # Analysis form, saving, uploads, and saved documents
│   │   ├── performance.py      # Stock Performance tab
│   │   ├── company_metrics.py  # Company Metrics tab
│   │   └── financial_statements.py  # Financial Statements tab
│   ├── plots/                  # Plotly charts
│   │   ├── theme.py            # Shared palette, fonts, and title helpers
│   │   ├── price_plots.py      # Price, volatility, and recession dashboard
│   │   └── company_plots.py    # Radar, analyst sentiment, and price-target charts
│   ├── data/                   # Market data loading
│   │   ├── price_ratings.py    # Yahoo Finance prices, statements, ratings, and FX rates
│   │   ├── news.py             # Alpaca and Yahoo Finance news; loads secrets.env
│   │   └── recessions.py       # FRED recession periods with a known-date fallback
│   ├── storage/                # Accounts and saved documents
│   │   ├── auth.py             # Password hashing and username/password rules
│   │   ├── database.py         # Users and document metadata tables (SQLAlchemy Core)
│   │   ├── object_store.py     # File contents by object key (local folder; S3 later)
│   │   └── storage.py          # Markdown report builders and the DocumentStore
│   └── analysis/               # Calculations on loaded data
│       ├── transformation.py   # Price metrics, summaries, and relative time
│       ├── fundamentals.py     # Financial statement comparisons and business-model scores
│       ├── statements.py       # Statement layouts and line-item units for the Financial Statements tab
│       └── analyst.py          # Analyst rating periods and buy/hold/sell sentiment
├── notebooks/              # Original exploratory notebooks (filings, news, stock_price_ratings)
├── documentation/          # AWS architecture and database write-ups
├── assets/                 # Architecture diagrams
├── scripts/                # CloudFormation template
├── local-data/             # Local database and saved files (created by --local; git-ignored)
├── secrets.env             # Your API keys (you create this; git-ignored)
└── requirements.txt        # Python dependencies
```

- `src/dashboard/loaders.py` caches price, news, and company lookups for 30 minutes (recession data for a day); ticker and provider problems are shown in the dashboard.
- The notebooks in `notebooks/` are the starting point the functions in `src/` were taken from. Run them with `jupyter notebook` if you want to explore the raw code.

## AWS architecture

The dashboard is designed to run in its own VPC on AWS. These documents describe the design:

- [AWS IAM access architecture](documentation/aws-iam-access-architecture.md): IAM Identity Center groups and permission sets. This was designed but not built, because the AWS sandbox does not allow IAM Identity Center or AWS Organizations.
- [AWS VPC architecture](documentation/aws-vpc-architecture.md): two-AZ VPC for the Streamlit web servers and S3 uploads. Built from the CloudFormation template [scripts/stock-research-dashboard-vpc.yaml](scripts/stock-research-dashboard-vpc.yaml).