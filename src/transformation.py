from __future__ import annotations

from datetime import datetime, timezone

from typing import Any, Dict, List, Optional

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


def _markdown_link(text:str, url:str) -> str:
    """Create a Markdown link with escaped brackets in its label.

    Inputs:
    - text: link label
    - url: link destination

    Outputs:
    - Markdown link
    """
    # This part escapes brackets so they remain part of the link label.
    escaped = text.replace("[", "\\[").replace("]", "\\]")
    return f"[{escaped}]({url})"


def format_alpaca_news(articles:list) -> pd.DataFrame:
    """Convert raw Alpaca articles into display-ready rows.

    Inputs:
    - articles: output of input_data.get_alpaca_news

    Outputs:
    - DataFrame with date, linked title, and summary columns
    """
    # This part formats dates, headlines, and article summaries.
    dates = pd.to_datetime(
        [article["created_at"] for article in articles]
    ).strftime("%Y-%m-%d")
    titles = [
        _markdown_link(article["headline"], article["url"])
        for article in articles
    ]
    summaries = [article.get("summary") or "No summary" for article in articles]
    return pd.DataFrame(
        {"Date": dates, "Title": titles, "Summary": summaries},
        dtype="object",
    )


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
    return float(
        (returns.mean() - daily_risk_free)
        / daily_std
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )


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
    # This part finds the latest first observation across all non-empty series.
    non_empty = {key: series.dropna() for key, series in prices.items()}
    available = {key: series for key, series in non_empty.items() if not series.empty}
    if not available:
        return {}
    start = max(series.index.min() for series in available.values())
    # This part trims each series to that shared start date.
    return {
        key: series.loc[series.index >= start]
        for key, series in non_empty.items()
    }


def summarize_prices(prices:pd.Series) -> dict[str, float]:
    """Calculate the metrics displayed for one stock.

    Inputs:
    - prices: daily prices

    Outputs:
    - Named latest price, return, drawdown, Sharpe, and volatility metrics
    """
    # This part removes missing observations before calculating metrics.
    clean = prices.dropna()
    if clean.empty:
        raise ValueError("No price observations are available.")
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
    values = pd.Series(
        recessions.values,
        index=pd.to_datetime(recessions.index),
    ).dropna().sort_index()
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
    # This part handles measurements that are similar within the tolerance.
    if np.isclose(first_value, second_value, atol=0.005):
        return similar_text
    # This part selects the leading ticker and fills the phrase template.
    first_leads = (
        first_value >= second_value
        if higher_is_better
        else first_value <= second_value
    )
    leader, other = (first, second) if first_leads else (second, first)
    return difference_text.format(leader=leader, other=other)


def plain_words_comparison(
    tickers:list[str],
    returns:dict[str, float],
    volatilities:dict[str, float],
    drawdowns:dict[str, float],
    period_label:str,
) -> str:
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
    # This part creates phrases for return, volatility, and drawdown comparisons.
    first, second = tickers
    growth = _comparison_phrase(
        first,
        second,
        returns[first],
        returns[second],
        f"{first} and {second} grew by similar amounts",
        "{leader} grew more than {other}",
    )
    volatility = _comparison_phrase(
        first,
        second,
        volatilities[first],
        volatilities[second],
        "their daily price swings were similar",
        "{leader} had more daily price swings than {other}",
    )
    drawdown = _comparison_phrase(
        first,
        second,
        drawdowns[first],
        drawdowns[second],
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
    # This part explains the price range and worst peak-to-low decline.
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


# This part adds the new data-transformation logic for the two-company comparison dashboard.
# This section is designed to be compatible with the newer input_data.py snapshot style.

# This helper extracts financial statement frames from either the old format or the new snapshot format.
def _extract_financials(company: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    financials = company.get("financials")
    if isinstance(financials, dict):
        return {
            "income_statement": financials.get(
                "Income Statement",
                financials.get("income_statement", pd.DataFrame()),
            ),
            "balance_sheet": financials.get(
                "Balance Sheet",
                financials.get("balance_sheet", pd.DataFrame()),
            ),
            "cash_flow": financials.get(
                "Cash Flow",
                financials.get("cash_flow", pd.DataFrame()),
            ),
        }

    return {
        "income_statement": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cash_flow": pd.DataFrame(),
    }


# This function defines the likely label names for each financial metric.
def _metric_candidates(metric: str) -> List[str]:
    mapping = {
        "Revenue": ["Total Revenue", "Revenue"],
        "Gross Profit": ["Gross Profit"],
        "Net Income": ["Net Income", "Net Income From Continuing Ops"],
        "Total Assets": ["Total Assets"],
        "Total Liabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities", "Total Debt"],
        "Cash & Equivalents": [
            "Cash And Cash Equivalents",
            "Cash & Cash Equivalents",
            "Cash And Cash Equivalents At Carrying Value",
        ],
        "Operating Cash Flow": ["Operating Cash Flow", "Net Cash Provided by Operating Activities"],
        "Free Cash Flow": ["Free Cash Flow"],
        "Total Equity": [
            "Total Stockholders Equity",
            "Stockholders Equity",
            "Stockholders' Equity",
            "Total Equity",
        ],
    }
    return mapping.get(metric, [metric])


# This function extracts a metric row from a statement table by trying likely label names.
def _get_metric_series(frame: pd.DataFrame, metric_candidates: List[str]) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)

    for candidate in metric_candidates:
        if candidate in frame.index:
            series = frame.loc[candidate].copy()
            series = series.dropna()
            if not series.empty:
                return series

    return pd.Series(dtype=float)


