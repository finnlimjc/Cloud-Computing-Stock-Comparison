import re
from datetime import date
from string import ascii_uppercase

import pandas as pd
import requests
from yfinance.exceptions import YFException

from src.analysis import transformation
from src.dashboard.config import MAX_STOCKS
from src.dashboard.loaders import load_news, load_prices
from src.data import price_ratings

def parse_tickers(text:str) -> tuple[list[str], list[str]]:
    """Split comma- or space-separated symbols into unique upper-case tickers, capped at MAX_STOCKS.
    
    Inputs:
    - text: user-entered ticker symbols
    
    Outputs:
    - Tickers in entry order and warnings about dropped entries
    """
    tickers = list(dict.fromkeys(re.split(r"[,\s]+", text.upper().strip())))
    tickers = [ticker for ticker in tickers if ticker]
    warnings = []
    if not tickers:
        warnings.append("Please enter a ticker symbol.")
    if len(tickers) > MAX_STOCKS:
        warnings.append(f"Only the first {MAX_STOCKS} tickers are used; ignored {', '.join(tickers[MAX_STOCKS:])}.")
    return tickers[:MAX_STOCKS], warnings

def analyze_ticker(role:str, ticker_input:str, start_date:date, end_date:date) -> tuple[dict | None, str | None]:
    """Load and summarize one stock's price history.
    
    Inputs:
    - role: letter for the stock's slot in the comparison ("A" for the first ticker, "B" for the second, ...), used to look up its color
    - ticker_input: user-entered symbol
    - start_date: inclusive first date
    - end_date: inclusive last date
    
    Outputs:
    - Stock analysis and optional warning
    """
    label = ticker_input.strip().upper()
    try:
        ticker = price_ratings.clean_ticker(ticker_input)
        prices = load_prices(ticker, start_date, end_date).dropna()
        if prices.empty:
            raise ValueError("No price history found.")
        stock = {
            "role": role,
            "ticker": ticker,
            "prices": prices,
            "metrics": transformation.summarize_prices(prices)
        }
        return stock, None
    except (ValueError, KeyError) as error:
        return None, f"{label}: {error}"
    except (YFException, requests.RequestException, OSError) as error:
        return None, f"{label}: data could not be loaded ({error})"

def news_timestamp(article:dict) -> int:
    """Return an article's UTC timestamp as a sort key, or zero when invalid."""
    timestamp = pd.to_datetime(article["created_at"], utc=True, errors="coerce")
    sort_key = int(timestamp.value) if not pd.isna(timestamp) else 0
    return sort_key

def collect_news(stocks:dict) -> tuple[list[dict], str]:
    """Collect recent articles for the loaded stocks, newest first, with a combined error message."""
    articles = []
    errors = []
    for stock in stocks.values():
        try:
            for article in load_news(stock["ticker"]):
                articles.append(
                    {
                        "role": stock["role"],
                        "ticker": stock["ticker"],
                        "created_at": article.get("created_at", ""),
                        "headline": article.get("headline", "No headline"),
                        "url": article.get("url", ""),
                        "summary": article.get("summary") or ""
                    }
                )
        except (requests.RequestException, OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"{stock['ticker']}: {error}")
    articles.sort(key=news_timestamp, reverse=True)
    error_message = "; ".join(errors)
    return articles, error_message

def load_analysis(tickers:list[str], start_date:date, end_date:date, range_label:str) -> tuple[dict, list[str]]:
    """Load available stock analyses and their news.
    
    Each ticker is assigned a role by entry position: "A" for the first, "B" for the second, and so on.
    Roles key the result's stocks and their colors, so a ticker that fails to load is skipped
    without changing the roles of the others.
    
    Inputs:
    - tickers: unique user-entered symbols, at most MAX_STOCKS
    - start_date: inclusive first date
    - end_date: inclusive last date
    - range_label: selected quick-range option
    
    Outputs:
    - Analysis result and ticker warnings
    """
    # Analyze each ticker where ascii_uppercase is the role "A", "B"
    stocks = {}
    warnings = []
    for role, ticker_input in zip(ascii_uppercase, tickers):
        stock, warning = analyze_ticker(role, ticker_input, start_date, end_date)
        if stock:
            stocks[role] = stock
        if warning:
            warnings.append(warning)
    if not stocks:
        return {}, warnings
    
    # Align a comparison on shared history
    if len(stocks) > 1:
        aligned = transformation.common_start_prices({role: stock["prices"] for role, stock in stocks.items()})
        if any(prices.empty for prices in aligned.values()):
            warnings.append("The selected stocks have no overlapping price history; showing the first stock only.")
            first_role = next(iter(stocks))
            stocks = {first_role: stocks[first_role]}
        else:
            for role, stock in stocks.items():
                stock["prices"] = aligned[role]
                stock["metrics"] = transformation.summarize_prices(stock["prices"])
    
    # Recorded after alignment so the end-of-range close matches the trimmed series
    for stock in stocks.values():
        stock["price_at_end_range"] = float(stock["prices"].iloc[-1])
        stock["price_at_end_date"] = stock["prices"].index[-1].date()
    
    # Assemble the result
    articles, news_error = collect_news(stocks)
    result = {
        "stocks": stocks,
        "start_date": start_date,
        "end_date": end_date,
        "range_label": range_label,
        "comparison": len(stocks) > 1,
        "news": articles,
        "news_error": news_error,
        "n_requested": len(tickers)
    }
    return result, warnings

def plain_words(result:dict) -> str:
    """Create a plain-language comparison or single-stock summary of the loaded data."""
    stocks = result["stocks"]
    range_label = result["range_label"]
    if range_label == "Custom":
        range_label = f"{result['start_date']:%Y-%m-%d} to {result['end_date']:%Y-%m-%d}"
    if not result["comparison"]:
        stock = next(iter(stocks.values()))
        summary = transformation.plain_words_single(stock["ticker"], stock["prices"], range_label)
        return summary
    
    ordered = list(stocks.values())
    tickers = [stock["ticker"] for stock in ordered]
    returns = {stock["ticker"]: stock["metrics"]["Return over period"] for stock in ordered}
    volatilities = {stock["ticker"]: stock["metrics"]["Average volatility"] for stock in ordered}
    drawdowns = {stock["ticker"]: stock["metrics"]["Max drawdown"] for stock in ordered}
    summary = transformation.plain_words_comparison(tickers, returns, volatilities, drawdowns, range_label)
    return summary
