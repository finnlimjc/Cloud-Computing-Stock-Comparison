import logging
import os
import re
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

from src.data.price_ratings import clean_ticker

# Setup
load_dotenv(Path(__file__).resolve().parents[2] / "secrets.env")
LOGGER = logging.getLogger(__name__)

# Alpaca API
# Source: https://docs.alpaca.markets/us/reference/news-3
ALPACA_NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
REQUEST_TIMEOUT_SECONDS = 10

# Yahoo article parsing
SUMMARY_MAX_CHARS = 200
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

class YahooArticle:
    def __init__(self, article:dict) -> None:
        self.article = article
        self.content = article.get("content") or {}
    
    @property
    def title(self) -> str:
        """Article title, or a placeholder when missing."""
        title = self.article.get("title") or self.content.get("title") or "No title"
        return title
    
    @property
    def description(self) -> str:
        """Article description or summary with HTML tags removed."""
        raw = (
            self.article.get("description")
            or self.article.get("summary")
            or self.content.get("description")
            or self.content.get("summary")
            or ""
        )
        description = HTML_TAG_PATTERN.sub("", raw)
        return description
    
    @property
    def url(self) -> str:
        """Article link, or an empty string when none is a valid URL string."""
        link = (
            self.article.get("link")
            or self.content.get("canonicalUrl")
            or self.content.get("clickThroughUrl")
            or {}
        )
        url = link.get("url", "") if isinstance(link, dict) else link
        url = url if isinstance(url, str) else ""
        return url
    
    @property
    def created_at(self) -> str:
        """Publication timestamp as a string, or an empty string when missing."""
        created_at = self.article.get("pubDate") or self.content.get("pubDate") or self.content.get("displayTime")
        publish_time = self.article.get("providerPublishTime")
        if not created_at and publish_time:
            created_at = pd.to_datetime(publish_time, unit="s", utc=True).isoformat()
        created_at = created_at or ""
        return created_at
    
    def to_dict(self) -> dict:
        """Convert to the Alpaca-style schema with title, description, headline, summary, created_at, and url."""
        summary = self.description[:SUMMARY_MAX_CHARS]
        article = {
            "title": self.title,
            "description": summary or "No description",
            "headline": self.title,
            "summary": summary,
            "created_at": self.created_at,
            "url": self.url
        }
        return article

def get_yahoo_news(ticker:str, limit:int=5) -> list[dict]:
    """Load Yahoo Finance news in the same schema as the Alpaca articles.
    
    Inputs:
    - ticker: stock symbol
    - limit: maximum number of articles
    
    Outputs:
    - Articles with title, description, headline, summary, created_at, and url fields
    """
    symbol = clean_ticker(ticker)
    search_type = getattr(yf, "Search", None) #older yfinance releases have no Search
    if search_type is not None:
        raw_articles = search_type(symbol, news_count=limit, max_results=limit).news
    else:
        raw_articles = yf.Ticker(symbol).news
    
    articles = [YahooArticle(article).to_dict() for article in (raw_articles or [])[:limit]]
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_alpaca_news(ticker:str, limit:int=5) -> list[dict]:
    """Load raw Alpaca news articles using ALPACA_API_KEY and ALPACA_SECRET_KEY.
    
    Inputs:
    - ticker: stock symbol
    - limit: maximum number of articles
    
    Outputs:
    - Alpaca articles in their original schema
    """
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise ValueError("Alpaca credentials not set. Define ALPACA_API_KEY and ALPACA_SECRET_KEY.")
    
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    params = {"symbols": clean_ticker(ticker), "limit": limit, "sort": "desc"}
    response = requests.get(ALPACA_NEWS_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    
    articles = response.json().get("news", [])
    if not articles:
        raise ValueError(f"No news found for {ticker}.")
    return articles

def get_news(ticker:str, limit:int=5) -> list[dict]:
    """Load news from Alpaca when configured, otherwise from Yahoo Finance."""
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        articles = get_alpaca_news(ticker, limit)
    else:
        LOGGER.info("Alpaca credentials are not configured; using Yahoo Finance news for %s.", ticker)
        articles = get_yahoo_news(ticker, limit)
    return articles
