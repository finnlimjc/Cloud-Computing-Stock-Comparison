from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

RISK_FREE_RATE = 0.0
TRADING_DAYS_PER_YEAR = 252

def compute_drawdown(prices:pd.Series) -> pd.Series:
    """Calculate each price's drawdown from its running peak.

    Inputs:
    - prices: daily prices

    Outputs:
    - Drawdowns as fractions
    """
    # This part calculates the running peak and each observation's drawdown.
    running_peak = prices.cummax()
    drawdown = prices / running_peak - 1
    drawdown.name = "Drawdown"
    return drawdown


def normalize_prices(prices:pd.Series) -> pd.Series:
    """Rebase a price series to 100 at its first available observation.

    Inputs:
    - prices: daily prices

    Outputs:
    - Cleaned and normalized prices
    """
    # This part removes missing prices and handles empty or zero starts.
    clean = prices.dropna()
    if clean.empty or clean.iloc[0] == 0:
        return clean
    return clean / clean.iloc[0] * 100


def period_return(prices:pd.Series) -> float:
    """Calculate the return between the first and last available prices.

    Inputs:
    - prices: daily prices

    Outputs:
    - Period return as a fraction
    """
    # This part validates the observations needed to calculate a return.
    clean = prices.dropna()
    if len(clean) < 2 or clean.iloc[0] == 0:
        return 0.0
    return float(clean.iloc[-1] / clean.iloc[0] - 1)


def sharpe_ratio(prices:pd.Series, risk_free_rate:float=RISK_FREE_RATE) -> float:
    """Calculate the annualized Sharpe ratio from daily returns.

    Inputs:
    - prices: daily prices
    - risk_free_rate: annual risk-free rate

    Outputs:
    - Annualized Sharpe ratio
    """
    # This part calculates daily returns and handles an empty series.
    returns = prices.dropna().pct_change().dropna()
    if returns.empty:
        return 0.0
    # This part annualizes the risk-free rate and checks return volatility.
    daily_risk_free = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    daily_std = returns.std()
    if not np.isfinite(daily_std) or daily_std == 0:
        return 0.0
    return float((returns.mean() - daily_risk_free) / daily_std * np.sqrt(TRADING_DAYS_PER_YEAR))


def rolling_volatility(prices:pd.Series) -> pd.Series:
    """Calculate annualized rolling 30-trading-day volatility.

    Inputs:
    - prices: daily prices

    Outputs:
    - Rolling annualized volatility
    """
    # This part calculates and labels the rolling standard deviation.
    result = prices.pct_change().rolling(30).std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    result.name = "Volatility"
    return result


def average_volatility(prices:pd.Series) -> float:
    """Calculate the mean of available rolling volatility values.

    Inputs:
    - prices: daily prices

    Outputs:
    - Average annualized volatility, or zero when unavailable
    """
    # This part calculates rolling volatility and handles short histories.
    volatility = rolling_volatility(prices).dropna()
    return float(volatility.mean()) if not volatility.empty else 0.0


