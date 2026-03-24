"""Watchlist CRUD with enriched stock data."""

from app.database import db
from app.data import yfinance_client
from app.scoring.stock_scorer import score_stock
from app.services import ticker_resolver_service


async def get_watchlist() -> list[dict]:
    items = await db.watchlist_list()
    enriched = []
    for item in items:
        resolution = ticker_resolver_service.resolve_ticker(item["ticker"], item.get("country_code"))
        ticker = resolution["ticker"] or item["ticker"]
        if ticker != item["ticker"] or resolution["country_code"] != item.get("country_code"):
            try:
                await db.watchlist_update(item["id"], ticker, resolution["country_code"])
                item["ticker"] = ticker
                item["country_code"] = resolution["country_code"]
            except Exception:
                pass
        try:
            info = await yfinance_client.get_stock_info(ticker)
            prices = await yfinance_client.get_price_history(ticker, period="3mo")
            qs = score_stock(info, price_hist=prices)
            price = info.get("current_price", 0)
            prev = info.get("prev_close", price)
            chg = ((price - prev) / prev * 100) if prev else 0
            enriched.append({
                **item,
                "name": info.get("name", ticker),
                "current_price": round(price, 2),
                "change_pct": round(chg, 2),
                "score_total": round(qs.total, 1),
                "resolution_note": resolution["note"],
            })
        except Exception:
            enriched.append({
                **item,
                "ticker": ticker,
                "country_code": resolution["country_code"],
                "name": ticker,
                "current_price": 0,
                "change_pct": 0,
                "score_total": 0,
                "resolution_note": resolution["note"],
            })
    return enriched


async def add_to_watchlist(ticker: str, country_code: str):
    resolution = ticker_resolver_service.resolve_ticker(ticker, country_code)
    await db.watchlist_add(resolution["ticker"], resolution["country_code"])
    return resolution


async def remove_from_watchlist(ticker: str):
    resolution = ticker_resolver_service.resolve_ticker(ticker)
    await db.watchlist_remove(resolution["ticker"] or ticker.upper())
