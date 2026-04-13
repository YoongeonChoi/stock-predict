from __future__ import annotations

from collections import defaultdict


def _exposure_map(holdings: list[dict], field: str) -> dict[str, float]:
    grouped: dict[str, float] = defaultdict(float)
    for holding in holdings:
        grouped[str(holding.get(field) or "Other")] += float(holding.get("weight_pct") or 0.0)
    return {key: round(value, 2) for key, value in grouped.items()}


def build_recommendation_context_maps(holdings: list[dict], watchlist_rows: list[dict]) -> dict[str, dict]:
    return {
        "watchlist_keys": {
            f"{row.get('country_code', 'KR')}:{row.get('ticker')}"
            for row in watchlist_rows
            if row.get("ticker")
        },
        "holding_lookup": {
            f"{item.get('country_code', 'KR')}:{item.get('ticker')}": item
            for item in holdings
            if item.get("ticker")
        },
        "country_exposure": _exposure_map(holdings, "country_code"),
        "sector_exposure": _exposure_map(holdings, "sector"),
    }
