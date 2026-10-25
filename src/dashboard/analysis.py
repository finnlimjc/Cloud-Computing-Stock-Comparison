import re
from datetime import date
from string import ascii_uppercase

import pandas as pd
import requests
from yfinance.exceptions import YFException

from src.analysis import analyst, fundamentals, statements, transformation
from src.dashboard.config import COMPARISON_METRICS, MAX_STOCKS, STATEMENT_OTHER_NOTE, STATEMENT_TALLY_NOTES, STATEMENT_UNITS_NOTE, VALUATION_HELP
from src.dashboard.loaders import load_company_snapshot, load_news, load_prices
from src.data import price_ratings

# Company metrics
COMPACT_UNITS = ((1e12, "T"), (1e9, "B"), (1e6, "M"))

# Financial statements
UNITS_PER_MILLION = 1_000_000
MISSING_VALUE = "—"
MARKDOWN_INDENT = "&nbsp;&nbsp;&nbsp;&nbsp;"

def parse_tickers(text:str) -> tuple[list[str], list[str]]:
    """Split comma- or space-separated symbols into unique upper-case tickers, capped at MAX_STOCKS.
    
    Inputs:
    - text: user-entered ticker symbols
    
    Outputs:
    - Tickers in entry order and warnings about dropped entries
    """
    tickers = list(dict.fromkeys(re.split(r"[,\s]+", text.upper().strip())))
    tickers = [ticker for ticker in tickers if ticker]
    warnings = []
    if not tickers:
        warnings.append("Please enter a ticker symbol.")
    if len(tickers) > MAX_STOCKS:
        warnings.append(f"Only the first {MAX_STOCKS} tickers are used; ignored {', '.join(tickers[MAX_STOCKS:])}.")
    return tickers[:MAX_STOCKS], warnings

def analyze_ticker(role:str, ticker_input:str, start_date:date, end_date:date) -> tuple[dict | None, str | None]:
    """Load and summarize one stock's price history.
    
    Inputs:
    - role: letter for the stock's slot in the comparison ("A" for the first ticker, "B" for the second, ...), used to look up its color
    - ticker_input: user-entered symbol
    - start_date: inclusive first date
    - end_date: inclusive last date
    
    Outputs:
    - Stock analysis and optional warning
    """
    label = ticker_input.strip().upper()
    try:
        ticker = price_ratings.clean_ticker(ticker_input)
        prices = load_prices(ticker, start_date, end_date).dropna()
        if prices.empty:
            raise ValueError("No price history found.")
        stock = {
            "role": role,
            "ticker": ticker,
            "prices": prices,
            "metrics": transformation.summarize_prices(prices)
        }
        return stock, None
    except (ValueError, KeyError) as error:
        return None, f"{label}: {error}"
    except (YFException, requests.RequestException, OSError) as error:
        return None, f"{label}: data could not be loaded ({error})"

def news_timestamp(article:dict) -> int:
    """Return an article's UTC timestamp as a sort key, or zero when invalid."""
    timestamp = pd.to_datetime(article["created_at"], utc=True, errors="coerce")
    sort_key = int(timestamp.value) if not pd.isna(timestamp) else 0
    return sort_key

def collect_news(stocks:dict) -> tuple[list[dict], str]:
    """Collect recent articles for the loaded stocks, newest first, with a combined error message."""
    articles = []
    errors = []
    for stock in stocks.values():
        try:
            for article in load_news(stock["ticker"]):
                articles.append(
                    {
                        "role": stock["role"],
                        "ticker": stock["ticker"],
                        "created_at": article.get("created_at", ""),
                        "headline": article.get("headline", "No headline"),
                        "url": article.get("url", ""),
                        "summary": article.get("summary") or ""
                    }
                )
        except (requests.RequestException, OSError, ValueError, KeyError, TypeError) as error:
            errors.append(f"{stock['ticker']}: {error}")
    articles.sort(key=news_timestamp, reverse=True)
    error_message = "; ".join(errors)
    return articles, error_message

