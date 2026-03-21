"""Stock comparison service."""

from app.data import yfinance_client
from app.scoring.stock_scorer import score_stock


async def compare_stocks(tickers: list[str]) -> list[dict]:
    results = []
    for ticker in tickers[:4]:
        try:
            info = await yfinance_client.get_stock_info(ticker)
            prices = await yfinance_client.get_price_history(ticker, period="3mo")
            qs = score_stock(info, price_hist=prices)
            price = info.get("current_price", 0)
            prev = info.get("prev_close", price)
            chg = ((price - prev) / prev * 100) if prev else 0
            results.append({
                "ticker": ticker,
                "name": info.get("name", ticker),
                "sector": info.get("sector", "N/A"),
                "current_price": round(price, 2),
                "change_pct": round(chg, 2),
                "market_cap": info.get("market_cap", 0),
                "pe_ratio": info.get("pe_ratio"),
                "pb_ratio": info.get("pb_ratio"),
                "ev_ebitda": info.get("ev_ebitda"),
                "roe": info.get("roe"),
                "revenue_growth": info.get("revenue_growth"),
                "dividend_yield": info.get("dividend_yield"),
                "beta": info.get("beta"),
                "score": qs.model_dump(),
                "price_history": prices,
            })
        except Exception:
            results.append({"ticker": ticker, "error": "Failed to fetch data"})
    return results
