from __future__ import annotations

import re
from functools import lru_cache

from app.data.universe_data import GICS_SECTORS, UNIVERSE
from app.models.country import COUNTRY_REGISTRY

_SUFFIX_COUNTRY = {
    ".KS": "KR",
    ".KQ": "KR",
    ".KR": "KR",
}

_PREFIX_COUNTRY = {
    "KRX": "KR",
    "KOSPI": "KR",
    "KOSDAQ": "KR",
    "KR": "KR",
}


@lru_cache(maxsize=1)
def _build_universe_maps() -> dict[str, dict]:
    by_ticker: dict[str, dict] = {}
    kr_by_base: dict[str, list[str]] = {}

    for country_code, sectors in UNIVERSE.items():
        for sector_name, tickers in sectors.items():
            for raw_ticker in tickers:
                ticker = str(raw_ticker or "").strip().upper()
                if not ticker:
                    continue
                by_ticker[ticker] = {
                    "ticker": ticker,
                    "country_code": country_code,
                    "sector": sector_name if sector_name in GICS_SECTORS else "Unknown",
                }
                base = ticker.split(".")[0]
                if country_code == "KR" and re.fullmatch(r"\d{6}", base):
                    kr_by_base.setdefault(base, []).append(ticker)

    for country in COUNTRY_REGISTRY.values():
        for index in country.indices:
            ticker = index.ticker.upper()
            by_ticker.setdefault(
                ticker,
                {
                    "ticker": ticker,
                    "country_code": country.code,
                    "sector": "Index",
                },
            )

    return {
        "by_ticker": by_ticker,
        "kr_by_base": kr_by_base,
    }


def normalize_country_code(country_code: str | None) -> str:
    normalized = str(country_code or "KR").strip().upper() or "KR"
    if normalized not in COUNTRY_REGISTRY:
        return "KR"
    return normalized


def _split_prefix(raw_ticker: str) -> tuple[str | None, str]:
    text = str(raw_ticker or "").strip().upper()
    if ":" in text:
        prefix, remainder = text.split(":", 1)
        prefix_country = _PREFIX_COUNTRY.get(prefix.strip())
        if prefix_country:
            return prefix_country, remainder.strip()
    return None, text


def _suffix_country(ticker: str) -> str | None:
    upper = ticker.upper()
    for suffix, country_code in _SUFFIX_COUNTRY.items():
        if upper.endswith(suffix):
            return country_code
    return None


def _candidate_note(match_basis: str, input_ticker: str, resolved_ticker: str) -> str:
    if match_basis == "verbatim":
        return "입력한 한국 티커 형식을 그대로 사용합니다."
    if match_basis == "kr_numeric":
        return f"{input_ticker} 숫자 코드를 한국 시장 표준 티커 {resolved_ticker}로 맞췄습니다."
    if match_basis == "prefixed":
        return f"KRX 접두어를 제거하고 표준 티커 {resolved_ticker}로 정리했습니다."
    if match_basis == "inferred":
        return f"입력한 값에 가장 가까운 한국 표준 티커 {resolved_ticker}를 적용했습니다."
    return "표준 한국 티커 형식으로 정리했습니다."


def get_ticker_metadata(ticker: str) -> dict:
    maps = _build_universe_maps()
    return maps["by_ticker"].get(
        ticker.upper(),
        {
            "ticker": ticker.upper(),
            "country_code": _suffix_country(ticker.upper()) or "KR",
            "sector": "Unknown",
        },
    )


def resolve_ticker(raw_ticker: str, country_code: str | None = "KR") -> dict:
    requested_country = normalize_country_code(country_code)
    input_value = str(raw_ticker or "").strip()
    prefix_country, candidate = _split_prefix(input_value)
    maps = _build_universe_maps()

    normalized = candidate.replace(" ", "").upper()
    if not normalized:
        return {
            "input_ticker": input_value,
            "normalized_input": "",
            "ticker": "",
            "country_code": requested_country,
            "sector": "Unknown",
            "match_basis": "empty",
            "confidence": "low",
            "matched": False,
            "note": "티커를 입력해 주세요.",
        }

    if normalized in maps["by_ticker"]:
        metadata = maps["by_ticker"][normalized]
        match_basis = "prefixed" if prefix_country else "verbatim"
        return {
            "input_ticker": input_value,
            "normalized_input": normalized,
            "ticker": normalized,
            "country_code": metadata["country_code"],
            "sector": metadata["sector"],
            "match_basis": match_basis,
            "confidence": "high",
            "matched": True,
            "note": _candidate_note(match_basis, input_value, normalized),
        }

    suffix_country = _suffix_country(normalized)
    if suffix_country == "KR":
        metadata = get_ticker_metadata(normalized)
        return {
            "input_ticker": input_value,
            "normalized_input": normalized,
            "ticker": normalized,
            "country_code": "KR",
            "sector": metadata["sector"],
            "match_basis": "verbatim",
            "confidence": "medium",
            "matched": normalized in maps["by_ticker"],
            "note": _candidate_note("verbatim", input_value, normalized),
        }

    if re.fullmatch(r"\d{6}", normalized):
        candidates = maps["kr_by_base"].get(normalized, [])
        resolved = candidates[0] if candidates else f"{normalized}.KS"
        metadata = get_ticker_metadata(resolved)
        return {
            "input_ticker": input_value,
            "normalized_input": normalized,
            "ticker": resolved,
            "country_code": "KR",
            "sector": metadata["sector"],
            "match_basis": "kr_numeric",
            "confidence": "high" if candidates else "medium",
            "matched": bool(candidates),
            "note": _candidate_note("kr_numeric", input_value, resolved),
        }

    return {
        "input_ticker": input_value,
        "normalized_input": normalized,
        "ticker": normalized,
        "country_code": "KR",
        "sector": get_ticker_metadata(normalized)["sector"],
        "match_basis": "inferred",
        "confidence": "low",
        "matched": False,
        "note": _candidate_note("inferred", input_value, normalized),
    }


async def search_candidates(query: str, country_code: str | None = None, limit: int = 15) -> list[dict]:
    q_upper = str(query or "").strip().upper()
    if not q_upper:
        return []

    resolved = resolve_ticker(q_upper, country_code)
    maps = _build_universe_maps()
    by_ticker = maps["by_ticker"]
    results: list[dict] = []
    seen: set[str] = set()

    def _append(ticker: str, match_basis: str):
        if ticker in seen:
            return
        meta = get_ticker_metadata(ticker)
        results.append(
            {
                "ticker": ticker,
                "country_code": meta["country_code"],
                "sector": meta["sector"],
                "match_basis": match_basis,
                "resolution_note": resolved["note"] if ticker == resolved["ticker"] else "",
            }
        )
        seen.add(ticker)

    if resolved["ticker"]:
        _append(resolved["ticker"], resolved["match_basis"])

    for ticker, meta in by_ticker.items():
        base = ticker.split(".")[0]
        if q_upper in ticker or q_upper == base or q_upper in base:
            _append(ticker, "partial_ticker")
            continue
        sector = str(meta.get("sector") or "").upper()
        if q_upper in sector:
            _append(ticker, "partial_sector")

    ordered = sorted(
        results,
        key=lambda item: (
            0 if item["ticker"] == resolved["ticker"] else 1,
            item["ticker"],
        ),
    )
    return ordered[:limit]
