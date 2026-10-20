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
    """Tidy up the user's input, e.g. ' mu ' -> 'MU'. Raises ValueError if empty."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Please enter a ticker symbol.")
    return ticker

def get_financials(ticker:str) -> dict:
    """
    From notebooks/filings.ipynb.
    Returns a dict of DataFrames: income statement, balance sheet, cash flow.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    result = {
        "Income Statement":stock.financials,
        "Balance Sheet":stock.balance_sheet,
        "Cash Flow":stock.cashflow
    }
    if all(df is None or df.empty for df in result.values()):
        raise ValueError(f"No financial statements found for {ticker}.")
    return result

def get_yahoo_news(ticker:str, limit:int=5) -> list:
    """
    From notebooks/news.ipynb.
    Returns a list of dicts with 'title' and 'description'.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    articles = []
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
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_alpaca_news(ticker:str, limit:int=5) -> list:
    """
    Returns the raw Alpaca news articles (original schema) for the ticker.
    Reads credentials from the ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables.
    Source: https://docs.alpaca.markets/us/reference/news-3
    """
    ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise ValueError("Alpaca credentials not set. Define ALPACA_API_KEY and ALPACA_SECRET_KEY.")
    
    headers = {
        "APCA-API-KEY-ID":api_key,
        "APCA-API-SECRET-KEY":secret_key
    }
    
    params = {
        "symbols":clean_ticker(ticker),
        "limit":limit,
        "sort":"desc"
    }
    
    response = requests.get(ALPACA_NEWS_URL, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    
    articles = response.json().get("news", [])
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_price(ticker:str) -> float:
    """
    From notebooks/stock_price_ratings.ipynb. Returns the current price.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    price = stock.info.get("currentPrice")
    if price is None:
        raise ValueError(f"No current price found for {ticker}.")
    return price

def get_latest_price(ticker:str, market_open:bool) -> float:
    """Fetch the latest intraday price while open, or most recent close while shut."""
    stock = yf.Ticker(clean_ticker(ticker))
    if market_open:
        history = stock.history(period="1d", interval="1m", prepost=False)
    else:
        history = stock.history(period="5d", interval="1d", prepost=False)
    if history.empty or "Close" not in history:
        raise ValueError(f"No latest price found for {ticker}.")
    price = history["Close"].dropna()
    if price.empty:
        raise ValueError(f"No latest price found for {ticker}.")
    return float(price.iloc[-1])

def get_analyst_ratings(ticker:str) -> pd.DataFrame:
    """
    From notebooks/stock_price_ratings.ipynb. Returns a DataFrame of recommendations.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    recs = stock.recommendations
    if recs is None or len(recs) == 0:
        raise ValueError(f"No analyst recommendations found for {ticker}.")
    ratings = recs.tail(10)
    return ratings

def get_price_history(ticker:str, start_date:date, end_date:date) -> pd.Series:
    """Returns daily closing prices for the inclusive date range."""
    stock = yf.Ticker(clean_ticker(ticker))
    history = stock.history(start=start_date, end=end_date + timedelta(days=1))
    if history.empty:
        raise ValueError(f"No price history found for {ticker}.")
    prices = history["Close"]
    prices.index = prices.index.tz_localize(None) #plotly renders tz-aware dates shifted to UTC
    prices.index.name = "Date"
    prices = prices.loc[
        (prices.index >= pd.Timestamp(start_date))
        & (prices.index <= pd.Timestamp(end_date))
    ]
    if prices.empty:
        raise ValueError(f"No price history found for {ticker} in the selected date range.")
    return prices


@st.cache_data(ttl=86400, show_spinner=False)
def get_recession_periods() -> list[dict]:
    """Load monthly US recession periods from FRED, with NBER dates as a fallback."""
    fallback = [
        {"start": pd.Timestamp("2007-12-01"), "end": pd.Timestamp("2009-06-30"), "label": "2008 Financial Crisis"},
        {"start": pd.Timestamp("2020-02-01"), "end": pd.Timestamp("2020-04-30"), "label": "COVID-19"},
    ]
    try:
        response = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=USREC",
            timeout=10,
        )
        response.raise_for_status()
        frame = pd.read_csv(StringIO(response.text))
        date_column, value_column = frame.columns[:2]
        frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
        frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
        periods = transformation.recession_periods_from_series(
            pd.Series(frame[value_column].values, index=frame[date_column])
        )
        return periods or fallback
    except Exception as error:
        LOGGER.warning("Could not load FRED recession data; using NBER dates: %s", error)
        return fallback
