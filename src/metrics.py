import pandas as pd

def compute_drawdown(prices:pd.Series) -> pd.Series:
    """Returns the drawdown from the running peak as a fraction (0 at a peak, -0.25 = 25% below it)."""
    running_peak = prices.cummax()
    drawdown = prices / running_peak - 1
    drawdown.name = "Drawdown"
    return drawdown
