"""Country-level analysis: aggregates data, calls LLM, builds report."""

import asyncio
from datetime import datetime

from app.analysis.forecast_engine import forecast_index
from app.analysis.llm_client import ask_json
from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.prompts import country_report_prompt
from app.analysis.sentiment import get_news_sentiment_for_country
from app.config import get_settings
from app.data import (
    boj_client,
    cache,
    ecos_client,
    fred_client,
    investor_flow_client,
    news_client,
    yfinance_client,
)
from app.errors import SP_2005, SP_3004, SP_6001
from app.models.country import (
    COUNTRY_REGISTRY,
    InstitutionalAnalysis,
    InstitutionView,
    NewsItem,
    StockSummaryRef,
)
from app.scoring.country_scorer import build_country_score
from app.scoring.fear_greed import calculate_fear_greed
from app.scoring.stock_scorer import score_stock
from app.utils.async_tools import gather_limited

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
    cache_key = f"country_report:v5:{country_code}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        err = SP_6001(country_code)
        err.log()
        return err.to_dict()

    market_tasks = [yfinance_client.get_index_quote(idx.ticker) for idx in country.indices]
    economic_task = _get_economic_data(country_code)
    news_by_inst_task = news_client.get_all_institution_news(country.research_institutions, country_code)
    market_news_task = news_client.get_market_news(country_code)

    market_quotes, economic_data, news_by_inst, market_news = await asyncio.gather(
        asyncio.gather(*market_tasks, return_exceptions=True),
        economic_task,
        news_by_inst_task,
        market_news_task,
    )

    market_data = {}
    for idx, quote in zip(country.indices, market_quotes):
        if isinstance(quote, Exception):
            SP_2005(idx.ticker).log("warning")
            market_data[idx.name] = {"price": 0, "change_pct": 0}
        else:
            market_data[idx.name] = quote

    system, user = country_report_prompt(
        country.name,
        country_code,
        country.research_institutions,
        economic_data,
        news_by_inst,
        market_data,
    )
    llm_result = await ask_json(system, user)
    llm_failed = "error_code" in llm_result or "error" in llm_result

    scores = llm_result.get("scores", {})
    country_score = build_country_score(scores)

    if llm_failed:
        institutional_analysis = InstitutionalAnalysis(
            policy_institutions=[],
            sell_side=[],
            policy_sellside_aligned=False,
            consensus_count=0,
            consensus_summary="LLM analysis unavailable - showing data only.",
        )
    else:
        inst_raw = llm_result.get("institutional_analysis", {})
        institutional_analysis = InstitutionalAnalysis(
            policy_institutions=[
                InstitutionView(**item) for item in inst_raw.get("policy_institutions", [])
            ],
            sell_side=[InstitutionView(**item) for item in inst_raw.get("sell_side", [])],
            policy_sellside_aligned=inst_raw.get("policy_sellside_aligned", False),
            consensus_count=inst_raw.get("consensus_count", 0),
            consensus_summary=inst_raw.get("consensus_summary", ""),
        )

    llm_reasons = {}
    if not llm_failed:
        raw_tickers = llm_result.get("top_5_tickers", [])
        top_reasons = llm_result.get("top_5_reasons", [])
        for i, raw_ticker in enumerate(raw_tickers[:5]):
            resolved = TICKER_FALLBACK.get(raw_ticker, raw_ticker)
            llm_reasons[resolved] = top_reasons[i] if i < len(top_reasons) else ""

    top_stocks = await _score_top_stocks(country_code, llm_reasons)

    key_news = [
        NewsItem(
            title=item["title"],
            source=item.get("source", ""),
            url=item.get("url", ""),
            published=item.get("published", ""),
        )
        for item in market_news[:10]
    ]

    primary_index = country.indices[0]
    primary_index_history = await yfinance_client.get_price_history(primary_index.ticker, period="6mo")

    sentiment = await get_news_sentiment_for_country(market_news)
    vix_val = economic_data.get("vix") if country_code == "US" else None
    spread = economic_data.get("treasury_spread")

    fear_greed = calculate_fear_greed(
        primary_index_history,
        vix_value=vix_val,
        news_sentiment=sentiment,
        treasury_spread=spread,
        country_code=country_code,
    )

    flow_signal = await investor_flow_client.get_flow_signal(
        country_code,
        ticker=primary_index.ticker,
        market=primary_index.name,
        reference_date=primary_index_history[-1]["date"] if primary_index_history else None,
        price_history=primary_index_history,
    )

    next_day = forecast_next_day(
        ticker=primary_index.ticker,
        name=primary_index.name,
        country_code=country_code,
        price_history=primary_index_history,
        news_items=market_news,
        flow_signal=flow_signal,
        context_bias=((country_score.total - 50) / 50) + ((fear_greed.score - 50) / 100),
        asset_type="index",
    )
    breadth_ratio = (
        sum(1 for stock in top_stocks if stock.change_pct > 0) / len(top_stocks)
        if top_stocks
        else None
    )
    market_regime = build_market_regime(
        country_code=country_code,
        name=primary_index.name,
        price_history=primary_index_history,
        fear_greed=fear_greed,
        next_day_forecast=next_day,
        economic_data=economic_data,
        breadth_ratio=breadth_ratio,
    )

    news_summary = "\n".join(item["title"] for item in market_news[:10])
    try:
        forecast = await forecast_index(
            primary_index.ticker, primary_index.name, economic_data, news_summary
        )
        forecast_data = forecast.model_dump()
    except Exception as exc:
        SP_3004(str(exc)[:150]).log("warning")
        forecast_data = {"scenarios": [], "current_price": 0, "index_name": primary_index.name}

    market_summary = llm_result.get("market_summary", "")
    if llm_failed:
        market_summary = llm_result.get(
            "message", llm_result.get("error", "Analysis temporarily unavailable.")
        )

    errors = []
    if llm_failed:
        errors.append(llm_result.get("error_code", "SP-4005"))

    report = {
        "country": country.model_dump(),
        "score": country_score.model_dump(),
        "market_summary": market_summary,
        "key_news": [item.model_dump() for item in key_news],
        "institutional_analysis": institutional_analysis.model_dump(),
        "top_stocks": [stock.model_dump() for stock in top_stocks],
        "fear_greed": fear_greed.model_dump(),
        "forecast": forecast_data,
        "next_day_forecast": next_day.model_dump(),
        "market_regime": market_regime.model_dump(),
        "primary_index_history": primary_index_history,
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
    """Score a broad sample of stocks from the country and return top 5 by score."""
    from app.data.universe_data import get_universe

    universe = await get_universe(country_code)
    all_tickers: list[str] = []
    for sector_tickers in universe.values():
        all_tickers.extend(sector_tickers[:10])

    async def _score_ticker(ticker: str):
        info, prices, analyst_raw = await asyncio.gather(
            yfinance_client.get_stock_info(ticker),
            yfinance_client.get_price_history(ticker, period="3mo"),
            yfinance_client.get_analyst_ratings(ticker),
        )
        if not info.get("current_price"):
            return None
        quant = score_stock(info, price_hist=prices, analyst_counts=analyst_raw)
        return quant.total, ticker, info

    scored: list[tuple[float, str, dict]] = []
    for item in await gather_limited(all_tickers, _score_ticker, limit=8):
        if isinstance(item, Exception) or item is None:
            continue
        scored.append(item)

    scored.sort(key=lambda row: row[0], reverse=True)

    top_stocks = []
    for rank, (total_score, ticker, info) in enumerate(scored[:5], start=1):
        price = info.get("current_price", 0)
        prev = info.get("prev_close", price)
        change_pct = ((price - prev) / prev * 100) if prev else 0
        reason = llm_reasons.get(ticker, f"Score: {total_score:.1f}/100")
        top_stocks.append(StockSummaryRef(
            rank=rank,
            ticker=ticker,
            name=info.get("name", ticker),
            score=round(total_score, 1),
            current_price=round(price, 2),
            change_pct=round(change_pct, 2),
            reason=reason,
        ))

    return top_stocks


async def _get_economic_data(country_code: str) -> dict:
    if country_code == "US":
        data = await fred_client.get_us_economic_snapshot()
        spread = await fred_client.get_treasury_spread()
        data["treasury_spread"] = spread
        return data
    if country_code == "KR":
        return await ecos_client.get_kr_economic_snapshot()
    if country_code == "JP":
        return await boj_client.get_jp_economic_snapshot()
    return {}