def load_analysis(tickers:list[str], start_date:date, end_date:date, range_label:str) -> tuple[dict, list[str]]:
    """Load available stock analyses and their news.
    
    Each ticker is assigned a role by entry position: "A" for the first, "B" for the second, and so on.
    Roles key the result's stocks and their colors, so a ticker that fails to load is skipped
    without changing the roles of the others.
    
    Inputs:
    - tickers: unique user-entered symbols, at most MAX_STOCKS
    - start_date: inclusive first date
    - end_date: inclusive last date
    - range_label: selected quick-range option
    
    Outputs:
    - Analysis result and ticker warnings
    """
    # Analyze each ticker where ascii_uppercase is the role "A", "B"
    stocks = {}
    warnings = []
    for role, ticker_input in zip(ascii_uppercase, tickers):
        stock, warning = analyze_ticker(role, ticker_input, start_date, end_date)
        if stock:
            stocks[role] = stock
        if warning:
            warnings.append(warning)
    if not stocks:
        return {}, warnings
    
    # Align a comparison on shared history
    if len(stocks) > 1:
        aligned = transformation.common_start_prices({role: stock["prices"] for role, stock in stocks.items()})
        if any(prices.empty for prices in aligned.values()):
            warnings.append("The selected stocks have no overlapping price history; showing the first stock only.")
            first_role = next(iter(stocks))
            stocks = {first_role: stocks[first_role]}
        else:
            for role, stock in stocks.items():
                stock["prices"] = aligned[role]
                stock["metrics"] = transformation.summarize_prices(stock["prices"])
    
    # Recorded after alignment so the end-of-range close matches the trimmed series
    for stock in stocks.values():
        stock["price_at_end_range"] = float(stock["prices"].iloc[-1])
        stock["price_at_end_date"] = stock["prices"].index[-1].date()
    
    # Assemble the result
    articles, news_error = collect_news(stocks)
    result = {
        "stocks": stocks,
        "start_date": start_date,
        "end_date": end_date,
        "range_label": range_label,
        "comparison": len(stocks) > 1,
        "news": articles,
        "news_error": news_error,
        "n_requested": len(tickers)
    }
    return result, warnings

def plain_words(result:dict) -> str:
    """Create a plain-language comparison or single-stock summary of the loaded data."""
    stocks = result["stocks"]
    range_label = result["range_label"]
    if range_label == "Custom":
        range_label = f"{result['start_date']:%Y-%m-%d} to {result['end_date']:%Y-%m-%d}"
    if not result["comparison"]:
        stock = next(iter(stocks.values()))
        summary = transformation.plain_words_single(stock["ticker"], stock["prices"], range_label)
        return summary
    
    ordered = list(stocks.values())
    tickers = [stock["ticker"] for stock in ordered]
    returns = {stock["ticker"]: stock["metrics"]["Return over period"] for stock in ordered}
    volatilities = {stock["ticker"]: stock["metrics"]["Average volatility"] for stock in ordered}
    drawdowns = {stock["ticker"]: stock["metrics"]["Max drawdown"] for stock in ordered}
    summary = transformation.plain_words_comparison(tickers, returns, volatilities, drawdowns, range_label)
    return summary

def load_company_snapshots(result:dict) -> tuple[list[dict], list[str]]:
    """Load the company snapshot for each analysed stock, skipping tickers that fail with a warning each."""
    snapshots = []
    warnings = []
    for stock in result["stocks"].values():
        try:
            snapshots.append(load_company_snapshot(stock["ticker"]))
        except (ValueError, KeyError, YFException, requests.RequestException, OSError) as error:
            warnings.append(f"{stock['ticker']}: company data could not be loaded ({error})")
    return snapshots, warnings

def rated_companies(snapshots:list[dict]) -> list[dict]:
    """Return the snapshots that have analyst ratings."""
    return [snapshot for snapshot in snapshots if not analyst.AnalystRatings(snapshot).is_empty]

def valuation_text(name:str, value:float | None, currency:str) -> str:
    """Format a valuation figure: market cap as 5.07T USD, dividend yield as 0.31%, and multiples as 39.9x."""
    if value is None or pd.isna(value):
        return "N/A"
    if name == "Market cap":
        threshold, suffix = next(((threshold, suffix) for threshold, suffix in COMPACT_UNITS if abs(value) >= threshold), (1, ""))
        compact = f"{value / threshold:,.2f}{suffix} {currency}".strip()
        return compact
    if name == "Dividend yield":
        return f"{value:.2f}%"
    return f"{value:.1f}x"

