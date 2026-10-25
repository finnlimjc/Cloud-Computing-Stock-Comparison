from typing import Callable, NamedTuple

import numpy as np
import pandas as pd

# Statement line items
METRIC_SOURCES = {
    "Revenue": ("Income Statement", ["Total Revenue", "Revenue"]),
    "Gross Profit": ("Income Statement", ["Gross Profit"]),
    "Net Income": ("Income Statement", ["Net Income", "Net Income From Continuing Ops"]),
    "Total Assets": ("Balance Sheet", ["Total Assets"]),
    "Total Liabilities": (
        "Balance Sheet",
        ["Total Liabilities Net Minority Interest", "Total Liabilities", "Total Debt"]
    ),
    "Cash & Equivalents": (
        "Balance Sheet",
        ["Cash And Cash Equivalents", "Cash & Cash Equivalents", "Cash And Cash Equivalents At Carrying Value"]
    ),
    "Total Equity": (
        "Balance Sheet",
        ["Total Stockholders Equity", "Stockholders Equity", "Stockholders' Equity", "Total Equity"]
    ),
    "Operating Cash Flow": ("Cash Flow", ["Operating Cash Flow", "Net Cash Provided by Operating Activities"]),
    "Free Cash Flow": ("Cash Flow", ["Free Cash Flow"])
}

# Metric history table
USD_PER_BILLION = 1_000_000_000
CAGR_COLUMN = "CAGR"

# Business model radar
MAX_SCORE = 100.0

def _ratio(numerator:float | None, denominator:float | None, scale:float=100.0) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    ratio = float(numerator / denominator * scale)
    return ratio

def _cagr(values:pd.Series) -> float:
    """Compound annual growth in percent between the first and last available years, or NaN when either end is not positive."""
    available = values.dropna()
    if len(available) < 2:
        return np.nan
    first = available.iloc[0]
    last = available.iloc[-1]
    if first <= 0 or last <= 0:
        return np.nan
    n_years = len(values.loc[available.index[0]:available.index[-1]]) - 1
    growth = ((last / first) ** (1 / n_years) - 1) * 100
    return growth

class CompanyFundamentals:
    """
    Annual statement figures and ratios for one company snapshot.
    
    Inputs:
    - company: company snapshot from Company.snapshot, whose financials maps statement names to DataFrames with one column per fiscal year-end
    """
    
    def __init__(self, company:dict) -> None:
        self.company = company
        self.ticker = company["ticker"]
    
    def statement(self, name:str) -> pd.DataFrame:
        """Return one financial statement, or an empty frame when missing."""
        frame = (self.company.get("financials") or {}).get(name)
        statement = pd.DataFrame(dtype="float64") if frame is None else frame
        return statement
    
    def fiscal_years(self) -> set[int]:
        """Return every fiscal year found in the income statement, balance sheet, or cash flow."""
        years = set()
        for name in ("Income Statement", "Balance Sheet", "Cash Flow"):
            for column in self.statement(name).columns:
                try:
                    years.add(pd.Timestamp(column).year)
                except (TypeError, ValueError):
                    continue
        return years
    
    def metric_series(self, metric:str) -> pd.Series:
        """Return the first non-empty statement row among the metric's candidate labels."""
        if metric not in METRIC_SOURCES:
            return pd.Series(dtype="float64")
        statement, candidates = METRIC_SOURCES[metric]
        frame = self.statement(statement)
        for candidate in candidates:
            if candidate in frame.index:
                series = frame.loc[candidate].dropna()
                if not series.empty:
                    return series
        return pd.Series(dtype="float64")
    
    def values_by_year(self, metric:str, target_years:list[int]) -> dict[int, float]:
        """Return the metric's values for the target fiscal years that are available."""
        values_by_year = {}
        for date, value in self.metric_series(metric).items():
            try:
                year = pd.Timestamp(date).year
                if year in target_years:
                    values_by_year[year] = float(value)
            except (TypeError, ValueError):
                continue
        return values_by_year
    
    def value(self, metric:str, year:int) -> float | None:
        """Return the metric's value for one fiscal year, or None when unavailable."""
        value = self.values_by_year(metric, [year]).get(year)
        return value
    
    def average_balance(self, metric:str, year:int) -> float | None:
        """Average the metric's prior and current year-end balances."""
        values = self.values_by_year(metric, [year - 1, year])
        previous = values.get(year - 1)
        current = values.get(year)
        if previous is None or current is None:
            return None
        average = (previous + current) / 2
        return average
    
    def gross_margin(self, year:int) -> float | None:
        """Gross profit as a percentage of revenue."""
        return _ratio(self.value("Gross Profit", year), self.value("Revenue", year))
    
    def return_on_equity(self, year:int) -> float | None:
        """Net income as a percentage of average shareholders' equity."""
        return _ratio(self.value("Net Income", year), self.average_balance("Total Equity", year))
    
    def asset_turnover(self, year:int) -> float | None:
        """Revenue as a multiple of average total assets."""
        return _ratio(self.value("Revenue", year), self.average_balance("Total Assets", year), scale=1.0)
    
    def safety_ratio(self, year:int) -> float | None:
        """Shareholders' equity as a percentage of total assets."""
        return _ratio(self.value("Total Equity", year), self.value("Total Assets", year))
    
    def fcf_margin(self, year:int) -> float | None:
        """Free cash flow as a percentage of revenue."""
        return _ratio(self.value("Free Cash Flow", year), self.value("Revenue", year))
    
    def revenue_growth(self, year:int) -> float | None:
        """Year-over-year revenue growth as a percentage."""
        current = self.value("Revenue", year)
        prior = self.value("Revenue", year - 1)
        if current is None or prior is None:
            return None
        change = current - prior
        growth = _ratio(change, prior)
        return growth

