"""
Analysis logic, adapted from the notebooks in notebooks/.
Every function RETURNS data (instead of printing) so the Streamlit UI can display it.
"""

import re
import yfinance as yf

def clean_ticker(ticker):
    """Tidy up the user's input, e.g. ' mu ' -> 'MU'. Raises ValueError if empty."""
    ticker = (ticker or "").strip().upper()
    if not ticker:
        raise ValueError("Please enter a ticker symbol.")
    return ticker

def get_financials(ticker):
    """
    From notebooks/filings.ipynb.
    Returns a dict of DataFrames: income statement, balance sheet, cash flow.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    result = {
        "Income Statement": stock.financials,
        "Balance Sheet": stock.balance_sheet,
        "Cash Flow": stock.cashflow,
    }
    if all(df is None or df.empty for df in result.values()):
        raise ValueError(f"No financial statements found for {ticker}.")
    return result

def get_news(ticker, limit=5):
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
                "title": content.get("title", "No title"),
                "description": description[:200] or "No description",
            }
        )
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_price(ticker):
    """
    From notebooks/stock_price_ratings.ipynb. Returns the current price.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    price = stock.info.get("currentPrice")
    if price is None:
        raise ValueError(f"No current price found for {ticker}.")
    return price

def get_analyst_ratings(ticker):
    """
    From notebooks/stock_price_ratings.ipynb. Returns a DataFrame of recommendations.
    """
    stock = yf.Ticker(clean_ticker(ticker))
    recs = stock.recommendations
    if recs is None or len(recs) == 0:
        raise ValueError(f"No analyst recommendations found for {ticker}.")
    return recs.tail(10)
