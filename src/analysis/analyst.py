import numpy as np
import pandas as pd

# Display labels
UNKNOWN_CONSENSUS = "Unknown"
LATEST_SNAPSHOT_LABEL = "Latest snapshot"

# Period sorting
UNAVAILABLE_PERIOD_MONTHS = 10**6 #sorts unparseable periods last

def _months_ago(period:str) -> int | None:
    try:
        months = abs(int(period.removesuffix("m")))
    except ValueError:
        months = None
    return months

def _period_sort_key(period:str) -> int:
    months = _months_ago(period)
    sort_key = UNAVAILABLE_PERIOD_MONTHS if months is None else months
    return sort_key

class AnalystRatings:
    """
    Analyst recommendation snapshots for one company snapshot.
    
    Inputs:
    - company: company snapshot from Company.snapshot, whose optional ratings is a DataFrame with one row per period, newest first
    
    Example company:
    {"ticker": "AAPL", "ratings": <DataFrame>}
    
    Example ratings:
       period  strongBuy  buy  hold  sell  strongSell
    0      0m         10   22    15     1           0
    1     -1m          9   21    16     2           0
    """
    
    def __init__(self, company:dict) -> None:
        self.company = company
        self.ticker = company["ticker"]
        self.ratings = company.get("ratings")
    
    @property
    def is_empty(self) -> bool:
        """Whether no analyst ratings were loaded."""
        is_empty = self.ratings is None or self.ratings.empty
        return is_empty
    
    def periods(self) -> set[str]:
        """Return the snapshot periods this company has ratings for."""
        if self.is_empty or "period" not in self.ratings.columns:
            return set()
        periods = set(self.ratings["period"].dropna().astype(str))
        return periods
    
    def snapshot(self, period:str | None) -> pd.Series:
        """
        Return the ratings row for one period, or the newest row when no period is given.
        
        Inputs:
        - period: snapshot period such as "0m" or "-1m", or None for the newest row
        
        Outputs:
        - One ratings row with strongBuy, buy, hold, sell and strongSell counts
        """
        if "period" not in self.ratings.columns:
            return self.ratings.iloc[-1]
        if period is None:
            return self.ratings.iloc[0]
        matching = self.ratings[self.ratings["period"].astype(str) == period]
        if matching.empty:
            raise ValueError(f"Analyst ratings for {self.ticker} are unavailable for {period}.")
        return matching.iloc[0]
    
    def sentiment(self, period:str | None) -> dict:
        """
        Group one snapshot into buy, hold, and sell counts with the consensus label.
        
        Inputs:
        - period: snapshot period such as "0m" or "-1m", or None for the newest row
        
        Outputs:
        - Buy (strong buy + buy), hold, and sell (sell + strong sell) counts, their total, and the consensus label of the largest bucket
        
        Example output:
        {"buy": 32.0, "hold": 15.0, "sell": 1.0, "total": 48.0, "consensus": "Buy"}
        
        With no ratings loaded: {"buy": 0, "hold": 0, "sell": 0, "total": 0, "consensus": "Unknown"}
        """
        if self.is_empty:
            return {"buy": 0, "hold": 0, "sell": 0, "total": 0, "consensus": UNKNOWN_CONSENSUS}
        snapshot = self.snapshot(period)
        
        counts = {
            "buy": float(snapshot.get("strongBuy", 0)) + float(snapshot.get("buy", 0)),
            "hold": float(snapshot.get("hold", 0)),
            "sell": float(snapshot.get("sell", 0)) + float(snapshot.get("strongSell", 0))
        }
        consensus = max(counts, key=counts.get).title() if sum(counts.values()) > 0 else UNKNOWN_CONSENSUS
        sentiment = {**counts, "total": sum(counts.values()), "consensus": consensus}
        return sentiment
    
    def buy_percent(self, period:str) -> float:
        """Return the share of covering analysts rating the stock buy or strong buy, or NaN with no coverage."""
        sentiment = self.sentiment(period)
        total = sentiment["buy"] + sentiment["hold"] + sentiment["sell"]
        return sentiment["buy"] / total * 100 if total else np.nan

