from __future__ import annotations

import math
from app.models.market import OpportunityItem

from .fallbacks import regime_tailwind_label
from .shared import clip


def resolve_detail_candidate_budget(
    *,
    limit: int,
    available: int,
    universe_source: str | None,
    max_candidates: int | None,
    min_candidates: int,
    large_universe_cap: int,
    max_detailed_candidates: int,
) -> int:
    if available <= 0:
        return 0
    if max_candidates is not None:
        return max(1, min(available, max_candidates))
    preferred = max(limit * 2, min_candidates)
    if available >= 120 and universe_source in {"fallback", "krx_listing"}:
        preferred = min(preferred, large_universe_cap)
    return max(1, min(available, min(preferred, max_detailed_candidates)))


def should_skip_detailed_scan(
    *,
    country_code: str,
    universe_source: str,
    ranked_count: int,
    limit: int,
    quote_only_threshold: int,
) -> bool:
    return (
        country_code == "KR"
        and universe_source in {"fallback", "krx_listing"}
        and ranked_count >= max(limit, quote_only_threshold)
    )


def build_quote_only_opportunity_item(
    *,
    rank: int,
    total_ranked: int,
    sector: str,
    ticker: str,
    name: str | None,
    current_price: float,
    change_pct: float,
    country_code: str,
    market_regime,
) -> OpportunityItem:
    regime_bias = 3.0 if market_regime.stance == "risk_on" else -3.0 if market_regime.stance == "risk_off" else 0.0
    rank_denominator = max(total_ranked - 1, 1)
    rank_fraction = clip(1.0 - ((max(rank, 1) - 1) / rank_denominator), 0.0, 1.0)
    momentum_component = 11.5 * math.tanh(change_pct / 6.25)
    rank_component = 10.0 * rank_fraction
    opportunity_score = clip(62.0 + momentum_component + rank_component + regime_bias, 15.0, 86.0)
    up_probability = clip(50.0 + change_pct * 1.9 + regime_bias * 0.7, 34.0, 77.0)
    predicted_return_pct = round(clip(change_pct * 0.55, -5.0, 6.5), 2)
    from datetime import datetime, timedelta

    target_date = (datetime.now() + timedelta(days=20)).date().isoformat()
    bull_case_price = round(current_price * 1.04, 2)
    base_case_price = round(current_price * (1.0 + predicted_return_pct / 100.0), 2)
    bear_case_price = round(current_price * 0.97, 2)
    action = "accumulate" if predicted_return_pct >= 1.4 else "breakout_watch" if predicted_return_pct >= 0.2 else "wait_pullback"
    return OpportunityItem(
        rank=rank,
        ticker=ticker,
        name=(str(name or "").strip() or ticker.split(".")[0]),
        country_code=country_code,
        sector=sector,
        current_price=round(current_price, 2),
        change_pct=round(change_pct, 2),
        opportunity_score=round(opportunity_score, 1),
        quant_score=round(clip(50.0 + change_pct * 1.8, 22.0, 78.0), 1),
        up_probability=round(up_probability, 1),
        confidence=41.0,
        predicted_return_pct=predicted_return_pct,
        target_horizon_days=20,
        target_date_20d=target_date,
        expected_return_pct_20d=predicted_return_pct,
        expected_excess_return_pct_20d=round(predicted_return_pct * 0.72, 2),
        median_return_pct_20d=predicted_return_pct,
        forecast_volatility_pct_20d=round(max(abs(change_pct) * 1.4, 2.4), 2),
        up_probability_20d=round(up_probability, 1),
        flat_probability_20d=round(max(100.0 - up_probability - 20.0, 6.0), 1),
        down_probability_20d=round(max(100.0 - up_probability - max(100.0 - up_probability - 20.0, 6.0), 6.0), 1),
        distribution_confidence_20d=41.0,
        price_q25_20d=bear_case_price,
        price_q50_20d=base_case_price,
        price_q75_20d=bull_case_price,
        bull_case_price=bull_case_price,
        base_case_price=base_case_price,
        bear_case_price=bear_case_price,
        bull_probability=round(up_probability, 1),
        base_probability=20.0,
        bear_probability=round(max(100.0 - up_probability - 20.0, 6.0), 1),
        setup_label="전수 1차 스캔",
        action=action,
        execution_bias="stay_selective",
        execution_note="현재 KR 레이더 유니버스를 1차 스캔했고, 상세 분포 계산이 지연된 종목은 시세 스냅샷 기준으로 먼저 정리했습니다.",
        regime_tailwind=regime_tailwind_label(market_regime.stance),
        entry_low=round(current_price * 0.99, 2),
        entry_high=round(current_price * 1.01, 2),
        stop_loss=round(current_price * 0.96, 2),
        take_profit_1=round(current_price * 1.03, 2),
        take_profit_2=round(current_price * 1.06, 2),
        risk_reward_estimate=1.15,
        thesis=["현재 KR 레이더 유니버스를 1차로 훑은 뒤 상위 종목을 먼저 정렬한 결과입니다."],
        risk_flags=["상세 분포 계산이 지연돼 시세 스냅샷 기반 후보로 표시합니다."],
        forecast_date=target_date,
    )
