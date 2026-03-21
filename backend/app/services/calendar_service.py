"""Economic and earnings calendar service with fallback schedule generation."""

from datetime import datetime, timedelta
from app.data import fmp_client, cache
from app.config import get_settings

MAJOR_EVENTS = {
    "US": [
        {"name": "FOMC Meeting", "frequency": "6 weeks"},
        {"name": "Non-Farm Payrolls", "frequency": "Monthly, 1st Friday"},
        {"name": "CPI Release", "frequency": "Monthly"},
        {"name": "GDP Report", "frequency": "Quarterly"},
        {"name": "Fed Chair Speech", "frequency": "As scheduled"},
    ],
    "KR": [
        {"name": "BOK 금통위", "frequency": "6 weeks"},
        {"name": "GDP 발표", "frequency": "Quarterly"},
        {"name": "CPI 발표", "frequency": "Monthly"},
        {"name": "수출입 동향", "frequency": "Monthly, 1st"},
        {"name": "고용동향", "frequency": "Monthly"},
    ],
    "JP": [
        {"name": "BOJ Policy Meeting", "frequency": "8 times/year"},
        {"name": "Tankan Survey", "frequency": "Quarterly"},
        {"name": "GDP Release", "frequency": "Quarterly"},
        {"name": "CPI Release", "frequency": "Monthly"},
        {"name": "Industrial Production", "frequency": "Monthly"},
    ],
}


def _generate_recurring_events(country_code: str, from_date: datetime, to_date: datetime) -> list[dict]:
    """Generate estimated recurring economic events when FMP data is unavailable."""
    events = []
    current = from_date

    if country_code == "US":
        while current <= to_date:
            d = current.day
            wd = current.weekday()
            m = current.month
            if d <= 7 and wd == 4:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "Non-Farm Payrolls", "country": "US"})
            if 10 <= d <= 14 and wd == 2:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "CPI Release", "country": "US"})
            if 14 <= d <= 18 and wd == 3:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "Retail Sales", "country": "US"})
            if 25 <= d <= 31 and wd == 4 and m in (1, 4, 7, 10):
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "GDP Report", "country": "US"})
            if d == 15:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "Industrial Production", "country": "US"})
            current += timedelta(days=1)
    elif country_code == "KR":
        while current <= to_date:
            d = current.day
            m = current.month
            if d == 1 and current.weekday() < 5:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "수출입 동향", "country": "KR"})
            if 2 <= d <= 5 and current.weekday() < 5:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "CPI 발표", "country": "KR"})
                current += timedelta(days=1)
                continue
            if 10 <= d <= 15 and current.weekday() < 5 and m in (1, 4, 7, 10):
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "GDP 발표", "country": "KR"})
                current += timedelta(days=1)
                continue
            if d == 15 and current.weekday() < 5:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "고용동향", "country": "KR"})
            current += timedelta(days=1)
    elif country_code == "JP":
        while current <= to_date:
            d = current.day
            m = current.month
            if 18 <= d <= 22 and current.weekday() == 4:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "CPI Release", "country": "JP"})
            if d == 1 and m in (4, 7, 10, 1) and current.weekday() < 5:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "Tankan Survey", "country": "JP"})
            if 13 <= d <= 16 and current.weekday() < 5 and m in (2, 5, 8, 11):
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "GDP Release", "country": "JP"})
                current += timedelta(days=1)
                continue
            if d == 28 and current.weekday() < 5:
                events.append({"date": current.strftime("%Y-%m-%d"), "event": "Industrial Production", "country": "JP"})
            current += timedelta(days=1)

    return events


async def get_calendar(country_code: str) -> dict:
    settings = get_settings()
    cache_key = f"calendar:{country_code}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    now = datetime.now()
    from_date = now - timedelta(days=5)
    to_date = now + timedelta(days=60)
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    earnings = await fmp_client.get_earning_calendar(from_str, to_str)
    economic = await fmp_client.get_economic_calendar(from_str, to_str)

    country_filter = {"US": "US", "KR": "KR", "JP": "JP"}.get(country_code, "")

    filtered_economic = [
        e for e in economic
        if country_filter.lower() in (e.get("country", "") or "").lower()
    ][:50]

    if not filtered_economic:
        filtered_economic = _generate_recurring_events(country_code, from_date, to_date)

    filtered_earnings = earnings[:80]

    result = {
        "country_code": country_code,
        "major_events": MAJOR_EVENTS.get(country_code, []),
        "economic_events": filtered_economic,
        "earnings_events": filtered_earnings,
        "generated_at": now.isoformat(),
    }

    await cache.set(cache_key, result, settings.cache_ttl_news)
    return result
