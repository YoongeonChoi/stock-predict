"""KR-led market calendar service with major overseas macro events."""

from __future__ import annotations

import asyncio
import re
from calendar import monthrange
from datetime import datetime, timedelta

from app.config import get_settings
from app.data import cache, fmp_client

CALENDAR_FETCH_TIMEOUT_SECONDS = 8
CALENDAR_WAIT_TIMEOUT_SECONDS = 2.5
CALENDAR_SOURCE_WAIT_TIMEOUT_SECONDS = 1.75
CALENDAR_STARTUP_SEED_TTL_SECONDS = 180
CALENDAR_STARTUP_FALLBACK_REASON = "calendar_startup_warming"

KR_MAJOR_EVENTS = (
    {
        "country_code": "KR",
        "name": "BOK Rate Decision",
        "name_local": "한국은행 금통위",
        "frequency": "연 8회",
        "description": "국내 금리와 외국인 수급 심리에 직접 영향을 주는 핵심 일정입니다.",
        "impact": "high",
        "color": "rose",
        "type": "policy",
    },
    {
        "country_code": "KR",
        "name": "CPI Release",
        "name_local": "한국 CPI 발표",
        "frequency": "매월 초",
        "description": "국내 물가 흐름은 금리 기대와 성장주 밸류에이션에 직접 반영됩니다.",
        "impact": "high",
        "color": "sky",
        "type": "economic",
    },
    {
        "country_code": "KR",
        "name": "Exports / Imports",
        "name_local": "수출입 동향",
        "frequency": "매월 초",
        "description": "반도체와 경기민감 업종 모멘텀을 가장 빨리 보여주는 경기 선행 신호입니다.",
        "impact": "high",
        "color": "emerald",
        "type": "economic",
    },
    {
        "country_code": "KR",
        "name": "Employment Report",
        "name_local": "고용동향",
        "frequency": "매월 중순",
        "description": "내수 경기와 소비 회복 속도를 점검하는 대표 지표입니다.",
        "impact": "medium",
        "color": "amber",
        "type": "economic",
    },
    {
        "country_code": "US",
        "name": "Interest Rate Decision",
        "name_local": "FOMC 금리결정",
        "frequency": "연 8회",
        "description": "미국 기준금리와 점도표 변화는 원/달러, 성장주 밸류에이션, 외국인 수급에 직접 영향을 줄 수 있습니다.",
        "impact": "high",
        "color": "rose",
        "type": "policy",
    },
    {
        "country_code": "US",
        "name": "CPI Release",
        "name_local": "미국 CPI 발표",
        "frequency": "매월 중순",
        "description": "미국 물가 지표는 글로벌 금리 경로 기대를 바꾸기 때문에 한국 성장주와 반도체 밸류에이션에도 바로 반영됩니다.",
        "impact": "high",
        "color": "sky",
        "type": "economic",
    },
    {
        "country_code": "US",
        "name": "Non Farm Payrolls",
        "name_local": "미국 비농업고용",
        "frequency": "매월 초",
        "description": "미국 고용 지표는 경기 둔화 여부와 금리 인하 기대를 함께 움직여 위험선호 흐름에 큰 영향을 줄 수 있습니다.",
        "impact": "high",
        "color": "emerald",
        "type": "economic",
    },
    {
        "country_code": "EU",
        "name": "Interest Rate Decision",
        "name_local": "ECB 금리결정",
        "frequency": "연 8회",
        "description": "ECB 결정은 유럽 경기민감 업종과 환율 방향뿐 아니라 글로벌 금리 기대에도 영향을 줍니다.",
        "impact": "medium",
        "color": "rose",
        "type": "policy",
    },
    {
        "country_code": "JP",
        "name": "Interest Rate Decision",
        "name_local": "BOJ 금리결정",
        "frequency": "연 8회",
        "description": "BOJ 정책 변화는 엔화, 반도체 공급망, 일본 수출주와 함께 한국 수급 심리에도 연결됩니다.",
        "impact": "medium",
        "color": "rose",
        "type": "policy",
    },
)

