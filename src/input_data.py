from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import yfinance as yf
from dotenv import load_dotenv
from src import transformation

load_dotenv(Path(__file__).resolve().parent.parent / "secrets.env")
LOGGER = logging.getLogger(__name__)

def clean_ticker(ticker:str) -> str:
    """Normalize a ticker symbol.

    Inputs:
    - ticker: user-entered stock symbol

    Outputs:
    - Uppercase ticker symbol
    """
    # This part trims whitespace and normalizes the ticker case.
    ticker = (ticker or "").strip().upper()
    # This part rejects empty ticker input.
    if not ticker:
        raise ValueError("Please enter a ticker symbol.")
    return ticker

def get_financials(ticker:str) -> dict:
    """Load the income statement, balance sheet, and cash flow statement.

    Inputs:
    - ticker: stock symbol

    Outputs:
    - Financial statements keyed by statement name
    """
    # This part retrieves the three financial statements from Yahoo Finance.
    stock = yf.Ticker(clean_ticker(ticker))
    result = {
        "Income Statement":stock.financials,
        "Balance Sheet":stock.balance_sheet,
        "Cash Flow":stock.cashflow
    }
    # This part rejects tickers with no available statements.
    if all(df is None or df.empty for df in result.values()):
        raise ValueError(f"No financial statements found for {ticker}.")
    return result

