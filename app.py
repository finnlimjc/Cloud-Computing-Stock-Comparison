from datetime import datetime
from pathlib import Path
import re

import streamlit as st
from src import input_data, plots, storage, transformation

ANALYSIS_TYPES = ["filings", "news", "stock price ratings", "price"]
THIRTY_MINUTES = 1800

@st.cache_data(ttl=THIRTY_MINUTES, show_spinner=False) #exceptions are not cached, so failed lookups are retried
def load_data(ticker:str, analysis_type:str) -> object:
    """Download the data for the selected analysis. This is the only place the ticker is used."""
    if analysis_type == "filings":
        data = input_data.get_financials(ticker)
    elif analysis_type == "news":
        data = input_data.get_alpaca_news(ticker, limit=5)
    elif analysis_type == "price":
        data = input_data.get_price_history(ticker)
    else:  # stock price ratings
        data = {"price":input_data.get_price(ticker), "ratings":input_data.get_analyst_ratings(ticker)}
    return data

def show_filings(statements:dict, ticker:str) -> None:
    """Display the income statement, balance sheet and cash flow."""
    st.subheader(f"Financial statements for {ticker}")
    for name, df in statements.items():
        st.write(f"**{name}**")
        if df is None or df.empty:
            st.write("No data available.")
        else:
            st.dataframe(df)

def show_news(articles:list, ticker:str) -> None:
    """Display the latest news as date, hyperlinked title and summary."""
    news = transformation.format_alpaca_news(articles)
    st.subheader(f"Latest news for {ticker}")
    for article in news.itertuples():
        st.markdown(f"**{article.Date}** · {article.Title}")
        st.write(article.Summary)

def show_price_drawdown(prices:object, ticker:str) -> None:
    """Display the linked price and drawdown chart with the max drawdown."""
    drawdown = transformation.compute_drawdown(prices)
    st.subheader(f"Price and Drawdown for {ticker}")
    fig = plots.plot_price_drawdown(prices, drawdown, ticker)
    st.plotly_chart(fig, use_container_width=True)
    st.metric("Max drawdown", f"{drawdown.min():.2%}")

def show_ratings(data:dict, ticker:str) -> None:
    """Display the current price and analyst recommendations."""
    st.subheader(f"Price and ratings for {ticker}")
    st.metric("Current price", f"{data['price']:,.2f}")
    st.write("**Analyst recommendations**")
    st.dataframe(data["ratings"])

def _append_dataframe(lines:list[str], title:str, dataframe:object) -> None:
    """Append a titled DataFrame as a readable Markdown code block.

    Inputs:
    - lines: report lines being assembled
    - title: section title
    - dataframe: table to add to the report

    Outputs:
    - None
    """
    # This part adds the section title and handles missing table data.
    lines.extend([f"## {title}", ""])
    if dataframe is None or dataframe.empty:
        lines.extend(["No data available.", ""])
        return
    # This part adds the table in a dependency-free text format.
    lines.extend(["```text", dataframe.to_string(), "```", ""])

def make_analysis_markdown(ticker:str, analysis_type:str, data:object, created_at:datetime) -> str:
    """Build a Markdown report for the selected stock analysis.

    Inputs:
    - ticker: analyzed stock symbol
    - analysis_type: selected analysis type
    - data: result returned by the selected data loader
    - created_at: report creation time

    Outputs:
    - Complete Markdown report
    """
    # This part creates report metadata for the selected ticker and analysis.
    lines = [
        f"# {ticker} {analysis_type.title()}",
        "",
        f"- Ticker: {ticker}",
        f"- Analysis type: {analysis_type}",
        f"- Created: {created_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "",
    ]
    # This part adds the fetched result for the selected analysis type.
    if analysis_type == "filings":
        for name, dataframe in data.items():
            _append_dataframe(lines, name, dataframe)
    elif analysis_type == "news":
        articles = transformation.format_alpaca_news(data)
        lines.extend(["## Latest news", ""])
        for article in articles.itertuples():
            lines.extend([f"### {article.Title}", "", f"Date: {article.Date}", "", article.Summary, ""])
    elif analysis_type == "price":
        drawdown = transformation.compute_drawdown(data)
        lines.extend(["## Price and drawdown", "", f"Max drawdown: {drawdown.min():.2%}", ""])
        _append_dataframe(lines, "Daily closing prices", data.to_frame(name="Close"))
    else:
        lines.extend(["## Current price", "", f"{data['price']:,.2f}", ""])
        _append_dataframe(lines, "Analyst recommendations", data["ratings"])
    # This part returns the report as a newline-terminated Markdown document.
    return "\n".join(lines) + "\n"