MARKET_COUNTRY_LABELS = {
    "KR": "한국",
    "US": "미국",
    "EU": "유로존",
    "JP": "일본",
}
TITLE_LOCAL_MAP = {(item["country_code"], item["name"]): item["name_local"] for item in KR_MAJOR_EVENTS}
MAJOR_EVENT_LOOKUP = {(item["country_code"], item["name"]): item for item in KR_MAJOR_EVENTS}
TRACKED_EARNINGS_SYMBOL_COUNTRY = {
    "005930.KS": "KR",
    "000660.KS": "KR",
    "035420.KS": "KR",
    "068270.KS": "KR",
    "373220.KS": "KR",
    "AAPL": "US",
    "MSFT": "US",
    "NVDA": "US",
    "AMZN": "US",
    "META": "US",
    "GOOGL": "US",
    "GOOG": "US",
    "TSLA": "US",
    "AVGO": "US",
    "AMD": "US",
    "ASML": "EU",
    "TSM": "US",
}
TRACKED_ECONOMIC_KEYWORDS = (
    "interest rate decision",
    "rate decision",
    "cpi",
    "inflation",
    "ppi",
    "producer price",
    "non farm payrolls",
    "payrolls",
    "employment change",
    "employment report",
    "unemployment rate",
    "exports",
    "imports",
    "trade balance",
    "retail sales",
    "industrial production",
    "gdp",
    "pmi",
    "consumer confidence",
)


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
    return f"calendar:v3:KR:{year}:{month:02d}"


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
    if any(token in lower for token in ("fomc", "rate decision", "금통위", "interest rate", "monetary policy")):
        return "policy"
    if any(token in lower for token in ("cpi", "ppi", "inflation", "물가")):
        return "inflation"
    if any(token in lower for token in ("employment", "payroll", "unemployment", "고용")):
        return "labor"
    if any(token in lower for token in ("export", "imports", "trade", "수출", "수입")):
        return "trade"
    if any(token in lower for token in ("gdp", "production", "industrial", "광공업", "retail sales", "pmi", "confidence")):
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


def _describe_event(category: str, title_local: str, symbol: str | None = None, country_code: str = "KR") -> str:
    country_label = MARKET_COUNTRY_LABELS.get(country_code, "해외")
    if category == "earnings" and symbol:
        if country_code == "KR":
            return f"{symbol} 실적 발표 일정입니다. 실제치와 컨센서스 차이가 크면 업종 전반 심리까지 흔들 수 있습니다."
        return f"{country_label} 대표 기업 {symbol} 실적 일정입니다. 기술주와 반도체 심리, 한국 수출주 기대까지 함께 흔들 수 있습니다."
    descriptions = {
        "policy": f"{country_label} 통화정책 이벤트는 금리 기대, 환율, 성장주 밸류에이션에 직접 영향을 줄 수 있습니다.",
        "inflation": f"{country_label} 물가 지표는 글로벌 금리 경로 기대를 바꾸기 때문에 한국 성장주와 수출주 심리에도 바로 반영됩니다.",
        "labor": f"{country_label} 고용 지표는 경기 둔화 여부와 위험선호 흐름을 함께 흔들 수 있습니다.",
        "trade": f"{country_label} 수출입 흐름은 반도체와 경기민감 업종의 단기 모멘텀을 판단하는 선행 신호입니다.",
        "growth": f"{country_label} 생산과 성장 지표는 경기민감 업종의 이익 기대를 점검하는 데 도움이 됩니다.",
        "activity": f"{title_local} 일정은 한국 시장 심리에 영향을 줄 수 있습니다.",
    }
    return descriptions.get(category, descriptions["activity"])


def _impact_for_event(
    category: str,
    event_type: str,
    symbol: str | None = None,
    country_code: str = "KR",
) -> str:
    if event_type == "policy":
        return "high"
    if category in {"inflation", "trade"} and country_code in {"KR", "US"}:
        return "high"
    if event_type == "earnings" and symbol and symbol.upper() in TRACKED_EARNINGS_SYMBOL_COUNTRY:
        return "high"
    if event_type == "earnings":
        return "medium"
    if category in {"labor", "growth"}:
        return "medium"
    return "low"


