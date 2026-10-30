from datetime import date, datetime

import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from src.dashboard.analysis import collect_company_metrics, collect_financial_statements, load_analysis, parse_tickers, plain_words
from src.dashboard.config import DIALOG_CSS, HISTORY_YEARS, MAX_STOCKS, MAX_UPLOAD_MB, MIN_RANGE_DAYS, OWNER_FILTERS, PAGE_KEY, PDF_HEIGHT, RANGE_OPTIONS, STATEMENTS_PAGE, UPLOAD_TYPES, VISIBILITY_OPTIONS
from src.dashboard.dates import resolve_date_range, years_before
from src.dashboard.financial_statements import selected_statement_ticker
from src.storage import storage
from src.storage.database import DOCUMENT_TYPES, DocumentSearch

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
    
    # Validate the tickers
    tickers, ticker_warnings = parse_tickers(" ".join(selected_tickers))
    for warning in ticker_warnings:
        st.warning(warning)
    if not tickers:
        return
    
    # Validate the date range
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

def _save_current_analysis(store:storage.DocumentStore, user:dict, result:dict, visibility:str) -> None:
    """Build the report for the open page and save it for the signed-in user."""
    now = datetime.now().astimezone()
    if st.session_state.get(PAGE_KEY) == STATEMENTS_PAGE:
        ticker = selected_statement_ticker(result)
        with st.spinner("Collecting financial statements..."):
            financial_statements = collect_financial_statements(ticker)
        
        markdown = storage.make_statements_markdown(financial_statements, ticker, now)
        tickers = [ticker]
        title = f"{ticker} statements"
        analysis_type = "statements"
        date_range = {}
    
    else:
        with st.spinner("Collecting company metrics..."):
            company_metrics = collect_company_metrics(result)
        markdown = storage.make_analysis_markdown(result, plain_words(result), now, company_metrics)
        tickers = [stock["ticker"] for stock in result["stocks"].values()]
        title = " vs ".join(tickers)
        analysis_type = "overview" if result["comparison"] else "single"
        date_range = {"start_date": result["start_date"], "end_date": result["end_date"], "range_label": result["range_label"]}
    
    store.save(user["user_id"], markdown.encode("utf-8"), UPLOAD_TYPES["md"], title, analysis_type, visibility, tickers, now, "md", **date_range)
    st.success(f"Analysis saved as {visibility}.")

def _upload_problem(data:bytes, extension:str) -> str | None:
    """Return why an uploaded file is refused, or None when it can be saved."""
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        return f"Files can be at most {MAX_UPLOAD_MB} MB."
    
    if extension == "pdf" and not data.startswith(b"%PDF-"):
        return "This file is not a valid PDF."
    
    if extension == "md":
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return "Markdown files must be UTF-8 text."
    return None

def _render_upload(store:storage.DocumentStore, user:dict) -> None:
    """Render the Markdown or PDF upload form and save the submitted file."""
    with st.expander("Upload document"):
        with st.form("upload_form", border=False, clear_on_submit=True):
            uploaded = st.file_uploader("Markdown or PDF file", type=list(UPLOAD_TYPES), max_upload_size=MAX_UPLOAD_MB)
            title = st.text_input("Title", placeholder="Defaults to the file name")
            ticker_text = st.text_input("Tickers (optional)", placeholder="AAPL MSFT")
            visibility = st.radio("Visibility", VISIBILITY_OPTIONS, horizontal=True, key="upload_visibility")
            submitted = st.form_submit_button("Upload", use_container_width=True)
        
        if not submitted:
            return
        if uploaded is None:
            st.warning("Choose a file to upload.")
            return
        
        data = uploaded.getvalue()
        extension = uploaded.name.rsplit(".", 1)[-1].lower()
        problem = _upload_problem(data, extension)
        if problem:
            st.error(problem)
            return
        
        tickers = parse_tickers(ticker_text)[0] if ticker_text.strip() else []
        title = title.strip() or uploaded.name.rsplit(".", 1)[0]
        try:
            store.save(user["user_id"], data, UPLOAD_TYPES[extension], title, "upload", visibility.lower(), tickers, datetime.now().astimezone(), extension)
            st.success(f"Uploaded {uploaded.name} as {visibility}.")
        except (OSError, ValueError, SQLAlchemyError) as error:
            st.error(f"Could not upload this file: {error}")

