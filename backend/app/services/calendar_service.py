"""Economic and earnings calendar service with monthly calendar normalization."""

from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import datetime, timedelta

from app.config import get_settings
from app.data import cache, fmp_client

MAJOR_EVENTS = {
    "US": [
        {
            "name": "FOMC Meeting",
            "name_local": "FOMC 회의",
            "frequency": "연 8회",
            "description": "금리 경로와 유동성 기대를 동시에 흔드는 핵심 이벤트입니다.",
            "impact": "high",
            "color": "rose",
        },
        {
            "name": "Non-Farm Payrolls",
            "name_local": "비농업고용지표",
            "frequency": "매월 첫째 주 금요일",
            "description": "고용 강도와 장기금리 방향을 가늠하는 대표 지표입니다.",
            "impact": "high",
            "color": "sky",
        },
        {
            "name": "CPI Release",
            "name_local": "미국 CPI 발표",
            "frequency": "매월 중순",
            "description": "인플레이션 경로가 밸류에이션과 금리 민감주에 직접 반영됩니다.",
            "impact": "high",
            "color": "sky",
        },
        {
            "name": "Retail Sales",
            "name_local": "소매판매",
            "frequency": "매월 중순",
            "description": "소비 둔화 또는 회복 여부를 빠르게 읽을 수 있는 지표입니다.",
            "impact": "medium",
            "color": "emerald",
        },
    ],
    "KR": [
        {
            "name": "BOK Rate Decision",
            "name_local": "한국은행 금통위",
            "frequency": "연 8회",
            "description": "국내 금리와 외국인 수급 심리에 가장 큰 영향을 주는 일정입니다.",
            "impact": "high",
            "color": "rose",
        },
        {
            "name": "CPI Release",
            "name_local": "한국 CPI 발표",
            "frequency": "매월 초",
            "description": "물가 압력이 높아지면 성장주와 금리 민감주의 변동성이 커질 수 있습니다.",
            "impact": "high",
            "color": "sky",
        },
        {
            "name": "Exports / Imports",
            "name_local": "수출입 동향",
            "frequency": "매월 1일 전후",
            "description": "반도체와 경기민감 업종에 대한 체감 모멘텀을 가장 빨리 보여줍니다.",
            "impact": "high",
            "color": "emerald",
        },
        {
            "name": "Employment Report",
            "name_local": "고용동향",
            "frequency": "매월 중순",
            "description": "내수 경기의 체력과 소비 회복 속도를 점검할 수 있습니다.",
            "impact": "medium",
            "color": "amber",
        },
    ],
    "JP": [
        {
            "name": "BOJ Policy Meeting",
            "name_local": "BOJ 금융정책결정회의",
            "frequency": "연 8회",
            "description": "엔화 방향성과 일본 증시의 리스크 온/오프를 결정하는 핵심 이벤트입니다.",
            "impact": "high",
            "color": "rose",
        },
        {
            "name": "Tankan Survey",
            "name_local": "단칸 조사",
            "frequency": "분기별",
            "description": "일본 기업심리와 설비투자 기대를 함께 읽을 수 있습니다.",
            "impact": "high",
            "color": "emerald",
        },
        {
            "name": "CPI Release",
            "name_local": "일본 CPI 발표",
            "frequency": "매월 하순",
            "description": "BOJ 정책 기대를 바꾸는 물가 흐름을 점검하는 지표입니다.",
            "impact": "medium",
            "color": "sky",
        },
        {
            "name": "Industrial Production",
            "name_local": "광공업생산",
            "frequency": "매월 말",
            "description": "제조업 체력과 수출 경기 흐름을 확인할 수 있습니다.",
            "impact": "medium",
            "color": "amber",
        },
    ],
}

TRANSLATIONS = {
    "FOMC Meeting": "FOMC 회의",
    "Non-Farm Payrolls": "비농업고용지표",
    "CPI Release": "CPI 발표",
    "GDP Report": "GDP 발표",
    "GDP Release": "GDP 발표",
    "Retail Sales": "소매판매",
    "Industrial Production": "광공업생산",
    "BOK Rate Decision": "한국은행 금통위",
    "Exports / Imports": "수출입 동향",
    "Employment Report": "고용동향",
    "Tankan Survey": "단칸 조사",
    "BOJ Policy Meeting": "BOJ 금융정책결정회의",
}

