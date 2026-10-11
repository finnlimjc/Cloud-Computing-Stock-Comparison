import streamlit as st
from src import input_data, plots, transformation

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

if __name__ == "__main__":
    main()
