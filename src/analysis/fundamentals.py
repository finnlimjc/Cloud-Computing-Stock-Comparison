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

# Core metrics table
CORE_METRICS = [
    ("Income Statement", "Revenue"),
    ("Income Statement", "Gross Profit"),
    ("Income Statement", "Net Income"),
    ("Balance Sheet", "Total Assets"),
    ("Balance Sheet", "Total Liabilities"),
    ("Balance Sheet", "Cash & Equivalents"),
    ("Cash Flow Statement", "Operating Cash Flow")
]
DEFAULT_YEARS = (2024, 2025)

# Business model radar
DEFAULT_FISCAL_YEAR = 2025
MAX_SCORE = 100.0

def _ratio(numerator:float | None, denominator:float | None, scale:float=100.0) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    ratio = float(numerator / denominator * scale)
    return ratio

def _validate_years(years:tuple[int, int]) -> None:
    if years[0] >= years[1]:
        raise ValueError("Select two fiscal years in chronological order.")

class CompanyFundamentals:
    '''Annual statement figures and ratios for one company snapshot.'''
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
    '''One radar axis: its reference range, unit, formula text, and calculation.'''
    
    label:str
    ref_min:float
    ref_max:float
    unit:str
    definition:str
    calculate:Callable[[CompanyFundamentals, int], float | None]

RADAR_DIMENSIONS = [
    RadarDimension("Gross Margin", 25.0, 85.0, "%", "Gross Profit / Revenue", CompanyFundamentals.gross_margin),
    RadarDimension("ROE", 5.0, 65.0, "%", "Net Income / Average Shareholders' Equity", CompanyFundamentals.return_on_equity),
    RadarDimension("Asset Turnover", 0.2, 2.5, "x", "Revenue / Average Total Assets", CompanyFundamentals.asset_turnover),
    RadarDimension("Safety Ratio", 10.0, 70.0, "%", "Shareholders' Equity / Total Assets", CompanyFundamentals.safety_ratio),
    RadarDimension("FCF Margin", 5.0, 35.0, "%", "Free Cash Flow / Revenue", CompanyFundamentals.fcf_margin),
    RadarDimension(
        "Revenue Growth", -5.0, 25.0, "%",
        "(FY{year} Revenue - FY{prior} Revenue) / FY{prior} Revenue", CompanyFundamentals.revenue_growth
    )
]

def _score(actual:float | None, dimension:RadarDimension) -> float | None:
    """Min-max scale an actual value to a 0-100 score."""
    if actual is None or pd.isna(actual):
        return None
    if dimension.ref_max == dimension.ref_min:
        return 0.0
    raw = (actual - dimension.ref_min) / (dimension.ref_max - dimension.ref_min) * MAX_SCORE
    clipped = min(MAX_SCORE, max(0.0, raw))
    score = round(clipped, 1)
    return score

def get_common_fiscal_years(company_a:dict, company_b:dict) -> list[int]:
    """Return fiscal years represented in both companies' annual statements."""
    common_years = sorted(CompanyFundamentals(company_a).fiscal_years() & CompanyFundamentals(company_b).fiscal_years())
    return common_years

