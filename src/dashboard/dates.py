from calendar import monthrange
from datetime import date, datetime

import pandas as pd

from src.dashboard.config import HISTORY_YEARS, MONTHS, NEW_YORK, RANGE_OPTIONS

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

def resolve_month_date(year:int, month:int, day:int, earliest_date:date, today:date) -> tuple[date, bool]:
    """Clamp a selected calendar date to the available history.
    
    Inputs:
    - year: selected calendar year
    - month: selected calendar month
    - day: selected calendar day
    - earliest_date: earliest available date
    - today: latest available date
    
    Outputs:
    - Resolved date and whether the selection needed adjustment
    """
    last_day = monthrange(year, month)[1]
    selected_day = min(day, last_day)
    selected_date = date(year, month, selected_day)
    resolved_date = min(max(selected_date, earliest_date), today)
    adjusted = selected_day != day or resolved_date != selected_date
    return resolved_date, adjusted

def resolve_date_range(range_label:str, today:date, start_parts:tuple, end_parts:tuple) -> tuple[date, date, list[str]]:
    """Turn the quick-range or custom selectors into start and end dates.
    
    Inputs:
    - range_label: selected quick-range option or "Custom"
    - today: current date
    - start_parts: custom (year, month name, day) start selection
    - end_parts: custom (year, month name, day) end selection
    
    Outputs:
    - Start date, end date, and notices about any adjusted custom dates
    """
    if range_label != "Custom":
        start_date = years_before(today, RANGE_OPTIONS[range_label])
        return start_date, today, []
    
    # Custom range
    earliest_date = years_before(today, HISTORY_YEARS)
    start_year, start_month, start_day = start_parts
    end_year, end_month, end_day = end_parts
    start_date, start_adjusted = resolve_month_date(start_year, MONTHS.index(start_month) + 1, start_day, earliest_date, today)
    end_date, end_adjusted = resolve_month_date(end_year, MONTHS.index(end_month) + 1, end_day, earliest_date, today)
    
    notices = []
    if start_adjusted:
        notices.append(f"Start date adjusted to {start_date:%Y-%m-%d} to fit the calendar and available date range.")
    if end_adjusted:
        notices.append(f"End date adjusted to {end_date:%Y-%m-%d} to fit the calendar and available date range.")
    return start_date, end_date, notices
