"""Country-level analysis: aggregates data, calls LLM, builds report."""

from datetime import datetime
from app.data import yfinance_client, fred_client, ecos_client, boj_client, news_client, cache
from app.analysis.llm_client import ask_json
from app.analysis.prompts import country_report_prompt
from app.analysis.forecast_engine import forecast_index
from app.analysis.sentiment import get_news_sentiment_for_country
from app.scoring.country_scorer import build_country_score
from app.scoring.stock_scorer import score_stock
from app.scoring.fear_greed import calculate_fear_greed
from app.models.country import COUNTRY_REGISTRY, CountryReport, StockSummaryRef, NewsItem, InstitutionalAnalysis, InstitutionView
from app.config import get_settings
from app.errors import SP_2005, SP_3004, SP_6001

TICKER_FALLBACK = {
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "네이버": "035420.KS",
    "카카오": "035720.KS", "LG화학": "051910.KS", "현대차": "005380.KS",
    "기아": "000270.KS", "삼성SDI": "006400.KS", "셀트리온": "068270.KS",
    "POSCO홀딩스": "005490.KS", "삼성바이오로직스": "207940.KS", "LG에너지솔루션": "373220.KS",
    "현대모비스": "012330.KS", "KB금융": "105560.KS", "신한지주": "055550.KS",
    "삼성물산": "028260.KS", "SK이노베이션": "096770.KS", "LG전자": "066570.KS",
    "한국전력": "015760.KS", "SK텔레콤": "017670.KS", "KT": "030200.KS",
    "포스코퓨처엠": "003670.KS", "엔씨소프트": "036570.KS", "크래프톤": "259960.KS",
    "하이브": "352820.KS", "두산에너빌리티": "034020.KS", "한화에어로스페이스": "012450.KS",
    "トヨタ": "7203.T", "ソニー": "6758.T", "任天堂": "7974.T",
    "ソフトバンク": "9984.T", "キーエンス": "6861.T", "三菱UFJ": "8306.T",
    "Toyota": "7203.T", "Sony": "6758.T", "Nintendo": "7974.T",
    "SoftBank": "9984.T", "Keyence": "6861.T",
}


async def analyze_country(country_code: str) -> dict:
    settings = get_settings()
    cache_key = f"country_report:{country_code}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        err = SP_6001(country_code)
        err.log()
        return err.to_dict()

    economic_data = await _get_economic_data(country_code)
    market_data = {}
    for idx in country.indices:
        try:
            q = await yfinance_client.get_index_quote(idx.ticker)
            market_data[idx.name] = q
        except Exception as e:
            SP_2005(idx.ticker).log("warning")
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
    llm_failed = "error_code" in llm_result or "error" in llm_result

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

    llm_reasons = {}
    if not llm_failed:
        raw_tickers = llm_result.get("top_5_tickers", [])
        top_reasons = llm_result.get("top_5_reasons", [])
        for i, t in enumerate(raw_tickers[:5]):
            resolved = TICKER_FALLBACK.get(t, t)
            llm_reasons[resolved] = top_reasons[i] if i < len(top_reasons) else ""

    top_stocks = await _score_top_stocks(country_code, llm_reasons)

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
        SP_3004(str(e)[:150]).log("warning")
        forecast_data = {"scenarios": [], "current_price": 0, "index_name": primary_index.name}

    market_summary = llm_result.get("market_summary", "")
    if llm_failed:
        market_summary = llm_result.get("message", llm_result.get("error", "Analysis temporarily unavailable."))

    errors = []
    if llm_failed:
        errors.append(llm_result.get("error_code", "SP-4005"))

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
        "errors": errors,
        "generated_at": datetime.now().isoformat(),
    }

    ttl = settings.cache_ttl_report if not llm_failed else 120
    await cache.set(cache_key, report, ttl)
    return report


async def _score_top_stocks(
    country_code: str, llm_reasons: dict[str, str]
) -> list[StockSummaryRef]:
    """Score a sample of stocks from the country and return top 5 by score."""
    from app.data.universe_data import get_universe
    universe = await get_universe(country_code)
    all_tickers: list[str] = []
    for sector_tickers in universe.values():
        all_tickers.extend(sector_tickers[:8])

    scored: list[tuple[float, str, dict]] = []
    for ticker in all_tickers:
        try:
            info = await yfinance_client.get_stock_info(ticker)
            if not info.get("current_price"):
                continue
            prices = await yfinance_client.get_price_history(ticker, period="3mo")
            qs = score_stock(info, price_hist=prices)
            scored.append((qs.total, ticker, info))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)

    top_stocks = []
    for rank, (total_score, ticker, info) in enumerate(scored[:5], start=1):
        price = info.get("current_price", 0)
        prev = info.get("prev_close", price)
        chg = ((price - prev) / prev * 100) if prev else 0
        reason = llm_reasons.get(ticker, f"Score: {total_score:.1f}/100")
        top_stocks.append(StockSummaryRef(
            rank=rank, ticker=ticker,
            name=info.get("name", ticker), score=round(total_score, 1),
            current_price=round(price, 2), change_pct=round(chg, 2),
            reason=reason,
        ))

    return top_stocks


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
