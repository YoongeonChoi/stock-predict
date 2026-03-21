"""Sector-level analysis: scores sector, ranks top 10 stocks."""

from datetime import datetime
from app.data import yfinance_client, news_client, cache
from app.analysis.llm_client import ask_json
from app.analysis.prompts import sector_report_prompt
from app.scoring.sector_scorer import build_sector_score
from app.scoring.stock_scorer import score_stock
from app.models.country import COUNTRY_REGISTRY
from app.config import get_settings


async def analyze_sector(country_code: str, sector_name: str) -> dict:
    settings = get_settings()
    sector_id = sector_name.lower().replace(" ", "_")
    cache_key = f"sector_report:{country_code}:{sector_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        return {"error": f"Unknown country: {country_code}"}

    tickers = await yfinance_client.get_sector_tickers(country_code, sector_name)
    if not tickers:
        return {"error": f"No tickers for sector {sector_name} in {country_code}"}

    stock_data = []
    for ticker in tickers[:15]:
        try:
            info = await yfinance_client.get_stock_info(ticker)
            prices = await yfinance_client.get_price_history(ticker, period="3mo")
            quant = score_stock(info, price_hist=prices)
            stock_data.append({
                **info,
                "quant_score": quant.total,
                "quant_detail": quant.model_dump(),
            })
        except Exception:
            continue

    inst_articles = []
    for inst in country.research_institutions[:3]:
        articles = await news_client.get_institution_news(
            inst, country_code, f"{sector_name} sector"
        )
        inst_articles.extend(articles)
    inst_news_text = "\n".join(f"- {a['title']} ({a.get('source', '')})" for a in inst_articles[:15])

    system, user = sector_report_prompt(
        sector_name, country_code, stock_data, inst_news_text
    )
    llm_result = await ask_json(system, user)
    llm_failed = "error_code" in llm_result or "error" in llm_result

    scores = llm_result.get("scores", {})
    sector_score = build_sector_score(scores)

    top_stocks = []
    if llm_failed:
        sorted_data = sorted(stock_data, key=lambda s: s.get("quant_score", 0), reverse=True)
        for i, sd in enumerate(sorted_data[:10]):
            price = sd.get("current_price", 0)
            prev = sd.get("prev_close", price)
            chg = ((price - prev) / prev * 100) if prev else 0
            top_stocks.append({
                "rank": i + 1, "ticker": sd.get("ticker", ""),
                "name": sd.get("name", sd.get("ticker", "")),
                "score": round(sd.get("quant_score", 0), 1),
                "current_price": round(price, 2), "change_pct": round(chg, 2),
                "pros": [], "cons": [], "buy_price": None, "sell_price": None,
            })
    else:
        top_10_raw = llm_result.get("top_10", [])
        for item in top_10_raw[:10]:
            ticker = item.get("ticker", "")
            matched = next((s for s in stock_data if s.get("ticker") == ticker), None)
            price = matched.get("current_price", 0) if matched else 0
            prev = matched.get("prev_close", price) if matched else price
            chg = ((price - prev) / prev * 100) if prev else 0
            q_score = matched.get("quant_score", 0) if matched else 0
            top_stocks.append({
                "rank": item.get("rank", 0), "ticker": ticker,
                "name": item.get("name", ticker),
                "score": round(q_score, 1), "current_price": round(price, 2),
                "change_pct": round(chg, 2),
                "pros": item.get("pros", []), "cons": item.get("cons", []),
                "buy_price": item.get("buy_price"), "sell_price": item.get("sell_price"),
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
