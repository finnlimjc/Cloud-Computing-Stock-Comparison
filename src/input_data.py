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

def get_price_history(
    ticker:str,
    start_date:date | str | None=None,
    end_date:date | None=None,
    period:str="1y",
) -> pd.Series:
    """Load daily closing prices indexed by timezone-naive date.

    Inputs:
    - ticker: stock symbol
    - start_date: inclusive first date, or a legacy period string
    - end_date: inclusive last date
    - period: Yahoo Finance period used by legacy calls without dates

    Outputs:
    - Daily closing prices indexed by date
    """
    # This part preserves the legacy positional period argument.
    if isinstance(start_date, str):
        period = start_date
        start_date = None
    if (start_date is None) != (end_date is None):
        raise ValueError("Both start_date and end_date must be provided.")
    # This part requests either the selected date range or the legacy period.
    stock = yf.Ticker(clean_ticker(ticker))
    if start_date is None:
        history = stock.history(period=period)
    else:
        history = stock.history(
            start=start_date,
            end=end_date + timedelta(days=1),
        )
    if history.empty:
        raise ValueError(f"No price history found for {ticker}.")
    prices = history["Close"]
    # This part removes timezone data and applies inclusive date bounds.
    prices.index = prices.index.tz_localize(None)
    prices.index.name = "Date"
    if start_date is not None:
        prices = prices.loc[
            (prices.index >= pd.Timestamp(start_date))
            & (prices.index <= pd.Timestamp(end_date))
        ]
        if prices.empty:
            raise ValueError(
                f"No price history found for {ticker} in the selected date range."
            )
    return prices


def recession_fallback_periods() -> list[dict]:
    """Return known US recession dates used when FRED is unavailable.

    Inputs:
    - None

    Outputs:
    - Known recession periods with inclusive dates
    """
    # This part returns the documented fallback periods.
    return [
        {
            "start": pd.Timestamp("2007-12-01"),
            "end": pd.Timestamp("2009-06-30"),
            "label": "2008 Financial Crisis",
        },
        {
            "start": pd.Timestamp("2020-02-01"),
            "end": pd.Timestamp("2020-04-30"),
            "label": "COVID-19",
        },
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
    """Load monthly US recession periods from FRED with a known-date fallback.

    Inputs:
    - None

    Outputs:
    - Recession periods with inclusive dates
    """
    try:
        # This part downloads and parses the FRED USREC series.
        response = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv?id=USREC",
            timeout=10,
        )
        response.raise_for_status()
        periods = parse_recession_periods(response.text)
        return periods or recession_fallback_periods()
    except (
        requests.RequestException,
        pd.errors.ParserError,
        ValueError,
        IndexError,
        KeyError,
    ) as error:
        # This part logs FRED failures and uses the documented fallback dates.
        LOGGER.warning("Could not load FRED recession data; using fallback dates: %s", error)
        return recession_fallback_periods()
