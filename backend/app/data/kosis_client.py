"""Optional KOSIS client using KOSIS statistics IDs on the shared API."""

from __future__ import annotations

import httpx

from app.config import get_settings
from app.data import cache
from app.errors import SP_2003

BASE_URL = "https://kosis.kr/openapi/statisticsData.do"

SERIES = {
    "cpi": {"setting_key": "kosis_cpi_stats_id", "prd_se": "M", "new_est_prd_cnt": 3},
    "employment": {"setting_key": "kosis_employment_stats_id", "prd_se": "M", "new_est_prd_cnt": 3},
    "industrial_production": {"setting_key": "kosis_industrial_production_stats_id", "prd_se": "M", "new_est_prd_cnt": 3},
}


async def get_series(stats_id: str, prd_se: str = "M", count: int = 3) -> list[dict]:
    settings = get_settings()
    if not (settings.kosis_api_key and stats_id):
        return []

    async def _fetch():
        params = {
            "method": "getList",
            "apiKey": settings.kosis_api_key,
            "format": "json",
            "jsonVD": "Y",
            "userStatsId": stats_id,
            "prdSe": prd_se,
            "newEstPrdCnt": max(1, count),
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(BASE_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            SP_2003(str(exc)[:150]).log("warning")
            return []

        if not isinstance(payload, list):
            return []

        rows: list[dict] = []
        for item in payload:
            rows.append(
                {
                    "date": str(item.get("PRD_DE") or ""),
                    "value": _parse_value(item.get("DT")),
                    "name": item.get("TBL_NM") or "",
                }
            )
        return rows

    return await cache.get_or_fetch(
        f"kosis:{stats_id}:{prd_se}:{count}",
        _fetch,
        settings.cache_ttl_economic,
    )


async def get_kr_macro_snapshot() -> dict:
    settings = get_settings()
    snapshot: dict[str, float | None] = {}
    for key, spec in SERIES.items():
        stats_id = getattr(settings, spec["setting_key"], "")
        rows = await get_series(
            stats_id=stats_id,
            prd_se=spec["prd_se"],
            count=spec["new_est_prd_cnt"],
        )
        snapshot[key] = rows[-1]["value"] if rows else None
    return snapshot


def _parse_value(value) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
