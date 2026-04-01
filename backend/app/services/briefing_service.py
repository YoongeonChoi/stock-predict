from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
import time

from app.data import cache
from app.database import db
from app.services import calendar_service, market_service, market_session_service

log = logging.getLogger("stock_predict.briefing")
BRIEFING_RADAR_TIMEOUT_SECONDS = 8
BRIEFING_CACHE_TTL_SECONDS = 300
BRIEFING_CALENDAR_WAIT_TIMEOUT_SECONDS = 2.5


def _build_briefing_request_trace(
    *,
    started_at: float,
    request_phase: str,
    cache_state: str,
    timeout_budget_ms: int | None,
    fallback_reason: str | None,
    served_state: str,
    upstream_source: str,
) -> dict:
    return {
        "request_phase": request_phase,
        "cache_state": cache_state,
        "cold_start_suspected": cache_state == "miss",
        "upstream_source": upstream_source,
        "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
        "timeout_budget_ms": timeout_budget_ms,
        "fallback_reason": fallback_reason,
        "served_state": served_state,
    }


def _annotate_briefing_response(
    payload: dict,
    *,
    started_at: float,
    request_phase: str,
    cache_state: str,
    fallback_tier: str,
    timeout_budget_ms: int | None,
    upstream_source: str,
    fallback_reason: str | None = None,
    served_state: str | None = None,
) -> dict:
    response = dict(payload)
    effective_fallback_reason = fallback_reason if fallback_reason is not None else response.get("fallback_reason")
    if effective_fallback_reason:
        response["fallback_reason"] = effective_fallback_reason
    response["fallback_tier"] = fallback_tier
    response["request_trace"] = _build_briefing_request_trace(
        started_at=started_at,
        request_phase=request_phase,
        cache_state=cache_state,
        timeout_budget_ms=timeout_budget_ms,
        fallback_reason=effective_fallback_reason,
        served_state=served_state or ("partial" if response.get("partial") else "fresh"),
        upstream_source=upstream_source,
    )
    return response


def _event_score(event: dict) -> tuple:
    impact_rank = {"high": 0, "medium": 1, "low": 2}.get(event.get("impact", "medium"), 1)
    return (event.get("date", "9999-12-31"), impact_rank, event.get("country_code", "ZZ"), event.get("title", ""))


def _event_summary(event: dict) -> str:
    base = f"{event.get('country_code')} {event.get('title')}"
    subtitle = event.get("subtitle")
    if subtitle:
        return f"{base} · {subtitle}"
    return base