DESCRIPTION_BY_CATEGORY = {
    "policy": "통화정책 이벤트는 지수 방향성과 밸류에이션 멀티플에 직접적인 영향을 줄 수 있습니다.",
    "inflation": "물가 지표는 금리 경로 기대를 바꾸기 때문에 성장주와 장기채 민감 자산에 특히 중요합니다.",
    "labor": "고용 지표는 경기 체력과 임금 압력을 동시에 보여줘 소비 관련 업종 심리에 영향을 줍니다.",
    "growth": "성장 지표는 경기민감 업종의 이익 기대와 지수 리더십에 영향을 줍니다.",
    "trade": "수출입 흐름은 반도체, 제조업, 환율 민감 업종의 모멘텀을 가늠하는 선행 신호가 됩니다.",
    "earnings": "실적 일정은 개별 종목뿐 아니라 같은 업종 전체의 기대 심리를 흔들 수 있습니다.",
    "activity": "실물 활동 지표는 경기민감 업종의 단기 추세를 가늠하는 데 도움이 됩니다.",
}

HIGH_IMPACT_SYMBOLS = {
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "TSM", "005930.KS", "7203.T"
}

COUNTRY_TOKENS = {
    "US": ["us", "united states", "usa"],
    "KR": ["kr", "korea", "south korea"],
    "JP": ["jp", "japan"],
}


def _date_key(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) >= 10:
        return text[:10]
    return None


def _slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "event"


def _sort_key(event: dict) -> tuple:
    impact_rank = {"high": 0, "medium": 1, "low": 2}.get(event.get("impact", "medium"), 1)
    type_rank = {"policy": 0, "economic": 1, "earnings": 2}.get(event.get("type", "economic"), 1)
    return (event.get("date", "9999-12-31"), impact_rank, type_rank, event.get("title", ""))


def _sunday_offset(dt: datetime) -> int:
    return (dt.weekday() + 1) % 7


def _month_window(year: int, month: int) -> tuple[datetime, datetime, datetime, datetime]:
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, monthrange(year, month)[1])
    grid_start = month_start - timedelta(days=_sunday_offset(month_start))
    grid_end = month_end + timedelta(days=(6 - _sunday_offset(month_end)))
    return month_start, month_end, grid_start, grid_end


def _infer_category(title: str) -> str:
    lower = title.lower()
    if any(token in lower for token in ("fomc", "rate decision", "금통위", "boj", "policy meeting", "interest rate")):
        return "policy"
    if any(token in lower for token in ("cpi", "ppi", "pce", "inflation", "물가")):
        return "inflation"
    if any(token in lower for token in ("payroll", "employment", "jobless", "고용")):
        return "labor"
    if any(token in lower for token in ("gdp", "industrial production", "retail sales", "production", "광공업", "소매")):
        return "growth"
    if any(token in lower for token in ("export", "imports", "trade", "수출", "수입")):
        return "trade"
    return "activity"


def _localize_title(title: str) -> str:
    return TRANSLATIONS.get(title, title)


def _infer_impact(category: str, title: str, symbol: str | None = None) -> str:
    if category in {"policy", "inflation", "labor"}:
        return "high"
    if symbol and symbol.upper() in HIGH_IMPACT_SYMBOLS:
        return "high"
    if any(token in title.lower() for token in ("gdp", "exports", "금통위", "fomc", "cpi", "payroll")):
        return "high"
    if category in {"growth", "trade", "earnings"}:
        return "medium"
    return "low"


def _color_for_event(event_type: str, impact: str) -> str:
    if event_type == "earnings":
        return "amber" if impact != "high" else "orange"
    if event_type == "policy":
        return "rose"
    if impact == "high":
        return "sky"
    if impact == "medium":
        return "emerald"
    return "slate"


def _describe_event(category: str, title_local: str, symbol: str | None = None) -> str:
    if category == "earnings" and symbol:
        return f"{symbol} 실적 발표 일정입니다. 예상치와 실제치 차이가 크면 업종 전반의 심리까지 흔들 수 있습니다."
    return DESCRIPTION_BY_CATEGORY.get(category, f"{title_local} 일정은 시장 심리에 영향을 줄 수 있습니다.")


def _time_label(raw_time: str | None) -> str | None:
    if not raw_time:
        return None
    lower = str(raw_time).strip().lower()
    if lower in {"amc", "after market close"}:
        return "장 마감 후"
    if lower in {"bmo", "before market open"}:
        return "장 시작 전"
    if len(lower) <= 10:
        return str(raw_time)
    return None


