from datetime import date, datetime

import streamlit as st

from src.dashboard.analysis import load_analysis, plain_words
from src.dashboard.config import DIALOG_CSS, HISTORY_YEARS, MIN_RANGE_DAYS, MONTHS, RANGE_OPTIONS
from src.dashboard.dates import resolve_date_range, years_before
from src.data import storage

# Saved analyses
STORE = storage.AnalysisStore()

def render_analysis_form(today:date) -> None:
    """Render the sidebar form and run the requested stock analysis."""
    earliest_date = years_before(today, HISTORY_YEARS)
    available_years = list(range(earliest_date.year, today.year + 1))
    
    # Form inputs
    with st.form("stock_analysis_form"):
        ticker_a = st.text_input("Stock A", value="AAPL")
        ticker_b = st.text_input("Stock B (optional)", value="", help="Leave empty to look at one stock.")
        range_label = st.selectbox("Time range", [*RANGE_OPTIONS, "Custom"], index=3)
        
        year_column, month_column, day_column = st.columns(3)
        start_year = year_column.selectbox("Start year", available_years, index=0, key="custom_start_year")
        start_month = month_column.selectbox("Start month", MONTHS, index=earliest_date.month - 1, key="custom_start_month")
        start_day = day_column.selectbox("Start day", range(1, 32), index=earliest_date.day - 1, key="custom_start_day")
        
        year_column, month_column, day_column = st.columns(3)
        end_year = year_column.selectbox("End year", available_years, index=len(available_years) - 1, key="custom_end_year")
        end_month = month_column.selectbox("End month", MONTHS, index=today.month - 1, key="custom_end_month")
        end_day = day_column.selectbox("End day", range(1, 32), index=today.day - 1, key="custom_end_day")
        
        run = st.form_submit_button("Run", type="primary", use_container_width=True)
    if not run:
        return
    
    # Validate the date range
    start_date, end_date, notices = resolve_date_range(
        range_label,
        today,
        (start_year, start_month, start_day),
        (end_year, end_month, end_day)
    )
    for notice in notices:
        st.info(notice)
    if start_date >= end_date or (end_date - start_date).days < MIN_RANGE_DAYS:
        st.warning(f"Choose a start date before the end date, at least {MIN_RANGE_DAYS} days apart.")
        return
    
    # Run the analysis
    with st.spinner("Loading prices and news..."):
        result, warnings = load_analysis(ticker_a, ticker_b, start_date, end_date, range_label)
    for warning in warnings:
        st.warning(warning)
    if result:
        st.session_state.analysis_results = result
    else:
        st.error("No valid stock price data was found. Check the ticker symbols and try again.")

def render_saved_analyses() -> str | None:
    """Render save and previous-analysis controls, returning the report to display if one was opened."""
    # Save the current analysis
    result = st.session_state.get("analysis_results")
    if result and st.button("Save Analysis", use_container_width=True):
        try:
            now = datetime.now().astimezone()
            markdown = storage.make_analysis_markdown(result, plain_words(result), now)
            tickers = [stock["ticker"] for stock in result["stocks"].values()]
            analysis_type = "overview" if result["comparison"] else "single"
            saved_path = STORE.save(markdown, tickers, analysis_type, now)
            st.success(f"Analysis saved: {saved_path.name}")
        except (OSError, ValueError) as error:
            st.error(f"Could not save this analysis: {error}")
    
    # List previous analyses
    st.subheader("Previous Analyses")
    try:
        saved_files = STORE.list_saved()
    except OSError as error:
        saved_files = []
        st.error(f"Could not list saved analyses: {error}")
    if not saved_files:
        st.caption("No saved analyses yet. Run an analysis and click Save Analysis to keep it here.")
        return None
    
    # Preview and open the selected analysis
    selected_path = st.selectbox("Saved analyses", saved_files, format_func=STORE.label, label_visibility="collapsed")
    try:
        st.caption(STORE.details(STORE.read(selected_path)))
    except (OSError, ValueError) as error:
        st.error(f"Could not read saved analysis details: {error}")
    if st.button("Show", use_container_width=True):
        try:
            return STORE.read(selected_path)
        except (OSError, ValueError) as error:
            st.error(f"Could not open this analysis: {error}")
    return None

@st.dialog("Previous analysis", width="large")
def show_saved_analysis(markdown:str) -> None:
    """Display a saved Markdown analysis in a dialog."""
    st.markdown(DIALOG_CSS, unsafe_allow_html=True)
    st.markdown(markdown)
