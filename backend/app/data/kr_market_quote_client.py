"""KR bulk quote client for full-market first-pass scans.

Uses Naver Finance market-cap pages for KOSPI/KOSDAQ bulk quotes and falls back
to yfinance for any remaining KR tickers such as KONEX names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.data import cache, yfinance_client
from app.utils.async_tools import gather_limited
from app.utils.market_calendar import latest_closed_trading_day, market_session_cache_token

NAVER_MARKET_SUM_URL = "https://finance.naver.com/sise/sise_market_sum.naver"
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0 Safari/537.36"
    ),
    "Referer": "https://finance.naver.com/",
}
NAVER_KOSPI = 0
NAVER_KOSDAQ = 1
NAVER_PAGE_CONCURRENCY = 6
KR_BULK_QUOTE_TTL = 900
KR_REMAINDER_FALLBACK_LIMIT = 180
KR_SMALL_REQUEST_FAST_PATH_LIMIT = 120
TICKER_CODE_PATTERN = re.compile(r"\d{6}")


@dataclass(slots=True)
class MarketPageQuote:
    ticker: str
    name: str
    current_price: float
    prev_close: float
    change_pct: float
    market_cap: float


def _to_float(value: str | None) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _extract_code_from_href(href: str | None) -> str | None:
    if not href:
        return None
    parsed = urlparse(href)
    code = parse_qs(parsed.query).get("code", [None])[0]
    if code and TICKER_CODE_PATTERN.fullmatch(code):
        return code
    return None


def _derive_prev_close(current_price: float, change_pct: float) -> float:
    if current_price <= 0:
        return 0.0
    denominator = 1.0 + (change_pct / 100.0)
    if abs(denominator) < 1e-9:
        return current_price
    return current_price / denominator


def _parse_last_page(soup: BeautifulSoup) -> int:
    anchor = soup.select_one("td.pgRR a")
    if not anchor:
        return 1
    href = anchor.get("href", "")
    match = re.search(r"[?&]page=(\d+)", href)
    if not match:
        return 1
    return max(int(match.group(1)), 1)


def _parse_market_page_quotes(html: str, *, suffix: str) -> tuple[int, dict[str, dict]]:
    soup = BeautifulSoup(html, "html.parser")
    last_page = _parse_last_page(soup)
    quotes: dict[str, dict] = {}

    for row in soup.select("table.type_2 tr"):
        link = row.select_one("a.tltle")
        if link is None:
            continue
        code = _extract_code_from_href(link.get("href"))
        if code is None:
            continue

        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        current_price = _to_float(cells[2].get_text(" ", strip=True))
        change_pct = _to_float(cells[4].get_text(" ", strip=True))
        market_cap_uk = _to_float(cells[6].get_text(" ", strip=True))
        if current_price is None or change_pct is None:
            continue

        ticker = f"{code}{suffix}"
        prev_close = _derive_prev_close(current_price, change_pct)
        quotes[ticker] = {
            "ticker": ticker,
            "name": link.get_text(strip=True),
            "current_price": round(current_price, 2),
            "prev_close": round(prev_close, 2),
            "change_pct": round(change_pct, 2),
            "market_cap": round((market_cap_uk or 0.0) * 100_000_000, 2),
            "session_date": latest_closed_trading_day("KR").isoformat(),
        }
    return last_page, quotes


async def _fetch_market_page(client: httpx.AsyncClient, *, sosok: int, page: int, suffix: str) -> tuple[int, dict[str, dict]]:
    response = await client.get(
        NAVER_MARKET_SUM_URL,
        params={"sosok": sosok, "page": page},
        headers=NAVER_HEADERS,
    )
    response.raise_for_status()
    return _parse_market_page_quotes(response.text, suffix=suffix)


async def _fetch_market_quotes(sosok: int, *, suffix: str) -> dict[str, dict]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        first_last_page, first_quotes = await _fetch_market_page(client, sosok=sosok, page=1, suffix=suffix)
        if first_last_page <= 1:
            return first_quotes

        async def _worker(page: int) -> dict[str, dict]:
            _, quotes = await _fetch_market_page(client, sosok=sosok, page=page, suffix=suffix)
            return quotes

        merged = dict(first_quotes)
        for result in await gather_limited(range(2, first_last_page + 1), _worker, limit=NAVER_PAGE_CONCURRENCY):
            if isinstance(result, Exception):
                continue
            merged.update(result)
        return merged


async def _fetch_full_kr_market_quotes() -> dict[str, dict]:
    session_token = market_session_cache_token(country_code="KR")
    settings = get_settings()

    async def _fetch():
        kospi_quotes, kosdaq_quotes = await gather_limited(
            [
                (NAVER_KOSPI, ".KS"),
                (NAVER_KOSDAQ, ".KQ"),
            ],
            lambda item: _fetch_market_quotes(item[0], suffix=item[1]),
            limit=2,
        )
        merged: dict[str, dict] = {}
        for chunk in (kospi_quotes, kosdaq_quotes):
            if isinstance(chunk, Exception):
                continue
            merged.update(chunk)
        return merged

    return await cache.get_or_fetch(
        f"kr_market_quotes:{session_token}",
        _fetch,
        min(max(settings.cache_ttl_price, 300), KR_BULK_QUOTE_TTL),
    )


def _normalize_yfinance_quote(ticker: str, quote: dict) -> dict | None:
    current_price = float(quote.get("current_price") or 0.0)
    if current_price <= 0:
        return None
    return {
        "ticker": ticker,
        "name": yfinance_client._kr_ticker_name(ticker) or ticker.split(".")[0],
        "current_price": round(current_price, 2),
        "prev_close": round(float(quote.get("prev_close") or current_price), 2),
        "change_pct": round(float(quote.get("change_pct") or 0.0), 2),
        "market_cap": 0.0,
        "session_date": quote.get("session_date"),
    }


async def get_kr_bulk_quotes(
    requested_tickers: list[str],
    *,
    skip_full_market_fallback: bool = False,
) -> dict[str, dict]:
    requested = list(dict.fromkeys(str(ticker or "").upper() for ticker in requested_tickers if ticker))
    if not requested:
        return {}

    if len(requested) <= KR_SMALL_REQUEST_FAST_PATH_LIMIT:
        fast_quotes = await yfinance_client.get_batch_stock_quotes(requested, period="5d")
        normalized_fast = {
            ticker: normalized
            for ticker in requested
            if (normalized := _normalize_yfinance_quote(ticker, fast_quotes.get(ticker) or {})) is not None
        }
        minimum_coverage = min(len(requested), max(4, (len(requested) * 3 + 3) // 4))
        if len(normalized_fast) >= minimum_coverage or skip_full_market_fallback:
            return normalized_fast

    available = await _fetch_full_kr_market_quotes()
    quotes = {
        ticker: available[ticker]
        for ticker in requested
        if ticker in available
    }

    missing = [ticker for ticker in requested if ticker not in quotes]
    if missing and len(missing) <= KR_REMAINDER_FALLBACK_LIMIT:
        fallback_quotes = await yfinance_client.get_batch_stock_quotes(missing, period="5d")
        for ticker in missing:
            normalized = _normalize_yfinance_quote(ticker, fallback_quotes.get(ticker) or {})
            if normalized is not None:
                quotes[ticker] = normalized

    return quotes