def format_statement_value(value:float, unit:str) -> str:
    """Format a statement figure in accounting style: millions, two-decimal per-share figures or percentages, with negatives in brackets."""
    if pd.isna(value):
        return MISSING_VALUE
    if unit == "per_share":
        text = f"{abs(value):,.2f}"
    elif unit == "ratio":
        text = f"{abs(value) * 100:.1f}%"
    else:
        text = f"{abs(value) / UNITS_PER_MILLION:,.0f}"
    if value < 0:
        return f"({text})"
    return text

def statement_units_note(snapshot:dict) -> str:
    """Describe the units of a company's statements, naming its reporting currency when known."""
    currency = snapshot.get("financial_currency") or "Reporting currency" #older cached snapshots lack the field
    return STATEMENT_UNITS_NOTE.format(currency=currency)

def _markdown_statement_row(row:dict) -> list[str]:
    """Markdown cells for one statement row: indented items, bold subtotal labels, and bold totals."""
    cells = [format_statement_value(value, row["unit"]) for value in row["values"]]
    if row["style"] == "item":
        return [MARKDOWN_INDENT + row["label"]] + cells
    if row["style"] == "subtotal":
        return [f"**{row['label']}**"] + cells
    return [f"**{row['label']}**"] + [f"**{cell}**" for cell in cells]

def collect_financial_statements(ticker:str) -> dict:
    """
    Build the saved-report tables for one company's financial statements.
    
    Inputs:
    - ticker: company selected on the Financial Statements tab
    
    Outputs:
    - Company title, a units note, notes on how the figures tally, and per statement a main section and a section of Yahoo's remaining line items, each with headers and rows of formatted cells; sections is empty and the note says why when nothing can be shown
    """
    try:
        snapshot = load_company_snapshot(ticker)
    except (ValueError, KeyError, YFException, requests.RequestException, OSError) as error:
        return {"title": ticker, "note": f"Financial statements could not be loaded ({error}).", "tally_notes": [], "sections": []}
    title = f"{snapshot['name']} ({ticker})"
    period_ends = statements.statement_fiscal_years(snapshot)
    if not period_ends:
        return {"title": title, "note": "Yahoo Finance has no annual statements for this company.", "tally_notes": [], "sections": []}
    
    headers = ["Line item"] + [f"FY{period_end.year}" for period_end in period_ends]
    sections = []
    for name in statements.STATEMENT_NAMES:
        statement = statements.build_statement(snapshot, name, period_ends)
        rows = []
        for section in statement["sections"]:
            rows.append([f"**{section['title'].upper()}**"] + [""] * len(period_ends))
            rows.extend(_markdown_statement_row(row) for row in section["rows"])
        if rows:
            sections.append({"title": name, "note": "", "headers": headers, "rows": rows})
        if statement["other"]:
            other_rows = [
                [row["label"]] + [format_statement_value(value, row["unit"]) for value in row["values"]]
                for row in statement["other"]
            ]
            sections.append({"title": f"{name}: other line items", "note": STATEMENT_OTHER_NOTE, "headers": headers, "rows": other_rows})
    return {"title": title, "note": statement_units_note(snapshot), "tally_notes": STATEMENT_TALLY_NOTES, "sections": sections}

def _count_with_percent(count:float, total:float) -> str:
    percent = count / total * 100 if total else 0.0
    return f"{int(count)} ({percent:.1f}%)"

def _financials_section(snapshots:list[dict]) -> dict | None:
    """Latest common fiscal year value and CAGR of each comparison metric, one column per ticker."""
    fiscal_years = fundamentals.get_common_fiscal_years(snapshots)
    if not fiscal_years:
        return None
    tickers = [snapshot["ticker"] for snapshot in snapshots]
    latest_column = f"FY{fiscal_years[-1]}"
    rows = []
    for metric in COMPARISON_METRICS:
        history = fundamentals.build_metric_history(snapshots, metric)
        cells = []
        for ticker in tickers:
            value = history.loc[ticker, latest_column]
            cagr = history.loc[ticker, fundamentals.CAGR_COLUMN]
            cell = "N/A" if pd.isna(value) else f"{value:,.4f}"
            if pd.notna(cagr):
                cell += f" ({cagr:+.1f}% CAGR)"
            cells.append(cell)
        rows.append([metric] + cells)
    section = {
        "title": f"Financials ({latest_column}, USD billions)",
        "note": f"CAGR is the compound annual growth from each company's first available year up to FY{fiscal_years[-1]}, left out when either end is not positive.",
        "headers": ["Metric"] + tickers,
        "rows": rows
    }
    return section