# This function converts timestamps into FY labels like FY2024.
def _fmt_year_label(value: Any) -> str:
    try:
        return f"FY{pd.Timestamp(value).year}"
    except Exception:
        return str(value)


# This helper selects the appropriate statement row for a financial metric.
def _get_company_metric_series(company: Dict[str, Any], metric: str) -> pd.Series:
    financials = _extract_financials(company)
    income = financials.get("income_statement", pd.DataFrame())
    balance = financials.get("balance_sheet", pd.DataFrame())
    cashflow = financials.get("cash_flow", pd.DataFrame())

    if metric in ["Revenue", "Gross Profit", "Net Income"]:
        return _get_metric_series(income, _metric_candidates(metric))
    if metric in ["Operating Cash Flow", "Free Cash Flow"]:
        return _get_metric_series(cashflow, _metric_candidates(metric))
    if metric in ["Total Assets", "Total Liabilities", "Cash & Equivalents", "Total Equity"]:
        return _get_metric_series(balance, _metric_candidates(metric))
    return pd.Series(dtype=float)


# This helper gets a metric's values for explicitly requested fiscal years.
def _get_company_metric_values_by_year(
    company: Dict[str, Any],
    metric: str,
    target_years: List[int],
) -> Dict[int, float]:
    series = _get_company_metric_series(company, metric)
    values_by_year = {}
    for date, value in series.items():
        try:
            year = pd.Timestamp(date).year
            if year in target_years:
                values_by_year[year] = float(value)
        except (TypeError, ValueError):
            continue
    return values_by_year


def get_common_fiscal_years(
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
) -> List[int]:
    """Return fiscal years represented in both companies' annual statements."""
    def years_for(company: Dict[str, Any]) -> set[int]:
        years = set()
        for frame in _extract_financials(company).values():
            if frame.empty:
                continue
            for value in frame.columns:
                try:
                    years.add(pd.Timestamp(value).year)
                except (TypeError, ValueError):
                    continue
        return years

    return sorted(years_for(company_a) & years_for(company_b))


def get_common_analyst_periods(
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
) -> List[str]:
    """Return analyst snapshot periods available for both companies, newest first."""
    def periods_for(company: Dict[str, Any]) -> set[str]:
        ratings = company.get("ratings")
        if ratings is None or ratings.empty or "period" not in ratings.columns:
            return set()
        return set(ratings["period"].dropna().astype(str))

    common_periods = periods_for(company_a) & periods_for(company_b)

    def months_ago(period: str) -> int:
        try:
            return abs(int(period.removesuffix("m")))
        except ValueError:
            return 10**6

    return sorted(common_periods, key=months_ago)


def analyst_period_label(period: str) -> str:
    """Format an analyst snapshot period for the selector and chart title."""
    months = abs(int(period.removesuffix("m")))
    if months == 0:
        return "Latest snapshot"
    unit = "month" if months == 1 else "months"
    return f"{months} {unit} ago"


# This function compares each company's selected fiscal-year values independently.
def build_core_metrics_table(
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
    years: tuple[int, int] = (2024, 2025),
) -> pd.DataFrame:
    year_a, year_b = years
    if year_a >= year_b:
        raise ValueError("Select two fiscal years in chronological order.")
    target_years = [year_a, year_b]
    year_a_label = f"FY{year_a}"
    year_b_label = f"FY{year_b}"
    rows = []

    for statement, metric in [
        ("Income Statement", "Revenue"),
        ("Income Statement", "Gross Profit"),
        ("Income Statement", "Net Income"),
        ("Balance Sheet", "Total Assets"),
        ("Balance Sheet", "Total Liabilities"),
        ("Balance Sheet", "Cash & Equivalents"),
        ("Cash Flow Statement", "Operating Cash Flow"),
    ]:
        for company in (company_a, company_b):
            values = _get_company_metric_values_by_year(company, metric, target_years)
            value_a = values.get(year_a, np.nan)
            value_b = values.get(year_b, np.nan)

            if pd.isna(value_a) and pd.isna(value_b):
                continue

            abs_change = (
                value_b - value_a
                if pd.notna(value_a) and pd.notna(value_b)
                else np.nan
            )
            growth_pct = (
                (abs_change / value_a) * 100
                if pd.notna(abs_change) and value_a != 0
                else np.nan
            )
            rows.append(
                {
                    "Statement": statement,
                    "Metric": metric,
                    "Company": company["ticker"],
                    year_a_label: value_a,
                    year_b_label: value_b,
                    "Abs_Change": abs_change,
                    "Growth_Pct": growth_pct,
                }
            )

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "Statement",
                "Metric",
                "Company",
                year_a_label,
                year_b_label,
                "Abs_Change",
                "Growth_Pct",
            ]
        )

    return df