def _normalize_economic_event(raw: dict, country_code: str, source: str) -> dict | None:
    date_str = _date_key(raw.get("date"))
    if not date_str:
        return None

    title_en = str(raw.get("event") or raw.get("name") or "Economic Event").strip()
    category = _infer_category(title_en)
    event_type = "policy" if category == "policy" else "economic"
    impact = _infer_impact(category, title_en)
    title_local = _localize_title(title_en)
    actual = raw.get("actual")
    forecast = raw.get("forecast")

    subtitle_parts = []
    if raw.get("country"):
        subtitle_parts.append(str(raw.get("country")))
    if actual not in (None, "") and forecast not in (None, ""):
        subtitle_parts.append(f"실제 {actual} / 예상 {forecast}")
    elif forecast not in (None, ""):
        subtitle_parts.append(f"예상 {forecast}")

    return {
        "id": f"econ:{date_str}:{_slug(title_en)}",
        "date": date_str,
        "type": event_type,
        "category": category,
        "title": title_local,
        "title_en": title_en,
        "subtitle": " · ".join(subtitle_parts) if subtitle_parts else None,
        "description": _describe_event(category, title_local),
        "impact": impact,
        "color": _color_for_event(event_type, impact),
        "source": source,
        "all_day": True,
        "time": None,
        "symbol": None,
        "country_code": country_code,
    }


def _earnings_matches_country(raw: dict, country_code: str) -> bool:
    symbol = str(raw.get("symbol") or "").upper()
    exchange = str(raw.get("exchange") or raw.get("exchangeShortName") or "").lower()
    country = str(raw.get("country") or "").lower()

    if country and any(token in country for token in COUNTRY_TOKENS[country_code]):
        return True
    if country_code == "KR":
        return symbol.endswith((".KS", ".KQ", ".KR")) or symbol.isdigit() and len(symbol) == 6 or "korea" in exchange
    if country_code == "JP":
        return symbol.endswith(".T") or symbol.isdigit() and len(symbol) == 4 or "japan" in exchange or "tokyo" in exchange
    return not symbol.endswith((".KS", ".KQ", ".KR", ".T"))


def _normalize_earnings_event(raw: dict, country_code: str) -> dict | None:
    if not _earnings_matches_country(raw, country_code):
        return None

    date_str = _date_key(raw.get("date"))
    symbol = str(raw.get("symbol") or "").strip().upper()
    if not date_str or not symbol:
        return None

    impact = _infer_impact("earnings", symbol, symbol=symbol)
    estimate = raw.get("epsEstimated")
    revenue = raw.get("revenueEstimated")
    time_label = _time_label(raw.get("time"))

    subtitle_parts = []
    if time_label:
        subtitle_parts.append(time_label)
    if estimate not in (None, ""):
        subtitle_parts.append(f"예상 EPS {estimate}")
    if revenue not in (None, ""):
        subtitle_parts.append(f"예상 매출 {revenue}")

    return {
        "id": f"earn:{date_str}:{_slug(symbol)}",
        "date": date_str,
        "type": "earnings",
        "category": "earnings",
        "title": f"{symbol} 실적 발표",
        "title_en": f"{symbol} Earnings",
        "subtitle": " · ".join(subtitle_parts) if subtitle_parts else "실적 발표 일정",
        "description": _describe_event("earnings", f"{symbol} 실적 발표", symbol=symbol),
        "impact": impact,
        "color": _color_for_event("earnings", impact),
        "source": "fmp",
        "all_day": True,
        "time": time_label,
        "symbol": symbol,
        "country_code": country_code,
    }


