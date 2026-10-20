# Cloud Computing Stock Comparison

A one-page Streamlit dashboard for SMU students learning to compare stock-price history. Compare two tickers or leave Stock B empty to view one stock. The overview includes price and volatility charts, recession shading, return/risk metrics, plain-language context, and recent Alpaca news when credentials are configured.

Choose a quick time range of 1, 5, 10, or 20 years, or select **Custom** to pick inclusive start and end dates. Custom ranges must be at least two months long, and the earliest selectable start date is 20 years before today.

The dashboard uses Yahoo Finance for historical prices and the Alpaca News API for headlines. Historical prices and news are cached for 30 minutes; the current price is cached for 60 seconds and refreshes while the US market is open (weekdays, 9:30 a.m.–4:00 p.m. Eastern, holidays ignored). When the market is closed, the dashboard shows the most recent closing price. Recession data is cached for one day. A 0% risk-free rate is used for the Sharpe ratio. The page is educational and does not provide investment advice.

## Run in GitHub Codespaces

In the project root, run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

To enable news, create `secrets.env` in the project root with your Alpaca News API credentials:

```env
ALPACA_API_KEY=your-alpaca-api-key
ALPACA_SECRET_KEY=your-alpaca-secret-key
```

Without the credentials, the dashboard still loads prices, charts, and metrics; the news panel explains that news is unavailable. `secrets.env` is ignored by Git. Never commit API keys.

## Run on EC2

On an EC2 instance with Python installed, clone the repository and run the same setup commands from the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0
```

Configure `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in the instance environment or in a protected `secrets.env` file. Allow access to the Streamlit port only from the intended network in the instance security group. The app saves analyses to `analyses-data/` under the project root on the existing disk; it does not require CloudFormation changes or additional storage.

## Verify Save Analysis and Previous Analyses

1. Start the app and click **Run** with one or two valid tickers.
2. Click **Save Analysis** in the sidebar. A success message should appear and a Markdown file should be created in the project-root `analyses-data/` folder.
3. The saved item should appear under **Previous Analyses**. Select it and click **Show** to view it in a pop-up.
4. Restart the app and confirm the file remains listed. The folder is intentionally ignored by Git.

## Project structure

```text
.
├── app.py                  # One-page Streamlit dashboard
├── .streamlit/config.toml  # SMU-inspired Streamlit theme
├── src/
│   ├── input_data.py       # Yahoo Finance, Alpaca news, and cached FRED data
│   ├── transformation.py   # Dashboard calculations and existing data helpers
│   ├── plots.py            # Dashboard charts and existing price/drawdown chart
│   └── storage.py          # Save and retrieve Markdown analyses
├── analyses-data/          # Saved analyses (created automatically; Git-ignored)
├── secrets.env             # Optional Alpaca credentials (you create this; Git-ignored)
└── requirements.txt        # Python dependencies
```

The existing data functions for financial statements, Yahoo Finance news, and analyst ratings remain in `src/input_data.py`; this overview page does not display filings or analyst-rating charts.

## AWS architecture

The dashboard is designed to run in its own VPC on AWS. These documents describe the design:

- [AWS IAM access architecture](documentation/aws-iam-access-architecture.md): IAM Identity Center groups and permission sets. This was designed but not built, because the AWS sandbox does not allow IAM Identity Center or AWS Organizations.
- [AWS VPC architecture](documentation/aws-vpc-architecture.md): two-AZ VPC for the Streamlit web servers and S3 uploads. Built from the CloudFormation template [scripts/stock-research-dashboard-vpc.yaml](scripts/stock-research-dashboard-vpc.yaml).
