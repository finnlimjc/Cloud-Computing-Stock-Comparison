import argparse
from datetime import date

import streamlit as st

from src.dashboard.auth import render_login
from src.dashboard.company_metrics import show_comparison_dashboard
from src.dashboard.config import LOCAL_DB_PATH, LOCAL_OBJECTS_DIR, PAGE_CSS, PAGE_KEY, PAGE_NAMES, SEED_CREDENTIALS_PATH
from src.dashboard.financial_statements import show_financial_statements
from src.dashboard.performance import render_dashboard
from src.dashboard.sidebar import render_analysis_form, render_saved_analyses, show_saved_analysis
from src.storage.database import Database
from src.storage.object_store import LocalObjectStore
from src.storage.seed import seed_accounts
from src.storage.storage import DocumentStore

def parse_args() -> argparse.Namespace:
    """Read script options passed after `--`, e.g. streamlit run src/app.py -- --local."""
    parser = argparse.ArgumentParser(description="Stock Comparison dashboard")
    parser.add_argument("--local", action="store_true", help="Store users and documents on this computer instead of AWS.")
    args, _ = parser.parse_known_args()
    return args

@st.cache_resource(show_spinner=False)
def open_store(local:bool) -> DocumentStore | None:
    """Open the document store once per server: SQLite and a local folder, or None until AWS storage exists."""
    if not local:
        return None
    LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = DocumentStore(Database(f"sqlite:///{LOCAL_DB_PATH}"), LocalObjectStore(LOCAL_OBJECTS_DIR))
    seed_accounts(store, SEED_CREDENTIALS_PATH)
    return store

def main() -> None:
    """Configure and render the Streamlit dashboard."""
    st.set_page_config(page_title="Stock Comparison", page_icon="📈", layout="wide")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.session_state.setdefault("analysis_results", None) #cache result
    st.session_state.setdefault("user", None)
    
    store = open_store(parse_args().local)
    if store is None:
        st.error("AWS storage is not implemented yet. Run locally with: python -m streamlit run src/app.py -- --local")
        st.stop()
    
    with st.sidebar:
        st.title("Stock Comparison")
        render_analysis_form(date.today())
        st.divider()
        user = render_login(store)
        saved_document = render_saved_analyses(store, user)
        st.caption("For learning only. Not investment advice.")
    
    performance_page, metrics_page, statements_page = st.tabs(PAGE_NAMES, key=PAGE_KEY, on_change="rerun") #tracked so Save Analysis knows the open page
    with performance_page:
        if saved_document is not None:
            show_saved_analysis(*saved_document)
        result = st.session_state.analysis_results
        if result:
            render_dashboard(result)
    with metrics_page:
        show_comparison_dashboard(st.session_state.analysis_results)
    with statements_page:
        show_financial_statements(st.session_state.analysis_results)

if __name__ == "__main__":
    main()
