"""KR-only economic and earnings calendar service."""

from __future__ import annotations

import asyncio
from calendar import monthrange
from datetime import datetime, timedelta

from app.config import get_settings
from app.data import cache, fmp_client

CALENDAR_FETCH_TIMEOUT_SECONDS = 8
CALENDAR_WAIT_TIMEOUT_SECONDS = 2.5

KR_MAJOR_EVENTS = (
    {
        "name": "BOK Rate Decision",
        "name_local": "한국은행 금통위",
        "frequency": "연 8회",
        "description": "국내 금리와 외국인 수급 심리에 직접 영향을 주는 핵심 일정입니다.",
        "impact": "high",
        "color": "rose",
        "type": "policy",
    },
    {
        "name": "CPI Release",
        "name_local": "한국 CPI 발표",
        "frequency": "매월 초",
        "description": "국내 물가 흐름은 금리 기대와 성장주 밸류에이션에 직접 반영됩니다.",
        "impact": "high",
        "color": "sky",
        "type": "economic",
    },
    {
        "name": "Exports / Imports",
        "name_local": "수출입 동향",
        "frequency": "매월 초",
        "description": "반도체와 경기민감 업종 모멘텀을 가장 빨리 보여주는 경기 선행 신호입니다.",
        "impact": "high",
        "color": "emerald",
        "type": "economic",
    },
    {
        "name": "Employment Report",
        "name_local": "고용동향",
        "frequency": "매월 중순",
        "description": "내수 경기와 소비 회복 속도를 점검하는 대표 지표입니다.",
        "impact": "medium",
        "color": "amber",
        "type": "economic",
    },
)

TITLE_LOCAL_MAP = {item["name"]: item["name_local"] for item in KR_MAJOR_EVENTS}
MAJOR_EVENT_LOOKUP = {item["name"]: item for item in KR_MAJOR_EVENTS}
MAJOR_KR_SYMBOLS = {"005930.KS", "000660.KS", "035420.KS", "068270.KS", "373220.KS"}


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


def _format_month_label(year: int, month: int) -> str:
    return f"{year}년 {month:02d}월"


def calendar_cache_key(year: int, month: int) -> str:
    return f"calendar:KR:{year}:{month:02d}"


def _month_window(year: int, month: int) -> tuple[datetime, datetime, datetime, datetime]:
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, monthrange(year, month)[1])
    grid_start = month_start - timedelta(days=(month_start.weekday() + 1) % 7)
    grid_end = month_end + timedelta(days=(6 - ((month_end.weekday() + 1) % 7)))
    return month_start, month_end, grid_start, grid_end


def _pick_weekday_date(
    year: int,
    month: int,
    start_day: int,
    end_day: int,
    allowed_weekdays: set[int] | None = None,
) -> datetime | None:
    last_day = monthrange(year, month)[1]
    for day in range(max(1, start_day), min(end_day, last_day) + 1):
        current = datetime(year, month, day)
        if current.weekday() >= 5:
            continue
        if allowed_weekdays is not None and current.weekday() not in allowed_weekdays:
            continue
        return current
    return None


def _infer_category(title: str) -> str:
    lower = title.lower()
    if any(token in lower for token in ("rate decision", "금통위", "interest rate")):
        return "policy"
    if any(token in lower for token in ("cpi", "ppi", "inflation", "물가")):
        return "inflation"
    if any(token in lower for token in ("employment", "payroll", "고용")):
        return "labor"
    if any(token in lower for token in ("export", "imports", "trade", "수출", "수입")):
        return "trade"
    if any(token in lower for token in ("gdp", "production", "industrial", "광공업")):
        return "growth"
    return "activity"


def _color_for_event(event_type: str, impact: str) -> str:
    if event_type == "policy":
        return "rose"
    if event_type == "earnings":
        return "orange" if impact == "high" else "amber"
    if impact == "high":
        return "sky"
    if impact == "medium":
        return "emerald"
    return "slate"


def _describe_event(category: str, title_local: str, symbol: str | None = None) -> str:
    if category == "earnings" and symbol:
        return f"{symbol} 실적 발표 일정입니다. 실제치와 컨센서스 차이가 크면 업종 전반 심리까지 흔들 수 있습니다."
    descriptions = {
        "policy": "통화정책 이벤트는 국내 금리 기대와 성장주 밸류에이션에 직접 영향을 줄 수 있습니다.",
        "inflation": "물가 지표는 금리 경로 기대를 바꾸기 때문에 성장주와 금리 민감 업종에 특히 중요합니다.",
        "labor": "고용 지표는 내수 체력과 임금 압력을 동시에 보여줘 소비 관련 업종 심리에 영향을 줍니다.",
        "trade": "수출입 흐름은 반도체와 경기민감 업종의 단기 모멘텀을 판단하는 선행 신호입니다.",
        "growth": "생산과 성장 지표는 경기민감 업종의 이익 기대를 점검하는 데 도움이 됩니다.",
        "activity": f"{title_local} 일정은 한국 시장 심리에 영향을 줄 수 있습니다.",
    }
    return descriptions.get(category, descriptions["activity"])


