"""Individual stock analysis: detailed report + buy/sell guide."""

import asyncio
from datetime import datetime

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator

from app.analysis.historical_pattern_forecast import build_historical_pattern_forecast
from app.analysis.llm_client import ask_json
from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.prompts import stock_analysis_prompt
from app.analysis.trade_planner import build_trade_plan
from app.config import get_settings
from app.data import cache, fmp_client, investor_flow_client, news_client, yfinance_client
from app.models.country import COUNTRY_REGISTRY
from app.models.stock import (
    AnalystRatings,
    BuySellGuide,
    DividendInfo,
    EarningsEvent,
    PeerComparison,
    PricePoint,
    QuarterlyFinancial,
    StockDetail,
    TechnicalIndicators,
    ValuationMethod,
)
from app.scoring import rubric
from app.scoring.stock_scorer import score_composite, score_stock
from app.utils.async_tools import gather_limited


async def analyze_stock(ticker: str) -> dict:
    settings = get_settings()
    cache_key = f"stock_detail:v7:{ticker}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    country_code = _detect_country(ticker)
    (
        info,
        prices_full,
        market_prices_full,
        financials_raw,
        analyst_raw,
        earnings_raw,
        peers,
    ) = await asyncio.gather(
        yfinance_client.get_stock_info(ticker),
        yfinance_client.get_price_history(ticker, period="2y"),
        yfinance_client.get_price_history(COUNTRY_REGISTRY[country_code].indices[0].ticker, period="2y"),
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
    news_task = news_client.search_news(
        f"{info.get('name', ticker)} {ticker} stock", country_code, max_results=12
    )
    flow_task = investor_flow_client.get_flow_signal(
        country_code,
        ticker=ticker,
        reference_date=prices_6mo[-1]["date"] if prices_6mo else None,
        price_history=prices_6mo or prices_raw,
    )
    peer_avg, news, flow_signal = await asyncio.gather(peer_avg_task, news_task, flow_task)

    quant_score = score_stock(info, peers_avg=peer_avg, price_hist=prices_raw, analyst_counts=analyst_raw)
    composite = score_composite(
        info,
        peers_avg=peer_avg,
        price_hist=prices_raw,
        price_hist_6mo=prices_6mo,
        analyst_counts=analyst_raw,
    )

    system, user = stock_analysis_prompt(
        ticker, info, financials_raw, news, quant_score.model_dump()
    )
    llm_result = await ask_json(system, user)
    llm_failed = "error_code" in llm_result or "error" in llm_result

    if not llm_failed:
        quant_score.total = (
            quant_score.fundamental.total
            + quant_score.valuation.total
            + quant_score.growth_momentum.total
            + quant_score.analyst.total
            + quant_score.risk.total
        )

    technical = _calc_technicals(prices_raw)
    price_history = [PricePoint(**p) for p in prices_raw]
    financials = [QuarterlyFinancial(**f) for f in financials_raw[:8]]
    earnings_history = [EarningsEvent(**e) for e in earnings_raw[:12]]
    peer_comparisons = _build_peer_comparisons(info, peer_avg)
    buy_sell = _build_buy_sell(info, llm_result, peer_avg)

    price = info.get("current_price", 0)
    prev = info.get("prev_close", price)
    change_pct = ((price - prev) / prev * 100) if prev else 0

    next_day_forecast = forecast_next_day(
        ticker=ticker,
        name=info.get("name", ticker),
        country_code=country_code,
        price_history=prices_6mo or prices_raw,
        news_items=news,
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
            asset_type="index",
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
        historical_pattern_forecast=historical_pattern_forecast,
        setup_backtest=setup_backtest,
        market_regime=market_regime,
        trade_plan=trade_plan,
    )

    result = detail.model_dump()
    result["composite_score"] = composite.model_dump()
    result["llm_available"] = not llm_failed
    result["errors"] = []

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

    if historical_error:
        result["errors"].append("SP-3007")
        result["historical_pattern_warning"] = historical_error

    await cache.set(cache_key, result, settings.cache_ttl_report)
    return result


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
    if ticker.endswith(".T"):
        return "JP"
    return "US"


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
