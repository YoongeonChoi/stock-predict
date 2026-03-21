"""Economic and earnings calendar service."""

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


async def get_calendar(country_code: str) -> dict:
    settings = get_settings()
    cache_key = f"calendar:{country_code}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    now = datetime.now()
    from_date = now.strftime("%Y-%m-%d")
    to_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    earnings = await fmp_client.get_earning_calendar(from_date, to_date)
    economic = await fmp_client.get_economic_calendar(from_date, to_date)

    country_filter = {"US": "US", "KR": "KR", "JP": "JP"}.get(country_code, "")

    filtered_economic = [
        e for e in economic
        if country_filter.lower() in (e.get("country", "") or "").lower()
    ][:30]

    filtered_earnings = earnings[:50]

    result = {
        "country_code": country_code,
        "major_events": MAJOR_EVENTS.get(country_code, []),
        "economic_events": filtered_economic,
        "earnings_events": filtered_earnings,
        "generated_at": now.isoformat(),
    }

    await cache.set(cache_key, result, settings.cache_ttl_news)
    return result