def _impact_for_event(category: str, event_type: str, symbol: str | None = None) -> str:
    if event_type == "policy" or category in {"inflation", "trade"}:
        return "high"
    if event_type == "earnings" and symbol and symbol.upper() in MAJOR_KR_SYMBOLS:
        return "high"
    if event_type == "earnings":
        return "medium"
    if category in {"labor", "growth"}:
        return "medium"
    return "low"


def _matches_kr_symbol(symbol: str) -> bool:
    upper = symbol.upper()
    return upper.endswith((".KS", ".KQ", ".KR")) or (upper.isdigit() and len(upper) == 6)


def _normalize_economic_event(raw: dict, source: str) -> dict | None:
    date_str = _date_key(raw.get("date"))
    if not date_str:
        return None

    country = str(raw.get("country") or "").lower()
    if country and "korea" not in country and "kr" not in country:
        return None

    title_en = str(raw.get("event") or raw.get("name") or "Economic Event").strip()
    category = _infer_category(title_en)
    event_type = "policy" if category == "policy" else "economic"
    title_local = TITLE_LOCAL_MAP.get(title_en, title_en)
    impact = _impact_for_event(category, event_type)

    subtitle_parts: list[str] = []
    actual = raw.get("actual")
    forecast = raw.get("forecast")
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
        "country_code": "KR",
    }


def _normalize_earnings_event(raw: dict) -> dict | None:
    date_str = _date_key(raw.get("date"))
    symbol = str(raw.get("symbol") or "").strip().upper()
    if not date_str or not symbol or not _matches_kr_symbol(symbol):
        return None

    title_en = f"{symbol} Earnings"
    subtitle_parts: list[str] = []
    time_hint = str(raw.get("time") or "").strip().lower()
    if time_hint in {"bmo", "before market open"}:
        subtitle_parts.append("장 시작 전")
    elif time_hint in {"amc", "after market close"}:
        subtitle_parts.append("장 마감 후")

    eps_estimate = raw.get("epsEstimated")
    if eps_estimate not in (None, ""):
        subtitle_parts.append(f"EPS 예상 {eps_estimate}")

    revenue_estimate = raw.get("revenueEstimated")
    if revenue_estimate not in (None, ""):
        subtitle_parts.append(f"매출 예상 {revenue_estimate}")

    impact = _impact_for_event("earnings", "earnings", symbol)
    return {
        "id": f"earn:{date_str}:{_slug(symbol)}",
        "date": date_str,
        "type": "earnings",
        "category": "earnings",
        "title": f"{symbol} 실적 발표",
        "title_en": title_en,
        "subtitle": " · ".join(subtitle_parts) if subtitle_parts else None,
        "description": _describe_event("earnings", f"{symbol} 실적 발표", symbol=symbol),
        "impact": impact,
        "color": _color_for_event("earnings", impact),
        "source": "fmp",
        "all_day": True,
        "time": None,
        "symbol": symbol,
        "country_code": "KR",
    }


def _build_recurring_major_events(year: int, month: int) -> list[dict]:
    recurring_rules = (
        ("BOK Rate Decision", _pick_weekday_date(year, month, 9, 16, {3})),
        ("CPI Release", _pick_weekday_date(year, month, 1, 7)),
        ("Exports / Imports", _pick_weekday_date(year, month, 1, 3)),
        ("Employment Report", _pick_weekday_date(year, month, 10, 16)),
    )

    events: list[dict] = []
    for title_en, target_date in recurring_rules:
        if not target_date:
            continue
        major = MAJOR_EVENT_LOOKUP[title_en]
        events.append(
            {
                "id": f"recurring:{target_date.date().isoformat()}:{_slug(title_en)}",
                "date": target_date.date().isoformat(),
                "type": major["type"],
                "category": _infer_category(title_en),
                "title": major["name_local"],
                "title_en": title_en,
                "subtitle": major["frequency"],
                "description": major["description"],
                "impact": major["impact"],
                "color": major["color"],
                "source": "recurring",
                "all_day": True,
                "time": None,
                "symbol": None,
                "country_code": "KR",
            }
        )
    return events


def _merge_events(recurring: list[dict], actual_events: list[dict]) -> list[dict]:
    actual_titles = {event["title_en"] for event in actual_events if event["type"] in {"economic", "policy"}}
    merged = [event for event in recurring if event["title_en"] not in actual_titles]
    merged.extend(actual_events)
    return sorted(
        merged,
        key=lambda event: (
            event.get("date", "9999-12-31"),
            {"high": 0, "medium": 1, "low": 2}.get(event.get("impact", "medium"), 1),
            event.get("title", ""),
        ),
    )


