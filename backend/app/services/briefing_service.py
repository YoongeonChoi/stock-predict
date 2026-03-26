from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.data import cache
from app.database import db
from app.services import calendar_service, market_service, market_session_service


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
            calendar = await calendar_service.get_calendar(country_code, year, month)
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


async def get_daily_briefing() -> dict:
    today = datetime.now().date().isoformat()
    cache_key = f"daily_briefing:v1:{today}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    sessions_task = market_session_service.get_market_sessions()
    radar_tasks = [market_service.get_market_opportunities(code, 4) for code in ("KR",)]
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

    response = {
        "generated_at": datetime.now().isoformat(),
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
    await cache.set(cache_key, response, 300)
    return response
