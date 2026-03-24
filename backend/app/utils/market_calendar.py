from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import warnings

import pandas_market_calendars as mcal

CALENDAR_BY_COUNTRY = {
    "US": "XNYS",
    "KR": "XKRX",
    "JP": "XTKS",
}

COUNTRY_BY_INDEX_TICKER = {
    "^GSPC": "US",
    "^DJI": "US",
    "^IXIC": "US",
    "^KS11": "KR",
    "^KQ11": "KR",
    "^N225": "JP",
}


@lru_cache(maxsize=8)
def _get_calendar(country_code: str):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*\['break_start', 'break_end'\] are discontinued.*",
            category=UserWarning,
        )
        calendar = mcal.get_calendar(CALENDAR_BY_COUNTRY.get(country_code, "XNYS"))
    for market_time in ("break_start", "break_end"):
        try:
            calendar.remove_time(market_time)
        except Exception:
            pass
    return calendar


def _normalize_date(value: date | datetime | str | None) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def _normalize_datetime(value: date | datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def market_country_code_for_ticker(ticker: str) -> str:
    normalized = str(ticker or "").upper()
    if normalized.endswith(".KS") or normalized.endswith(".KQ"):
        return "KR"
    if normalized.endswith(".T"):
        return "JP"
    return COUNTRY_BY_INDEX_TICKER.get(normalized, "US")


def latest_closed_trading_day(
    country_code: str,
    reference_time: date | datetime | str | None = None,
) -> date:
    now_utc = _normalize_datetime(reference_time)
    start = (now_utc - timedelta(days=15)).date()
    end = (now_utc + timedelta(days=1)).date()

    try:
        schedule = _get_calendar(country_code).schedule(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        if not schedule.empty:
            closed = schedule[schedule["market_close"] <= now_utc]
            if not closed.empty:
                return closed.index[-1].date()
    except Exception:
        pass

    cursor = now_utc.date()
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor


def is_market_open(
    country_code: str,
    reference_time: date | datetime | str | None = None,
) -> bool:
    now_utc = _normalize_datetime(reference_time)
    start = (now_utc - timedelta(days=1)).date()
    end = (now_utc + timedelta(days=1)).date()
    try:
        schedule = _get_calendar(country_code).schedule(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        if schedule.empty:
            return False
        current = schedule[
            (schedule["market_open"] <= now_utc)
            & (schedule["market_close"] > now_utc)
        ]
        return not current.empty
    except Exception:
        return False


def market_session_cache_token(
    *,
    country_code: str | None = None,
    ticker: str | None = None,
    reference_time: date | datetime | str | None = None,
) -> str:
    resolved_country = country_code or market_country_code_for_ticker(ticker or "")
    closed_day = latest_closed_trading_day(resolved_country, reference_time).isoformat()
    state = "open" if is_market_open(resolved_country, reference_time) else "closed"
    return f"{closed_day}:{state}"


def market_session_snapshot(
    country_code: str,
    reference_time: date | datetime | str | None = None,
) -> dict:
    now_utc = _normalize_datetime(reference_time)
    start = (now_utc - timedelta(days=3)).date()
    end = (now_utc + timedelta(days=10)).date()

    latest_closed = latest_closed_trading_day(country_code, now_utc)
    next_day = next_trading_day(country_code, now_utc.date())
    snapshot = {
        "country_code": country_code,
        "is_open": False,
        "trading_day_today": False,
        "latest_closed_date": latest_closed.isoformat(),
        "next_trading_day": next_day.isoformat(),
        "opened_at": None,
        "closed_at": None,
        "next_open_at": None,
        "next_close_at": None,
        "next_event": "open",
        "session_token": market_session_cache_token(country_code=country_code, reference_time=now_utc),
    }

    try:
        schedule = _get_calendar(country_code).schedule(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        if schedule.empty:
            return snapshot

        same_day = schedule[schedule.index.date == now_utc.date()]
        if not same_day.empty:
            row = same_day.iloc[0]
            market_open = row["market_open"].to_pydatetime().astimezone(timezone.utc)
            market_close = row["market_close"].to_pydatetime().astimezone(timezone.utc)
            snapshot["trading_day_today"] = True
            snapshot["opened_at"] = market_open
            snapshot["closed_at"] = market_close
            snapshot["is_open"] = market_open <= now_utc < market_close
            snapshot["next_event"] = "close" if snapshot["is_open"] else "open"

        future = schedule[schedule["market_open"] > now_utc]
        if not future.empty:
            next_row = future.iloc[0]
            snapshot["next_open_at"] = next_row["market_open"].to_pydatetime().astimezone(timezone.utc)
            snapshot["next_close_at"] = next_row["market_close"].to_pydatetime().astimezone(timezone.utc)
    except Exception:
        pass

    return snapshot


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
