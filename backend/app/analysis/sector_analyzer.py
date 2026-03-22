"""Sector-level analysis: scores sector, ranks top stocks."""

import asyncio
from datetime import datetime

from app.analysis.llm_client import ask_json
from app.analysis.prompts import sector_report_prompt
from app.config import get_settings
from app.data import cache, news_client, yfinance_client
from app.models.country import COUNTRY_REGISTRY
from app.scoring.sector_scorer import build_sector_score
from app.scoring.stock_scorer import score_stock
from app.utils.async_tools import gather_limited


async def analyze_sector(country_code: str, sector_name: str) -> dict:
    settings = get_settings()
    sector_id = sector_name.lower().replace(" ", "_")
    cache_key = f"sector_report:v2:{country_code}:{sector_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        return {"error": f"Unknown country: {country_code}"}

    tickers = await yfinance_client.get_sector_tickers(country_code, sector_name)
    if not tickers:
        return {"error": f"No tickers for sector {sector_name} in {country_code}"}

    async def _load_stock(ticker: str):
        info, prices = await asyncio.gather(
            yfinance_client.get_stock_info(ticker),
            yfinance_client.get_price_history(ticker, period="3mo"),
        )
        quant = score_stock(info, price_hist=prices)
        return {
            **info,
            "quant_score": quant.total,
            "quant_detail": quant.model_dump(),
        }

    stock_data = []
    for item in await gather_limited(tickers[:15], _load_stock, limit=6):
        if isinstance(item, Exception):
            continue
        stock_data.append(item)

    async def _load_inst_news(institution: str):
        return await news_client.get_institution_news(institution, country_code, f"{sector_name} sector")

    inst_articles = []
    for item in await gather_limited(country.research_institutions[:3], _load_inst_news, limit=3):
        if isinstance(item, Exception):
            continue
        inst_articles.extend(item)
    inst_news_text = "\n".join(f"- {article['title']} ({article.get('source', '')})" for article in inst_articles[:15])

    system, user = sector_report_prompt(
        sector_name, country_code, stock_data, inst_news_text
    )
    llm_result = await ask_json(system, user)
    llm_failed = "error_code" in llm_result or "error" in llm_result

    scores = llm_result.get("scores", {})
    sector_score = build_sector_score(scores)

    quant_sorted = sorted(stock_data, key=lambda stock: stock.get("quant_score", 0), reverse=True)
    quant_index = {stock.get("ticker", ""): stock for stock in quant_sorted}

    top_stocks = []
    if not llm_failed:
        requested = llm_result.get("top_10", [])
        seen = set()
        for item in requested[:10]:
            ticker = item.get("ticker", "")
            matched = quant_index.get(ticker)
            if not matched:
                continue
            seen.add(ticker)
            price = matched.get("current_price", 0)
            prev = matched.get("prev_close", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            top_stocks.append({
                "rank": len(top_stocks) + 1,
                "ticker": ticker,
                "name": item.get("name", matched.get("name", ticker)),
                "score": round(matched.get("quant_score", 0), 1),
                "current_price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "pros": item.get("pros", []),
                "cons": item.get("cons", []),
                "buy_price": item.get("buy_price"),
                "sell_price": item.get("sell_price"),
            })

        for fallback in quant_sorted:
            if len(top_stocks) >= 10:
                break
            ticker = fallback.get("ticker", "")
            if ticker in seen:
                continue
            price = fallback.get("current_price", 0)
            prev = fallback.get("prev_close", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            top_stocks.append({
                "rank": len(top_stocks) + 1,
                "ticker": ticker,
                "name": fallback.get("name", ticker),
                "score": round(fallback.get("quant_score", 0), 1),
                "current_price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "pros": [],
                "cons": [],
                "buy_price": None,
                "sell_price": None,
            })
    else:
        for fallback in quant_sorted[:10]:
            price = fallback.get("current_price", 0)
            prev = fallback.get("prev_close", price)
            change_pct = ((price - prev) / prev * 100) if prev else 0
            top_stocks.append({
                "rank": len(top_stocks) + 1,
                "ticker": fallback.get("ticker", ""),
                "name": fallback.get("name", fallback.get("ticker", "")),
                "score": round(fallback.get("quant_score", 0), 1),
                "current_price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "pros": [],
                "cons": [],
                "buy_price": None,
                "sell_price": None,
            })

    summary = llm_result.get("summary", "")
    if llm_failed:
        summary = llm_result.get("error", "AI analysis unavailable. Showing quantitative rankings only.")

    errors = []
    if llm_failed:
        errors.append(llm_result.get("error_code", "SP-4005"))

    report = {
        "sector": {
            "id": sector_id,
            "name": sector_name,
            "country_code": country_code,
            "stock_count": len(tickers),
        },
        "score": sector_score.model_dump(),
        "summary": summary,
        "top_stocks": top_stocks,
        "llm_available": not llm_failed,
        "errors": errors,
        "generated_at": datetime.now().isoformat(),
    }

    ttl = settings.cache_ttl_report if not llm_failed else 120
    await cache.set(cache_key, report, ttl)
    return report