def _normalize_market_country(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(re.sub(r"[^a-z]+", " ", str(value).lower()).split())
    if normalized in {"kr", "korea", "south korea", "republic of korea"}:
        return "KR"
    if normalized in {"us", "usa", "united states", "united states of america"}:
        return "US"
    if normalized in {"eu", "euro area", "euro zone", "eurozone", "european union"}:
        return "EU"
    if normalized in {"jp", "japan"}:
        return "JP"
    return None


def _localize_economic_event(country_code: str, title_en: str) -> str:
    exact = TITLE_LOCAL_MAP.get((country_code, title_en))
    if exact:
        return exact

    lower = title_en.lower()
    if "interest rate decision" in lower:
        base = "금리결정"
    elif "non farm payrolls" in lower or "payroll" in lower:
        base = "비농업고용"
    elif "cpi" in lower:
        base = "CPI 발표"
    elif "ppi" in lower or "producer price" in lower:
        base = "PPI 발표"
    elif "retail sales" in lower:
        base = "소매판매"
    elif "industrial production" in lower:
        base = "산업생산"
    elif "exports" in lower or "imports" in lower or "trade balance" in lower:
        base = "무역지표"
    elif "gdp" in lower:
        base = "GDP 발표"
    elif "unemployment" in lower or "employment change" in lower or "employment report" in lower:
        base = "고용지표"
    elif "pmi" in lower:
        base = "PMI 발표"
    elif "consumer confidence" in lower:
        base = "소비심리지수"
    elif "inflation" in lower:
        base = "인플레이션 지표"
    else:
        base = title_en
    return f"{MARKET_COUNTRY_LABELS.get(country_code, '해외')} {base}"


def _is_tracked_economic_event(country_code: str | None, title_en: str) -> bool:
    if country_code not in {"KR", "US", "EU", "JP"}:
        return False
    lower = title_en.lower()
    return any(keyword in lower for keyword in TRACKED_ECONOMIC_KEYWORDS)


def _tracked_symbol_country(symbol: str) -> str | None:
    upper = symbol.upper()
    if upper in TRACKED_EARNINGS_SYMBOL_COUNTRY:
        return TRACKED_EARNINGS_SYMBOL_COUNTRY[upper]
    if upper.endswith((".KS", ".KQ", ".KR")) or (upper.isdigit() and len(upper) == 6):
        return "KR"
    return None


def _normalize_economic_event(raw: dict, source: str) -> dict | None:
    date_str = _date_key(raw.get("date"))
    if not date_str:
        return None

    country_code = _normalize_market_country(raw.get("country"))
    title_en = str(raw.get("event") or raw.get("name") or "Economic Event").strip()
    if not _is_tracked_economic_event(country_code, title_en):
        return None

    category = _infer_category(title_en)
    event_type = "policy" if category == "policy" else "economic"
    title_local = _localize_economic_event(country_code or "KR", title_en)
    impact = _impact_for_event(category, event_type, country_code=country_code or "KR")

    subtitle_parts: list[str] = []
    actual = raw.get("actual")
    forecast = raw.get("forecast")
    if actual not in (None, "") and forecast not in (None, ""):
        subtitle_parts.append(f"실제 {actual} / 예상 {forecast}")
    elif forecast not in (None, ""):
        subtitle_parts.append(f"예상 {forecast}")

    return {
        "id": f"econ:{country_code or 'KR'}:{date_str}:{_slug(title_en)}",
        "date": date_str,
        "type": event_type,
        "category": category,
        "title": title_local,
        "title_en": title_en,
        "subtitle": " · ".join(subtitle_parts) if subtitle_parts else None,
        "description": _describe_event(category, title_local, country_code=country_code or "KR"),
        "impact": impact,
        "color": _color_for_event(event_type, impact),
        "source": source,
        "all_day": True,
        "time": None,
        "symbol": None,
        "country_code": country_code or "KR",
    }


def _normalize_earnings_event(raw: dict) -> dict | None:
    date_str = _date_key(raw.get("date"))
    symbol = str(raw.get("symbol") or "").strip().upper()
    country_code = _tracked_symbol_country(symbol)
    if not date_str or not symbol or not country_code:
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

    impact = _impact_for_event("earnings", "earnings", symbol, country_code=country_code)
    return {
        "id": f"earn:{country_code}:{date_str}:{_slug(symbol)}",
        "date": date_str,
        "type": "earnings",
        "category": "earnings",
        "title": f"{symbol} 실적 발표",
        "title_en": title_en,
        "subtitle": " · ".join(subtitle_parts) if subtitle_parts else None,
        "description": _describe_event("earnings", f"{symbol} 실적 발표", symbol=symbol, country_code=country_code),
        "impact": impact,
        "color": _color_for_event("earnings", impact),
        "source": "fmp",
        "all_day": True,
        "time": None,
        "symbol": symbol,
        "country_code": country_code,
    }


def _build_recurring_major_events(year: int, month: int) -> list[dict]:
    recurring_rules = (
        ("KR", "BOK Rate Decision", _pick_weekday_date(year, month, 9, 16, {3})),
        ("KR", "CPI Release", _pick_weekday_date(year, month, 1, 7)),
        ("KR", "Exports / Imports", _pick_weekday_date(year, month, 1, 3)),
        ("KR", "Employment Report", _pick_weekday_date(year, month, 10, 16)),
        ("US", "Interest Rate Decision", _pick_weekday_date(year, month, 18, 31, {2})),
        ("US", "CPI Release", _pick_weekday_date(year, month, 10, 15)),
        ("US", "Non Farm Payrolls", _pick_weekday_date(year, month, 1, 7, {4})),
        ("EU", "Interest Rate Decision", _pick_weekday_date(year, month, 4, 24, {3})),
        ("JP", "Interest Rate Decision", _pick_weekday_date(year, month, 15, 31, {1, 2})),
    )

    events: list[dict] = []
    for country_code, title_en, target_date in recurring_rules:
        if not target_date:
            continue
        major = MAJOR_EVENT_LOOKUP[(country_code, title_en)]
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
                "country_code": country_code,
            }
        )
    return events


