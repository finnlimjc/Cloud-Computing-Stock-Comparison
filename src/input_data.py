import os
import re
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "secrets.env")

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

def get_price_history(ticker:str, period:str="1y") -> pd.Series:
    """Returns daily closing prices indexed by (timezone-naive) date."""
    stock = yf.Ticker(clean_ticker(ticker))
    history = stock.history(period=period)
    if history.empty:
        raise ValueError(f"No price history found for {ticker}.")
    prices = history["Close"]
    prices.index = prices.index.tz_localize(None) #plotly renders tz-aware dates shifted to UTC
    prices.index.name = "Date"
    return prices