class RadarDimension(NamedTuple):
    """One radar axis: its reference range, unit, formula text, plain-language meaning, and calculation."""
    label:str
    ref_min:float
    ref_max:float
    unit:str
    definition:str
    meaning:str
    calculate:Callable[[CompanyFundamentals, int], float | None]

RADAR_DIMENSIONS = [
    RadarDimension(
        "Gross Margin", 25.0, 85.0, "%", "Gross Profit / Revenue",
        "How much of each dollar of sales is left after the direct cost of making the product or service. Higher suggests pricing power or cheap production.",
        CompanyFundamentals.gross_margin
    ),
    RadarDimension(
        "ROE", 5.0, 65.0, "%", "Net Income / Average Shareholders' Equity",
        "Profit earned for each dollar shareholders have put in. Higher means equity is used more efficiently, though heavy borrowing can also push it up.",
        CompanyFundamentals.return_on_equity
    ),
    RadarDimension(
        "Asset Turnover", 0.2, 2.5, "x", "Revenue / Average Total Assets",
        "Sales generated for each dollar of assets. Higher means the business needs fewer factories, stores or cash to produce its revenue.",
        CompanyFundamentals.asset_turnover
    ),
    RadarDimension(
        "Safety Ratio", 10.0, 70.0, "%", "Shareholders' Equity / Total Assets",
        "Share of the company's assets paid for by shareholders rather than debt. Higher means less reliance on borrowing and more room to absorb losses.",
        CompanyFundamentals.safety_ratio
    ),
    RadarDimension(
        "FCF Margin", 5.0, 35.0, "%", "Free Cash Flow / Revenue",
        "Cash left from each dollar of sales after running the business and paying for new investment. This is what funds dividends, buybacks and debt repayment.",
        CompanyFundamentals.fcf_margin
    ),
    RadarDimension(
        "Revenue Growth", -5.0, 25.0, "%", "(FY{year} Revenue - FY{prior} Revenue) / FY{prior} Revenue",
        "How much sales grew compared with the previous fiscal year.",
        CompanyFundamentals.revenue_growth
    )
]

def _score(actual:float | None, ref_min:float, ref_max:float) -> float | None:
    """Min-max scale an actual value to a 0-100 score."""
    if actual is None or pd.isna(actual):
        return None
    if ref_max == ref_min:
        return 0.0
    raw = (actual - ref_min) / (ref_max - ref_min) * MAX_SCORE
    clipped = min(MAX_SCORE, max(0.0, raw))
    score = round(clipped, 1)
    return score