def _merge_events(events: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for event in events:
        key = (event.get("date", ""), event.get("title_en") or event.get("title") or event.get("id"))
        if key not in merged:
            merged[key] = event
            continue
        existing = merged[key]
        if existing.get("source") == "recurring" and event.get("source") != "recurring":
            merged[key] = event
    return sorted(merged.values(), key=_sort_key)


def _generate_recurring_events(country_code: str, from_date: datetime, to_date: datetime) -> list[dict]:
    events = []
    current = from_date

    while current <= to_date:
        day = current.day
        weekday = current.weekday()
        month = current.month
        date_str = current.strftime("%Y-%m-%d")

        if country_code == "US":
            if day <= 7 and weekday == 4:
                events.append({"date": date_str, "event": "Non-Farm Payrolls", "country": "US"})
            if 10 <= day <= 14 and weekday in (1, 2, 3):
                events.append({"date": date_str, "event": "CPI Release", "country": "US"})
            if 14 <= day <= 18 and weekday in (2, 3):
                events.append({"date": date_str, "event": "Retail Sales", "country": "US"})
            if 25 <= day <= 31 and weekday == 4 and month in (1, 4, 7, 10):
                events.append({"date": date_str, "event": "GDP Report", "country": "US"})
        elif country_code == "KR":
            if day == 1 and weekday < 5:
                events.append({"date": date_str, "event": "Exports / Imports", "country": "KR"})
            if 2 <= day <= 5 and weekday < 5:
                events.append({"date": date_str, "event": "CPI Release", "country": "KR"})
            if 10 <= day <= 15 and weekday < 5 and month in (1, 4, 7, 10):
                events.append({"date": date_str, "event": "GDP Release", "country": "KR"})
            if 13 <= day <= 17 and weekday < 5:
                events.append({"date": date_str, "event": "Employment Report", "country": "KR"})
        elif country_code == "JP":
            if 18 <= day <= 22 and weekday in (3, 4):
                events.append({"date": date_str, "event": "CPI Release", "country": "JP"})
            if day == 1 and month in (1, 4, 7, 10) and weekday < 5:
                events.append({"date": date_str, "event": "Tankan Survey", "country": "JP"})
            if 13 <= day <= 16 and weekday < 5 and month in (2, 5, 8, 11):
                events.append({"date": date_str, "event": "GDP Release", "country": "JP"})
            if 27 <= day <= 30 and weekday < 5:
                events.append({"date": date_str, "event": "Industrial Production", "country": "JP"})

        current += timedelta(days=1)

    return events


def _filter_economic_by_country(events: list[dict], country_code: str) -> list[dict]:
    accepted = COUNTRY_TOKENS[country_code]
    results = []
    for event in events:
        country = str(event.get("country") or "").lower()
        if not country or any(token in country for token in accepted):
            results.append(event)
    return results


def _select_upcoming(events: list[dict], today: str, month_start: str, limit: int = 12) -> list[dict]:
    ordered = sorted(events, key=_sort_key)
    future = [event for event in ordered if event.get("date", "") >= today]
    if future:
        return future[:limit]
    month_events = [event for event in ordered if event.get("date", "") >= month_start]
    return month_events[:limit]


async def get_calendar(country_code: str, year: int | None = None, month: int | None = None) -> dict:
    settings = get_settings()
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month

    cache_key = f"calendar:{country_code}:{target_year:04d}:{target_month:02d}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    month_start, month_end, grid_start, grid_end = _month_window(target_year, target_month)
    from_str = grid_start.strftime("%Y-%m-%d")
    to_str = grid_end.strftime("%Y-%m-%d")

    earnings_raw, economic_raw = await asyncio.gather(
        fmp_client.get_earning_calendar(from_str, to_str),
        fmp_client.get_economic_calendar(from_str, to_str),
    )

    normalized_economic = [
        _normalize_economic_event(event, country_code, source="fmp")
        for event in _filter_economic_by_country(economic_raw, country_code)
    ]
    normalized_economic = [event for event in normalized_economic if event]

    fallback_economic = [
        _normalize_economic_event(event, country_code, source="recurring")
        for event in _generate_recurring_events(country_code, grid_start, grid_end)
    ]
    fallback_economic = [event for event in fallback_economic if event]

    economic_events = _merge_events([*normalized_economic, *fallback_economic])
    earnings_events = _merge_events([
        event
        for event in (_normalize_earnings_event(item, country_code) for item in earnings_raw)
        if event
    ])

    events = sorted([*economic_events, *earnings_events], key=_sort_key)

    month_start_str = month_start.strftime("%Y-%m-%d")
    month_end_str = month_end.strftime("%Y-%m-%d")
    month_events = [event for event in events if month_start_str <= event.get("date", "") <= month_end_str]
    high_impact_count = sum(1 for event in month_events if event.get("impact") == "high")
    policy_count = sum(1 for event in month_events if event.get("type") == "policy")
    earnings_count = sum(1 for event in month_events if event.get("type") == "earnings")

    summary_note = "실제 경제 일정과 정기 반복 일정을 함께 반영했습니다."
    if not normalized_economic:
        summary_note = "외부 경제 캘린더 응답이 부족해 반복 스케줄 추정치를 더 많이 사용했습니다."

    result = {
        "country_code": country_code,
        "year": target_year,
        "month": target_month,
        "month_label": month_start.strftime("%Y년 %m월"),
        "range_start": from_str,
        "range_end": to_str,
        "generated_at": now.isoformat(),
        "summary": {
            "total_events": len(month_events),
            "high_impact_count": high_impact_count,
            "policy_count": policy_count,
            "earnings_count": earnings_count,
            "economic_count": sum(1 for event in month_events if event.get("type") in {"economic", "policy"}),
            "note": summary_note,
        },
        "major_events": MAJOR_EVENTS.get(country_code, []),
        "events": events,
        "upcoming_events": _select_upcoming(month_events, now.strftime("%Y-%m-%d"), month_start_str),
        "economic_events": economic_events,
        "earnings_events": earnings_events,
    }

    await cache.set(cache_key, result, settings.cache_ttl_news)
    return result

