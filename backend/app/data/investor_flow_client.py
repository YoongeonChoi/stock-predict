"""Best-effort investor flow signals, with pykrx support for Korea."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

from app.data import cache
from app.models.forecast import FlowSignal
from app.utils.async_tools import run_blocking

log = logging.getLogger("stock_predict.investor_flow")

try:
    from pykrx import stock as pykrx_stock
except Exception:  # pragma: no cover - optional dependency safety
    pykrx_stock = None

KRX_MARKET_BY_TICKER = {
    "^KS11": "KOSPI",
    "^KQ11": "KOSDAQ",
}


def _parse_date(value: str | date | datetime | None) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def _resolve_anchor(reference_date: str | date | datetime | None, price_history: list[dict] | None) -> date:
    if price_history:
        last_date = price_history[-1].get("date")
        if last_date:
            return _parse_date(last_date)
    return _parse_date(reference_date)


def _normalize_kr_ticker(ticker: str) -> str:
    return re.sub(r"\.(KS|KQ)$", "", ticker, flags=re.IGNORECASE)


def _pick_column(columns: list[str], *needles: str) -> str | None:
    normalized = {re.sub(r"\s+", "", str(col)): str(col) for col in columns}
    for needle in needles:
        for compact, original in normalized.items():
            if needle in compact:
                return original
    return None


def _safe_sum(df, column: str | None, window: int = 5) -> float | None:
    if not column or column not in df.columns:
        return None
    try:
        value = float(df[column].tail(window).sum())
        return round(value, 2)
    except Exception:
        return None


def _fetch_kr_flow_sync(market: str | None, ticker: str | None, anchor_date: date) -> dict:
    if pykrx_stock is None:
        return FlowSignal(available=False, source="pykrx_unavailable", market=market or "", unit="KRW").model_dump()

    end_date = anchor_date.strftime("%Y%m%d")
    start_date = (anchor_date - timedelta(days=21)).strftime("%Y%m%d")
    query = market or _normalize_kr_ticker(ticker or "")

    try:
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        if previous_level <= logging.INFO:
            root_logger.setLevel(logging.WARNING)
        try:
            df = pykrx_stock.get_market_trading_value_by_date(start_date, end_date, query)
        finally:
            if root_logger.level != previous_level:
                root_logger.setLevel(previous_level)
    except Exception as exc:
        log.warning("investor flow fetch failed for %s: %s", query, exc)
        return FlowSignal(
            available=False,
            source="pykrx_error",
            market=market or query,
            unit="KRW",
        ).model_dump()

    if df is None or getattr(df, "empty", True):
        return FlowSignal(
            available=False,
            source="pykrx_empty",
            market=market or query,
            unit="KRW",
        ).model_dump()

    columns = [str(col) for col in df.columns]
    foreign_col = _pick_column(columns, "외국인합계", "외국인", "외국인투자자")
    institutional_col = _pick_column(columns, "기관합계", "기관")
    retail_col = _pick_column(columns, "개인")

    signal = FlowSignal(
        available=True,
        source="pykrx",
        market=market or query,
        unit="KRW",
        foreign_net_buy=_safe_sum(df, foreign_col),
        institutional_net_buy=_safe_sum(df, institutional_col),
        retail_net_buy=_safe_sum(df, retail_col),
    )
    return signal.model_dump()


async def get_flow_signal(
    country_code: str,
    *,
    ticker: str | None = None,
    market: str | None = None,
    reference_date: str | date | datetime | None = None,
    price_history: list[dict] | None = None,
) -> FlowSignal:
    """Return best-effort net-buying flow data for the requested market or ticker."""
    if country_code != "KR":
        return FlowSignal(available=False, source="not_supported", market=market or ticker or "", unit="")

    anchor = _resolve_anchor(reference_date, price_history)
    resolved_market = market or KRX_MARKET_BY_TICKER.get(ticker or "", "")
    cache_key = f"flow:KR:{resolved_market or ticker}:{anchor.isoformat()}"

    async def _fetch():
        return await run_blocking(_fetch_kr_flow_sync, resolved_market or None, ticker, anchor)

    data = await cache.get_or_fetch(cache_key, _fetch, ttl=3600)
    return FlowSignal(**data) if data else FlowSignal(
        available=False,
        source="unavailable",
        market=resolved_market or ticker or "",
        unit="KRW",
    )