def get_yahoo_news(ticker:str, limit:int=5) -> list:
    """Load and clean recent Yahoo Finance news.

    Inputs:
    - ticker: stock symbol
    - limit: maximum number of articles

    Outputs:
    - Articles with title and description fields
    """
    # This part retrieves the ticker's recent articles.
    stock = yf.Ticker(clean_ticker(ticker))
    articles = []
    # This part extracts and cleans each article's display text.
    for article in (stock.news or [])[:limit]:
        content = article.get("content", {})
        description = content.get("description") or content.get("summary") or ""
        # Yahoo sometimes returns HTML tags in the description; strip them.
        description = re.sub(r"<[^>]+>", "", description)
        articles.append(
            {
                "title":content.get("title", "No title"),
                "description":description[:200] or "No description"
            }
        )
    # This part reports when no news is available.
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_alpaca_news(ticker:str, limit:int=5) -> list:
    """Load recent Alpaca news articles for a ticker.

    Inputs:
    - ticker: stock symbol
    - limit: maximum number of articles

    Outputs:
    - Raw Alpaca news articles
    """
    # This part reads and validates the Alpaca credentials.
    ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise ValueError("Alpaca credentials not set. Define ALPACA_API_KEY and ALPACA_SECRET_KEY.")
    
    # This part prepares the authenticated request.
    headers = {
        "APCA-API-KEY-ID":api_key,
        "APCA-API-SECRET-KEY":secret_key
    }
    
    # This part adds the ticker and article limit to the request.
    params = {
        "symbols":clean_ticker(ticker),
        "limit":limit,
        "sort":"desc"
    }
    
    # This part sends the request and validates the response status.
    response = requests.get(ALPACA_NEWS_URL, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    
    # This part extracts articles and rejects an empty result.
    articles = response.json().get("news", [])
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_price(ticker:str) -> float:
    """Load the current price reported by Yahoo Finance.

    Inputs:
    - ticker: stock symbol

    Outputs:
    - Current price
    """
    # This part retrieves the current price field.
    stock = yf.Ticker(clean_ticker(ticker))
    price = stock.info.get("currentPrice")
    # This part reports when Yahoo Finance has no current price.
    if price is None:
        raise ValueError(f"No current price found for {ticker}.")
    return price

def get_latest_price(ticker:str, market_open:bool) -> float:
    """Fetch the latest intraday price or most recent close.

    Inputs:
    - ticker: stock symbol
    - market_open: whether regular US trading is open

    Outputs:
    - Latest available price
    """
    # This part selects intraday or daily history based on market hours.
    stock = yf.Ticker(clean_ticker(ticker))
    if market_open:
        history = stock.history(period="1d", interval="1m", prepost=False)
    else:
        history = stock.history(period="5d", interval="1d", prepost=False)
    # This part validates the returned closing-price series.
    if history.empty or "Close" not in history:
        raise ValueError(f"No latest price found for {ticker}.")
    price = history["Close"].dropna()
    if price.empty:
        raise ValueError(f"No latest price found for {ticker}.")
    return float(price.iloc[-1])

def get_analyst_ratings(ticker:str) -> pd.DataFrame:
    """Load the ten most recent analyst recommendations.

    Inputs:
    - ticker: stock symbol

    Outputs:
    - Recent analyst recommendations
    """
    # This part retrieves and validates the recommendation history.
    stock = yf.Ticker(clean_ticker(ticker))
    recs = stock.recommendations
    if recs is None or len(recs) == 0:
        raise ValueError(f"No analyst recommendations found for {ticker}.")
    # This part returns only the latest ten recommendations.
    ratings = recs.tail(10)
    return ratings

def get_price_history(ticker:str, start_date:date, end_date:date) -> pd.Series:
    """Load daily closing prices for an inclusive date range.

    Inputs:
    - ticker: stock symbol
    - start_date: inclusive first date
    - end_date: inclusive last date

    Outputs:
    - Daily closing prices indexed by date
    """
    # This part includes the requested end date in Yahoo Finance's exclusive range.
    stock = yf.Ticker(clean_ticker(ticker))
    history = stock.history(start=start_date, end=end_date + timedelta(days=1))
    # This part validates the downloaded history and selects closing prices.
    if history.empty:
        raise ValueError(f"No price history found for {ticker}.")
    prices = history["Close"]
    # This part removes timezone data because Plotly otherwise shifts dates to UTC.
    prices.index = prices.index.tz_localize(None)
    prices.index.name = "Date"
    # This part trims any observations outside the inclusive date range.
    prices = prices.loc[
        (prices.index >= pd.Timestamp(start_date))
        & (prices.index <= pd.Timestamp(end_date))
    ]
    # This part reports when no prices remain in the selected date range.
    if prices.empty:
        raise ValueError(f"No price history found for {ticker} in the selected date range.")
    return prices


def recession_fallback_periods() -> list[dict]:
    """Return the fixed recession dates used when FRED is unavailable.

    Inputs:
    - None

    Outputs:
    - Known recession periods with inclusive dates
    """
    # This part returns the documented fallback periods.
    return [
        {"start": pd.Timestamp("2007-12-01"), "end": pd.Timestamp("2009-06-30"), "label": "2008 Financial Crisis"},
        {"start": pd.Timestamp("2020-02-01"), "end": pd.Timestamp("2020-04-30"), "label": "COVID-19"},
    ]


def parse_recession_periods(response_text:str) -> list[dict]:
    """Convert FRED CSV text into monthly recession ranges.

    Inputs:
    - response_text: downloaded FRED CSV content

    Outputs:
    - Recession periods with inclusive start and end dates
    """
    # This part parses and normalizes the monthly recession observations.
    frame = pd.read_csv(StringIO(response_text))
    date_column, value_column = frame.columns[:2]
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    # This part converts the observations to inclusive date ranges.
    return transformation.recession_periods_from_series(
        pd.Series(frame[value_column].values, index=frame[date_column])
    )


@st.cache_data(ttl=86400, show_spinner=False)
def get_recession_periods() -> list[dict]:
    """Load monthly US recession periods from FRED, with NBER dates as a fallback.

    Inputs:
    - None

    Outputs:
    - Recession periods with inclusive start and end dates
    """
    try:
        # This part downloads and parses the monthly FRED recession series.
        response = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=USREC",
            timeout=10,
        )
        response.raise_for_status()
        # This part converts the monthly series into labeled date ranges.
        periods = parse_recession_periods(response.text)
        return periods or recession_fallback_periods()
    except Exception as error:
        # This part logs the failure and returns the known fallback periods.
        LOGGER.warning("Could not load FRED recession data; using NBER dates: %s", error)
        return recession_fallback_periods()
