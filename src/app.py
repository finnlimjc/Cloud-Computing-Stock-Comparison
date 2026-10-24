from datetime import date

import streamlit as st

from src.dashboard.company_metrics import show_comparison_dashboard
from src.dashboard.config import PAGE_CSS
from src.dashboard.performance import render_dashboard
from src.dashboard.sidebar import render_analysis_form, render_saved_analyses, show_saved_analysis

def main() -> None:
    """Configure and render the Streamlit dashboard."""
    st.set_page_config(page_title="Stock Comparison", page_icon="📈", layout="wide")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.session_state.setdefault("analysis_results", None) #cache result
    
    with st.sidebar:
        st.title("Stock Comparison")
        render_analysis_form(date.today())
        saved_report = render_saved_analyses()
        st.caption("For learning only. Not investment advice.")
    
    performance_page, metrics_page = st.tabs(["Stock Performance", "Company Metrics"])
    with performance_page:
        if saved_report is not None:
            show_saved_analysis(saved_report)
        result = st.session_state.analysis_results
        if result:
            render_dashboard(result)
    with metrics_page:
        show_comparison_dashboard()

if __name__ == "__main__":
    main()
