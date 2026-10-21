# Cloud Computing Stock Comparison

A Streamlit stock research dashboard, plus the AWS architecture designed to host it. Enter a ticker (e.g. `MU`), pick an analysis type and click **Run**.

| Analysis type | What it shows | Source |
|---|---|---|
| filings | Income statement, balance sheet and cash flow | Yahoo Finance (`yfinance`) |
| news | Latest 5 headlines (hyperlinked) with date and summary | Alpaca News API |
| stock price ratings | Current price and the last 10 analyst recommendations | Yahoo Finance (`yfinance`) |
| price | 1-year price chart linked to a drawdown chart, plus max drawdown | Yahoo Finance (`yfinance`) |

## Setup

1. Create a virtual environment and install the packages.

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. **Set up `secrets.env`** (required for the `news` analysis).

   The news analysis calls the Alpaca News API, which needs API credentials. Get a free key pair from [Alpaca](https://alpaca.markets/), then create a file named `secrets.env` in the project root (next to `app.py`) containing:

   ```env
   ALPACA_API_KEY=your-alpaca-api-key
   ALPACA_SECRET_KEY=your-alpaca-secret-key
   ```

   - The file is loaded automatically by `src/input_data.py` via `python-dotenv`.
   - `*.env` is listed in `.gitignore`, so it will not be committed. Never commit or share your keys.
   - Without it, the `news` analysis shows "Alpaca credentials not set"; the other analysis types still work.

3. Run the app.

   ```bash
   streamlit run app.py
   ```

## Save and View Analyses

After running an analysis for a ticker, click **Save Analysis** in the sidebar to save a Markdown report. Saved reports appear under **Previous Analyses**; select one and click **Show** to open it in a pop-up. Reports are stored in `analyses-data/` in the project root, which is ignored by Git.

## Project structure

```text
.
├── app.py                  # Streamlit UI (run this)
├── src/
│   ├── input_data.py       # Data loading: Yahoo Finance and Alpaca; loads secrets.env
│   ├── transformation.py   # compute_drawdown, format_alpaca_news
│   └── plots.py            # Plotly price and drawdown chart
├── notebooks/              # Original exploratory notebooks (filings, news, stock_price_ratings)
├── documentation/          # AWS architecture write-ups
├── assets/                 # Architecture diagrams
├── scripts/                # CloudFormation template
├── secrets.env             # Your API keys (you create this; git-ignored)
└── requirements.txt        # Python dependencies
```

- `app.py` caches each lookup for 30 minutes and shows expected problems (empty ticker, no data) as warnings and anything else as errors.
- The notebooks in `notebooks/` are the starting point the functions in `src/` were taken from. Run them with `jupyter notebook` if you want to explore the raw code.

## AWS architecture

The dashboard is designed to run in its own VPC on AWS. These documents describe the design:

- [AWS IAM access architecture](documentation/aws-iam-access-architecture.md): IAM Identity Center groups and permission sets. This was designed but not built, because the AWS sandbox does not allow IAM Identity Center or AWS Organizations.
- [AWS VPC architecture](documentation/aws-vpc-architecture.md): two-AZ VPC for the Streamlit web servers and S3 uploads. Built from the CloudFormation template [scripts/stock-research-dashboard-vpc.yaml](scripts/stock-research-dashboard-vpc.yaml).