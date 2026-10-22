# Cloud Computing Stock Comparison

A Streamlit stock research dashboard, plus the AWS architecture designed to host it. Enter Stock A and optionally Stock B, choose a quick time range, and click **Run**.

The dashboard supports single-stock and comparison modes, with four summary metrics, an "In plain words" summary, recent news, and price/volatility charts. Comparison prices are rebased to $100 at the start of their shared history; chart hover text also shows each stock's actual price. US recession periods are shaded using FRED's USREC series, with known recession dates as a fallback.

The available time ranges are **1 year**, **5 years**, **10 years**, and **20 years** (default). The dashboard uses historical closing prices and does not auto-refresh live prices.

## Setup

1. Create a virtual environment and install the packages.

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

2. **Set up `secrets.env`** (optional, for news).

   The news analysis calls the Alpaca News API, which needs API credentials. Get a free key pair from [Alpaca](https://alpaca.markets/), then create a file named `secrets.env` in the project root (next to `app.py`) containing:

   ```env
   ALPACA_API_KEY=your-alpaca-api-key
   ALPACA_SECRET_KEY=your-alpaca-secret-key
   ```

   - The file is loaded automatically by `src/input_data.py` via `python-dotenv`.
   - `*.env` is listed in `.gitignore`, so it will not be committed. Never commit or share your keys.
   - Without it, stock prices and charts still work; the dashboard will report that news could not be loaded.

3. Run the app.

   ```bash
   streamlit run app.py
   ```

## Save and View Analyses

After running a single-stock or comparison analysis, click **Save Analysis** in the sidebar to save a Markdown report. Saved reports appear under **Previous Analyses**; select one and click **Show** to open it in a pop-up. Reports are stored in `analyses-data/` in the project root, which is ignored by Git.

## Project structure

```text
.
├── app.py                  # Streamlit UI (run this)
├── src/
│   ├── input_data.py       # Data loading: Yahoo Finance and Alpaca; loads secrets.env
│   ├── transformation.py   # Price metrics, summaries, and news formatting
│   └── plots.py            # Plotly price, volatility, and drawdown charts
├── notebooks/              # Original exploratory notebooks (filings, news, stock_price_ratings)
├── documentation/          # AWS architecture write-ups
├── assets/                 # Architecture diagrams
├── scripts/                # CloudFormation template
├── secrets.env             # Your API keys (you create this; git-ignored)
└── requirements.txt        # Python dependencies
```

- `app.py` caches price and news lookups for 30 minutes and shows ticker/provider problems in the dashboard.
- The notebooks in `notebooks/` are the starting point the functions in `src/` were taken from. Run them with `jupyter notebook` if you want to explore the raw code.

## AWS architecture

The dashboard is designed to run in its own VPC on AWS. These documents describe the design:

- [AWS IAM access architecture](documentation/aws-iam-access-architecture.md): IAM Identity Center groups and permission sets. This was designed but not built, because the AWS sandbox does not allow IAM Identity Center or AWS Organizations.
- [AWS VPC architecture](documentation/aws-vpc-architecture.md): two-AZ VPC for the Streamlit web servers and S3 uploads. Built from the CloudFormation template [scripts/stock-research-dashboard-vpc.yaml](scripts/stock-research-dashboard-vpc.yaml).