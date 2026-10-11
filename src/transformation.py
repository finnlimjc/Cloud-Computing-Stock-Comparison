import pandas as pd

def compute_drawdown(prices:pd.Series) -> pd.Series:
    """Returns the drawdown from the running peak as a fraction (0 at a peak, -0.25 = 25% below it)."""
    running_peak = prices.cummax()
    drawdown = prices / running_peak - 1
    drawdown.name = "Drawdown"
    return drawdown

def _markdown_link(text:str, url:str) -> str:
    escaped = text.replace("[", "\\[").replace("]", "\\]") #brackets in a headline would end the link text early
    link = f"[{escaped}]({url})"
    return link

def format_alpaca_news(articles:list) -> pd.DataFrame:
    """
    Converts raw Alpaca news articles into display rows for Streamlit.
    
    Inputs:
    - articles: output of input_data.get_alpaca_news
    
    Outputs:
    - DataFrame with 'Date' (YYYY-MM-DD), 'Title' (markdown hyperlink) and 'Summary' columns
    """
    dates = pd.to_datetime([article["created_at"] for article in articles]).strftime("%Y-%m-%d")
    titles = [_markdown_link(article["headline"], article["url"]) for article in articles]
    summaries = [article.get("summary") or "No summary" for article in articles]
    news = pd.DataFrame({"Date":dates, "Title":titles, "Summary":summaries}, dtype="object")
    return news