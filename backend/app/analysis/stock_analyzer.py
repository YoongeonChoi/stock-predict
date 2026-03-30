"""Individual stock analysis: detailed report + buy/sell guide."""

import asyncio
from datetime import datetime, timezone
import re

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator

from app.analysis.distributional_return_engine import (
    EventFeatures,
    build_heuristic_event_context,
    build_structured_event_context,
)
from app.analysis.free_kr_forecast import build_free_kr_forecast
from app.analysis.historical_pattern_forecast import build_historical_pattern_forecast
from app.analysis.llm_client import ask_json
from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.prompts import stock_detail_analysis_prompt, stock_public_summary_prompt
from app.analysis.trade_planner import build_trade_plan
from app.config import get_settings
from app.errors import SP_4004
from app.data import (
    cache,
    ecos_client,
    fmp_client,
    investor_flow_client,
    kosis_client,
    naver_news_client,
    news_client,
    opendart_client,
    yfinance_client,
)
from app.models.country import COUNTRY_REGISTRY
from app.models.stock import (
    AnalystRatings,
    BuySellGuide,
    DividendInfo,
    EarningsEvent,
    PeerComparison,
    PricePoint,
    PublicStockSummary,
    QuarterlyFinancial,
    StockDetail,
    TechnicalIndicators,
    ValuationMethod,
)
from app.scoring import rubric
from app.scoring.stock_scorer import score_composite, score_stock
from app.utils.async_tools import gather_limited

STOCK_ANALYSIS_LLM_TIMEOUT_SECONDS = 8.0
EVENT_CONTEXT_TIMEOUT_SECONDS = 8.0
STOCK_DETAIL_PRICE_REFRESH_TIMEOUT_SECONDS = 3.5
STOCK_DETAIL_CACHE_VERSION = "v9"
STOCK_DETAIL_LATEST_CACHE_VERSION = "latest-v9"


def _stock_detail_cache_key(ticker: str, prices: list[dict]) -> str:
    return f"stock_detail:{STOCK_DETAIL_CACHE_VERSION}:{ticker}:{_latest_price_stamp(prices)}"


def _stock_detail_latest_cache_key(ticker: str) -> str:
    return f"stock_detail:{STOCK_DETAIL_LATEST_CACHE_VERSION}:{ticker}"


async def get_cached_stock_detail(ticker: str, *, refresh_quote: bool = False) -> dict | None:
    cached = await cache.get(_stock_detail_latest_cache_key(ticker))
    if not cached:
        return None
    if not refresh_quote:
        return dict(cached)
    return await _refresh_cached_stock_detail(dict(cached), ticker)