def common_start_prices(prices:dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Trim comparison series to their shared start date.

    Inputs:
    - prices: price series keyed by comparison role

    Outputs:
    - Cleaned price series beginning on the same date
    """
    # This part finds the latest first observation across all series.
    start = max(series.dropna().index.min() for series in prices.values())
    # This part trims each series to that shared start date.
    return {key: series.loc[series.index >= start].dropna() for key, series in prices.items()}


def summarize_prices(prices:pd.Series) -> dict[str, float]:
    """Calculate the metrics displayed for one stock.

    Inputs:
    - prices: daily prices

    Outputs:
    - Named price, return, drawdown, Sharpe, and volatility metrics
    """
    # This part removes missing observations before calculating metrics.
    clean = prices.dropna()
    # This part returns the metrics used by the dashboard.
    return {
        "Latest price": float(clean.iloc[-1]),
        "Return over period": period_return(clean),
        "Max drawdown": float(compute_drawdown(clean).min()),
        "Sharpe ratio": sharpe_ratio(clean, RISK_FREE_RATE),
        "Average volatility": average_volatility(clean),
    }


def recession_periods_from_series(recessions:pd.Series) -> list[dict]:
    """Convert monthly USREC observations into inclusive monthly date ranges.

    Inputs:
    - recessions: monthly recession indicator series

    Outputs:
    - Recession periods with start, end, and label fields
    """
    # This part sorts valid monthly observations and groups active periods.
    values = pd.Series(recessions.values, index=pd.to_datetime(recessions.index)).dropna().sort_index()
    active = values == 1
    groups = active.ne(active.shift(fill_value=False)).cumsum()
    periods = []
    # This part converts each active group into an inclusive date range.
    for _, dates in values[active].groupby(groups[active]):
        start = pd.Timestamp(dates.index[0]).normalize().replace(day=1)
        end = pd.Timestamp(dates.index[-1]).normalize() + pd.offsets.MonthEnd(0)
        label = ""
        if start <= pd.Timestamp("2009-06-30") and end >= pd.Timestamp("2007-12-01"):
            label = "2008 Financial Crisis"
        elif start <= pd.Timestamp("2020-04-30") and end >= pd.Timestamp("2020-02-01"):
            label = "COVID-19"
        periods.append({"start": start, "end": end, "label": label})
    return periods


def _comparison_phrase(
    first:str,
    second:str,
    first_value:float,
    second_value:float,
    similar_text:str,
    difference_text:str,
    higher_is_better:bool=True,
) -> str:
    """Describe whether two measured values are similar or different.

    Inputs:
    - first: first ticker
    - second: second ticker
    - first_value: first ticker's measurement
    - second_value: second ticker's measurement
    - similar_text: wording for similar measurements
    - difference_text: wording template for different measurements
    - higher_is_better: whether the larger measurement leads

    Outputs:
    - Plain-language comparison phrase
    """
    # This part handles measurements that are similar within the existing tolerance.
    if np.isclose(first_value, second_value, atol=0.005):
        return similar_text
    # This part selects the leading ticker and fills the phrase template.
    first_leads = first_value >= second_value if higher_is_better else first_value <= second_value
    leader, other = (first, second) if first_leads else (second, first)
    return difference_text.format(leader=leader, other=other)


def plain_words_comparison(
    tickers:list[str],
    returns:dict[str, float],
    volatilities:dict[str, float],
    drawdowns:dict[str, float],
    period_label:str,
) -> str:
    """Summarize measured growth and risk without making an investment recommendation.

    Inputs:
    - tickers: the two compared symbols
    - returns: period returns keyed by ticker
    - volatilities: average volatility keyed by ticker
    - drawdowns: maximum drawdowns keyed by ticker
    - period_label: human-readable analysis range

    Outputs:
    - Plain-language comparison summary
    """
    # This part creates phrases for return, volatility, and drawdown comparisons.
    first, second = tickers
    growth = _comparison_phrase(
        first, second, returns[first], returns[second],
        f"{first} and {second} grew by similar amounts",
        "{leader} grew more than {other}",
    )
    volatility = _comparison_phrase(
        first, second, volatilities[first], volatilities[second],
        "their daily price swings were similar",
        "{leader} had more daily price swings than {other}",
    )
    drawdown = _comparison_phrase(
        first, second, drawdowns[first], drawdowns[second],
        "their worst peak-to-low falls were similar",
        "{leader} fell further at its worst than {other}",
        higher_is_better=False,
    )
    # This part combines the comparison phrases with the selected date range.
    return f"Over {period_label}, {growth}; {volatility}, and {drawdown}."


def plain_words_single(ticker:str, prices:pd.Series, period_label:str) -> str:
    """Summarize a single stock's price range and worst drawdown.

    Inputs:
    - ticker: stock symbol
    - prices: daily prices
    - period_label: human-readable analysis range

    Outputs:
    - Plain-language single-stock summary
    """
    # This part checks for available prices and calculates maximum drawdown.
    clean = prices.dropna()
    if clean.empty:
        return f"There is not enough price data to summarize {ticker} over {period_label}."
    maximum_drawdown = abs(float(compute_drawdown(clean).min()))
    return (
        f"Over {period_label}, {ticker} went from ${clean.iloc[0]:,.2f} to "
        f"${clean.iloc[-1]:,.2f} a share. At its worst it was "
        f"{maximum_drawdown:.1%} below its previous high."
    )


def relative_time(value:object, now:datetime | None=None) -> str:
    """Format an article timestamp as a short relative label.

    Inputs:
    - value: article timestamp
    - now: optional current time for testing

    Outputs:
    - Relative time label or formatted date
    """
    # This part parses the timestamp and assigns UTC to naive values.
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    # This part normalizes the current time and calculates elapsed seconds.
    current = pd.Timestamp(now or datetime.now(timezone.utc))
    if current.tzinfo is None:
        current = current.tz_localize(timezone.utc)
    seconds = max(0, int((current - timestamp).total_seconds()))
    # This part selects a concise label for the elapsed time.
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 172800:
        return "Yesterday"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return timestamp.strftime("%d %b %Y")