def get_common_fiscal_years(companies:list[dict]) -> list[int]:
    """Return fiscal years represented in every company's annual statements."""
    year_sets = [CompanyFundamentals(company).fiscal_years() for company in companies]
    common_years = sorted(set.intersection(*year_sets)) if year_sets else []
    return common_years

def build_metric_history(companies:list[dict], metric:str) -> pd.DataFrame:
    """
    Collect one metric for every company across their common fiscal years, in USD billions.
    
    Inputs:
    - companies: company snapshots, each with a usd_rate converting its reporting currency to USD
    - metric: name from METRIC_SOURCES, such as "Revenue"
    
    Outputs:
    - One row per ticker, one FY column per common fiscal year (oldest first), and a CAGR column in percent
    
    Example output:
          FY2022  FY2023  FY2024  FY2025  CAGR
    AAPL   394.3   383.3   391.0   416.2   1.8
    MSFT   198.3   211.9   245.1   281.7  12.4
    """
    fiscal_years = get_common_fiscal_years(companies)
    n_companies = len(companies)
    n_years = len(fiscal_years)
    values = np.full((n_companies, n_years), np.nan, dtype=np.float64)
    for company_idx, company in enumerate(companies):
        values_by_year = CompanyFundamentals(company).values_by_year(metric, fiscal_years)
        usd_billions_per_unit = company["usd_rate"] / USD_PER_BILLION
        for year_idx, year in enumerate(fiscal_years):
            if year in values_by_year:
                values[company_idx, year_idx] = values_by_year[year] * usd_billions_per_unit
    
    tickers = [company["ticker"] for company in companies]
    history = pd.DataFrame(values, index=tickers, columns=[f"FY{year}" for year in fiscal_years], dtype="float64")
    history[CAGR_COLUMN] = history.apply(_cagr, axis=1).astype("float64")
    return history

def default_score_ranges() -> dict[str, tuple[float, float]]:
    """Return each radar dimension's default (low, high) reference values."""
    return {dimension.label: (dimension.ref_min, dimension.ref_max) for dimension in RADAR_DIMENSIONS}

def build_business_model_radar_data(companies:list[dict], fiscal_year:int, ranges:dict[str, tuple[float, float]] | None=None) -> dict:
    """Build normalized business-model scores and actual values for every company.
    
    Inputs:
    - companies: company snapshots
    - fiscal_year: fiscal year to evaluate
    - ranges: optional (low, high) reference values keyed by dimension label, scoring 0 and 100; missing labels use the defaults
    
    Outputs:
    - Radar labels, definitions, units, the fiscal year, metrics missing for any company, and per-company tickers, names, scores and actual values
    """
    # Actual values and scores
    score_ranges = default_score_ranges() | (ranges or {})
    radar_companies = []
    for company in companies:
        fundamentals = CompanyFundamentals(company)
        actuals = [dimension.calculate(fundamentals, fiscal_year) for dimension in RADAR_DIMENSIONS]
        radar_companies.append(
            {
                "ticker": company["ticker"],
                "name": company.get("name") or company["ticker"],
                "scores": [_score(actual, *score_ranges[dimension.label]) for actual, dimension in zip(actuals, RADAR_DIMENSIONS)],
                "actuals": actuals
            }
        )
    
    # Gaps
    missing_metrics = [
        {"company": radar_company["ticker"], "metric": dimension.label}
        for dimension_idx, dimension in enumerate(RADAR_DIMENSIONS)
        for radar_company in radar_companies
        if radar_company["actuals"][dimension_idx] is None
    ]
    
    radar_data = {
        "labels": [dimension.label for dimension in RADAR_DIMENSIONS],
        "definitions": {
            dimension.label: dimension.definition.format(year=fiscal_year, prior=fiscal_year - 1)
            for dimension in RADAR_DIMENSIONS
        },
        "units": {dimension.label: dimension.unit for dimension in RADAR_DIMENSIONS},
        "fiscal_year": fiscal_year,
        "companies": radar_companies,
        "missing_metrics": missing_metrics
    }
    return radar_data