def get_common_analyst_periods(companies:list[dict]) -> list[str]:
    """
    Return analyst snapshot periods available for every company, newest first.
    
    Inputs:
    - companies: company snapshots
    
    Outputs:
    - Periods present in every company's ratings, sorted by months ago
    
    Example output: ["0m", "-1m", "-2m", "-3m"]
    """
    period_sets = [AnalystRatings(company).periods() for company in companies]
    common_periods = set.intersection(*period_sets) if period_sets else set()
    ordered_periods = sorted(common_periods, key=_period_sort_key)
    return ordered_periods

def analyst_period_label(period:str) -> str:
    """
    Format an analyst snapshot period for the selector and chart title.
    
    Inputs:
    - period: snapshot period such as "0m" or "-3m"
    
    Outputs:
    - "Latest snapshot" for the current period, otherwise a label such as "1 month ago" or "3 months ago"
    """
    months = _months_ago(period)
    if not months:
        return LATEST_SNAPSHOT_LABEL
    unit = "month" if months == 1 else "months"
    label = f"{months} {unit} ago"
    return label

def build_analyst_sentiment_data(companies:list[dict], period:str | None=None) -> dict:
    """
    Group every company's analyst ratings into buy, hold, and sell counts.
    
    Inputs:
    - companies: company snapshots
    - period: analyst snapshot period, or None for the newest period all companies share
    
    Outputs:
    - The selected period and its label, plus buy, hold, sell counts, total and consensus per company
    
    Example output:
    {
        "period": "0m",
        "period_label": "Latest snapshot",
        "companies": [
            {"ticker": "AAPL", "buy": 32.0, "hold": 15.0, "sell": 1.0, "total": 48.0, "consensus": "Buy"},
            {"ticker": "MSFT", "buy": 48.0, "hold": 3.0, "sell": 0.0, "total": 51.0, "consensus": "Buy"}
        ]
    }
    """
    if period is None:
        common_periods = get_common_analyst_periods(companies)
        period = common_periods[0] if common_periods else None
    label = analyst_period_label(period) if period is not None else LATEST_SNAPSHOT_LABEL
    
    sentiment = {
        "period": period,
        "period_label": label,
        "companies": [{"ticker": company["ticker"], **AnalystRatings(company).sentiment(period)} for company in companies]
    }
    return sentiment

def build_sentiment_trend(companies:list[dict]) -> pd.DataFrame:
    """
    Track each company's buy share across the snapshot periods they all share.
    
    Inputs:
    - companies: company snapshots
    
    Outputs:
    - One row per period, oldest first and indexed by its label, one column per ticker holding the buy percentage
    
    Example output:
                  AAPL  MSFT
    3 months ago  65.1  92.0
    Latest        58.5  94.1
    """
    periods = list(reversed(get_common_analyst_periods(companies)))
    ratings = [AnalystRatings(company) for company in companies]
    n_periods = len(periods)
    n_companies = len(companies)
    buy_percents = np.empty((n_periods, n_companies), dtype=np.float64)
    for period_idx, period in enumerate(periods):
        for company_idx, company_ratings in enumerate(ratings):
            buy_percents[period_idx, company_idx] = company_ratings.buy_percent(period)
    
    labels = [analyst_period_label(period) for period in periods]
    tickers = [company["ticker"] for company in companies]
    trend = pd.DataFrame(buy_percents, index=labels, columns=tickers, dtype="float64")
    return trend

def build_price_targets(companies:list[dict]) -> list[dict]:
    """
    Express each company's analyst price targets relative to its current price.
    
    Inputs:
    - companies: company snapshots, whose price_targets holds current, low, median, mean and high prices
    
    Outputs:
    - One dict per company with published targets: ticker, listing currency, the prices, and each target as a percentage above or below the current price
    
    Example output:
    [{"ticker": "AAPL", "currency": "USD", "current": 347.7, "low": 215.0, "median": 335.0, "mean": 328.4, "high": 405.0,
      "low_pct": -38.2, "median_pct": -3.7, "mean_pct": -5.6, "high_pct": 16.5}]
    """
    targets = []
    for company in companies:
        prices = company.get("price_targets") or {}
        if not prices or not prices["current"]:
            continue
        relative = {f"{key}_pct": (prices[key] / prices["current"] - 1) * 100 for key in ("low", "median", "mean", "high")}
        currency = (company.get("valuation") or {}).get("Currency", "")
        targets.append({"ticker": company["ticker"], "currency": currency, **prices, **relative})
    return targets
