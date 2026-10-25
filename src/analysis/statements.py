from typing import NamedTuple

import numpy as np
import pandas as pd

from src.analysis.fundamentals import CompanyFundamentals

STATEMENT_NAMES = ["Income Statement", "Balance Sheet", "Cash Flow"]

# Row units, read from the Yahoo key so unlisted rows are scaled correctly too
PER_SHARE_MARKERS = ["EPS", "Per Share"]
SHARE_COUNT_MARKERS = ["Shares", "Share Issued"]
RATIO_KEYS = ["Tax Rate For Calcs"]

class TemplateRow(NamedTuple):
    """One statement line: its display label, the Yahoo keys it accepts in order of preference, and its emphasis (item, subtotal or total)."""
    label:str
    keys:list[str]
    style:str="item"

# Yahoo uses the same standardised keys for every company; companies differ only in which keys they report
STATEMENT_TEMPLATES = {
    "Income Statement": [
        ("Revenue", [
            TemplateRow("Total revenue", ["Total Revenue", "Operating Revenue"], "subtotal"),
            TemplateRow("Cost of revenue", ["Cost Of Revenue", "Reconciled Cost Of Revenue"]),
            TemplateRow("Gross profit", ["Gross Profit"], "total")
        ]),
        ("Operating expenses", [
            TemplateRow("Research & development", ["Research And Development"]),
            TemplateRow("Selling, general & administrative", ["Selling General And Administration"]),
            TemplateRow("Depreciation & amortisation", ["Depreciation Amortization Depletion Income Statement", "Depreciation And Amortization In Income Statement"]),
            TemplateRow("Other operating expenses", ["Other Operating Expenses"]),
            TemplateRow("Total operating expenses", ["Operating Expense"], "subtotal"),
            TemplateRow("Operating income", ["Operating Income"], "total")
        ]),
        ("Non-operating items", [
            TemplateRow("Interest income", ["Interest Income Non Operating", "Interest Income"]),
            TemplateRow("Interest expense", ["Interest Expense Non Operating", "Interest Expense"]),
            TemplateRow("Other non-operating income", ["Other Non Operating Income Expenses"]),
            TemplateRow("Unusual items", ["Total Unusual Items", "Special Income Charges"]),
            TemplateRow("Pretax income", ["Pretax Income"], "subtotal"),
            TemplateRow("Income tax", ["Tax Provision"]),
            TemplateRow("Minority interests", ["Minority Interests"]),
            TemplateRow("Net income", ["Net Income", "Net Income Common Stockholders"], "total")
        ]),
        ("Per share", [
            TemplateRow("Basic EPS", ["Basic EPS"]),
            TemplateRow("Diluted EPS", ["Diluted EPS"]),
            TemplateRow("Basic weighted shares", ["Basic Average Shares"]),
            TemplateRow("Diluted weighted shares", ["Diluted Average Shares"])
        ]),
        ("Supplemental", [
            TemplateRow("EBIT", ["EBIT"]),
            TemplateRow("EBITDA", ["EBITDA", "Normalized EBITDA"]),
            TemplateRow("Depreciation & amortisation (total)", ["Reconciled Depreciation"]),
            TemplateRow("Tax rate", ["Tax Rate For Calcs"])
        ])
    ],
    "Balance Sheet": [
        ("Current assets", [
            TemplateRow("Cash & cash equivalents", ["Cash And Cash Equivalents", "Cash Cash Equivalents And Federal Funds Sold"]),
            TemplateRow("Short-term investments", ["Other Short Term Investments"]),
            TemplateRow("Cash & short-term investments", ["Cash Cash Equivalents And Short Term Investments"], "subtotal"),
            TemplateRow("Receivables", ["Receivables", "Accounts Receivable"]),
            TemplateRow("Inventory", ["Inventory"]),
            TemplateRow("Prepaid assets", ["Prepaid Assets"]),
            TemplateRow("Other current assets", ["Other Current Assets"]),
            TemplateRow("Total current assets", ["Current Assets"], "subtotal")
        ]),
        ("Non-current assets", [
            TemplateRow("Property, plant & equipment", ["Net PPE"]),
            TemplateRow("Goodwill", ["Goodwill"]),
            TemplateRow("Other intangible assets", ["Other Intangible Assets"]),
            TemplateRow("Long-term investments", ["Investments And Advances", "Long Term Equity Investment"]),
            TemplateRow("Loans", ["Net Loan"]),
            TemplateRow("Deferred tax assets", ["Non Current Deferred Taxes Assets", "Non Current Deferred Assets"]),
            TemplateRow("Other non-current assets", ["Other Non Current Assets"]),
            TemplateRow("Total non-current assets", ["Total Non Current Assets"], "subtotal"),
            TemplateRow("Total assets", ["Total Assets"], "total")
        ]),
        ("Current liabilities", [
            TemplateRow("Accounts payable", ["Accounts Payable", "Payables"]),
            TemplateRow("Accrued expenses", ["Current Accrued Expenses"]),
            TemplateRow("Income tax payable", ["Income Tax Payable", "Total Tax Payable"]),
            TemplateRow("Short-term debt", ["Current Debt", "Current Debt And Capital Lease Obligation"]),
            TemplateRow("Deferred revenue", ["Current Deferred Revenue", "Current Deferred Liabilities"]),
            TemplateRow("Other current liabilities", ["Other Current Liabilities"]),
            TemplateRow("Total current liabilities", ["Current Liabilities"], "subtotal")
        ]),
        ("Non-current liabilities", [
            TemplateRow("Long-term debt", ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]),
            TemplateRow("Long-term lease obligations", ["Long Term Capital Lease Obligation"]),
            TemplateRow("Non-current deferred revenue", ["Non Current Deferred Revenue"]),
            TemplateRow("Deferred tax liabilities", ["Non Current Deferred Taxes Liabilities"]),
            TemplateRow("Other non-current liabilities", ["Other Non Current Liabilities"]),
            TemplateRow("Total non-current liabilities", ["Total Non Current Liabilities Net Minority Interest"], "subtotal"),
            TemplateRow("Total liabilities", ["Total Liabilities Net Minority Interest"], "total")
        ]),
        ("Equity", [
            TemplateRow("Preferred stock", ["Preferred Stock"]),
            TemplateRow("Common stock", ["Common Stock"]),
            TemplateRow("Additional paid-in capital", ["Additional Paid In Capital"]),
            TemplateRow("Retained earnings", ["Retained Earnings"]),
            TemplateRow("Treasury stock", ["Treasury Stock"]),
            TemplateRow("Accumulated other comprehensive income", ["Gains Losses Not Affecting Retained Earnings"]),
            TemplateRow("Shareholders' equity", ["Stockholders Equity", "Common Stock Equity"], "subtotal"),
            TemplateRow("Minority interest", ["Minority Interest"]),
            TemplateRow("Total equity", ["Total Equity Gross Minority Interest"], "total")
        ]),
        ("Supplemental", [
            TemplateRow("Total debt", ["Total Debt"]),
            TemplateRow("Net debt", ["Net Debt"]),
            TemplateRow("Working capital", ["Working Capital"]),
            TemplateRow("Shares outstanding", ["Ordinary Shares Number", "Share Issued"])
        ])
    ],
    "Cash Flow": [
        ("Operating activities", [
            TemplateRow("Net income", ["Net Income From Continuing Operations"]),
            TemplateRow("Depreciation & amortisation", ["Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation"]),
            TemplateRow("Stock-based compensation", ["Stock Based Compensation"]),
            TemplateRow("Deferred taxes", ["Deferred Tax", "Deferred Income Tax"]),
            TemplateRow("Other non-cash items", ["Other Non Cash Items"]),
            TemplateRow("Change in working capital", ["Change In Working Capital"]),
            TemplateRow("Cash from operating activities", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], "total")
        ]),
        ("Investing activities", [
            TemplateRow("Capital expenditure", ["Capital Expenditure", "Purchase Of PPE"]),
            TemplateRow("Acquisitions", ["Net Business Purchase And Sale", "Purchase Of Business"]),
            TemplateRow("Investments, net", ["Net Investment Purchase And Sale"]),
            TemplateRow("Other investing", ["Net Other Investing Changes"]),
            TemplateRow("Cash from investing activities", ["Investing Cash Flow", "Cash Flow From Continuing Investing Activities"], "total")
        ]),
        ("Financing activities", [
            TemplateRow("Debt issued (repaid), net", ["Net Issuance Payments Of Debt"]),
            TemplateRow("Share repurchases", ["Repurchase Of Capital Stock", "Common Stock Payments"]),
            TemplateRow("Share issuance", ["Issuance Of Capital Stock", "Common Stock Issuance"]),
            TemplateRow("Dividends paid", ["Cash Dividends Paid", "Common Stock Dividend Paid"]),
            TemplateRow("Other financing", ["Net Other Financing Charges"]),
            TemplateRow("Cash from financing activities", ["Financing Cash Flow", "Cash Flow From Continuing Financing Activities"], "total")
        ]),
        ("Cash position", [
            TemplateRow("Beginning cash", ["Beginning Cash Position"]),
            TemplateRow("Net change in cash", ["Changes In Cash"]),
            TemplateRow("Exchange rate effect", ["Effect Of Exchange Rate Changes"]),
            TemplateRow("Ending cash", ["End Cash Position"], "total")
        ]),
        ("Supplemental", [
            TemplateRow("Free cash flow", ["Free Cash Flow"], "subtotal"),
            TemplateRow("Interest paid", ["Interest Paid Supplemental Data"]),
            TemplateRow("Income taxes paid", ["Income Tax Paid Supplemental Data"])
        ])
    ]
}