async def _upcoming_events() -> list[dict]:
    now = datetime.now()
    today = now.date()
    upcoming: list[dict] = []
    months = {(today.year, today.month)}
    if (today + timedelta(days=14)).month != today.month:
        next_month = today + timedelta(days=31)
        months.add((next_month.year, next_month.month))

    for country_code in ("KR",):
        for year, month in sorted(months):
            calendar = await cache.get(calendar_service.calendar_cache_key(year, month))
            if not calendar:
                calendar = calendar_service.build_calendar_fallback(
                    year,
                    month,
                    fallback_reason="calendar_snapshot_pending",
                    note="브리핑에서는 월간 핵심 일정만 먼저 사용하고, 세부 캘린더는 다시 동기화되면 이어서 반영합니다.",
                )
            for event in calendar.get("events", []):
                event_date = str(event.get("date") or "")
                if not event_date or event_date < today.isoformat():
                    continue
                if event.get("impact") not in {"high", "medium"}:
                    continue
                upcoming.append(event)

    upcoming.sort(key=_event_score)
    deduped: list[dict] = []
    seen: set[str] = set()
    for event in upcoming:
        key = str(event.get("id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(
            {
                "date": event.get("date"),
                "country_code": event.get("country_code"),
                "title": event.get("title"),
                "subtitle": event.get("subtitle"),
                "impact": event.get("impact"),
                "type": event.get("type"),
                "summary": _event_summary(event),
            }
        )
        if len(deduped) >= 6:
            break
    return deduped


def _build_priority_lines(sessions: list[dict], radar_map: dict[str, dict], archive_status: dict) -> list[str]:
    lines: list[str] = []

    kr = radar_map.get("KR")
    if kr and kr.get("opportunities"):
        top = kr["opportunities"][0]
        lines.append(
            f"한국 레이더 최상단은 {top['ticker']} ({top['name']})로, 상방 확률 {top['up_probability']:.1f}%와 액션 `{top['action']}` 신호가 함께 나왔습니다."
        )

    open_markets = [item["name_local"] for item in sessions if item.get("is_open")]
    if open_markets:
        lines.append(f"현재 정규장이 진행 중인 시장은 {', '.join(open_markets)}이며, 예측 엔진은 마지막 완결 종가를 기준으로 유지됩니다.")
    else:
        lines.append("현재 주요 시장은 정규장이 닫혀 있어, 최신 완결 종가 기준으로 다음 거래일 예측을 점검하기 좋은 시간대입니다.")

    todays_reports = int(archive_status.get("todays_reports") or 0)
    if todays_reports:
        lines.append(f"공공 리서치 아카이브에는 오늘자 보고서가 {todays_reports}건 반영돼 있어, 거시 판단을 함께 교차 점검할 수 있습니다.")

    return lines[:4]


def _radar_fallback(country_code: str, note: str) -> dict:
    return {
        "country_code": country_code,
        "generated_at": datetime.now().isoformat(),
        "market_regime": {
            "label": "요약 지연",
            "stance": "neutral",
            "conviction": 0,
            "summary": note,
        },
        "total_scanned": 0,
        "actionable_count": 0,
        "bullish_count": 0,
        "universe_source": "fallback",
        "universe_note": note,
        "opportunities": [],
    }


async def _load_briefing_radar(country_code: str) -> dict:
    cached_full = await market_service.get_cached_market_opportunities(country_code, 4, max_candidates=8)
    if cached_full and cached_full.get("opportunities"):
        return cached_full

    cached_quick = await market_service.get_cached_market_opportunities_quick(country_code, 4)
    if cached_quick and cached_quick.get("opportunities"):
        return cached_quick

    try:
        return await asyncio.wait_for(
            market_service.get_market_opportunities_quick(country_code, 4),
            timeout=max(4.0, BRIEFING_RADAR_TIMEOUT_SECONDS / 2),
        )
    except asyncio.TimeoutError:
        note = "공개 추천 계산이 길어져 브리핑에는 요약만 표시합니다."
        log.warning("Daily briefing radar timed out for %s after %ss", country_code, BRIEFING_RADAR_TIMEOUT_SECONDS)
        return _radar_fallback(country_code, note)
    except Exception as exc:
        note = "공개 추천 계산에 실패해 브리핑에는 요약만 표시합니다."
        log.warning("Daily briefing radar failed for %s: %s", country_code, exc, exc_info=True)
        return _radar_fallback(country_code, note)


async def get_daily_briefing() -> dict:
    started_at = time.perf_counter()
    today = datetime.now().date().isoformat()
    cache_key = f"daily_briefing:v1:{today}"
    cached, cache_source = await cache.get_with_source(cache_key)
    if cached:
        return _annotate_briefing_response(
            cached,
            started_at=started_at,
            request_phase="quick",
            cache_state=cache_source,
            fallback_tier="cached",
            timeout_budget_ms=0,
            upstream_source="daily_briefing_cache",
        )

    sessions_task = market_session_service.get_market_sessions()
    radar_tasks = [_load_briefing_radar(code) for code in ("KR",)]
    archive_task = db.research_report_status(today)
    events_task = _upcoming_events()

    sessions_data, radar_results, archive_status, upcoming_events = await asyncio.gather(
        sessions_task,
        asyncio.gather(*radar_tasks),
        archive_task,
        events_task,
    )

    radar_map = {item["country_code"]: item for item in radar_results}
    country_views = []
    focus_cards = []
    for country_code in ("KR",):
        radar = radar_map.get(country_code) or {}
        regime = radar.get("market_regime") or {}
        opportunities = radar.get("opportunities") or []
        top = opportunities[0] if opportunities else None
        country_views.append(
            {
                "country_code": country_code,
                "label": regime.get("label", "중립"),
                "stance": regime.get("stance", "neutral"),
                "conviction": round(float(regime.get("conviction") or 0), 1),
                "actionable_count": int(radar.get("actionable_count") or 0),
                "bullish_count": int(radar.get("bullish_count") or 0),
                "summary": regime.get("summary", ""),
            }
        )
        if top:
            focus_cards.append(
                {
                    "country_code": country_code,
                    "ticker": top["ticker"],
                    "name": top["name"],
                    "sector": top["sector"],
                    "action": top["action"],
                    "up_probability": top["up_probability"],
                    "confidence": top["confidence"],
                    "predicted_return_pct": top["predicted_return_pct"],
                    "execution_note": top.get("execution_note"),
                }
            )

    partial = any(not item.get("opportunities") for item in radar_results)
    fallback_reason = "briefing_partial_snapshot" if partial else None
    response = {
        "generated_at": datetime.now().isoformat(),
        "partial": partial,
        "fallback_reason": fallback_reason,
        "sessions": sessions_data["sessions"],
        "market_view": country_views,
        "focus_cards": focus_cards,
        "upcoming_events": upcoming_events,
        "research_archive": {
            "todays_reports": int(archive_status.get("todays_reports") or 0),
            "total_reports": int(archive_status.get("total_reports") or 0),
            "source_count": int(archive_status.get("source_count") or 0),
            "last_synced_at": archive_status.get("last_synced_at"),
        },
        "priorities": _build_priority_lines(sessions_data["sessions"], radar_map, archive_status),
    }
    await cache.set(cache_key, response, BRIEFING_CACHE_TTL_SECONDS)
    return _annotate_briefing_response(
        response,
        started_at=started_at,
        request_phase="quick",
        cache_state="miss",
        fallback_tier="quick" if partial else "full",
        timeout_budget_ms=BRIEFING_RADAR_TIMEOUT_SECONDS * 1000,
        upstream_source="daily_briefing_build",
    )


async def get_daily_briefing_fallback(note: str) -> dict:
    started_at = time.perf_counter()
    now = datetime.now()
    sessions_data = await market_session_service.get_market_sessions()
    upcoming_events = await _upcoming_events()
    today = now.date().isoformat()
    archive_status = await db.research_report_status(today)
    return _annotate_briefing_response({
        "generated_at": now.isoformat(),
        "partial": True,
        "fallback_reason": "briefing_timeout",
        "sessions": sessions_data["sessions"],
        "market_view": [
            {
                "country_code": "KR",
                "label": "브리핑 지연",
                "stance": "neutral",
                "conviction": 0.0,
                "actionable_count": 0,
                "bullish_count": 0,
                "summary": note,
            }
        ],
        "focus_cards": [],
        "upcoming_events": upcoming_events[:3],
        "research_archive": {
            "todays_reports": int(archive_status.get("todays_reports") or 0),
            "total_reports": int(archive_status.get("total_reports") or 0),
            "source_count": int(archive_status.get("source_count") or 0),
            "last_synced_at": archive_status.get("last_synced_at"),
        },
        "priorities": [
            "브리핑 전체 계산이 길어져 지금은 핵심 일정과 세션 상태를 먼저 보여줍니다.",
            "레이더 후보는 같은 화면을 다시 열거나 잠시 뒤 새로고침하면 quick 스냅샷부터 다시 붙습니다.",
        ],
    },
        started_at=started_at,
        request_phase="quick",
        cache_state="miss",
        fallback_tier="degraded",
        timeout_budget_ms=None,
        upstream_source="daily_briefing_fallback",
        served_state="degraded",
    )