def build_core_metrics_table(company_a:dict, company_b:dict, years:tuple[int, int]=DEFAULT_YEARS) -> pd.DataFrame:
    """Compare each company's values between two fiscal years.
    
    Inputs:
    - company_a: first company snapshot
    - company_b: second company snapshot
    - years: earlier and later fiscal years
    
    Outputs:
    - One row per company and metric with both years, absolute change, and growth percentage
    """
    _validate_years(years)
    year_a, year_b = years
    label_a, label_b = f"FY{year_a}", f"FY{year_b}"
    companies = [CompanyFundamentals(company_a), CompanyFundamentals(company_b)]
    
    # One row per company and metric
    rows = []
    for statement, metric in CORE_METRICS:
        for company in companies:
            values = company.values_by_year(metric, [year_a, year_b])
            value_a = values.get(year_a, np.nan)
            value_b = values.get(year_b, np.nan)
            if pd.isna(value_a) and pd.isna(value_b):
                continue
            
            abs_change = value_b - value_a
            growth_pct = abs_change / value_a * 100 if pd.notna(abs_change) and value_a != 0 else np.nan
            rows.append(
                {
                    "Statement": statement,
                    "Metric": metric,
                    "Company": company.ticker,
                    label_a: value_a,
                    label_b: value_b,
                    "Abs_Change": abs_change,
                    "Growth_Pct": growth_pct
                }
            )
    
    columns = ["Statement", "Metric", "Company", label_a, label_b, "Abs_Change", "Growth_Pct"]
    metrics = pd.DataFrame(rows, columns=columns, dtype="object")
    numeric_columns = [label_a, label_b, "Abs_Change", "Growth_Pct"]
    metrics[numeric_columns] = metrics[numeric_columns].astype("float64")
    return metrics

def build_grouped_bar_dataset(company_a:dict, company_b:dict, metric:str, years:tuple[int, int]=DEFAULT_YEARS) -> dict:
    """Collect one metric's values for both companies across two fiscal years."""
    _validate_years(years)
    values_a = CompanyFundamentals(company_a).values_by_year(metric, list(years))
    values_b = CompanyFundamentals(company_b).values_by_year(metric, list(years))
    if not values_a and not values_b:
        raise ValueError(f"Metric '{metric}' is not available for the selected companies.")
    dataset = {
        "metric": metric,
        "years": [f"FY{year}" for year in years],
        "company_a": company_a["ticker"],
        "company_b": company_b["ticker"],
        "series_a": [values_a.get(year, np.nan) for year in years],
        "series_b": [values_b.get(year, np.nan) for year in years]
    }
    return dataset

def build_business_model_radar_data(company_a:dict, company_b:dict, fiscal_year:int=DEFAULT_FISCAL_YEAR) -> dict:
    """Build normalized business-model scores and actual values for both companies.
    
    Inputs:
    - company_a: first company snapshot
    - company_b: second company snapshot
    - fiscal_year: fiscal year to evaluate
    
    Outputs:
    - Radar labels, definitions, units, scores, actual values, and metrics missing for either company
    """
    fundamentals_a = CompanyFundamentals(company_a)
    fundamentals_b = CompanyFundamentals(company_b)
    
    # Actual values and gaps
    actuals_a = [dimension.calculate(fundamentals_a, fiscal_year) for dimension in RADAR_DIMENSIONS]
    actuals_b = [dimension.calculate(fundamentals_b, fiscal_year) for dimension in RADAR_DIMENSIONS]
    missing_metrics = [
        {"company": company.ticker, "metric": dimension.label}
        for dimension, actual_a, actual_b in zip(RADAR_DIMENSIONS, actuals_a, actuals_b)
        for company, actual in ((fundamentals_a, actual_a), (fundamentals_b, actual_b))
        if actual is None
    ]
    
    # Scores
    radar_data = {
        "labels": [dimension.label for dimension in RADAR_DIMENSIONS],
        "definitions": {
            dimension.label: dimension.definition.format(year=fiscal_year, prior=fiscal_year - 1)
            for dimension in RADAR_DIMENSIONS
        },
        "units": {dimension.label: dimension.unit for dimension in RADAR_DIMENSIONS},
        "fiscal_year": fiscal_year,
        "company_a": company_a["ticker"],
        "company_b": company_b["ticker"],
        "name_a": company_a.get("name") or company_a["ticker"],
        "name_b": company_b.get("name") or company_b["ticker"],
        "values_a": [_score(actual, dimension) for actual, dimension in zip(actuals_a, RADAR_DIMENSIONS)],
        "values_b": [_score(actual, dimension) for actual, dimension in zip(actuals_b, RADAR_DIMENSIONS)],
        "actuals_a": actuals_a,
        "actuals_b": actuals_b,
        "missing_metrics": missing_metrics
    }
    return radar_data