def row_unit(key:str) -> str:
    """Classify a Yahoo key as per_share, shares, ratio or currency."""
    if key in RATIO_KEYS:
        return "ratio"
    if any(marker in key for marker in PER_SHARE_MARKERS):
        return "per_share"
    if any(marker in key for marker in SHARE_COUNT_MARKERS):
        return "shares"
    return "currency"

def _period_end_columns(frame:pd.DataFrame) -> pd.DatetimeIndex:
    return pd.to_datetime(frame.columns, errors="coerce")

def statement_fiscal_years(company:dict) -> list[pd.Timestamp]:
    """Return the latest period-end date of every fiscal year found in any of the three statements, oldest first."""
    fundamentals = CompanyFundamentals(company)
    period_ends = {}
    for name in STATEMENT_NAMES:
        for period_end in _period_end_columns(fundamentals.statement(name)).dropna():
            period_ends[period_end.year] = max(period_end, period_ends.get(period_end.year, period_end))
    return [period_ends[year] for year in sorted(period_ends)]

def _yearly_values(frame:pd.DataFrame, years:list[int]) -> pd.DataFrame:
    """Statement rows re-keyed by fiscal year and aligned to the given years, dropping rows with no figure in any of them."""
    if frame.empty:
        return pd.DataFrame(dtype="float64", columns=years)
    yearly = frame.astype("float64")
    yearly.columns = _period_end_columns(frame).year
    yearly = yearly.loc[:, ~yearly.columns.duplicated()] #a 53-week year can repeat a fiscal year; keep Yahoo's newest
    aligned = yearly.reindex(columns=years).dropna(how="all")
    return aligned

