from datetime import date, timedelta
from functools import cached_property

import pandas as pd
import yfinance as yf

# Analyst ratings and price targets
ANALYST_RATINGS_LIMIT = 10
PRICE_TARGET_KEYS = ("current", "low", "median", "mean", "high")

# Valuation, keyed by display name; Yahoo already reports dividendYield in percent (0.31 means 0.31%)
VALUATION_FIELDS = {
    "Market cap": "marketCap",
    "Trailing P/E": "trailingPE",
    "Forward P/E": "forwardPE",
    "EV/EBITDA": "enterpriseToEbitda",
    "Dividend yield": "dividendYield"
}

# Currency conversion
CURRENCY_SELECTION_ERROR = "Please select companies with valid currencies or exchange rates."

def clean_ticker(ticker:str) -> str:
    """Tidy up the user's input, e.g. ' mu ' -> 'MU'. Raises ValueError if empty."""
    symbol = (ticker or "").strip().upper()
    if not symbol:
        raise ValueError("Please enter a ticker symbol.")
    return symbol

def _close_px(history:pd.DataFrame) -> pd.Series:
    if "Close" not in history:
        return pd.Series(dtype="float64")
    return history["Close"].dropna()

def _latest_close(symbol:str) -> float | None:
    closing_px = _close_px(yf.Ticker(symbol).history(period="5d")) #workaround to get the latest data
    close = float(closing_px.iloc[-1]) if not closing_px.empty else None
    return close

class Company:
    """
    Yahoo Finance market data for one listed company.
    
    Inputs:
    - ticker: user-entered symbol, cleaned with clean_ticker
    """
    
    def __init__(self, ticker:str) -> None:
        self.symbol = clean_ticker(ticker)
        self._stock = yf.Ticker(self.symbol)
    
    @cached_property
    def info(self) -> dict:
        """Yahoo Finance company profile, or an empty dict when unavailable."""
        info = self._stock.info or {}
        return info
    
    def financials(self) -> dict[str, pd.DataFrame]:
        """Load the income statement, balance sheet, and cash flow statement."""
        statements = {
            "Income Statement": self._stock.financials,
            "Balance Sheet": self._stock.balance_sheet,
            "Cash Flow": self._stock.cashflow
        }
        if all(statement is None or statement.empty for statement in statements.values()):
            raise ValueError(f"No financial statements found for {self.symbol}.")
        return statements
    
    def analyst_ratings(self) -> pd.DataFrame:
        """Load the most recent analyst recommendation snapshots, or an empty frame when none are published."""
        recommendations = self._stock.recommendations
        if recommendations is None or len(recommendations) == 0:
            return pd.DataFrame(dtype="float64")
        ratings = recommendations.tail(ANALYST_RATINGS_LIMIT)
        return ratings
    
    def price_targets(self) -> dict[str, float]:
        """Load the current price and the low, median, mean and high analyst price targets, or an empty dict when unavailable."""
        targets = self._stock.analyst_price_targets or {}
        if any(targets.get(key) is None for key in PRICE_TARGET_KEYS):
            return {}
        return {key: float(targets[key]) for key in PRICE_TARGET_KEYS}
    
    def valuation(self) -> dict:
        """Read market cap, valuation multiples and dividend yield from the company profile, with None for missing values."""
        valuation = {name: self.info.get(field) for name, field in VALUATION_FIELDS.items()}
        valuation["Currency"] = self.info.get("currency") or ""
        return valuation
    
    def latest_price(self, market_open:bool) -> float:
        """Fetch the latest intraday price, or the most recent close when the market is shut."""
        if market_open:
            history = self._stock.history(period="1d", interval="1m", prepost=False)
        else:
            history = self._stock.history(period="5d", interval="1d", prepost=False)
        closing_px = _close_px(history)
        if closing_px.empty:
            raise ValueError(f"No latest price found for {self.symbol}.")
        price = float(closing_px.iloc[-1])
        return price
    
    def price_history(self, start_date:date, end_date:date) -> pd.Series:
        """Load daily closing prices between two inclusive dates, indexed by timezone-naive date."""
        history = self._stock.history(start=start_date, end=end_date + timedelta(days=1)) #Yahoo treats end as exclusive
        if history.empty:
            raise ValueError(f"No price history found for {self.symbol}.")
        prices = history["Close"]
        prices.index = prices.index.tz_localize(None)
        prices.index.name = "Date"
        
        in_range = (prices.index >= pd.Timestamp(start_date)) & (prices.index <= pd.Timestamp(end_date))
        prices = prices.loc[in_range]
        if prices.empty:
            raise ValueError(f"No price history found for {self.symbol} in the selected date range.")
        return prices
    
    def usd_conversion_rate(self) -> float:
        """Return the latest USD value of one unit of the company's reporting currency."""
        # Get Local Currency of Stock
        currency = self.info.get("financialCurrency")
        if not currency:
            raise ValueError(CURRENCY_SELECTION_ERROR)
        currency = str(currency).upper()
        if currency == "USD":
            return 1.0
        
        # Get Conversion Rate
        rate = _latest_close(f"{currency}USD=X")
        if rate is None:
            inverse_rate = _latest_close(f"USD{currency}=X") #Yahoo only lists some pairs in one direction
            rate = 1 / inverse_rate if inverse_rate is not None and inverse_rate > 0 else None
        if rate is None or rate <= 0:
            raise ValueError(CURRENCY_SELECTION_ERROR)
        return rate
    
    def snapshot(self) -> dict:
        """Load the name, financial statements, analyst ratings and price targets, valuation, and USD conversion rate."""
        snapshot = {
            "ticker": self.symbol,
            "name": self.info.get("longName") or self.symbol,
            "financials": self.financials(),
            "ratings": self.analyst_ratings(),
            "price_targets": self.price_targets(),
            "valuation": self.valuation(),
            "usd_rate": self.usd_conversion_rate()
        }
        return snapshot