# This function builds the grouped bar dataset used by the grouped bar chart.
def build_grouped_bar_dataset(
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
    metric: str,
    years: tuple[int, int] = (2024, 2025),
) -> Dict[str, Any]:
    year_a, year_b = years
    if year_a >= year_b:
        raise ValueError("Select two fiscal years in chronological order.")
    target_years = [year_a, year_b]
    values_a = _get_company_metric_values_by_year(company_a, metric, target_years)
    values_b = _get_company_metric_values_by_year(company_b, metric, target_years)

    if not values_a and not values_b:
        raise ValueError(f"Metric '{metric}' is not available for the selected companies.")

    return {
        "metric": metric,
        "years": [f"FY{year_a}", f"FY{year_b}"],
        "company_a": company_a["ticker"],
        "company_b": company_b["ticker"],
        "series_a": [values_a.get(year, np.nan) for year in target_years],
        "series_b": [values_b.get(year, np.nan) for year in target_years],
    }


# This function normalizes a value into a 0-to-100 score using min-max scaling.
def _normalize(value: Optional[float], ref_min: float, ref_max: float) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    if ref_max == ref_min:
        return 0.0
    score = (value - ref_min) / (ref_max - ref_min) * 100
    return min(100.0, max(0.0, score))


def _average_balance_value(
    company: Dict[str, Any],
    metric: str,
    fiscal_year: int,
) -> Optional[float]:
    values = _get_company_metric_values_by_year(company, metric, [fiscal_year - 1, fiscal_year])
    previous = values.get(fiscal_year - 1)
    current = values.get(fiscal_year)
    if previous is None or current is None:
        return None
    return (previous + current) / 2


# This function calculates actual business-model metrics for one fiscal year.
def _get_company_metric_float(
    company: Dict[str, Any],
    metric: str,
    fiscal_year: int = 2025,
) -> Optional[float]:
    if metric == "Gross Margin":
        revenue = _get_company_metric_values_by_year(company, "Revenue", [fiscal_year]).get(fiscal_year)
        gross_profit = _get_company_metric_values_by_year(company, "Gross Profit", [fiscal_year]).get(fiscal_year)
        if revenue is None or gross_profit is None or revenue == 0:
            return None
        return float(gross_profit / revenue * 100)

    if metric == "ROE":
        net_income = _get_company_metric_values_by_year(company, "Net Income", [fiscal_year]).get(fiscal_year)
        average_equity = _average_balance_value(company, "Total Equity", fiscal_year)
        if net_income is None or average_equity is None or average_equity == 0:
            return None
        return float(net_income / average_equity * 100)

    if metric == "Asset Turnover":
        revenue = _get_company_metric_values_by_year(company, "Revenue", [fiscal_year]).get(fiscal_year)
        average_assets = _average_balance_value(company, "Total Assets", fiscal_year)
        if revenue is None or average_assets is None or average_assets == 0:
            return None
        return float(revenue / average_assets)

    if metric == "Safety Ratio":
        equity = _get_company_metric_values_by_year(company, "Total Equity", [fiscal_year]).get(fiscal_year)
        assets = _get_company_metric_values_by_year(company, "Total Assets", [fiscal_year]).get(fiscal_year)
        if equity is None or assets is None or assets == 0:
            return None
        return float(equity / assets * 100)

    if metric == "FCF Margin":
        fcf = _get_company_metric_values_by_year(company, "Free Cash Flow", [fiscal_year]).get(fiscal_year)
        revenue = _get_company_metric_values_by_year(company, "Revenue", [fiscal_year]).get(fiscal_year)
        if fcf is None or revenue is None or revenue == 0:
            return None
        return float(fcf / revenue * 100)

    if metric == "Revenue Growth":
        revenues = _get_company_metric_values_by_year(company, "Revenue", [fiscal_year - 1, fiscal_year])
        current = revenues.get(fiscal_year)
        prior = revenues.get(fiscal_year - 1)
        if current is None or prior is None or prior == 0:
            return None
        return float((current - prior) / prior * 100)

    return None


