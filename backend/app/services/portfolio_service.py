from app.database import db
from app.data import yfinance_client


async def get_portfolio():
    """Get portfolio with current prices and P&L calculation."""
    holdings = await db.portfolio_list()

    enriched = []
    total_invested = 0
    total_current = 0

    sectors = {}
    countries = {}

    for h in holdings:
        ticker = h["ticker"]
        try:
            info = await yfinance_client.get_stock_info(ticker)
            current_price = info.get("current_price", 0)
            sector = info.get("sector", "Other")
        except Exception:
            current_price = h["buy_price"]
            sector = "Unknown"

        invested = h["buy_price"] * h["quantity"]
        current_val = current_price * h["quantity"]
        pnl = current_val - invested
        pnl_pct = (pnl / invested * 100) if invested else 0

        total_invested += invested
        total_current += current_val

        country = h.get("country_code", "US")
        sectors[sector] = sectors.get(sector, 0) + current_val
        countries[country] = countries.get(country, 0) + current_val

        enriched.append({
            "id": h["id"],
            "ticker": ticker,
            "name": h.get("name") or info.get("name", ticker),
            "country_code": country,
            "sector": sector,
            "buy_price": h["buy_price"],
            "current_price": round(current_price, 2),
            "quantity": h["quantity"],
            "buy_date": h["buy_date"],
            "invested": round(invested, 2),
            "current_value": round(current_val, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    sector_alloc = [{"name": k, "value": round(v, 2)} for k, v in sorted(sectors.items(), key=lambda x: x[1], reverse=True)]
    country_alloc = [{"name": k, "value": round(v, 2)} for k, v in sorted(countries.items(), key=lambda x: x[1], reverse=True)]

    return {
        "holdings": enriched,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "holding_count": len(enriched),
        },
        "allocation": {
            "by_sector": sector_alloc,
            "by_country": country_alloc,
        },
    }


async def add_holding(ticker: str, buy_price: float, quantity: float, buy_date: str, country_code: str = "US"):
    try:
        info = await yfinance_client.get_stock_info(ticker)
        name = info.get("name", ticker)
    except Exception:
        name = ticker
    await db.portfolio_add(ticker, name, country_code, buy_price, quantity, buy_date)


async def remove_holding(holding_id: int):
    await db.portfolio_delete(holding_id)
