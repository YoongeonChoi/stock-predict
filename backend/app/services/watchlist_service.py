"""Watchlist CRUD with enriched stock data."""

from app.database import db
from app.data import yfinance_client
from app.scoring.stock_scorer import score_stock


async def get_watchlist() -> list[dict]:
    items = await db.watchlist_list()
    enriched = []
    for item in items:
        ticker = item["ticker"]
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
            })
        except Exception:
            enriched.append({**item, "name": ticker, "current_price": 0, "change_pct": 0, "score_total": 0})
    return enriched


async def add_to_watchlist(ticker: str, country_code: str):
    await db.watchlist_add(ticker, country_code)


async def remove_from_watchlist(ticker: str):
    await db.watchlist_remove(ticker)
