"""Streamlit UI. Run with:  streamlit run app.py"""

import streamlit as st

from src import analysis

st.set_page_config(page_title="Stock Analysis", page_icon="📈")
st.title("📈 Stock Analysis")

ticker = st.text_input("Ticker symbol", value="MU", placeholder="e.g. MU, GOOG, AAPL")
analysis_type = st.selectbox(
    "Analysis type", ["filings", "news", "stock price ratings"]
)

if st.button("Run"):
    try:
        with st.spinner("Fetching data from Yahoo Finance..."):
            if analysis_type == "filings":
                statements = analysis.get_financials(ticker)
                st.subheader(f"Financial statements for {ticker.strip().upper()}")
                for name, df in statements.items():
                    st.write(f"**{name}**")
                    if df is None or df.empty:
                        st.write("No data available.")
                    else:
                        st.dataframe(df)

            elif analysis_type == "news":
                articles = analysis.get_news(ticker)
                st.subheader(f"Latest news for {ticker.strip().upper()}")
                for i, article in enumerate(articles, 1):
                    st.write(f"**{i}. {article['title']}**")
                    st.write(article["description"])

            else:  # stock price ratings
                price = analysis.get_price(ticker)
                ratings = analysis.get_analyst_ratings(ticker)
                st.subheader(f"Price and ratings for {ticker.strip().upper()}")
                st.metric("Current price (USD)", f"{price:,.2f}")
                st.write("**Analyst recommendations**")
                st.dataframe(ratings)

    except ValueError as e:
        # Expected problems: empty input, no data found
        st.warning(str(e))
    except Exception as e:
        # Anything else: network issues, invalid ticker, Yahoo errors
        st.error(f"Something went wrong: {e}")