async def analyze_stock(ticker: str) -> dict:
    settings = get_settings()
    country_code = _detect_country(ticker)
    cached_latest = await get_cached_stock_detail(ticker, refresh_quote=True)
    if cached_latest:
        return cached_latest
    prices_full, market_prices_full = await asyncio.gather(
        yfinance_client.get_price_history(ticker, period="2y"),
        yfinance_client.get_price_history(COUNTRY_REGISTRY[country_code].indices[0].ticker, period="2y"),
    )
    cache_key = _stock_detail_cache_key(ticker, prices_full)
    cached = await cache.get(cache_key)
    if cached:
        return await _refresh_cached_stock_detail(cached, ticker)

    (
        info,
        financials_raw,
        analyst_raw,
        earnings_raw,
        peers,
    ) = await asyncio.gather(
        yfinance_client.get_stock_info(ticker),
        yfinance_client.get_financials(ticker),
        yfinance_client.get_analyst_ratings(ticker),
        yfinance_client.get_earnings_history(ticker),
        fmp_client.get_stock_peers(ticker),
    )

    prices_raw = _window_prices(prices_full, 63)
    prices_6mo = _window_prices(prices_full, 126)
    market_prices = _window_prices(market_prices_full, 126)
    info = _enrich_info_from_history(info, prices_full)

    peer_avg_task = _calc_peer_averages(peers)
    google_news_task = news_client.search_news(
        f"{info.get('name', ticker)} {ticker} stock", country_code, max_results=12
    )
    naver_news_task = naver_news_client.search_news(
        f"{info.get('name', ticker)} {ticker}",
        max_results=10,
        sort="date",
    )
    filings_task = opendart_client.get_recent_filings(ticker, limit=8)
    ecos_task = ecos_client.get_kr_economic_snapshot()
    kosis_task = kosis_client.get_kr_macro_snapshot()
    flow_task = investor_flow_client.get_flow_signal(
        country_code,
        ticker=ticker,
        reference_date=prices_6mo[-1]["date"] if prices_6mo else None,
        price_history=prices_6mo or prices_raw,
    )
    (
        peer_avg,
        google_news,
        naver_news,
        filings,
        ecos_snapshot,
        kosis_snapshot,
        flow_signal,
    ) = await asyncio.gather(
        peer_avg_task,
        google_news_task,
        naver_news_task,
        filings_task,
        ecos_task,
        kosis_task,
        flow_task,
    )

    quant_score = score_stock(info, peers_avg=peer_avg, price_hist=prices_raw, analyst_counts=analyst_raw)
    composite = score_composite(
        info,
        peers_avg=peer_avg,
        price_hist=prices_raw,
        price_hist_6mo=prices_6mo,
        analyst_counts=analyst_raw,
    )

    technical = _calc_technicals(prices_raw)
    price_history = [PricePoint(**p) for p in prices_raw]
    financials = [QuarterlyFinancial(**f) for f in financials_raw[:8]]
    earnings_history = [EarningsEvent(**e) for e in earnings_raw[:12]]
    peer_comparisons = _build_peer_comparisons(info, peer_avg)

    price = info.get("current_price", 0)
    prev = info.get("prev_close", price)
    change_pct = ((price - prev) / prev * 100) if prev else 0
    combined_news = [*google_news, *naver_news]
    reference_date = prices_6mo[-1]["date"] if prices_6mo else prices_raw[-1]["date"]
    system, user = stock_detail_analysis_prompt(
        ticker, info, financials_raw, google_news, quant_score.model_dump()
    )
    public_system, public_user = stock_public_summary_prompt(
        ticker, info, combined_news, quant_score.model_dump()
    )
    llm_result, public_llm_result, event_context = await asyncio.gather(
        _ask_stock_summary_with_timeout(system, user),
        _ask_public_stock_summary_with_timeout(public_system, public_user),
        _build_event_context_with_timeout(
            ticker=ticker,
            asset_name=info.get("name", ticker),
            country_code=country_code,
            news_items=combined_news,
            filings=filings,
            reference_date=reference_date,
        ),
    )
    llm_failed = "error_code" in llm_result or "error" in llm_result
    public_llm_failed = "error_code" in public_llm_result or "error" in public_llm_result

    if not llm_failed:
        quant_score.total = (
            quant_score.fundamental.total
            + quant_score.valuation.total
            + quant_score.growth_momentum.total
            + quant_score.analyst.total
            + quant_score.risk.total
        )

    buy_sell = _build_buy_sell(info, llm_result, peer_avg)

    next_day_forecast = forecast_next_day(
        ticker=ticker,
        name=info.get("name", ticker),
        country_code=country_code,
        price_history=prices_6mo or prices_raw,
        news_items=combined_news,
        analyst_context={
            **analyst_raw,
            "target_mean": info.get("target_mean"),
            "target_median": info.get("target_median"),
            "target_high": info.get("target_high"),
            "target_low": info.get("target_low"),
        },
        flow_signal=flow_signal,
        context_bias=((composite.total if composite else quant_score.total) - 50) / 50,
        asset_type="stock",
        benchmark_history=market_prices_full or market_prices,
        macro_snapshot=ecos_snapshot,
        kosis_snapshot=kosis_snapshot,
        fundamental_context=info,
        filings=filings,
        event_context=event_context,
    )
    free_kr_forecast = build_free_kr_forecast(
        ticker=ticker,
        name=info.get("name", ticker),
        price_history=prices_full or prices_6mo or prices_raw,
        market_history=market_prices_full or market_prices,
        google_news=google_news,
        naver_news=naver_news,
        filings=filings,
        flow_signal=flow_signal,
        analyst_context={
            **analyst_raw,
            "target_mean": info.get("target_mean"),
            "target_median": info.get("target_median"),
            "target_high": info.get("target_high"),
            "target_low": info.get("target_low"),
        },
        ecos_snapshot=ecos_snapshot,
        kosis_snapshot=kosis_snapshot,
        fundamental_context=info,
        event_context=event_context,
    )
    historical_pattern_forecast = None
    setup_backtest = None
    historical_error = None
    try:
        historical_pattern_forecast, setup_backtest = build_historical_pattern_forecast(
            ticker=ticker,
            name=info.get("name", ticker),
            country_code=country_code,
            price_history=prices_full or prices_6mo or prices_raw,
            market_history=market_prices_full or market_prices,
        )
    except Exception as exc:
        historical_error = str(exc)[:180]
    market_regime = build_market_regime(
        country_code=country_code,
        name=COUNTRY_REGISTRY[country_code].indices[0].name,
        price_history=market_prices,
        next_day_forecast=forecast_next_day(
            ticker=COUNTRY_REGISTRY[country_code].indices[0].ticker,
            name=COUNTRY_REGISTRY[country_code].indices[0].name,
            country_code=country_code,
            price_history=market_prices,
            macro_snapshot=ecos_snapshot,
            kosis_snapshot=kosis_snapshot,
            asset_type="index",
            event_context=event_context,
        ),
    )
    trade_plan = build_trade_plan(
        ticker=ticker,
        current_price=round(price, 2),
        price_history=price_history,
        technical=technical,
        buy_sell_guide=buy_sell,
        next_day_forecast=next_day_forecast,
        market_regime=market_regime,
    )
    public_summary = _build_public_stock_summary(
        llm_result=public_llm_result,
        info=info,
        quant_score=quant_score,
        next_day_forecast=next_day_forecast,
        market_regime=market_regime,
        trade_plan=trade_plan,
        buy_sell_guide=buy_sell,
        llm_available=not public_llm_failed,
    )

    detail = StockDetail(
        ticker=ticker,
        name=info.get("name", ticker),
        country_code=country_code,
        sector=info.get("sector", "N/A"),
        industry=info.get("industry", "N/A"),
        market_cap=info.get("market_cap", 0),
        current_price=round(price, 2),
        change_pct=round(change_pct, 2),
        financials=financials,
        pe_ratio=info.get("pe_ratio"),
        pb_ratio=info.get("pb_ratio"),
        ev_ebitda=info.get("ev_ebitda"),
        peg_ratio=info.get("peg_ratio"),
        week52_high=info.get("52w_high"),
        week52_low=info.get("52w_low"),
        peer_comparisons=peer_comparisons,
        dividend=DividendInfo(
            dividend_yield=info.get("dividend_yield"),
            payout_ratio=info.get("payout_ratio"),
        ),
        analyst_ratings=AnalystRatings(
            **analyst_raw,
            target_mean=info.get("target_mean"),
            target_median=info.get("target_median"),
            target_high=info.get("target_high"),
            target_low=info.get("target_low"),
        ),
        earnings_history=earnings_history,
        price_history=price_history,
        technical=technical,
        score=quant_score,
        buy_sell_guide=buy_sell,
        next_day_forecast=next_day_forecast,
        free_kr_forecast=free_kr_forecast,
        historical_pattern_forecast=historical_pattern_forecast,
        setup_backtest=setup_backtest,
        market_regime=market_regime,
        trade_plan=trade_plan,
        public_summary=public_summary,
    )

    result = detail.model_dump()
    result["composite_score"] = composite.model_dump()
    result["llm_available"] = not llm_failed
    result["errors"] = []
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    result["partial"] = False
    result["fallback_reason"] = None

    if llm_failed:
        result["errors"].append(llm_result.get("error_code", "SP-4005"))
        result["analysis_summary"] = llm_result.get(
            "message", "AI analysis unavailable. Showing quantitative data only."
        )
        result["key_risks"] = []
        result["key_catalysts"] = []
    else:
        result["analysis_summary"] = llm_result.get("analysis_summary", "")
        result["key_risks"] = llm_result.get("key_risks", [])
        result["key_catalysts"] = llm_result.get("key_catalysts", [])

    result["public_summary"] = public_summary.model_dump()

    if historical_error:
        result["errors"].append("SP-3007")
        result["historical_pattern_warning"] = historical_error

    await cache.set(cache_key, result, settings.cache_ttl_report)
    await cache.set(_stock_detail_latest_cache_key(ticker), result, settings.cache_ttl_report)
    return result


