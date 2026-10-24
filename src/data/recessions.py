import logging
from io import StringIO

import pandas as pd
import requests

LOGGER = logging.getLogger(__name__)

# FRED download
FRED_USREC_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=USREC"
REQUEST_TIMEOUT_SECONDS = 10

# Fallback and labelling
KNOWN_RECESSIONS = (
    ("2008 Financial Crisis", "2007-12-01", "2009-06-30"),
    ("COVID-19", "2020-02-01", "2020-04-30")
)

def known_recession_periods() -> list[dict]:
    """Return known US recession periods used when FRED is unavailable."""
    periods = [
        {"start": pd.Timestamp(start), "end": pd.Timestamp(end), "label": label}
        for label, start, end in KNOWN_RECESSIONS
    ]
    return periods

def _label_for(start:pd.Timestamp, end:pd.Timestamp) -> str:
    for label, known_start, known_end in KNOWN_RECESSIONS:
        if start <= pd.Timestamp(known_end) and end >= pd.Timestamp(known_start):
            return label
    return ""

def periods_from_series(recessions:pd.Series) -> list[dict]:
    """Convert monthly USREC observations into inclusive monthly date ranges.
    
    Inputs:
    - recessions: monthly recession indicator series
    
    Outputs:
    - Recession periods with start, end, and label fields
    """
    observations = recessions.dropna().sort_index()
    active = observations == 1
    group_ids = active.ne(active.shift(fill_value=False)).cumsum()
    
    periods = []
    for _, group in observations[active].groupby(group_ids[active]):
        start = pd.Timestamp(group.index[0]).normalize().replace(day=1)
        end = pd.Timestamp(group.index[-1]).normalize() + pd.offsets.MonthEnd(0) #USREC dates are month starts
        periods.append({"start": start, "end": end, "label": _label_for(start, end)})
    return periods

def parse_recession_periods(response_text:str) -> list[dict]:
    """Convert FRED CSV text into monthly recession ranges.
    
    Inputs:
    - response_text: downloaded FRED CSV content
    
    Outputs:
    - Recession periods with inclusive start and end dates
    """
    frame = pd.read_csv(StringIO(response_text))
    date_column, value_column = frame.columns[:2]
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    values = pd.to_numeric(frame[value_column], errors="coerce")
    
    recessions = pd.Series(values.values, index=dates, dtype="float64")
    recessions = recessions[recessions.index.notna()]
    periods = periods_from_series(recessions)
    return periods

def get_recession_periods() -> list[dict]:
    """Load monthly US recession periods from FRED with a known-date fallback."""
    try:
        response = requests.get(FRED_USREC_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        periods = parse_recession_periods(response.text) or known_recession_periods()
    except (requests.RequestException, pd.errors.ParserError, ValueError, IndexError, KeyError) as error:
        LOGGER.warning("Could not load FRED recession data; using fallback dates: %s", error)
        periods = known_recession_periods()
    return periods
