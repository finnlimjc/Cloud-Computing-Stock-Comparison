import streamlit as st

from src import input_data, metrics, plots

ANALYSIS_TYPES = ["filings", "news", "stock price ratings", "price drawdown"]

def show_filings(ticker:str) -> None:
    """Display the income statement, balance sheet and cash flow."""
    statements = input_data.get_financials(ticker)
    st.subheader(f"Financial statements for {input_data.clean_ticker(ticker)}")
    for name, df in statements.items():
        st.write(f"**{name}**")
        if df is None or df.empty:
            st.write("No data available.")
        else:
            st.dataframe(df)

def show_news(ticker:str) -> None:
    """Display the latest news headlines."""
    articles = input_data.get_news(ticker)
    st.subheader(f"Latest news for {input_data.clean_ticker(ticker)}")
    for article_num, article in enumerate(articles, 1):
        st.write(f"**{article_num}. {article['title']}**")
        st.write(article["description"])

def show_drawdown(ticker:str) -> None:
    """Display the linked price and drawdown chart with the max drawdown."""
    prices = input_data.get_price_history(ticker)
    drawdown = metrics.compute_drawdown(prices)
    clean = input_data.clean_ticker(ticker)
    st.subheader(f"Price and Drawdown for {clean}")
    fig = plots.plot_price_drawdown(prices, drawdown, clean)
    st.plotly_chart(fig, use_container_width=True)
    st.metric("Max drawdown", f"{drawdown.min():.2%}")

def show_ratings(ticker:str) -> None:
    """Display the current price and analyst recommendations."""
    price = input_data.get_price(ticker)
    ratings = input_data.get_analyst_ratings(ticker)
    st.subheader(f"Price and ratings for {input_data.clean_ticker(ticker)}")
    st.metric("Current price", f"{price:,.2f}")
    st.write("**Analyst recommendations**")
    st.dataframe(ratings)

def run_analysis(ticker:str, analysis_type:str) -> None:
    """Dispatch to the selected analysis, showing errors in the UI."""
    try:
        with st.spinner("Fetching data from Yahoo Finance..."):
            if analysis_type == "filings":
                show_filings(ticker)
            elif analysis_type == "news":
                show_news(ticker)
            elif analysis_type == "price drawdown":
                show_drawdown(ticker)
            else:  # stock price ratings
                show_ratings(ticker)
    
    except ValueError as e:
        # Expected problems: empty input, no data found
        st.warning(str(e))
    except Exception as e:
        # Anything else: network issues, invalid ticker, Yahoo errors
        st.error(f"Something went wrong: {e}")

def main() -> None:
    st.set_page_config(page_title="Stock Analysis", page_icon="📈")
    st.title("📈 Stock Analysis")
    
    ticker = st.text_input("Ticker symbol", value="MU", placeholder="e.g. MU, GOOG, AAPL")
    analysis_type = st.selectbox("Analysis type", ANALYSIS_TYPES)
    if st.button("Run"):
        run_analysis(ticker, analysis_type)

if __name__ == "__main__":
    main()