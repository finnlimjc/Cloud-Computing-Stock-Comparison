from html import escape

import pandas as pd
import streamlit as st

from src.analysis import statements
from src.dashboard.analysis import format_statement_value, load_company_snapshots, statement_units_note

# Layout
LABEL_WIDTH_PCT = 40
COMPANY_KEY = "statements_company_{tickers}"

def statements_company_key(result:dict) -> str:
    """Session-state key of the company pills, built from the analysed tickers so the sidebar can read the selection."""
    tickers = [stock["ticker"] for stock in result["stocks"].values()]
    return COMPANY_KEY.format(tickers="_".join(tickers)) #options change with every analysis

def selected_statement_ticker(result:dict) -> str:
    """Return the company picked on the Financial Statements tab, or the first analysed ticker before any pick."""
    tickers = [stock["ticker"] for stock in result["stocks"].values()]
    selected = st.session_state.get(statements_company_key(result))
    if selected in tickers:
        return selected
    return tickers[0]

def _row_html(row:dict) -> str:
    cells = "".join(f"<td>{format_statement_value(value, row['unit'])}</td>" for value in row["values"])
    return f'<tr class="fs-{row["style"]}"><td>{escape(row["label"])}</td>{cells}</tr>'

def statement_html(sections:list[dict], period_ends:list[pd.Timestamp], units:str) -> str:
    """
    Build a statement table whose columns line up with every other statement table.
    
    Inputs:
    - sections: titled groups of rows from statements.build_statement; an empty title adds no section row
    - period_ends: fiscal year-end dates shared by all three statements
    - units: label for the top-left header cell, such as "USD millions"
    
    Outputs:
    - HTML table with a fixed-width label column and one equal-width column per fiscal year
    """
    n_years = len(period_ends)
    year_width = (100 - LABEL_WIDTH_PCT) / n_years
    columns = f'<col style="width:{LABEL_WIDTH_PCT}%">' + f'<col style="width:{year_width:.3f}%">' * n_years
    header = f"<th>{escape(units)}</th>" + "".join(
        f'<th>FY{period_end.year}<span class="fs-date">{period_end:%b %Y}</span></th>' for period_end in period_ends
    )
    
    body = []
    for section in sections:
        if section["title"]:
            body.append(f'<tr class="fs-section"><td colspan="{n_years + 1}">{escape(section["title"])}</td></tr>')
        body.extend(_row_html(row) for row in section["rows"])
    table = (
        f'<div class="fs-scroll"><table class="fs-table"><colgroup>{columns}</colgroup>'
        f'<thead><tr>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )
    return table

def render_statement(snapshot:dict, name:str, period_ends:list[pd.Timestamp]) -> None:
    """Render one financial statement card with its template rows and an expander for Yahoo's remaining line items."""
    with st.container(border=True, key=f"statement_card_{name.lower().replace(' ', '_')}"):
        st.subheader(name, anchor=False)
        statement = statements.build_statement(snapshot, name, period_ends)
        if not statement["sections"] and not statement["other"]:
            st.info(f"Yahoo Finance has no {name.lower()} for {snapshot['ticker']}.")
            return
        
        currency = snapshot.get("financial_currency") or "Reporting currency"
        units = f"{currency} millions"
        if statement["sections"]:
            st.markdown(statement_html(statement["sections"], period_ends, units), unsafe_allow_html=True)
        if statement["other"]:
            with st.expander(f"Other line items ({len(statement['other'])})"):
                st.markdown(statement_html([{"title": "", "rows": statement["other"]}], period_ends, units), unsafe_allow_html=True)

def show_financial_statements(result:dict | None) -> None:
    """Render the Financial Statements tab: the three statements of one company, chosen with pills when several were analysed."""
    if not result:
        st.info("Run an analysis in the sidebar to see financial statements.")
        return
    
    with st.spinner("Loading financial statements..."):
        snapshots, warnings = load_company_snapshots(result)
    for warning in warnings:
        st.warning(warning)
    if not snapshots:
        return
    
    # Company picker
    tickers = [snapshot["ticker"] for snapshot in snapshots]
    selected = tickers[0]
    if len(tickers) > 1:
        selected = st.pills(
            "Company",
            tickers,
            selection_mode="single",
            default=tickers[0],
            label_visibility="collapsed",
            key=statements_company_key(result)
        ) or tickers[0] #pills can be deselected
    snapshot = next(snapshot for snapshot in snapshots if snapshot["ticker"] == selected)
    
    # Statements
    st.title(f"{snapshot['name']} ({selected})", anchor=False)
    st.caption(f"Annual statements from Yahoo Finance. {statement_units_note(snapshot)}")
    period_ends = statements.statement_fiscal_years(snapshot)
    if not period_ends:
        st.info(f"Yahoo Finance has no annual statements for {selected}.")
        return
    for name in statements.STATEMENT_NAMES:
        render_statement(snapshot, name, period_ends)