def build_statement(company:dict, name:str, period_ends:list[pd.Timestamp]) -> dict:
    """
    Lay out one financial statement in reporting order using the statement template.
    
    Inputs:
    - company: company snapshot
    - name: statement name from STATEMENT_NAMES
    - period_ends: fiscal year-end dates from statement_fiscal_years, shared by all three statements so their columns align
    
    Outputs:
    - Template sections holding only rows with data, and the remaining Yahoo rows with data under other, in top-down order
    
    Example output:
    {
        "sections": [{"title": "Revenue", "rows": [{"label": "Total revenue", "style": "subtotal", "unit": "currency", "values": array([...])}]}],
        "other": [{"label": "Total Expenses", "style": "item", "unit": "currency", "values": array([...])}]
    }
    """
    years = [period_end.year for period_end in period_ends]
    aligned = _yearly_values(CompanyFundamentals(company).statement(name), years)
    
    # Template rows
    used_keys = set()
    sections = []
    for title, template_rows in STATEMENT_TEMPLATES[name]:
        rows = []
        for template_row in template_rows:
            used_keys.update(template_row.keys) #aliases of a matched row are duplicates, not extra items
            key = next((key for key in template_row.keys if key in aligned.index), None)
            if key is None:
                continue
            rows.append(
                {
                    "label": template_row.label,
                    "style": template_row.style,
                    "unit": row_unit(key),
                    "values": aligned.loc[key].to_numpy(dtype=np.float64)
                }
            )
        if rows:
            sections.append({"title": title, "rows": rows})
    
    # Yahoo lists rows bottom-up, so reverse them to read like a statement
    other = [
        {"label": key, "style": "item", "unit": row_unit(key), "values": aligned.loc[key].to_numpy(dtype=np.float64)}
        for key in aligned.index[::-1]
        if key not in used_keys
    ]
    return {"sections": sections, "other": other}
