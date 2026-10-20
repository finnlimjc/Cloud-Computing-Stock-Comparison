from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

RISK_FREE_RATE = 0.0
TRADING_DAYS_PER_YEAR = 252

def compute_drawdown(prices:pd.Series) -> pd.Series:
    """Returns the drawdown from the running peak as a fraction (0 at a peak, -0.25 = 25% below it)."""
    running_peak = prices.cummax()
    drawdown = prices / running_peak - 1
    drawdown.name = "Drawdown"
    return drawdown


def normalize_prices(prices:pd.Series) -> pd.Series:
    """Rebase a price series to 100 at its first available observation."""
    clean = prices.dropna()
    if clean.empty or clean.iloc[0] == 0:
        return clean
    return clean / clean.iloc[0] * 100


def period_return(prices:pd.Series) -> float:
    clean = prices.dropna()
    if len(clean) < 2 or clean.iloc[0] == 0:
        return 0.0
    return float(clean.iloc[-1] / clean.iloc[0] - 1)


def sharpe_ratio(prices:pd.Series, risk_free_rate:float=RISK_FREE_RATE) -> float:
    """Annualized Sharpe ratio using daily returns and an annual risk-free rate."""
    returns = prices.dropna().pct_change().dropna()
    if returns.empty:
        return 0.0
    daily_risk_free = (1 + risk_free_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    daily_std = returns.std()
    if not np.isfinite(daily_std) or daily_std == 0:
        return 0.0
    return float((returns.mean() - daily_risk_free) / daily_std * np.sqrt(TRADING_DAYS_PER_YEAR))


def rolling_volatility(prices:pd.Series) -> pd.Series:
    """Annualized rolling 30-trading-day standard deviation of daily returns."""
    result = prices.pct_change().rolling(30).std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    result.name = "Volatility"
    return result


def average_volatility(prices:pd.Series) -> float:
    volatility = rolling_volatility(prices).dropna()
    return float(volatility.mean()) if not volatility.empty else 0.0


def common_start_prices(prices:dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Trim comparison series to their shared start so growth uses the same period."""
    start = max(series.dropna().index.min() for series in prices.values())
    return {key: series.loc[series.index >= start].dropna() for key, series in prices.items()}


def summarize_prices(prices:pd.Series) -> dict[str, float]:
    """Calculate the metrics displayed for one stock."""
    clean = prices.dropna()
    return {
        "Latest price": float(clean.iloc[-1]),
        "Return over period": period_return(clean),
        "Max drawdown": float(compute_drawdown(clean).min()),
        "Sharpe ratio": sharpe_ratio(clean, RISK_FREE_RATE),
        "Average volatility": average_volatility(clean),
    }


def recession_periods_from_series(recessions:pd.Series) -> list[dict]:
    """Convert monthly USREC observations into inclusive monthly recession ranges."""
    values = pd.Series(recessions.values, index=pd.to_datetime(recessions.index)).dropna().sort_index()
    active = values == 1
    groups = active.ne(active.shift(fill_value=False)).cumsum()
    periods = []
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


def plain_words_comparison(
    tickers:list[str],
    returns:dict[str, float],
    volatilities:dict[str, float],
    drawdowns:dict[str, float],
    period_label:str,
) -> str:
    """Summarize the measured growth and risk without making an investment recommendation."""
    first, second = tickers
    growth_leader = first if returns[first] >= returns[second] else second
    growth_other = second if growth_leader == first else first
    if np.isclose(returns[first], returns[second], atol=0.005):
        growth = f"{first} and {second} grew by similar amounts"
    else:
        growth = f"{growth_leader} grew more than {growth_other}"
    bumpier = first if volatilities[first] >= volatilities[second] else second
    calmer = second if bumpier == first else first
    if np.isclose(volatilities[first], volatilities[second], atol=0.005):
        volatility = "their daily price swings were similar"
    else:
        volatility = f"{bumpier} had more daily price swings than {calmer}"
    deeper = first if drawdowns[first] <= drawdowns[second] else second
    shallower = second if deeper == first else first
    if np.isclose(drawdowns[first], drawdowns[second], atol=0.005):
        drawdown = "their worst peak-to-low falls were similar"
    else:
        drawdown = f"{deeper} fell further at its worst than {shallower}"
    return f"Over {period_label}, {growth}; {volatility}, and {drawdown}."


def plain_words_single(ticker:str, prices:pd.Series, period_label:str) -> str:
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
    """Format an article timestamp as a short relative label."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    current = pd.Timestamp(now or datetime.now(timezone.utc))
    if current.tzinfo is None:
        current = current.tz_localize(timezone.utc)
    seconds = max(0, int((current - timestamp).total_seconds()))
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

def _markdown_link(text:str, url:str) -> str:
    escaped = text.replace("[", "\\[").replace("]", "\\]") #brackets in a headline would end the link text early
    link = f"[{escaped}]({url})"
    return link

def format_alpaca_news(articles:list) -> pd.DataFrame:
    """
    Converts raw Alpaca news articles into display rows for Streamlit.
    
    Inputs:
    - articles: output of input_data.get_alpaca_news
    
    Outputs:
    - DataFrame with 'Date' (YYYY-MM-DD), 'Title' (markdown hyperlink) and 'Summary' columns
    """
    dates = pd.to_datetime([article["created_at"] for article in articles]).strftime("%Y-%m-%d")
    titles = [_markdown_link(article["headline"], article["url"]) for article in articles]
    summaries = [article.get("summary") or "No summary" for article in articles]
    news = pd.DataFrame({"Date":dates, "Title":titles, "Summary":summaries}, dtype="object")
    return news