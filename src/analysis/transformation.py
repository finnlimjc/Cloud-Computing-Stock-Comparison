from datetime import datetime, timezone

import numpy as np
import pandas as pd

# Risk metrics
RISK_FREE_RATE = 0.0
TRADING_DAYS_PER_YEAR = 252
VOLATILITY_WINDOW = 30

# Calendar years starting after Jan 7 or ending before Dec 24 are treated as partial
PARTIAL_YEAR_START = (1, 7)
PARTIAL_YEAR_END = (12, 24)

# Plain-language summaries
SIMILARITY_TOLERANCE = 0.005

# Relative time labels
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 86400

def compute_drawdown(prices:pd.Series) -> pd.Series:
    """Calculate each price's drawdown from its running peak as a fraction."""
    running_peak = prices.cummax()
    drawdown = prices / running_peak - 1
    drawdown.name = "Drawdown"
    return drawdown

def normalize_prices(prices:pd.Series) -> pd.Series:
    """Rebase a price series to 100 at its first available observation."""
    clean = prices.dropna()
    if clean.empty or clean.iloc[0] == 0:
        return clean
    normalized = clean / clean.iloc[0] * 100
    return normalized

def period_return(prices:pd.Series) -> float:
    """Calculate the return between the first and last available prices as a fraction."""
    clean = prices.dropna()
    if len(clean) < 2 or clean.iloc[0] == 0:
        return 0.0
    total_return = float(clean.iloc[-1] / clean.iloc[0] - 1)
    return total_return

def calendar_year_returns(prices:pd.Series) -> pd.Series:
    """Calculate each calendar year's return, labelling years only partly covered with a trailing asterisk.
    
    Inputs:
    - prices: daily prices
    
    Outputs:
    - Returns indexed by year label; the first year is measured from the first available price
    """
    clean = prices.dropna()
    year_end = clean.groupby(clean.index.year).last()
    year_start = year_end.shift(1)
    year_start.iloc[0] = clean.iloc[0]
    returns = year_end / year_start - 1
    
    first_year = year_end.index[0]
    last_year = year_end.index[-1]
    partial_start = (clean.index[0].month, clean.index[0].day) > PARTIAL_YEAR_START
    partial_end = (clean.index[-1].month, clean.index[-1].day) < PARTIAL_YEAR_END
    labels = [
        f"{year}*" if (year == first_year and partial_start) or (year == last_year and partial_end) else str(year)
        for year in returns.index
    ]
    returns.index = labels
    returns.name = "Calendar-year return"
    return returns

def sharpe_ratio(prices:pd.Series, risk_free_rate:float=RISK_FREE_RATE) -> float:
    """Calculate the annualized Sharpe ratio from daily returns.
    
    Inputs:
    - prices: daily prices
    - risk_free_rate: annual risk-free rate
    
    Outputs:
    - Annualized Sharpe ratio, or zero when returns are unavailable or constant
    """
    returns = prices.dropna().pct_change().dropna()
    if returns.empty:
        return 0.0
    daily_std = returns.std()
    if not np.isfinite(daily_std) or daily_std == 0:
        return 0.0
    
    daily_risk_free = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess_return = returns.mean() - daily_risk_free
    sharpe = float(excess_return / daily_std * np.sqrt(TRADING_DAYS_PER_YEAR))
    return sharpe

def rolling_volatility(prices:pd.Series) -> pd.Series:
    """Calculate annualized rolling 30-trading-day volatility."""
    daily_std = prices.pct_change().rolling(VOLATILITY_WINDOW).std()
    volatility = daily_std * np.sqrt(TRADING_DAYS_PER_YEAR)
    volatility.name = "Volatility"
    return volatility

def average_volatility(prices:pd.Series) -> float:
    """Calculate the mean rolling volatility, or zero when the history is too short."""
    volatility = rolling_volatility(prices).dropna()
    average = float(volatility.mean()) if not volatility.empty else 0.0
    return average