def _render_owner_controls(store:storage.DocumentStore, user:dict, document:dict) -> None:
    """Render visibility and delete controls for a document the signed-in user owns."""
    other_visibility = "public" if document["visibility"] == "private" else "private"
    toggle_column, delete_column = st.columns(2)
    if toggle_column.button(f"Make {other_visibility}", use_container_width=True):
        store.set_visibility(document["document_id"], user["user_id"], other_visibility)
        st.rerun()
    
    if delete_column.button("Delete", use_container_width=True):
        try:
            store.delete(document["document_id"], user["user_id"])
            st.rerun()
        except (OSError, SQLAlchemyError) as error:
            st.error(f"Could not delete this document: {error}")

def _render_admin_controls(store:storage.DocumentStore, user:dict, document:dict) -> None:
    """Render a delete control for an admin viewing a document they do not own."""
    if st.button("Delete (admin)", use_container_width=True):
        try:
            store.delete(document["document_id"], user["user_id"], is_admin=True)
            st.rerun()
        except (OSError, SQLAlchemyError) as error:
            st.error(f"Could not delete this document: {error}")

def _render_search(store:storage.DocumentStore, user_id:int, is_admin:bool) -> DocumentSearch:
    """Render the saved-document search box and filters, returning the search they describe."""
    text = st.text_input("Search", placeholder="Title, file name, ticker or owner", key="document_search")
    with st.expander("Filters"):
        tickers = st.multiselect(
            "Tickers",
            store.list_tickers(user_id, is_admin),
            placeholder="Any ticker",
            key="document_search_tickers",
            help="Only documents covering every selected ticker."
        )
        document_types = st.multiselect("Type", DOCUMENT_TYPES, format_func=str.title, placeholder="Any type", key="document_search_types")
        owner = st.radio("Owner", list(OWNER_FILTERS), horizontal=True, key="document_search_owner")
    return DocumentSearch(text, tuple(tickers), tuple(document_types), OWNER_FILTERS[owner])

def render_saved_analyses(store:storage.DocumentStore, user:dict | None) -> tuple[dict, bytes] | None:
    """Render save, upload and saved-document controls, returning the document and contents to display if one was opened."""
    user_id = user["user_id"] if user else None
    is_admin = bool(user and user.get("is_admin")) #.get: sessions opened before the admin role existed lack the key
    
    # Save the current analysis and upload documents
    result = st.session_state.get("analysis_results")
    if user:
        if result:
            visibility = st.radio("Save as", VISIBILITY_OPTIONS, horizontal=True, key="save_visibility")
            if st.button("Save Analysis", use_container_width=True):
                try:
                    _save_current_analysis(store, user, result, visibility.lower())
                except (OSError, ValueError, SQLAlchemyError) as error:
                    st.error(f"Could not save this analysis: {error}")
        _render_upload(store, user)
    else:
        st.caption("Log in to save analyses, upload documents and see saved analyses.")
        return None
    
    # Search the documents this user may see
    st.subheader("Previous Analyses")
    search = DocumentSearch()
    try:
        search = _render_search(store, user_id, is_admin)
        documents = {document["document_id"]: document for document in store.list_visible(user_id, is_admin, search)}
    except SQLAlchemyError as error:
        documents = {}
        st.error(f"Could not list saved analyses: {error}")
    
    searching = search != DocumentSearch()
    if not documents:
        if searching:
            st.caption("No saved documents match this search.")
        else:
            st.caption("No saved analyses yet. Run an analysis and click Save Analysis to keep it here.")
        return None
    if searching:
        st.caption(f"Matching documents: {len(documents)}")
    
    # Preview and open the selected document
    selected_id = st.selectbox(
        "Saved analyses",
        list(documents),
        format_func=lambda document_id: store.label(documents[document_id]),
        label_visibility="collapsed"
    )
    document = documents[selected_id]
    st.caption(store.details(document))
    opened = None
    if st.button("Show", use_container_width=True):
        try:
            opened = store.read(selected_id, user_id, is_admin)
        except (OSError, ValueError, SQLAlchemyError) as error:
            st.error(f"Could not open this analysis: {error}")
    if user and document["owner_id"] == user_id:
        _render_owner_controls(store, user, document)
    elif is_admin:
        _render_admin_controls(store, user, document)
    return opened

@st.dialog("Previous analysis", width="large")
def show_saved_analysis(document:dict, data:bytes) -> None:
    """Display a saved Markdown or PDF document in a dialog, with a download button."""
    st.markdown(DIALOG_CSS, unsafe_allow_html=True)
    st.download_button("Download", data, file_name=document["filename"], mime=document["content_type"])
    if document["content_type"] == UPLOAD_TYPES["pdf"]:
        st.pdf(data, height=PDF_HEIGHT)
    else:
        st.markdown(data.decode("utf-8"))
