from __future__ import annotations

from app.data.universe_data import UniverseSelection

from .shared import safe_float


def flatten_universe(universe: dict[str, list[str]]) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sector, tickers in universe.items():
        for ticker in tickers:
            if ticker in seen:
                continue
            seen.add(ticker)
            flattened.append((sector, ticker))
    return flattened


def sample_universe_pairs(universe: dict[str, list[str]], limit: int) -> list[tuple[str, str]]:
    if limit <= 0:
        return []
    sector_names = list(universe.keys())
    offsets = {sector: 0 for sector in sector_names}
    sampled: list[tuple[str, str]] = []
    seen: set[str] = set()

    while len(sampled) < limit:
        advanced = False
        for sector in sector_names:
            tickers = universe.get(sector) or []
            index = offsets[sector]
            while index < len(tickers) and tickers[index] in seen:
                index += 1
            offsets[sector] = index
            if index >= len(tickers):
                continue
            ticker = tickers[index]
            offsets[sector] = index + 1
            seen.add(ticker)
            sampled.append((sector, ticker))
            advanced = True
            if len(sampled) >= limit:
                break
        if not advanced:
            break

    return sampled


def build_sector_lookup(universe: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for sector, tickers in universe.items():
        for ticker in tickers:
            normalized = str(ticker or "").upper()
            if normalized and normalized not in lookup:
                lookup[normalized] = sector
    return lookup


def group_ranked_quotes_by_sector(ranked_quotes: list[dict]) -> dict[str, list[str]]:
    sectors: dict[str, list[str]] = {}
    for item in ranked_quotes:
        ticker = str(item.get("ticker") or "").upper()
        sector = str(item.get("sector") or "대표 후보").strip() or "대표 후보"
        if not ticker:
            continue
        sectors.setdefault(sector, []).append(ticker)
    return sectors


def build_seeded_quote_screen_from_quick_payload(
    payload: dict | None,
    *,
    candidate_limit: int,
) -> tuple[UniverseSelection, dict] | None:
    if not payload:
        return None
    opportunities = list(payload.get("opportunities") or [])
    if not opportunities:
        return None

    ranked_quotes: list[dict] = []
    for item in opportunities:
        ticker = str(item.get("ticker") or "").upper()
        current_price = safe_float(item.get("current_price"), 0.0)
        if not ticker or current_price <= 0:
            continue
        ranked_quotes.append(
            {
                "sector": str(item.get("sector") or "대표 후보").strip() or "대표 후보",
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "change_pct": round(safe_float(item.get("change_pct")), 2),
            }
        )
        if len(ranked_quotes) >= candidate_limit:
            break

    if not ranked_quotes:
        return None

    universe_source = str(payload.get("universe_source") or "fallback")
    universe_note = str(payload.get("universe_note") or "").strip()
    seeded_note = "최근 usable quick 후보를 seed로 정밀 후보 계산을 다시 시도합니다."
    selection = UniverseSelection(
        sectors=group_ranked_quotes_by_sector(ranked_quotes),
        source=universe_source,
        note=" ".join(part for part in [universe_note, seeded_note] if part).strip(),
    )
    quote_screen = {
        "universe_size": int(payload.get("universe_size") or len(ranked_quotes)),
        "scanned_count": int(payload.get("total_scanned") or len(ranked_quotes)),
        "quote_available_count": int(payload.get("quote_available_count") or len(ranked_quotes)),
        "ranked": ranked_quotes,
    }
    return selection, quote_screen

