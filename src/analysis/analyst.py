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
        - Buy (strong buy + buy), hold, and sell (sell + strong sell) counts, plus the consensus label of the largest bucket
        
        Example output:
        {"buy": 32.0, "hold": 15.0, "sell": 1.0, "consensus": "Buy"}
        
        With no ratings loaded: {"buy": 0, "hold": 0, "sell": 0, "consensus": "Unknown"}
        """
        if self.is_empty:
            return {"buy": 0, "hold": 0, "sell": 0, "consensus": UNKNOWN_CONSENSUS}
        snapshot = self.snapshot(period)
        
        counts = {
            "buy": float(snapshot.get("strongBuy", 0)) + float(snapshot.get("buy", 0)),
            "hold": float(snapshot.get("hold", 0)),
            "sell": float(snapshot.get("sell", 0)) + float(snapshot.get("strongSell", 0))
        }
        consensus = max(counts, key=counts.get).title() if sum(counts.values()) > 0 else UNKNOWN_CONSENSUS
        sentiment = {**counts, "consensus": consensus}
        return sentiment

def get_common_analyst_periods(company_a:dict, company_b:dict) -> list[str]:
    """
    Return analyst snapshot periods available for both companies, newest first.
    
    Inputs:
    - company_a: first company snapshot
    - company_b: second company snapshot
    
    Outputs:
    - Periods present in both companies' ratings, sorted by months ago
    
    Example output: ["0m", "-1m", "-2m", "-3m"]
    """
    common_periods = AnalystRatings(company_a).periods() & AnalystRatings(company_b).periods()
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

def build_analyst_sentiment_data(company_a:dict, company_b:dict, period:str | None=None) -> dict:
    """
    Group both companies' analyst ratings into buy, hold, and sell counts.
    
    Inputs:
    - company_a: first company snapshot
    - company_b: second company snapshot
    - period: analyst snapshot period, or None for the newest period both companies share
    
    Outputs:
    - Buy, hold, sell counts and consensus per company, plus the selected period and its label
    
    Example output:
    {
        "company_a": "AAPL",
        "company_b": "MSFT",
        "period": "0m",
        "period_label": "Latest snapshot",
        "a": {"buy": 32.0, "hold": 15.0, "sell": 1.0, "consensus": "Buy"},
        "b": {"buy": 48.0, "hold": 3.0, "sell": 0.0, "consensus": "Buy"}
    }
    """
    if period is None:
        common_periods = get_common_analyst_periods(company_a, company_b)
        period = common_periods[0] if common_periods else None
    label = analyst_period_label(period) if period is not None else LATEST_SNAPSHOT_LABEL
    
    sentiment = {
        "company_a": company_a["ticker"],
        "company_b": company_b["ticker"],
        "period": period,
        "period_label": label,
        "a": AnalystRatings(company_a).sentiment(period),
        "b": AnalystRatings(company_b).sentiment(period)
    }
    return sentiment
