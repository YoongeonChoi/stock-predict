"""Individual stock analysis: detailed report + buy/sell guide."""

import numpy as np
from datetime import datetime
from ta.trend import MACD, SMAIndicator
from ta.momentum import RSIIndicator
import pandas as pd

from app.data import yfinance_client, fmp_client, news_client, cache
from app.analysis.llm_client import ask_json
from app.analysis.prompts import stock_analysis_prompt
from app.scoring.stock_scorer import score_stock
from app.scoring import rubric
from app.models.stock import (
    StockDetail, BuySellGuide, ValuationMethod, DividendInfo,
    AnalystRatings, TechnicalIndicators, PricePoint, QuarterlyFinancial,
    PeerComparison, EarningsEvent,
)
from app.config import get_settings


async def analyze_stock(ticker: str) -> dict:
    settings = get_settings()
    cache_key = f"stock_detail:{ticker}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    info = await yfinance_client.get_stock_info(ticker)
    prices_raw = await yfinance_client.get_price_history(ticker, period="3mo")
    financials_raw = await yfinance_client.get_financials(ticker)
    analyst_raw = await yfinance_client.get_analyst_ratings(ticker)
    earnings_raw = await yfinance_client.get_earnings_history(ticker)

    peers = await fmp_client.get_stock_peers(ticker)
    peer_avg = await _calc_peer_averages(peers) if peers else {}

    quant_score = score_stock(info, peers_avg=peer_avg, price_hist=prices_raw)

    news = await news_client.search_news(
        f"{info.get('name', ticker)} stock", _detect_country(ticker), max_results=10
    )

    system, user = stock_analysis_prompt(
        ticker, info, financials_raw, news, quant_score.model_dump()
    )
    llm_result = await ask_json(system, user)
    llm_failed = "error_code" in llm_result or "error" in llm_result

    if not llm_failed:
        est_rev_score = float(llm_result.get("estimate_revision_score", 2.5))
        quant_score.analyst.items[-1].score = min(5, max(0, est_rev_score))
        quant_score.analyst.total = sum(i.score for i in quant_score.analyst.items)
        quant_score.total = (
            quant_score.fundamental.total + quant_score.valuation.total +
            quant_score.growth_momentum.total + quant_score.analyst.total +
            quant_score.risk.total
        )

    technical = _calc_technicals(prices_raw)
    price_history = [PricePoint(**p) for p in prices_raw]
    financials = [QuarterlyFinancial(**f) for f in financials_raw[:8]]
    earnings_history = [EarningsEvent(**e) for e in earnings_raw[:12]]

    buy_sell = _build_buy_sell(info, llm_result, peer_avg)

    price = info.get("current_price", 0)
    prev = info.get("prev_close", price)
    change_pct = ((price - prev) / prev * 100) if prev else 0

    peer_comparisons = _build_peer_comparisons(info, peer_avg)

    detail = StockDetail(
        ticker=ticker,
        name=info.get("name", ticker),
        country_code=_detect_country(ticker),
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
    )

    result = detail.model_dump()
    errors = []
    if llm_failed:
        errors.append(llm_result.get("error_code", "SP-4005"))
        result["analysis_summary"] = llm_result.get("message", "AI analysis unavailable. Showing quantitative data only.")
        result["key_risks"] = []
        result["key_catalysts"] = []
        result["llm_available"] = False
    else:
        result["analysis_summary"] = llm_result.get("analysis_summary", "")
        result["key_risks"] = llm_result.get("key_risks", [])
        result["key_catalysts"] = llm_result.get("key_catalysts", [])
        result["llm_available"] = True
    result["errors"] = errors

    await cache.set(cache_key, result, settings.cache_ttl_report)
    return result


def _calc_technicals(prices: list[dict]) -> TechnicalIndicators:
    if len(prices) < 5:
        return TechnicalIndicators(
            ma_20=[], ma_60=[], rsi_14=[], macd=[], macd_signal=[], macd_hist=[], dates=[]
        )

    df = pd.DataFrame(prices)
    close = df["close"]
    dates = df["date"].tolist()

    ma20 = SMAIndicator(close, window=min(20, len(close))).sma_indicator()
    ma60 = SMAIndicator(close, window=min(60, len(close))).sma_indicator() if len(close) >= 14 else close * 0
    rsi = RSIIndicator(close, window=min(14, len(close) - 1)).rsi()
    macd_ind = MACD(close, window_slow=min(26, len(close)), window_fast=min(12, len(close)),
                     window_sign=min(9, len(close)))

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
    for m in llm.get("valuation_methods", []):
        methods.append(ValuationMethod(
            name=m.get("name", ""),
            value=round(float(m.get("value", 0)), 2),
            weight=float(m.get("weight", 0.33)),
            details=m.get("details", ""),
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
    pe_vals, pb_vals, ev_vals = [], [], []
    for p in peers[:5]:
        try:
            pinfo = await yfinance_client.get_stock_info(p)
            if pinfo.get("pe_ratio"):
                pe_vals.append(pinfo["pe_ratio"])
            if pinfo.get("pb_ratio"):
                pb_vals.append(pinfo["pb_ratio"])
            if pinfo.get("ev_ebitda"):
                ev_vals.append(pinfo["ev_ebitda"])
        except Exception:
            continue
    return {
        "pe_avg": round(np.mean(pe_vals), 2) if pe_vals else None,
        "pb_avg": round(np.mean(pb_vals), 2) if pb_vals else None,
        "ev_ebitda_avg": round(np.mean(ev_vals), 2) if ev_vals else None,
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
