"""Country-level analysis: aggregates data, calls LLM, builds report."""

import logging
from datetime import datetime
from app.data import yfinance_client, fred_client, ecos_client, boj_client, news_client, cache
from app.analysis.llm_client import ask_json
from app.analysis.prompts import country_report_prompt
from app.analysis.forecast_engine import forecast_index
from app.analysis.sentiment import get_news_sentiment_for_country
from app.scoring.country_scorer import build_country_score
from app.scoring.fear_greed import calculate_fear_greed
from app.models.country import COUNTRY_REGISTRY, CountryReport, StockSummaryRef, NewsItem, InstitutionalAnalysis, InstitutionView
from app.config import get_settings

log = logging.getLogger(__name__)


async def analyze_country(country_code: str) -> dict:
    settings = get_settings()
    cache_key = f"country_report:{country_code}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        return {"error": f"Unknown country: {country_code}"}

    economic_data = await _get_economic_data(country_code)
    market_data = {}
    for idx in country.indices:
        try:
            q = await yfinance_client.get_index_quote(idx.ticker)
            market_data[idx.name] = q
        except Exception as e:
            log.warning(f"Failed to get quote for {idx.ticker}: {e}")
            market_data[idx.name] = {"price": 0, "change_pct": 0}

    news_by_inst = await news_client.get_all_institution_news(
        country.research_institutions, country_code
    )
    market_news = await news_client.get_market_news(country_code)

    system, user = country_report_prompt(
        country.name, country_code,
        country.research_institutions,
        economic_data, news_by_inst, market_data,
    )
    llm_result = await ask_json(system, user)
    llm_failed = "error" in llm_result

    scores = llm_result.get("scores", {})
    country_score = build_country_score(scores)

    if llm_failed:
        institutional_analysis = InstitutionalAnalysis(
            policy_institutions=[], sell_side=[],
            policy_sellside_aligned=False, consensus_count=0,
            consensus_summary="LLM analysis unavailable - showing data only.",
        )
    else:
        inst_raw = llm_result.get("institutional_analysis", {})
        institutional_analysis = InstitutionalAnalysis(
            policy_institutions=[
                InstitutionView(**i) for i in inst_raw.get("policy_institutions", [])
            ],
            sell_side=[InstitutionView(**i) for i in inst_raw.get("sell_side", [])],
            policy_sellside_aligned=inst_raw.get("policy_sellside_aligned", False),
            consensus_count=inst_raw.get("consensus_count", 0),
            consensus_summary=inst_raw.get("consensus_summary", ""),
        )

    top_stocks = []
    if not llm_failed:
        top_tickers = llm_result.get("top_5_tickers", [])
        top_reasons = llm_result.get("top_5_reasons", [])
        for i, ticker in enumerate(top_tickers[:5]):
            try:
                info = await yfinance_client.get_stock_info(ticker)
                price = info.get("current_price", 0)
                prev = info.get("prev_close", price)
                chg = ((price - prev) / prev * 100) if prev else 0
                top_stocks.append(StockSummaryRef(
                    rank=i + 1, ticker=ticker,
                    name=info.get("name", ticker), score=0,
                    current_price=round(price, 2), change_pct=round(chg, 2),
                    reason=top_reasons[i] if i < len(top_reasons) else "",
                ))
            except Exception:
                top_stocks.append(StockSummaryRef(
                    rank=i + 1, ticker=ticker, name=ticker, score=0,
                    current_price=0, change_pct=0,
                    reason=top_reasons[i] if i < len(top_reasons) else "",
                ))

    key_news = [
        NewsItem(title=n["title"], source=n.get("source", ""), url=n.get("url", ""),
                 published=n.get("published", ""))
        for n in market_news[:10]
    ]

    primary_index = country.indices[0]
    price_hist = await yfinance_client.get_price_history(primary_index.ticker, period="1y")

    sentiment = await get_news_sentiment_for_country(market_news)
    vix_val = economic_data.get("vix") if country_code == "US" else None
    spread = economic_data.get("treasury_spread")

    fear_greed = calculate_fear_greed(
        price_hist, vix_value=vix_val, news_sentiment=sentiment,
        treasury_spread=spread, country_code=country_code,
    )

    news_summary = "\n".join(n["title"] for n in market_news[:10])
    try:
        forecast = await forecast_index(
            primary_index.ticker, primary_index.name, economic_data, news_summary
        )
        forecast_data = forecast.model_dump()
    except Exception as e:
        log.warning(f"Forecast failed: {e}")
        forecast_data = {"scenarios": [], "current_price": 0, "index_name": primary_index.name}

    market_summary = llm_result.get("market_summary", "")
    if llm_failed:
        market_summary = llm_result.get("error", "Analysis temporarily unavailable. Market data is still shown below.")

    report = {
        "country": country.model_dump(),
        "score": country_score.model_dump(),
        "market_summary": market_summary,
        "key_news": [n.model_dump() for n in key_news],
        "institutional_analysis": institutional_analysis.model_dump(),
        "top_stocks": [s.model_dump() for s in top_stocks],
        "fear_greed": fear_greed.model_dump(),
        "forecast": forecast_data,
        "market_data": market_data,
        "llm_available": not llm_failed,
        "generated_at": datetime.now().isoformat(),
    }

    ttl = settings.cache_ttl_report if not llm_failed else 120
    await cache.set(cache_key, report, ttl)
    return report


async def _get_economic_data(country_code: str) -> dict:
    if country_code == "US":
        data = await fred_client.get_us_economic_snapshot()
        spread = await fred_client.get_treasury_spread()
        data["treasury_spread"] = spread
        return data
    elif country_code == "KR":
        return await ecos_client.get_kr_economic_snapshot()
    elif country_code == "JP":
        return await boj_client.get_jp_economic_snapshot()
    return {}