def common_start_prices(prices:dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Trim comparison series to their shared start date.
    
    Inputs:
    - prices: price series keyed by comparison role
    
    Outputs:
    - Cleaned price series beginning on the same date
    """
    cleaned = {role: series.dropna() for role, series in prices.items()}
    non_empty = [series for series in cleaned.values() if not series.empty]
    if not non_empty:
        return {}
    start = max(series.index.min() for series in non_empty)
    trimmed = {role: series.loc[series.index >= start] for role, series in cleaned.items()}
    return trimmed

def summarize_prices(prices:pd.Series) -> dict[str, float]:
    """Calculate the latest price, return, drawdown, Sharpe, and volatility metrics for one stock."""
    clean = prices.dropna()
    if clean.empty:
        raise ValueError("No price observations are available.")
    summary = {
        "Latest price": float(clean.iloc[-1]),
        "Return over period": period_return(clean),
        "Max drawdown": float(compute_drawdown(clean).min()),
        "Current drawdown": float(compute_drawdown(clean).iloc[-1]),
        "Sharpe ratio": sharpe_ratio(clean),
        "Average volatility": average_volatility(clean)
    }
    return summary

def _comparison_phrase(first:str, second:str, first_value:float, second_value:float, similar_text:str, difference_text:str, higher_is_better:bool=True) -> str:
    if np.isclose(first_value, second_value, atol=SIMILARITY_TOLERANCE):
        return similar_text
    first_leads = first_value >= second_value if higher_is_better else first_value <= second_value
    leader, other = (first, second) if first_leads else (second, first)
    phrase = difference_text.format(leader=leader, other=other)
    return phrase

def _plain_words_ranking(tickers:list[str], returns:dict[str, float], volatilities:dict[str, float], drawdowns:dict[str, float], period_label:str) -> str:
    """Summarize three or more stocks by naming the best and worst on growth, swings and falls."""
    best_return = max(tickers, key=returns.get)
    worst_return = min(tickers, key=returns.get)
    most_volatile = max(tickers, key=volatilities.get)
    deepest_fall = min(tickers, key=drawdowns.get)
    summary = (
        f"Over {period_label}, {best_return} grew the most and {worst_return} the least; "
        f"{most_volatile} had the most daily price swings, and {deepest_fall} fell furthest at its worst."
    )
    return summary

def plain_words_comparison(tickers:list[str], returns:dict[str, float], volatilities:dict[str, float], drawdowns:dict[str, float], period_label:str) -> str:
    """Summarize measured growth and risk without making a recommendation.
    
    Inputs:
    - tickers: the two compared symbols
    - returns: period returns keyed by ticker
    - volatilities: average volatility keyed by ticker
    - drawdowns: maximum drawdowns keyed by ticker
    - period_label: human-readable analysis range
    
    Outputs:
    - Plain-language comparison summary
    """
    if len(tickers) > 2:
        return _plain_words_ranking(tickers, returns, volatilities, drawdowns, period_label)
    first, second = tickers
    
    growth = _comparison_phrase(
        first, second, returns[first], returns[second],
        f"{first} and {second} grew by similar amounts",
        "{leader} grew more than {other}"
    )
    volatility = _comparison_phrase(
        first, second, volatilities[first], volatilities[second],
        "their daily price swings were similar",
        "{leader} had more daily price swings than {other}"
    )
    drawdown = _comparison_phrase(
        first, second, drawdowns[first], drawdowns[second],
        "their worst peak-to-low falls were similar",
        "{leader} fell further at its worst than {other}",
        higher_is_better=False
    )
    
    summary = f"Over {period_label}, {growth}; {volatility}, and {drawdown}."
    return summary

def plain_words_single(ticker:str, prices:pd.Series, period_label:str) -> str:
    """Summarize a single stock's price range and worst drawdown."""
    clean = prices.dropna()
    if clean.empty:
        return f"There is not enough price data to summarize {ticker} over {period_label}."
    maximum_drawdown = abs(float(compute_drawdown(clean).min()))
    summary = (
        f"Over {period_label}, {ticker} went from {clean.iloc[0]:,.2f} to "
        f"{clean.iloc[-1]:,.2f} a share. At its worst it was "
        f"{maximum_drawdown:.1%} below its previous high."
    )
    return summary

def _as_utc(value:object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc) #feeds without a timezone are UTC
    return timestamp

def relative_time(value:object, now:datetime | None=None) -> str:
    """Format an article timestamp as a short relative label.
    
    Inputs:
    - value: article timestamp
    - now: optional current time for testing
    
    Outputs:
    - Relative time label, or a formatted date after a week
    """
    timestamp = _as_utc(value)
    current = _as_utc(now or datetime.now(timezone.utc))
    seconds = max(0, int((current - timestamp).total_seconds()))
    
    if seconds < SECONDS_PER_MINUTE:
        label = "Just now"
    elif seconds < SECONDS_PER_HOUR:
        label = f"{seconds // SECONDS_PER_MINUTE}m ago"
    elif seconds < SECONDS_PER_DAY:
        label = f"{seconds // SECONDS_PER_HOUR}h ago"
    elif seconds < 2 * SECONDS_PER_DAY:
        label = "Yesterday"
    elif seconds < 7 * SECONDS_PER_DAY:
        label = f"{seconds // SECONDS_PER_DAY}d ago"
    else:
        label = timestamp.strftime("%d %b %Y")
    return label
