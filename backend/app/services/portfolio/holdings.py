from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from app.services.portfolio.validation import validate_portfolio_holding_input


StockInfoLoader = Callable[[str], Awaitable[dict[str, Any]]]


async def build_holding_write_payload(
    ticker: str,
    buy_price: float,
    quantity: float,
    buy_date: str,
    country_code: str,
    *,
    stock_info_loader: StockInfoLoader,
) -> dict[str, Any]:
    payload = validate_portfolio_holding_input(ticker, buy_price, quantity, buy_date, country_code)
    normalized_ticker = str(payload["ticker"])
    normalized_country = str(payload["country_code"])

    try:
        info = await stock_info_loader(normalized_ticker)
        name = info.get("name", normalized_ticker)
    except Exception:
        name = normalized_ticker

    return {
        "ticker": normalized_ticker,
        "name": name,
        "country_code": normalized_country,
        "buy_price": float(payload["buy_price"]),
        "quantity": float(payload["quantity"]),
        "buy_date": str(payload["buy_date"]),
    }
