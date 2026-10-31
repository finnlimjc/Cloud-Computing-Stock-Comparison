import argparse
from datetime import date
from functools import partial

import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import SQLAlchemyError

from src.dashboard.auth import render_login
from src.dashboard.company_metrics import show_comparison_dashboard
from src.dashboard.config import (ALPACA_PARAMETERS, BUCKET_NAME_PARAMETER, DB_HOST_PARAMETER, DB_NAME, DB_PASSWORD_PARAMETER, DB_PORT,
                                  DB_USERNAME_PARAMETER, LOCAL_DB_PATH, LOCAL_OBJECTS_DIR, PAGE_CSS, PAGE_KEY, PAGE_NAMES,
                                  SEED_CREDENTIALS_PATH, SEED_PARAMETER_PREFIX)
from src.dashboard.financial_statements import show_financial_statements
from src.dashboard.performance import render_dashboard
from src.dashboard.sidebar import render_analysis_form, render_saved_analyses, show_saved_analysis
from src.storage.database import Database, postgres_url
from src.storage.object_store import LocalObjectStore, S3ObjectStore
from src.storage.parameters import ParameterStore, use_instance_region
from src.storage.seed import append_credentials, save_to_parameters, seed_accounts
from src.storage.storage import DocumentStore

def parse_args() -> argparse.Namespace:
    """Read script options passed after `--`, e.g. streamlit run src/app.py -- --local."""
    parser = argparse.ArgumentParser(description="Stock Comparison dashboard")
    parser.add_argument("--local", action="store_true", help="Store users and documents on this computer instead of AWS (RDS and S3).")
    args, _ = parser.parse_known_args()
    return args

def open_local_store() -> DocumentStore:
    """Open SQLite and a local folder, writing seed passwords to a gitignored file."""
    LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    store = DocumentStore(Database(f"sqlite:///{LOCAL_DB_PATH}"), LocalObjectStore(LOCAL_OBJECTS_DIR))
    seed_accounts(store, partial(append_credentials, SEED_CREDENTIALS_PATH))
    return store

def open_aws_store() -> DocumentStore:
    """Open RDS PostgreSQL and the S3 bucket named in Parameter Store, loading the Alpaca keys and writing seed passwords there too."""
    use_instance_region()
    parameters = ParameterStore()
    parameters.export_to_environment(ALPACA_PARAMETERS) #news falls back to Yahoo when the keys are missing
    config = parameters.get_many([BUCKET_NAME_PARAMETER, DB_HOST_PARAMETER, DB_USERNAME_PARAMETER, DB_PASSWORD_PARAMETER])
    url = postgres_url(config[DB_HOST_PARAMETER], DB_PORT, DB_NAME, config[DB_USERNAME_PARAMETER], config[DB_PASSWORD_PARAMETER])
    store = DocumentStore(Database(url), S3ObjectStore(config[BUCKET_NAME_PARAMETER]))
    seed_accounts(store, partial(save_to_parameters, parameters, SEED_PARAMETER_PREFIX))
    return store

@st.cache_resource(show_spinner=False)
def open_store(local:bool) -> DocumentStore:
    """Open the document store once per server. A failure is not cached, so the next page load tries again."""
    if local:
        return open_local_store()
    return open_aws_store()

def main() -> None:
    """Configure and render the Streamlit dashboard."""
    st.set_page_config(page_title="Stock Comparison", page_icon="📈", layout="wide")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.session_state.setdefault("analysis_results", None) #cache result
    st.session_state.setdefault("user", None)
    
    try:
        store = open_store(parse_args().local)
    except (ValueError, OSError, BotoCoreError, ClientError, SQLAlchemyError) as error:
        st.error(f"Could not open storage: {error}")
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
