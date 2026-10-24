from datetime import date, datetime

import pandas as pd

from src.dashboard.config import NEW_YORK, RANGE_OPTIONS

def us_market_is_open(now:datetime | None=None) -> bool:
    """Check weekday US regular trading hours (09:30-16:00 Eastern)."""
    eastern_now = datetime.now(NEW_YORK) if now is None else now
    if eastern_now.tzinfo is None:
        eastern_now = eastern_now.replace(tzinfo=NEW_YORK)
    else:
        eastern_now = eastern_now.astimezone(NEW_YORK)
    
    market_time = (eastern_now.hour, eastern_now.minute)
    is_open = eastern_now.weekday() < 5 and (9, 30) <= market_time < (16, 0)
    return is_open

def years_before(today:date, years:int) -> date:
    """Return the calendar date a whole number of years before today."""
    earlier = (pd.Timestamp(today) - pd.DateOffset(years=years)).date()
    return earlier

def resolve_date_range(range_label:str, today:date, custom_dates:tuple) -> tuple[date, date] | None:
    """Turn the quick-range or custom date selection into start and end dates.
    
    Inputs:
    - range_label: selected quick-range option or "Custom"
    - today: current date
    - custom_dates: dates returned by the custom range picker
    
    Outputs:
    - Start and end dates, or None when the custom range has no end date yet
    """
    if range_label != "Custom":
        start_date = years_before(today, RANGE_OPTIONS[range_label])
        return start_date, today
    
    if len(custom_dates) != 2: #the picker returns one date until the end date is clicked
        return None
    return custom_dates