def _merge_events(recurring: list[dict], actual_events: list[dict]) -> list[dict]:
    actual_titles = {
        (event.get("country_code"), event["title_en"])
        for event in actual_events
        if event["type"] in {"economic", "policy"}
    }
    merged = [
        event
        for event in recurring
        if (event.get("country_code"), event["title_en"]) not in actual_titles
    ]
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
    upcoming_events = [event for event in events if event["date"] >= now.date().isoformat()][:12]
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
            "note": note or "한국장 일정과 주요 해외 매크로·대표 기업 실적을 함께 반영했습니다.",
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
    partial_sources: list[str] = []

    async def _await_rows(loader, source_label: str) -> list[dict]:
        task = asyncio.create_task(loader())
        try:
            rows = await asyncio.wait_for(asyncio.shield(task), timeout=CALENDAR_SOURCE_WAIT_TIMEOUT_SECONDS)
            return rows or []
        except Exception:
            partial_sources.append(source_label)
            return []

    economic_rows, earnings_rows = await asyncio.gather(
        _await_rows(
            lambda: fmp_client.get_economic_calendar(
                grid_start.date().isoformat(),
                grid_end.date().isoformat(),
            ),
            "economic_calendar",
        ),
        _await_rows(
            lambda: fmp_client.get_earning_calendar(
                grid_start.date().isoformat(),
                grid_end.date().isoformat(),
            ),
            "earning_calendar",
        ),
    )

    actual_events = [
        event
        for event in [
            *(_normalize_economic_event(row, "fmp") for row in economic_rows),
            *(_normalize_earnings_event(row) for row in earnings_rows),
        ]
        if event is not None
    ]
    events = _merge_events(_build_recurring_major_events(target_year, target_month), actual_events)
    economic_source_status, earnings_source_status = await asyncio.gather(
        fmp_client.get_feature_status("economic_calendar"),
        fmp_client.get_feature_status("earning_calendar"),
    )
    partial = bool(partial_sources)
    fallback_reason = None
    note = None
    if economic_source_status or earnings_source_status:
        partial = True
        fallback_reason = "calendar_external_source_unavailable"
        note = "외부 캘린더 공급 제한으로 이번 달은 월간 핵심 일정 위주로 먼저 보여주고, 실제 세부 일정은 다른 공급원이 확보되면 보강합니다."
    elif partial_sources:
        fallback_reason = "calendar_live_partial_data"
        if actual_events:
            note = "외부 일정 일부가 지연돼 확인된 실제 국내·해외 일정부터 먼저 보여주고, 남은 항목은 캐시가 채워지면 바로 반영합니다."
        else:
            note = "외부 캘린더 연결이 늦어 한국과 해외 핵심 일정부터 먼저 보여주고, 실제 일정은 캐시가 채워지면 바로 반영합니다."
    elif not actual_events:
        note = "이번 달은 확인된 실제 일정이 많지 않아 한국과 해외 핵심 일정 위주로 먼저 보여줍니다."

    return _build_calendar_result(
        target_year=target_year,
        target_month=target_month,
        month_start=month_start,
        month_end=month_end,
        now=now,
        events=events,
        partial=partial,
        fallback_reason=fallback_reason,
        note=note,
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


async def prewarm_public_calendar_cache_seed() -> None:
    settings = get_settings()
    if not getattr(settings, "startup_memory_safe_mode", False):
        return

    now = datetime.now()
    target_year = now.year
    target_month = now.month
    cache_key = calendar_cache_key(target_year, target_month)
    cached = await cache.get(cache_key)
    if cached is not None:
        return

    seed_ttl = min(
        CALENDAR_STARTUP_SEED_TTL_SECONDS,
        max(1, int(getattr(settings, "cache_ttl_news", CALENDAR_STARTUP_SEED_TTL_SECONDS))),
    )
    payload = build_calendar_fallback(
        target_year,
        target_month,
        fallback_reason=CALENDAR_STARTUP_FALLBACK_REASON,
        note="배포 직후 첫 요청 지연을 줄이기 위해 이번 달 핵심 일정을 먼저 시드합니다. 외부 세부 일정은 캐시가 채워지면 바로 반영합니다.",
    )
    await cache.set(cache_key, payload, ttl=seed_ttl)


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
