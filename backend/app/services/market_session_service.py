from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.country import COUNTRY_REGISTRY
from app.utils import market_calendar

_DISPLAY_TZ = {
    "US": ZoneInfo("America/New_York"),
    "KR": ZoneInfo("Asia/Seoul"),
    "JP": ZoneInfo("Asia/Tokyo"),
}

_AFTER_HOURS_NOTE = {
    "US": "무료 데이터 기준으로 프리마켓·애프터마켓 일부는 보일 수 있지만, 예측 엔진은 완결 종가만 기준으로 사용합니다.",
    "KR": "현재 무료 데이터 스택에서는 한국 시간외 단일가 가격을 안정적으로 반영하지 않습니다.",
    "JP": "현재 무료 데이터 스택에서는 일본 장후 가격을 안정적으로 반영하지 않습니다.",
}


def _to_local_label(dt: datetime | None, country_code: str) -> str | None:
    if dt is None:
        return None
    tz = _DISPLAY_TZ[country_code]
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def _phase_label(snapshot: dict) -> str:
    if snapshot.get("is_open"):
        return "정규장 진행 중"
    if snapshot.get("trading_day_today") and snapshot.get("next_event") == "open":
        return "개장 전"
    if snapshot.get("trading_day_today"):
        return "정규장 종료"
    return "휴장"


def _readiness_note(snapshot: dict) -> str:
    latest_closed = snapshot.get("latest_closed_date")
    if snapshot.get("is_open"):
        return f"예측 기준 종가는 {latest_closed} 마감값이며, 오늘 장이 끝나면 자동으로 갱신됩니다."
    if snapshot.get("trading_day_today"):
        return f"오늘 장은 마감되었고, {latest_closed} 종가 기준으로 다음 거래일 예측이 준비됐습니다."
    return f"최근 완결 종가는 {latest_closed}이며, 다음 거래일 전까지 동일 기준으로 유지됩니다."


async def get_market_sessions(reference_time: datetime | None = None) -> dict:
    sessions = []
    for country_code, country in COUNTRY_REGISTRY.items():
        snapshot = market_calendar.market_session_snapshot(country_code, reference_time)
        sessions.append(
            {
                "country_code": country_code,
                "name": country.name,
                "name_local": country.name_local,
                "currency": country.currency,
                "phase": _phase_label(snapshot),
                "is_open": snapshot["is_open"],
                "trading_day_today": snapshot["trading_day_today"],
                "latest_closed_date": snapshot["latest_closed_date"],
                "next_trading_day": snapshot["next_trading_day"],
                "session_token": snapshot["session_token"],
                "opened_at": _to_local_label(snapshot.get("opened_at"), country_code),
                "closed_at": _to_local_label(snapshot.get("closed_at"), country_code),
                "next_open_at": _to_local_label(snapshot.get("next_open_at"), country_code),
                "next_close_at": _to_local_label(snapshot.get("next_close_at"), country_code),
                "after_hours_supported": country_code == "US",
                "provider_note": _AFTER_HOURS_NOTE[country_code],
                "forecast_ready_note": _readiness_note(snapshot),
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "sessions": sessions,
    }
