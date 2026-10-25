from datetime import date, datetime

import streamlit as st

from src.dashboard.analysis import collect_company_metrics, load_analysis, parse_tickers, plain_words
from src.dashboard.config import DIALOG_CSS, HISTORY_YEARS, MAX_STOCKS, MIN_RANGE_DAYS, RANGE_OPTIONS
from src.dashboard.dates import resolve_date_range, years_before
from src.data import storage

# Saved analyses
STORE = storage.AnalysisStore()

def render_analysis_form(today:date) -> None:
    """Render the sidebar form and run the requested stock analysis."""
    earliest_date = years_before(today, HISTORY_YEARS)
    
    # Inputs (no form, so the date picker can appear as soon as Custom is selected)
    selected_tickers = st.multiselect(
        "Tickers",
        options=["AAPL"],
        default=["AAPL"],
        accept_new_options=True,
        max_selections=MAX_STOCKS,
        placeholder="Type a ticker and press Enter",
        help=f"Up to {MAX_STOCKS} symbols. One symbol shows a single stock; more compare them."
    )
    range_label = st.selectbox("Time range", [*RANGE_OPTIONS, "Custom"], index=3)
    custom_dates = ()
    if range_label == "Custom":
        custom_dates = st.date_input(
            "Custom range",
            value=(earliest_date, today),
            min_value=earliest_date,
            max_value=today,
            format="YYYY-MM-DD"
        )
    run = st.button("Run", type="primary", use_container_width=True)
    if not run:
        return
    
    # Validate the tickers and date range
    tickers, ticker_warnings = parse_tickers(" ".join(selected_tickers))
    for warning in ticker_warnings:
        st.warning(warning)
    if not tickers:
        return
    date_range = resolve_date_range(range_label, today, custom_dates)
    if date_range is None:
        st.warning("Pick both a start date and an end date.")
        return
    start_date, end_date = date_range
    if start_date >= end_date or (end_date - start_date).days < MIN_RANGE_DAYS:
        st.warning(f"Choose a start date before the end date, at least {MIN_RANGE_DAYS} days apart.")
        return
    
    # Run the analysis
    with st.spinner("Loading prices and news..."):
        result, warnings = load_analysis(tickers, start_date, end_date, range_label)
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
            with st.spinner("Collecting company metrics..."):
                company_metrics = collect_company_metrics(result)
            markdown = storage.make_analysis_markdown(result, plain_words(result), now, company_metrics)
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