def _build_calendar_result(
    *,
    target_year: int,
    target_month: int,
    month_start: datetime,
    month_end: datetime,
    now: datetime,
    events: list[dict],
    partial: bool = False,
    fallback_reason: str | None = None,
    note: str | None = None,
) -> dict:
    upcoming_events = [event for event in events if event["date"] >= now.date().isoformat()][:8]
    economic_events = [event for event in events if event["type"] in {"economic", "policy"}]
    earnings_events = [event for event in events if event["type"] == "earnings"]

    result = {
        "country_code": "KR",
        "year": target_year,
        "month": target_month,
        "month_label": _format_month_label(target_year, target_month),
        "range_start": month_start.date().isoformat(),
        "range_end": month_end.date().isoformat(),
        "generated_at": now.isoformat(),
        "summary": {
            "total_events": len(events),
            "high_impact_count": sum(1 for event in events if event["impact"] == "high"),
            "policy_count": sum(1 for event in events if event["type"] == "policy"),
            "earnings_count": len(earnings_events),
            "economic_count": len(economic_events),
            "note": note or "한국장 공식 일정과 무료 외부 캘린더를 함께 반영했습니다.",
        },
        "major_events": [
            {
                "name": item["name"],
                "name_local": item["name_local"],
                "frequency": item["frequency"],
                "description": item["description"],
                "impact": item["impact"],
                "color": item["color"],
            }
            for item in KR_MAJOR_EVENTS
        ],
        "events": events,
        "upcoming_events": upcoming_events,
        "economic_events": economic_events,
        "earnings_events": earnings_events,
    }
    if partial:
        result["partial"] = True
    if fallback_reason:
        result["fallback_reason"] = fallback_reason
    return result


async def _build_calendar_payload(target_year: int, target_month: int, now: datetime) -> dict:
    month_start, month_end, grid_start, grid_end = _month_window(target_year, target_month)
    economic_rows: list[dict] = []
    earnings_rows: list[dict] = []
    try:
        economic_rows = await fmp_client.get_economic_calendar(
            grid_start.date().isoformat(),
            grid_end.date().isoformat(),
        )
    except Exception:
        economic_rows = []
    try:
        earnings_rows = await fmp_client.get_earning_calendar(
            grid_start.date().isoformat(),
            grid_end.date().isoformat(),
        )
    except Exception:
        earnings_rows = []

    actual_events = [
        event
        for event in [*(_normalize_economic_event(row, "fmp") for row in economic_rows), *(_normalize_earnings_event(row) for row in earnings_rows)]
        if event is not None
    ]
    events = _merge_events(_build_recurring_major_events(target_year, target_month), actual_events)
    return _build_calendar_result(
        target_year=target_year,
        target_month=target_month,
        month_start=month_start,
        month_end=month_end,
        now=now,
        events=events,
    )


def build_calendar_fallback(
    year: int,
    month: int,
    *,
    note: str | None = None,
    fallback_reason: str = "calendar_live_timeout",
) -> dict:
    now = datetime.now()
    month_start, month_end, _, _ = _month_window(year, month)
    events = _build_recurring_major_events(year, month)
    return _build_calendar_result(
        target_year=year,
        target_month=month,
        month_start=month_start,
        month_end=month_end,
        now=now,
        events=events,
        partial=True,
        fallback_reason=fallback_reason,
        note=note or "공식 일정은 먼저 보여주고, 외부 캘린더 세부 항목은 다시 동기화되면 바로 반영합니다.",
    )


async def get_calendar(country_code: str, year: int | None = None, month: int | None = None) -> dict:
    del country_code
    now = datetime.now()
    target_year = year or now.year
    target_month = month or now.month
    cache_key = calendar_cache_key(target_year, target_month)

    cached = await cache.get(cache_key)
    if cached:
        return cached

    async def _fetch_calendar():
        try:
            return await asyncio.wait_for(
                _build_calendar_payload(target_year, target_month, now),
                timeout=CALENDAR_FETCH_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            return build_calendar_fallback(target_year, target_month)
        except Exception:
            return build_calendar_fallback(
                target_year,
                target_month,
                fallback_reason="calendar_live_error",
                note="외부 캘린더 연결이 지연돼 이번 응답은 월간 핵심 일정만 먼저 제공합니다.",
            )

    return await cache.get_or_fetch(
        cache_key,
        _fetch_calendar,
        ttl=get_settings().cache_ttl_news,
        wait_timeout=CALENDAR_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=lambda: build_calendar_fallback(target_year, target_month),
    )
