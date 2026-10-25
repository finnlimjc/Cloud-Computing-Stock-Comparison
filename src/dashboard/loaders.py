from datetime import date, datetime, timezone

import pandas as pd
import streamlit as st

from src.dashboard.config import LATEST_PRICE_TTL, ONE_DAY_SECONDS, THIRTY_MINUTES
from src.data import news, price_ratings, recessions

@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_prices(ticker:str, start_date:date, end_date:date) -> pd.Series:
    """Load daily closing prices for an inclusive date range."""
    prices = price_ratings.Company(ticker).price_history(start_date, end_date)
    return prices

@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_company_snapshot(ticker:str) -> dict:
    """Download and cache one company's snapshot for the company metrics tab and saved reports."""
    snapshot = price_ratings.Company(ticker).snapshot()
    return snapshot

@st.cache_data(ttl=LATEST_PRICE_TTL, show_spinner=False)
def load_latest_price(ticker:str, market_open:bool) -> tuple[float, datetime]:
    """Load the latest available price and its UTC fetch time."""
    price = price_ratings.Company(ticker).latest_price(market_open)
    return price, datetime.now(timezone.utc)

@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False)
def load_news(ticker:str) -> list[dict]:
    """Load recent news, from Alpaca when configured and Yahoo Finance otherwise."""
    articles = news.get_news(ticker, limit=5)
    return articles

@st.cache_data(ttl=ONE_DAY_SECONDS, show_spinner=False)
def load_recession_periods() -> list[dict]:
    """Load monthly US recession periods from FRED with a known-date fallback."""
    periods = recessions.get_recession_periods()
    return periods
