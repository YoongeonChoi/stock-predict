from datetime import date, datetime, timedelta
from functools import lru_cache

import pandas_market_calendars as mcal

CALENDAR_BY_COUNTRY = {
    "US": "XNYS",
    "KR": "XKRX",
    "JP": "XTKS",
}


@lru_cache(maxsize=8)
def _get_calendar(country_code: str):
    return mcal.get_calendar(CALENDAR_BY_COUNTRY.get(country_code, "XNYS"))


def _normalize_date(value: date | datetime | str | None) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def next_trading_day(country_code: str, reference_date: date | datetime | str | None) -> date:
    """Return the next trading day for a market, falling back to weekdays."""
    anchor = _normalize_date(reference_date)
    start = anchor + timedelta(days=1)
    end = start + timedelta(days=14)

    try:
        schedule = _get_calendar(country_code).schedule(
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
        )
        if not schedule.empty:
            return schedule.index[0].date()
    except Exception:
        pass

    cursor = start
    while cursor.weekday() >= 5:
        cursor += timedelta(days=1)
    return cursor


def trading_days_forward(
    country_code: str,
    reference_date: date | datetime | str | None,
    count: int,
) -> list[date]:
    """Return the next `count` trading days after the reference date."""
    days: list[date] = []
    cursor = _normalize_date(reference_date)
    for _ in range(max(count, 0)):
        cursor = next_trading_day(country_code, cursor)
        days.append(cursor)
    return days
