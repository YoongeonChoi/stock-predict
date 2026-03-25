"""Korean stock universe provider.

Tries FMP Stock Screener API first for dynamic KRX data.
Falls back to a curated KOSPI/KOSDAQ universe when the free source is missing
or temporarily unstable.
"""

import asyncio
import logging
from dataclasses import dataclass

from app.config import get_settings
from app.utils.async_tools import gather_limited

log = logging.getLogger("stock_predict.universe")

GICS_SECTORS = [
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
]

EXCHANGE_MAP = {
    "KR": ["KSE"],
}

SUFFIX_MAP = {"KR": ".KS"}
INVALID_TICKERS = {
    "091990.KS",
    "098560.KS",
    "042670.KS",
    "006390.KS",
    "119860.KS",
    "002270.KS",
    "002550.KS",
    "003410.KS",
    "010620.KS",
    "034300.KS",
    "049770.KS",
}


@dataclass(slots=True)
class UniverseSelection:
    sectors: dict[str, list[str]]
    source: str
    note: str = ""


def _sanitize_tickers(tickers: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = str(raw or "").strip().upper()
        if not ticker or ticker in INVALID_TICKERS or ticker in seen:
            continue
        seen.add(ticker)
        cleaned.append(ticker)
    return cleaned


async def fetch_dynamic_universe(country_code: str) -> dict[str, list[str]] | None:
    """Try fetching top Korean stocks per sector from FMP Stock Screener API."""
    if country_code != "KR":
        return None

    try:
        from app.data import cache, fmp_client

        cached = await cache.get(f"dynamic_universe:{country_code}")
        if cached:
            return cached

        exchanges = EXCHANGE_MAP.get(country_code, [])
        if not exchanges:
            return None

        market_cap_min = 100_000_000
        probe_results = await gather_limited(
            exchanges,
            lambda exchange: fmp_client.probe_stock_screener(
                exchange=exchange,
                market_cap_min=market_cap_min,
            ),
            limit=max(1, min(3, len(exchanges))),
        )
        available_exchanges = [
            exchange
            for exchange, allowed in zip(exchanges, probe_results)
            if not isinstance(allowed, Exception) and allowed
        ]
        if not available_exchanges:
            return None

        result: dict[str, list[str]] = {}
        suffix = SUFFIX_MAP.get(country_code, "")

        async def _fetch_sector(sector: str):
            tickers: list[str] = []
            tasks = [
                fmp_client.screen_stocks(
                    exchange=exchange,
                    sector=sector,
                    market_cap_min=market_cap_min,
                    limit=60,
                )
                for exchange in available_exchanges
            ]
            for fetched in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(fetched, Exception):
                    continue
                for ticker in fetched:
                    if suffix and not ticker.endswith(suffix):
                        ticker = ticker + suffix
                    if ticker not in tickers:
                        tickers.append(ticker)
            tickers = _sanitize_tickers(tickers)
            if tickers:
                return sector, tickers[:50]
            return sector, []

        for item in await gather_limited(GICS_SECTORS, _fetch_sector, limit=4):
            if isinstance(item, Exception):
                continue
            sector, tickers = item
            if tickers:
                result[sector] = tickers

        if len(result) >= 5:
            await cache.set(f"dynamic_universe:{country_code}", result, 86400)
            log.info(
                "Dynamic universe for %s: %s tickers across %s sectors",
                country_code,
                sum(len(v) for v in result.values()),
                len(result),
            )
            return result
    except Exception as exc:
        log.warning("Dynamic universe fetch failed for %s: %s", country_code, exc)
    return None


async def get_universe(country_code: str) -> dict[str, list[str]]:
    """Get stock universe: dynamic first, curated fallback."""
    return (await resolve_universe(country_code)).sectors


def _fallback_universe(country_code: str) -> dict[str, list[str]]:
    return {
        sector: _sanitize_tickers(tickers)
        for sector, tickers in UNIVERSE.get(country_code, {}).items()
    }


def _fallback_note() -> str:
    settings = get_settings()
    if not settings.fmp_api_key:
        return "FMP API 키가 없어 검증된 한국 기본 종목군으로 추천 중입니다."
    return "실시간 FMP 스크리너 연결이 제한돼 검증된 한국 기본 종목군으로 추천 중입니다."


async def resolve_universe(country_code: str) -> UniverseSelection:
    """Return universe data with source metadata."""
    dynamic = await fetch_dynamic_universe(country_code)
    if dynamic:
        return UniverseSelection(
            sectors={sector: _sanitize_tickers(tickers) for sector, tickers in dynamic.items()},
            source="dynamic",
        )
    return UniverseSelection(
        sectors=_fallback_universe(country_code),
        source="fallback",
        note=_fallback_note(),
    )


KR = {
    "Information Technology": [
        "005930.KS",
        "000660.KS",
        "035420.KS",
        "035720.KS",
        "036570.KS",
        "263750.KS",
        "034730.KS",
        "066570.KS",
        "006400.KS",
        "009150.KS",
        "402340.KS",
        "377300.KS",
        "058470.KS",
        "042700.KS",
        "018260.KS",
        "005387.KS",
        "005935.KS",
        "000990.KS",
        "010620.KS",
        "011070.KS",
        "012450.KS",
        "064350.KS",
        "086900.KS",
        "041510.KS",
        "302440.KS",
    ],
    "Financials": [
        "105560.KS",
        "055550.KS",
        "086790.KS",
        "316140.KS",
        "024110.KS",
        "138930.KS",
        "003550.KS",
        "005830.KS",
        "032830.KS",
        "071050.KS",
        "000810.KS",
        "029780.KS",
        "005940.KS",
        "003410.KS",
        "001450.KS",
        "002550.KS",
        "005387.KS",
        "090350.KS",
        "030000.KS",
        "006800.KS",
        "139130.KS",
        "175330.KS",
        "024110.KS",
        "006360.KS",
        "088350.KS",
    ],
    "Consumer Discretionary": [
        "005380.KS",
        "000270.KS",
        "012330.KS",
        "051910.KS",
        "004020.KS",
        "003490.KS",
        "004170.KS",
        "069960.KS",
        "161390.KS",
        "030200.KS",
        "011200.KS",
        "097950.KS",
        "004370.KS",
        "007310.KS",
        "003240.KS",
        "001040.KS",
        "023530.KS",
        "028050.KS",
        "006260.KS",
        "005300.KS",
        "014680.KS",
        "001680.KS",
        "005740.KS",
        "003920.KS",
        "007700.KS",
    ],
    "Industrials": [
        "010130.KS",
        "028260.KS",
        "009540.KS",
        "042660.KS",
        "011200.KS",
        "010140.KS",
        "034020.KS",
        "047050.KS",
        "000120.KS",
        "267250.KS",
        "000880.KS",
        "042670.KS",
        "009830.KS",
        "003570.KS",
        "002380.KS",
        "001740.KS",
        "000150.KS",
        "034730.KS",
        "011790.KS",
        "006260.KS",
        "047040.KS",
        "003030.KS",
        "014820.KS",
        "004490.KS",
        "069460.KS",
    ],
    "Materials": [
        "051910.KS",
        "005490.KS",
        "010130.KS",
        "011170.KS",
        "006800.KS",
        "003670.KS",
        "004000.KS",
        "001120.KS",
        "078930.KS",
        "005300.KS",
        "006390.KS",
        "011780.KS",
        "001520.KS",
        "000720.KS",
        "014580.KS",
        "010060.KS",
        "008930.KS",
        "004090.KS",
        "000210.KS",
        "004980.KS",
        "092780.KS",
        "008350.KS",
        "069620.KS",
        "023150.KS",
        "019170.KS",
    ],
    "Health Care": [
        "207940.KS",
        "068270.KS",
        "128940.KS",
        "326030.KS",
        "145020.KS",
        "196170.KQ",
        "004090.KS",
        "001630.KS",
        "195940.KS",
        "185750.KS",
        "214370.KS",
        "141080.KS",
        "006280.KS",
        "003060.KS",
        "002390.KS",
        "000100.KS",
        "119860.KS",
        "294870.KS",
        "237690.KS",
        "263750.KS",
    ],
    "Energy": [
        "096770.KS",
        "010950.KS",
        "267250.KS",
        "078930.KS",
        "006120.KS",
        "007070.KS",
        "003620.KS",
        "011760.KS",
        "036460.KS",
        "014680.KS",
        "006650.KS",
        "005090.KS",
        "014530.KS",
        "001510.KS",
        "004090.KS",
        "078520.KS",
        "009770.KS",
        "004170.KS",
        "003580.KS",
        "117580.KS",
    ],
    "Consumer Staples": [
        "097950.KS",
        "271560.KS",
        "004370.KS",
        "033780.KS",
        "280360.KS",
        "005610.KS",
        "005180.KS",
        "004990.KS",
        "014710.KS",
        "007310.KS",
        "001680.KS",
        "005740.KS",
        "003920.KS",
        "002270.KS",
        "003230.KS",
        "034120.KS",
        "016360.KS",
        "049770.KS",
        "007070.KS",
        "004410.KS",
    ],
    "Communication Services": [
        "030200.KS",
        "036570.KS",
        "035720.KS",
        "251270.KS",
        "041510.KS",
        "035900.KS",
        "293490.KS",
        "352820.KS",
        "259960.KS",
        "018260.KS",
        "017670.KS",
        "032640.KS",
        "078340.KS",
        "034830.KS",
        "030520.KS",
        "215600.KS",
        "053800.KS",
        "048410.KS",
        "060250.KS",
        "054220.KS",
    ],
    "Utilities": [
        "015760.KS",
        "034590.KS",
        "017390.KS",
        "071090.KS",
        "053210.KS",
        "006360.KS",
        "001440.KS",
        "029780.KS",
        "025820.KS",
        "003580.KS",
        "093370.KS",
        "071320.KS",
        "034590.KS",
        "130660.KS",
        "006040.KS",
        "032350.KS",
        "023350.KS",
        "025530.KS",
        "004150.KS",
        "036580.KS",
    ],
    "Real Estate": [
        "316140.KS",
        "377300.KS",
        "395400.KS",
        "365550.KS",
        "334890.KS",
        "448730.KS",
        "357120.KS",
        "417310.KS",
        "432320.KS",
        "330590.KS",
        "010960.KS",
        "012630.KS",
        "005010.KS",
        "003300.KS",
        "009770.KS",
        "023000.KS",
        "034300.KS",
        "006340.KS",
        "003520.KS",
        "001430.KS",
    ],
}

UNIVERSE = {"KR": KR}