async def _refresh_cached_stock_detail(cached: dict, ticker: str) -> dict:
    refreshed = dict(cached)
    try:
        info = await asyncio.wait_for(
            yfinance_client.get_stock_info(ticker),
            timeout=STOCK_DETAIL_PRICE_REFRESH_TIMEOUT_SECONDS,
        )
    except Exception:
        return refreshed
    current_price = float(info.get("current_price") or refreshed.get("current_price") or 0.0)
    prev_close = float(info.get("prev_close") or current_price)
    refreshed["current_price"] = round(current_price, 2)
    refreshed["change_pct"] = round(((current_price - prev_close) / prev_close * 100.0) if prev_close else 0.0, 2)
    return refreshed


async def _ask_stock_summary_with_timeout(system_prompt: str, user_prompt: str) -> dict:
    try:
        return await asyncio.wait_for(
            ask_json(system_prompt, user_prompt),
            timeout=STOCK_ANALYSIS_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        err = SP_4004()
        err.log("warning")
        return err.to_dict()


async def _ask_public_stock_summary_with_timeout(system_prompt: str, user_prompt: str) -> dict:
    try:
        return await asyncio.wait_for(
            ask_json(system_prompt, user_prompt),
            timeout=STOCK_ANALYSIS_LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        SP_4004().log("warning")
        return {}


async def _build_event_context_with_timeout(
    *,
    ticker: str,
    asset_name: str,
    country_code: str,
    news_items: list[dict],
    filings: list[dict],
    reference_date: str,
) -> EventFeatures:
    heuristic = build_heuristic_event_context(
        news_items=news_items,
        filings=filings,
        reference_date=reference_date,
    )
    try:
        return await asyncio.wait_for(
            build_structured_event_context(
                ticker=ticker,
                asset_name=asset_name,
                country_code=country_code,
                news_items=news_items,
                filings=filings,
                reference_date=reference_date,
            ),
            timeout=EVENT_CONTEXT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        SP_4004().log("warning")
        if not heuristic.summary:
            heuristic.summary = "이벤트 구조화 응답이 늦어 정량 시계열 신호를 우선 사용했습니다."
        return heuristic


def _normalize_public_summary_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _contains_hangul(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value))


def _contains_public_summary_prohibited_content(value: str) -> bool:
    lowered = value.lower()
    prohibited_keywords = (
        "fair value",
        "buy zone",
        "sell zone",
        "target price",
        "analyst target",
        "목표가",
        "적정가",
        "매수 구간",
        "매도 구간",
        "buy target",
        "sell target",
    )
    if any(keyword in lowered for keyword in prohibited_keywords):
        return True
    if re.search(r"[A-Za-z]", value) and not _contains_hangul(value):
        return True
    return bool(re.search(r"\d", value))


def _clean_public_summary_text(value: str | None, fallback: str) -> str:
    text = _normalize_public_summary_text(value)
    if not text or _contains_public_summary_prohibited_content(text):
        return fallback
    return text


def _clean_public_summary_items(values: list[str] | None, *, limit: int = 2) -> list[str]:
    cleaned: list[str] = []
    for raw in values or []:
        text = _normalize_public_summary_text(raw)
        if not text or _contains_public_summary_prohibited_content(text) or text in cleaned:
            continue
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _merge_public_summary_items(primary: list[str], fallback: list[str], *, limit: int = 2) -> list[str]:
    merged: list[str] = []
    for item in [*primary, *fallback]:
        text = _normalize_public_summary_text(item)
        if not text or text in merged:
            continue
        merged.append(text)
        if len(merged) >= limit:
            break
    return merged


def _build_public_stock_summary(
    *,
    llm_result: dict,
    info: dict,
    quant_score,
    next_day_forecast,
    market_regime,
    trade_plan,
    buy_sell_guide,
    llm_available: bool,
) -> PublicStockSummary:
    fallback_summary = _build_public_summary_fallback_text(
        next_day_forecast=next_day_forecast,
        market_regime=market_regime,
        trade_plan=trade_plan,
    )
    support_points = _build_public_support_points(
        trade_plan=trade_plan,
        next_day_forecast=next_day_forecast,
        market_regime=market_regime,
        quant_score=quant_score,
    )
    counter_points = _build_public_counter_points(
        trade_plan=trade_plan,
        next_day_forecast=next_day_forecast,
        market_regime=market_regime,
    )
    wait_points = _build_public_wait_points(
        info=info,
        trade_plan=trade_plan,
        market_regime=market_regime,
        buy_sell_guide=buy_sell_guide,
    )
    breaker_points = _build_public_thesis_breakers(
        trade_plan=trade_plan,
        next_day_forecast=next_day_forecast,
        market_regime=market_regime,
    )

    return PublicStockSummary(
        summary=_clean_public_summary_text(llm_result.get("summary"), fallback_summary),
        evidence_for=_merge_public_summary_items(
            _clean_public_summary_items(llm_result.get("evidence_for")),
            support_points,
        ),
        evidence_against=_merge_public_summary_items(
            _clean_public_summary_items(llm_result.get("evidence_against")),
            counter_points,
        ),
        why_not_buy_now=_merge_public_summary_items(
            _clean_public_summary_items(llm_result.get("why_not_buy_now")),
            wait_points,
        ),
        thesis_breakers=_merge_public_summary_items(
            _clean_public_summary_items(llm_result.get("thesis_breakers")),
            breaker_points,
        ),
        data_quality=_clean_public_summary_text(
            llm_result.get("data_quality"),
            _build_public_data_quality_note(llm_available=llm_available, market_regime=market_regime),
        ),
        confidence_note=_clean_public_summary_text(
            llm_result.get("confidence_note"),
            _build_public_confidence_note(next_day_forecast=next_day_forecast, trade_plan=trade_plan),
        ),
    )


def _build_public_summary_fallback_text(*, next_day_forecast, market_regime, trade_plan) -> str:
    action = getattr(trade_plan, "action", "")
    if action in {"reduce_risk", "avoid"}:
        lead = "현재 정량 신호는 비중 확대보다 방어 대응이 먼저라는 쪽에 가깝습니다."
    elif action == "wait_pullback":
        lead = "관심은 유지할 수 있지만 지금 바로 추격하기보다 진입 조건을 다시 확인하는 편이 낫습니다."
    elif action == "breakout_watch":
        lead = "추세 확인 여지는 있지만 돌파가 자리 잡는지부터 지켜보는 편이 더 자연스럽습니다."
    else:
        lead = "정량 신호는 우호적이지만 한 방향으로 과하게 단정하기보다 조건 확인을 곁들여 읽는 편이 좋습니다."

    regime_sentence = ""
    if getattr(market_regime, "stance", None) == "risk_off":
        regime_sentence = "시장 국면도 공격적 확대보다 방어 해석에 무게를 두고 있습니다."
    elif getattr(market_regime, "stance", None) == "risk_on":
        regime_sentence = "시장 국면은 완전한 역풍은 아니지만 개별 종목별 선별이 계속 중요합니다."

    confidence = float(getattr(next_day_forecast, "confidence", 0.0) or 0.0)
    if confidence >= 70:
        confidence_sentence = "신호 강도는 나쁘지 않지만 실패 조건을 함께 보는 전제가 필요합니다."
    elif confidence >= 55:
        confidence_sentence = "확률 우위가 아주 넓지는 않아 분할 대응과 재확인이 어울립니다."
    else:
        confidence_sentence = "신뢰 우위가 크지 않아 성급한 확대보다 관찰과 보수적 대응이 더 적합합니다."

    return " ".join(
        sentence for sentence in [lead, regime_sentence, confidence_sentence] if sentence
    )


def _build_public_support_points(*, trade_plan, next_day_forecast, market_regime, quant_score) -> list[str]:
    points = _clean_public_summary_items(list(getattr(trade_plan, "thesis", []) or []), limit=2)
    if points:
        return points

    driver_points: list[str] = []
    for driver in getattr(next_day_forecast, "drivers", []) or []:
        signal = getattr(driver, "signal", "")
        detail = _normalize_public_summary_text(getattr(driver, "detail", ""))
        if signal == "bullish" and detail and not _contains_public_summary_prohibited_content(detail):
            driver_points.append(detail)
        if len(driver_points) >= 2:
            break
    if driver_points:
        return driver_points

    score_total = float(getattr(quant_score, "total", 0.0) or 0.0)
    if score_total >= 65:
        points.append("기초체력과 밸류에이션 점수가 함께 무너지지 않았습니다.")
    if getattr(market_regime, "stance", None) != "risk_off":
        points.append("시장 국면이 완전한 위험회피로 기울지 않아 선별 관찰 여지가 남아 있습니다.")
    if not points:
        points.append("정량 시계열 신호 기준으로는 아직 관찰할 가치는 남아 있습니다.")
    return points[:2]


def _build_public_counter_points(*, trade_plan, next_day_forecast, market_regime) -> list[str]:
    points = _clean_public_summary_items(list(getattr(next_day_forecast, "risk_flags", []) or []), limit=2)
    if getattr(trade_plan, "action", "") in {"reduce_risk", "avoid"}:
        points.append("현재 실행 플랜이 비중 확대보다 리스크 관리 쪽으로 기울어 있습니다.")
    if getattr(market_regime, "stance", None) == "risk_off":
        points.append("시장 국면이 방어적으로 기울어 개별 종목 우위가 약해질 수 있습니다.")
    if float(getattr(next_day_forecast, "up_probability", 0.0) or 0.0) <= 50:
        points.append("상승 확률 우위가 크게 벌어지지 않았습니다.")
    return _merge_public_summary_items([], points)


def _build_public_wait_points(*, info: dict, trade_plan, market_regime, buy_sell_guide) -> list[str]:
    points: list[str] = []
    current_price = float(info.get("current_price") or 0.0)
    buy_high = float(getattr(buy_sell_guide, "buy_zone_high", 0.0) or 0.0)
    if current_price > 0 and buy_high > 0 and current_price > buy_high:
        points.append("현재 가격이 선호 진입 구간 위에 있어 추격보다 재확인이 낫습니다.")

    action = getattr(trade_plan, "action", "")
    action_reason = {
        "breakout_watch": "돌파 확인 전까지는 성급한 확대보다 추세 확인이 먼저입니다.",
        "wait_pullback": "진입 타이밍을 더 고를 여지가 있어 바로 매수 쪽으로 기울 필요는 없습니다.",
        "reduce_risk": "현재 플랜은 신규 확대보다 기존 리스크 점검을 우선합니다.",
        "avoid": "현재 구조에서는 매수 근거보다 피해야 할 조건이 더 많습니다.",
        "accumulate": "긍정 신호가 있어도 분할 대응과 손절 기준 확인이 먼저입니다.",
    }.get(action)
    if action_reason:
        points.append(action_reason)

    if float(getattr(trade_plan, "risk_reward_estimate", 0.0) or 0.0) < 1.2:
        points.append("손익비가 넉넉하지 않아 진입 타이밍을 더 가려야 합니다.")
    if getattr(market_regime, "stance", None) == "risk_off":
        points.append("시장 국면이 위험회피 쪽이라 개별 종목 확대보다 방어 비중 점검이 우선입니다.")
    return _merge_public_summary_items([], points)


def _build_public_thesis_breakers(*, trade_plan, next_day_forecast, market_regime) -> list[str]:
    points: list[str] = []
    invalidation = _normalize_public_summary_text(getattr(trade_plan, "invalidation", ""))
    if invalidation and not _contains_public_summary_prohibited_content(invalidation):
        points.append(invalidation)
    if getattr(next_day_forecast, "risk_flags", None):
        points.extend(list(getattr(next_day_forecast, "risk_flags", []) or [])[:1])
    if getattr(market_regime, "stance", None) == "risk_off":
        points.append("시장 국면 약세가 더 강해지면 현재 가설은 접는 편이 낫습니다.")
    if not points:
        points.append("핵심 가정이 흔들리면 관찰 의견을 보수적으로 낮춰야 합니다.")
    return _merge_public_summary_items([], points)


def _build_public_data_quality_note(*, llm_available: bool, market_regime) -> str:
    if not llm_available:
        return "공개 요약은 정량 시계열과 공개 데이터 기준으로 구성했고, 서술형 보조 요약은 fallback으로 정리했습니다."
    if getattr(market_regime, "stance", None) == "risk_off":
        return "가격, 변동성, 뉴스, 수급, 시장 국면을 함께 반영했고 방어 신호를 더 먼저 읽도록 정리했습니다."
    return "가격, 변동성, 뉴스, 수급, 시장 국면을 함께 반영했고 공개 요약은 실행 가이드보다 근거와 반대 조건을 먼저 보여줍니다."


def _build_public_confidence_note(*, next_day_forecast, trade_plan) -> str:
    action = getattr(trade_plan, "action", "")
    confidence = float(getattr(next_day_forecast, "confidence", 0.0) or 0.0)
    if action in {"reduce_risk", "avoid"}:
        return "현재 해석은 공격적 진입보다 방어 대응 쪽 신뢰가 더 높습니다."
    if action == "wait_pullback":
        return "우호 신호가 있어도 타이밍 확인이 더 필요해 선택적으로 접근하는 편이 좋습니다."
    if action == "breakout_watch":
        return "추세 확인이 끝나기 전까지는 후보 관찰과 조건 확인을 함께 가져가는 편이 안전합니다."
    if confidence >= 70:
        return "신뢰도는 양호하지만 무효화 조건을 함께 확인하는 전제가 필요합니다."
    if confidence >= 55:
        return "확률 우위는 있으나 한 번에 밀어붙이기보다 분할 대응이 더 어울립니다."
    return "신뢰 우위가 충분히 크지 않아 관찰과 재확인을 우선하는 해석이 적합합니다."


def _latest_price_stamp(prices: list[dict]) -> str:
    if not prices:
        return datetime.now(timezone.utc).date().isoformat()
    return str(prices[-1].get("date") or datetime.now(timezone.utc).date().isoformat())


def _calc_technicals(prices: list[dict]) -> TechnicalIndicators:
    if len(prices) < 5:
        return TechnicalIndicators(
            ma_20=[], ma_60=[], rsi_14=[], macd=[], macd_signal=[], macd_hist=[], dates=[]
        )

    df = pd.DataFrame(prices)
    close = df["close"].astype(float)
    dates = df["date"].tolist()

    ma20 = SMAIndicator(close, window=min(20, len(close))).sma_indicator()
    ma60 = (
        SMAIndicator(close, window=60).sma_indicator()
        if len(close) >= 60
        else pd.Series([None] * len(close))
    )
    rsi = RSIIndicator(close, window=min(14, max(len(close) - 1, 2))).rsi()
    macd_ind = MACD(
        close,
        window_slow=min(26, len(close)),
        window_fast=min(12, max(len(close) - 1, 2)),
        window_sign=min(9, max(len(close) - 1, 2)),
    )

    def _to_list(series):
        return [round(float(v), 2) if pd.notna(v) else None for v in series]

    return TechnicalIndicators(
        ma_20=_to_list(ma20),
        ma_60=_to_list(ma60),
        rsi_14=_to_list(rsi),
        macd=_to_list(macd_ind.macd()),
        macd_signal=_to_list(macd_ind.macd_signal()),
        macd_hist=_to_list(macd_ind.macd_diff()),
        dates=dates,
    )


def _build_buy_sell(info: dict, llm: dict, peer_avg: dict) -> BuySellGuide:
    fair_value = float(llm.get("fair_value", 0))
    if fair_value <= 0:
        price = info.get("current_price", 0)
        target = info.get("target_mean") or price
        fair_value = (price + target) / 2 if target else price

    buy_low = float(llm.get("buy_zone_low", fair_value * (1 - rubric.BUY_ZONE_DISCOUNT)))
    buy_high = float(llm.get("buy_zone_high", fair_value * (1 - rubric.BUY_ZONE_DISCOUNT * 0.5)))
    sell_low = float(llm.get("sell_zone_low", fair_value * (1 + rubric.SELL_ZONE_PREMIUM * 0.6)))
    sell_high = float(llm.get("sell_zone_high", fair_value * (1 + rubric.SELL_ZONE_PREMIUM)))
    grade = llm.get("confidence_grade", "C")

    current = info.get("current_price", 0)
    rr = ((sell_low - current) / (current - buy_high)) if current > buy_high and current != buy_high else 0

    methods = []
    for method in llm.get("valuation_methods", []):
        methods.append(ValuationMethod(
            name=method.get("name", ""),
            value=round(float(method.get("value", 0)), 2),
            weight=float(method.get("weight", 0.33)),
            details=method.get("details", ""),
        ))

    return BuySellGuide(
        buy_zone_low=round(buy_low, 2),
        buy_zone_high=round(buy_high, 2),
        fair_value=round(fair_value, 2),
        sell_zone_low=round(sell_low, 2),
        sell_zone_high=round(sell_high, 2),
        risk_reward_ratio=round(rr, 2),
        confidence_grade=grade,
        methodology=methods,
        summary=llm.get("analysis_summary", "")[:300],
    )


async def _calc_peer_averages(peers: list[str]) -> dict:
    if not peers:
        return {"pe_avg": None, "pb_avg": None, "ev_ebitda_avg": None}

    async def _fetch(peer: str):
        return await yfinance_client.get_stock_info(peer)

    results = await gather_limited(peers[:5], _fetch, limit=3)
    pe_vals, pb_vals, ev_vals = [], [], []
    for item in results:
        if isinstance(item, Exception):
            continue
        if item.get("pe_ratio"):
            pe_vals.append(item["pe_ratio"])
        if item.get("pb_ratio"):
            pb_vals.append(item["pb_ratio"])
        if item.get("ev_ebitda"):
            ev_vals.append(item["ev_ebitda"])

    return {
        "pe_avg": round(float(np.mean(pe_vals)), 2) if pe_vals else None,
        "pb_avg": round(float(np.mean(pb_vals)), 2) if pb_vals else None,
        "ev_ebitda_avg": round(float(np.mean(ev_vals)), 2) if ev_vals else None,
    }


def _build_peer_comparisons(info: dict, peer_avg: dict) -> list[PeerComparison]:
    metrics = [
        ("P/E", info.get("pe_ratio"), peer_avg.get("pe_avg")),
        ("P/B", info.get("pb_ratio"), peer_avg.get("pb_avg")),
        ("EV/EBITDA", info.get("ev_ebitda"), peer_avg.get("ev_ebitda_avg")),
    ]
    return [
        PeerComparison(metric=name, company_value=val, peer_avg=pavg, sector_avg=pavg)
        for name, val, pavg in metrics
    ]


def _detect_country(ticker: str) -> str:
    if ticker.endswith(".KS") or ticker.endswith(".KQ"):
        return "KR"
    return "KR"


def _window_prices(prices: list[dict], window: int) -> list[dict]:
    if len(prices) <= window:
        return prices
    return prices[-window:]


def _enrich_info_from_history(info: dict, prices: list[dict]) -> dict:
    if not prices:
        return info

    enriched = dict(info)
    closes = [float(item.get("close", 0) or 0) for item in prices if item.get("close") is not None]
    highs = [float(item.get("high", 0) or 0) for item in prices[-252:] if item.get("high") is not None]
    lows = [float(item.get("low", 0) or 0) for item in prices[-252:] if item.get("low") is not None]
    volumes = [float(item.get("volume", 0) or 0) for item in prices[-20:] if item.get("volume") is not None]

    if closes:
        enriched["current_price"] = enriched.get("current_price") or round(closes[-1], 2)
        enriched["prev_close"] = enriched.get("prev_close") or round(closes[-2] if len(closes) >= 2 else closes[-1], 2)
    if highs and enriched.get("52w_high") is None:
        enriched["52w_high"] = round(max(highs), 2)
    if lows and enriched.get("52w_low") is None:
        enriched["52w_low"] = round(min(lows), 2)
    if volumes and enriched.get("avg_volume") is None:
        enriched["avg_volume"] = round(float(np.mean(volumes)))
    return enriched