# This function builds the normalized radar values used in the business model comparison.
def build_business_model_radar_data(
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
    fiscal_year: int = 2025,
) -> Dict[str, Any]:
    dimensions = [
        ("Gross Margin", 25.0, 85.0, "%", "Gross Profit / Revenue"),
        ("ROE", 5.0, 65.0, "%", "Net Income / Average Shareholders' Equity"),
        ("Asset Turnover", 0.2, 2.5, "x", "Revenue / Average Total Assets"),
        ("Safety Ratio", 10.0, 70.0, "%", "Shareholders' Equity / Total Assets"),
        ("FCF Margin", 5.0, 35.0, "%", "Free Cash Flow / Revenue"),
        (
            "Revenue Growth",
            -5.0,
            25.0,
            "%",
            f"(FY{fiscal_year} Revenue - FY{fiscal_year - 1} Revenue) / FY{fiscal_year - 1} Revenue",
        ),
    ]

    labels = [dimension[0] for dimension in dimensions]
    values_a: List[Optional[float]] = []
    values_b: List[Optional[float]] = []
    actuals_a: List[Optional[float]] = []
    actuals_b: List[Optional[float]] = []
    missing_metrics = []

    for label, ref_min, ref_max, _, _ in dimensions:
        actual_a = _get_company_metric_float(company_a, label, fiscal_year)
        actual_b = _get_company_metric_float(company_b, label, fiscal_year)

        score_a = _normalize(actual_a, ref_min, ref_max)
        score_b = _normalize(actual_b, ref_min, ref_max)
        values_a.append(round(score_a, 1) if score_a is not None else None)
        values_b.append(round(score_b, 1) if score_b is not None else None)
        actuals_a.append(actual_a)
        actuals_b.append(actual_b)

        if actual_a is None:
            missing_metrics.append({"company": company_a["ticker"], "metric": label})
        if actual_b is None:
            missing_metrics.append({"company": company_b["ticker"], "metric": label})

    return {
        "labels": labels,
        "definitions": {dimension[0]: dimension[4] for dimension in dimensions},
        "units": {dimension[0]: dimension[3] for dimension in dimensions},
        "fiscal_year": fiscal_year,
        "company_a": company_a["ticker"],
        "company_b": company_b["ticker"],
        "name_a": company_a.get("name") or company_a["ticker"],
        "name_b": company_b.get("name") or company_b["ticker"],
        "values_a": values_a,
        "values_b": values_b,
        "actuals_a": actuals_a,
        "actuals_b": actuals_b,
        "missing_metrics": missing_metrics,
    }


# This function creates the stacked analyst sentiment data used by the buy-hold-sell chart.
def build_analyst_sentiment_data(
    company_a: Dict[str, Any],
    company_b: Dict[str, Any],
    period: Optional[str] = None,
) -> Dict[str, Any]:
    selected_period = period
    if selected_period is None:
        available_periods = get_common_analyst_periods(company_a, company_b)
        selected_period = available_periods[0] if available_periods else None

    def sentiment_for(company: Dict[str, Any]) -> Dict[str, Any]:
        ratings = company.get("ratings")
        if ratings is None or ratings.empty:
            return {"buy": 0, "hold": 0, "sell": 0, "consensus": "Unknown"}

        if "period" in ratings.columns:
            if selected_period is None:
                latest = ratings.iloc[0]
            else:
                matching = ratings[ratings["period"].astype(str) == selected_period]
                if matching.empty:
                    raise ValueError(
                        f"Analyst ratings for {company['ticker']} are unavailable "
                        f"for {selected_period}."
                    )
                latest = matching.iloc[0]
        else:
            latest = ratings.iloc[-1]
        buy = float(latest.get("strongBuy", 0)) + float(latest.get("buy", 0))
        hold = float(latest.get("hold", 0))
        sell = float(latest.get("sell", 0)) + float(latest.get("strongSell", 0))

        total = buy + hold + sell
        if total == 0:
            consensus = "Unknown"
        else:
            counts = {"buy": buy, "hold": hold, "sell": sell}
            consensus = max(counts, key=counts.get).title()

        return {
            "buy": buy,
            "hold": hold,
            "sell": sell,
            "consensus": consensus,
        }

    return {
        "company_a": company_a["ticker"],
        "company_b": company_b["ticker"],
        "period": selected_period,
        "period_label": (
            analyst_period_label(selected_period)
            if selected_period is not None
            else "Latest snapshot"
        ),
        "a": sentiment_for(company_a),
        "b": sentiment_for(company_b),
    }