def _business_model_section(snapshots:list[dict]) -> dict | None:
    """Actual business-model ratios for the latest common fiscal year, one column per ticker."""
    fiscal_years = fundamentals.get_common_fiscal_years(snapshots)
    if not fiscal_years:
        return None
    radar_data = fundamentals.build_business_model_radar_data(snapshots, fiscal_years[-1])
    rows = []
    for label_idx, label in enumerate(radar_data["labels"]):
        unit = radar_data["units"][label]
        cells = [
            "N/A" if company["actuals"][label_idx] is None else f"{company['actuals'][label_idx]:.1f}{unit}"
            for company in radar_data["companies"]
        ]
        rows.append([label] + cells)
    section = {
        "title": f"Business model (FY{radar_data['fiscal_year']})",
        "note": "",
        "headers": ["Metric"] + [company["ticker"] for company in radar_data["companies"]],
        "rows": rows
    }
    return section

def _sentiment_section(snapshots:list[dict]) -> dict | None:
    """Latest analyst buy, hold and sell counts with their shares, total and consensus."""
    rated = rated_companies(snapshots)
    if not rated:
        return None
    sentiment_data = analyst.build_analyst_sentiment_data(rated)
    rows = [
        [
            sentiment["ticker"],
            sentiment["consensus"],
            _count_with_percent(sentiment["buy"], sentiment["total"]),
            _count_with_percent(sentiment["hold"], sentiment["total"]),
            _count_with_percent(sentiment["sell"], sentiment["total"]),
            str(int(sentiment["total"]))
        ]
        for sentiment in sentiment_data["companies"]
    ]
    section = {
        "title": f"Analyst sentiment ({sentiment_data['period_label']})",
        "note": "",
        "headers": ["Ticker", "Consensus", "Buy", "Hold", "Sell", "Total analysts"],
        "rows": rows
    }
    return section

def _price_targets_section(snapshots:list[dict]) -> dict | None:
    """Analyst price targets in each listing currency, with the median's distance from the current price."""
    targets = analyst.build_price_targets(snapshots)
    if not targets:
        return None
    rows = [
        [target["ticker"], target["currency"]]
        + [f"{target[key]:,.2f}" for key in ("current", "low", "median", "mean", "high")]
        + [f"{target['median_pct']:+.1f}%"]
        for target in targets
    ]
    section = {
        "title": "Analyst price targets",
        "note": "",
        "headers": ["Ticker", "Currency", "Current", "Low", "Median", "Mean", "High", "Median vs current"],
        "rows": rows
    }
    return section

def collect_company_metrics(result:dict) -> dict:
    """
    Build the saved-report tables for the Company Metrics tab.
    
    Inputs:
    - result: dashboard analysis result, whose stocks give the tickers to load
    
    Outputs:
    - Sections, each with a title, note, headers and rows of formatted cells, plus a note naming tickers that could not be loaded
    
    Example output:
    {
        "sections": [{"title": "Valuation", "note": "", "headers": ["Ticker", "Market cap", ...], "rows": [["AAPL", "5.07T USD", ...]]}],
        "note": "XYZ: company data could not be loaded (...)"
    }
    """
    snapshots, warnings = load_company_snapshots(result)
    if not snapshots:
        return {"sections": [], "note": "; ".join(warnings) or "Company data was unavailable."}
    
    valuation_rows = [
        [snapshot["ticker"]] + [valuation_text(name, snapshot["valuation"][name], snapshot["valuation"]["Currency"]) for name in VALUATION_HELP]
        for snapshot in snapshots
    ]
    sections = [{"title": "Valuation", "note": "", "headers": ["Ticker"] + list(VALUATION_HELP), "rows": valuation_rows}]
    for build_section in (_financials_section, _business_model_section, _sentiment_section, _price_targets_section):
        section = build_section(snapshots)
        if section is not None:
            sections.append(section)
    return {"sections": sections, "note": "; ".join(warnings)}