def analysis_label(path:Path) -> str:
    """Create a readable label for a saved analysis path.

    Inputs:
    - path: saved report path

    Outputs:
    - Human-readable analysis label
    """
    # This part extracts the ticker and timestamp from the filename.
    match = re.fullmatch(r"(.+)_single_(\d{8}-\d{6})(?:_\d+)?", path.stem)
    if match:
        ticker, timestamp = match.groups()
        created = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
        # This part formats the filename timestamp for the dropdown.
        date_format = "%d %b %H:%M" if created.year == datetime.now().year else "%d %b %Y %H:%M"
        return f"{ticker} · {created.strftime(date_format)}"
    return path.stem

@st.dialog("Previous analysis", width="large")
def show_saved_analysis(markdown:str) -> None:
    """Display a saved Markdown analysis in a dialog.

    Inputs:
    - markdown: saved analysis report

    Outputs:
    - None
    """
    # This part displays the saved report content.
    st.markdown(markdown)

def render_saved_analyses() -> str | None:
    """Render controls for saving and opening previous analyses.

    Inputs:
    - None

    Outputs:
    - Selected saved report to display, if requested
    """
    # This part saves the latest successfully rendered analysis when requested.
    analysis = st.session_state.get("analysis_to_save")
    if analysis and st.button("Save Analysis"):
        try:
            now = datetime.now().astimezone()
            markdown = make_analysis_markdown(analysis["ticker"], analysis["analysis_type"], analysis["data"], now)
            saved_path = storage.save_analysis(markdown, [analysis["ticker"]], "single", now)
            st.success(f"Analysis saved: {saved_path.name}")
        except (OSError, ValueError) as error:
            st.error(f"Could not save this analysis: {error}")
    # This part lists saved reports and handles storage errors.
    st.subheader("Previous Analyses")
    try:
        saved_files = storage.list_analyses()
    except OSError as error:
        saved_files = []
        st.error(f"Could not list saved analyses: {error}")
    # This part returns the selected report when Show is clicked.
    if saved_files:
        selected_path = st.selectbox("Saved analyses", saved_files, format_func=analysis_label, label_visibility="collapsed")
        if st.button("Show"):
            try:
                return storage.read_analysis(selected_path)
            except (OSError, ValueError) as error:
                st.error(f"Could not open this analysis: {error}")
    else:
        st.caption("No saved analyses yet. Run an analysis and click Save Analysis to keep it here.")
    return None

def run_analysis(ticker:str, analysis_type:str) -> None:
    """Dispatch to the selected analysis, showing errors in the UI."""
    try:
        clean = input_data.clean_ticker(ticker)
        with st.spinner("Fetching data..."):
            data = load_data(clean, analysis_type)
        
        if analysis_type == "filings":
            show_filings(data, clean)
        
        elif analysis_type == "news":
            show_news(data, clean)
        
        elif analysis_type == "price":
            show_price_drawdown(data, clean)
        
        else:  # stock price ratings
            show_ratings(data, clean)
        st.session_state.analysis_to_save = {"ticker":clean, "analysis_type":analysis_type, "data":data}
    
    except ValueError as e:
        # Expected problems: empty input, no data found
        st.warning(str(e))
    except Exception as e:
        # Anything else: network issues, invalid ticker, API errors
        st.error(f"Something went wrong: {e}")

def main() -> None:
    st.set_page_config(page_title="Stock Analysis", page_icon="📈")
    st.title("📈 Stock Analysis")

    with st.sidebar:
        ticker = st.text_input("Ticker symbol", value="MU", placeholder="e.g. MU, GOOG, AAPL")
        analysis_type = st.selectbox("Analysis type", ANALYSIS_TYPES)
        run = st.button("Run")
    if run:
        run_analysis(ticker, analysis_type)
    with st.sidebar:
        saved_analysis = render_saved_analyses()
    if saved_analysis is not None:
        show_saved_analysis(saved_analysis)

if __name__ == "__main__":
    main()
