from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import asyncio
import hashlib
import json

from app.data import cache
from app.data.universe_data import GICS_SECTORS
from app.data.supabase_client import supabase_client
from app.services.portfolio.recommendations import build_recommendation_context_maps
from app.services.portfolio_optimizer import attach_candidate_return_series
from app.services import market_service, portfolio_service
from app.utils.async_tools import gather_limited

COUNTRY_FILTERS = ["KR"]
STYLE_FILTERS = ["defensive", "balanced", "offensive"]

STYLE_PRESETS = {
    "defensive": {
        "style_label": "방어형",
        "recommended_equity_pct": 68.0,
        "cash_buffer_pct": 32.0,
        "max_single_weight_pct": 12.0,
        "max_country_weight_pct": 38.0,
        "max_sector_weight_pct": 22.0,
    },
    "balanced": {
        "style_label": "균형형",
        "recommended_equity_pct": 82.0,
        "cash_buffer_pct": 18.0,
        "max_single_weight_pct": 14.5,
        "max_country_weight_pct": 48.0,
        "max_sector_weight_pct": 28.0,
    },
    "offensive": {
        "style_label": "공격형",
        "recommended_equity_pct": 90.0,
        "cash_buffer_pct": 10.0,
        "max_single_weight_pct": 16.5,
        "max_country_weight_pct": 56.0,
        "max_sector_weight_pct": 36.0,
    },
}


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_country_filter(country_code: str | None) -> str:
    normalized = str(country_code or "KR").strip().upper() or "KR"
    return normalized if normalized in COUNTRY_FILTERS else "KR"


def _normalize_sector_filter(sector: str | None) -> str:
    normalized = str(sector or "ALL").strip()
    if not normalized:
        return "ALL"
    if normalized == "ALL":
        return "ALL"
    return normalized if normalized in GICS_SECTORS else "ALL"


def _normalize_style(style: str | None) -> str:
    normalized = str(style or "balanced").strip().lower() or "balanced"
    return normalized if normalized in STYLE_FILTERS else "balanced"


def _budget_for_style(
    *,
    style: str,
    max_items: int,
    country_locked: bool,
    sector_locked: bool,
) -> dict:
    preset = STYLE_PRESETS[style]
    target_count = max(3, min(max_items, 8))
    return {
        "style": style,
        "style_label": preset["style_label"],
        "recommended_equity_pct": preset["recommended_equity_pct"],
        "cash_buffer_pct": preset["cash_buffer_pct"],
        "target_position_count": target_count,
        "max_single_weight_pct": preset["max_single_weight_pct"],
        "max_country_weight_pct": 100.0 if country_locked else preset["max_country_weight_pct"],
        "max_sector_weight_pct": 100.0 if sector_locked else preset["max_sector_weight_pct"],
    }


def _auto_style_from_risk(risk: dict) -> str:
    label = str(risk.get("overall_label") or "moderate")
    if label in {"aggressive", "elevated"}:
        return "defensive"
    if label == "balanced":
        return "offensive"
    return "balanced"


def _recommendation_options() -> dict:
    return {
        "countries": COUNTRY_FILTERS,
        "sectors": ["ALL", *GICS_SECTORS],
        "styles": STYLE_FILTERS,
    }


def _response_defaults(message: str) -> dict:
    return {
        "generated_at": datetime.now().isoformat(),
        "budget": _budget_for_style(style="balanced", max_items=5, country_locked=False, sector_locked=False),
        "summary": {
            "selected_count": 0,
            "candidate_count": 0,
            "watchlist_focus_count": 0,
            "existing_overlap_count": 0,
            "model_up_probability": 0.0,
            "model_predicted_return_pct": 0.0,
            "expected_return_pct_20d": 0.0,
            "expected_excess_return_pct_20d": 0.0,
            "forecast_volatility_pct_20d": 0.0,
            "up_probability_20d": 0.0,
            "down_probability_20d": 0.0,
            "turnover_pct": 0.0,
            "focus_country": None,
            "focus_sector": None,
        },
        "recommendations": [],
        "notes": [message],
    }


def _portfolio_state_signature(portfolio_rows: list[dict], watchlist_rows: list[dict]) -> str:
    holdings_payload = sorted(
        (
            str(row.get("ticker") or ""),
            str(row.get("country_code") or "KR"),
            round(float(row.get("buy_price") or 0.0), 4),
            round(float(row.get("quantity") or 0.0), 4),
            str(row.get("buy_date") or ""),
        )
        for row in portfolio_rows
        if row.get("ticker")
    )
    watchlist_payload = sorted(
        (
            str(row.get("ticker") or ""),
            str(row.get("country_code") or "KR"),
        )
        for row in watchlist_rows
        if row.get("ticker")
    )
    raw = json.dumps(
        {"holdings": holdings_payload, "watchlist": watchlist_payload},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


async def _load_recommendation_context(
    scan_countries: list[str],
    *,
    user_id: str,
    portfolio_snapshot: dict | None = None,
    watchlist_rows_seed: list[dict] | None = None,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict]]:
    portfolio_task = portfolio_service.get_portfolio(user_id) if portfolio_snapshot is None else None
    watchlist_task = supabase_client.watchlist_list(user_id) if watchlist_rows_seed is None else None
    radar_task = gather_limited(
        scan_countries,
        lambda code: market_service.get_market_opportunities(code, limit=8),
        limit=max(1, min(3, len(scan_countries))),
    )
    async_results = await asyncio.gather(
        portfolio_task or asyncio.sleep(0, result=portfolio_snapshot),
        watchlist_task or asyncio.sleep(0, result=watchlist_rows_seed),
        radar_task,
        return_exceptions=True,
    )
    portfolio, watchlist_rows, radar_responses = async_results
    if isinstance(portfolio, Exception) or portfolio is None:
        portfolio = {"holdings": [], "risk": {}}
    if isinstance(watchlist_rows, Exception) or watchlist_rows is None:
        watchlist_rows = []
    if isinstance(radar_responses, Exception) or radar_responses is None:
        radar_responses = []

    holdings = portfolio.get("holdings") or []
    radar_items = [
        opportunity
        for response in radar_responses
        if not isinstance(response, Exception)
        for opportunity in response.get("opportunities", [])
    ]
    regimes = [
        {
            "country_code": response.get("country_code"),
            "label": (response.get("market_regime") or {}).get("label"),
            "stance": (response.get("market_regime") or {}).get("stance"),
            "actionable_count": response.get("actionable_count", 0),
            "universe_note": response.get("universe_note"),
        }
        for response in radar_responses
        if not isinstance(response, Exception)
    ]
    return portfolio, holdings, watchlist_rows, radar_items, regimes


def _build_candidate(
    *,
    opportunity: dict,
    watchlist_keys: set[str],
    holding_lookup: dict[str, dict],
    country_exposure: dict[str, float],
    sector_exposure: dict[str, float],
    country_locked: bool,
    sector_locked: bool,
) -> dict | None:
    key = f"{opportunity.get('country_code', 'KR')}:{opportunity.get('ticker')}"
    current_holding = holding_lookup.get(key)
    score, notes, source, confidence_floor_passed = portfolio_service._radar_model_score(opportunity, watchlist_keys)
    if not confidence_floor_passed:
        return None
    current_weight_pct = round(float((current_holding or {}).get("weight_pct") or 0.0), 2)
    current_country_exposure = float(country_exposure.get(opportunity.get("country_code", "KR"), 0.0))
    current_sector_exposure = float(sector_exposure.get(opportunity.get("sector", "Other"), 0.0))

    score += max(18.0 - current_country_exposure, 0.0) * 0.18
    score += max(14.0 - current_sector_exposure, 0.0) * 0.15
    if not country_locked:
        score -= max(current_country_exposure - 34.0, 0.0) * 0.26
    if not sector_locked:
        score -= max(current_sector_exposure - 26.0, 0.0) * 0.28
    if current_weight_pct > 0:
        score -= min(current_weight_pct, 25.0) * 0.18
        notes.append(f"현재 보유 비중 {current_weight_pct:.1f}%라 신규 추천에서는 우선순위를 조금 낮췄습니다.")
    if current_country_exposure > 0:
        notes.append(f"현재 {opportunity.get('country_code')} 익스포저는 {current_country_exposure:.1f}%입니다.")
    if current_sector_exposure > 0:
        notes.append(f"현재 {opportunity.get('sector')} 비중은 {current_sector_exposure:.1f}%입니다.")

    execution_bias = opportunity.get("execution_bias") or "stay_selective"
    if execution_bias in {"reduce_risk", "capital_preservation"}:
        score -= 5.5
        notes.append("이 후보는 신규 확대보다 보류·축소 관점에서 먼저 확인하는 편이 좋습니다.")

    model_score = round(_clip(score, 0.0, 100.0), 1)
    weight_score = max(model_score - 58.0, 1.0) if execution_bias in {"reduce_risk", "capital_preservation"} else max(model_score - 48.0, 4.0)
    return {
        "key": key,
        "ticker": opportunity.get("ticker"),
        "name": opportunity.get("name"),
        "country_code": opportunity.get("country_code", "KR"),
        "sector": opportunity.get("sector", "Other"),
        "source": source,
        "in_watchlist": source == "watchlist",
        "confidence_floor_passed": confidence_floor_passed,
        "current_weight_pct": current_weight_pct,
        "current_country_exposure_pct": round(current_country_exposure, 2),
        "current_sector_exposure_pct": round(current_sector_exposure, 2),
        "model_score": model_score,
        "weight_score": weight_score,
        "opportunity_score": round(float(opportunity.get("opportunity_score") or 0.0), 1),
        "target_horizon_days": int(opportunity.get("target_horizon_days") or 20),
        "target_date_20d": opportunity.get("target_date_20d"),
        "expected_return_pct_20d": float(opportunity.get("expected_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0),
        "expected_excess_return_pct_20d": float(opportunity.get("expected_excess_return_pct_20d") or 0.0),
        "median_return_pct_20d": float(opportunity.get("median_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0),
        "forecast_volatility_pct_20d": float(opportunity.get("forecast_volatility_pct_20d") or 0.0),
        "up_probability_20d": float(opportunity.get("up_probability_20d") or opportunity.get("up_probability") or 0.0),
        "flat_probability_20d": float(opportunity.get("flat_probability_20d") or 0.0),
        "down_probability_20d": float(opportunity.get("down_probability_20d") or opportunity.get("bear_probability") or 0.0),
        "distribution_confidence_20d": float(opportunity.get("distribution_confidence_20d") or opportunity.get("confidence") or 0.0),
        "price_q25_20d": opportunity.get("price_q25_20d"),
        "price_q50_20d": opportunity.get("price_q50_20d"),
        "price_q75_20d": opportunity.get("price_q75_20d"),
        "up_probability": float(opportunity.get("up_probability_20d") or opportunity.get("up_probability") or 0.0),
        "predicted_return_pct": float(opportunity.get("expected_return_pct_20d") or opportunity.get("predicted_return_pct") or 0.0),
        "confidence": float(opportunity.get("confidence") or 0.0),
        "bull_probability": opportunity.get("up_probability_20d") or opportunity.get("bull_probability"),
        "base_probability": opportunity.get("flat_probability_20d") or opportunity.get("base_probability"),
        "bear_probability": opportunity.get("down_probability_20d") or opportunity.get("bear_probability"),
        "bull_case_price": opportunity.get("price_q75_20d") or opportunity.get("bull_case_price"),
        "base_case_price": opportunity.get("price_q50_20d") or opportunity.get("base_case_price"),
        "bear_case_price": opportunity.get("price_q25_20d") or opportunity.get("bear_case_price"),
        "execution_bias": execution_bias,
        "setup_label": opportunity.get("setup_label"),
        "action": opportunity.get("action"),
        "entry_low": opportunity.get("entry_low"),
        "entry_high": opportunity.get("entry_high"),
        "stop_loss": opportunity.get("stop_loss"),
        "take_profit_1": opportunity.get("take_profit_1"),
        "take_profit_2": opportunity.get("take_profit_2"),
        "risk_reward_estimate": opportunity.get("risk_reward_estimate"),
        "rationale": notes[:4],
        "risk_flags": list(opportunity.get("risk_flags") or []),
    }


def _select_recommendations(
    candidates: list[dict],
    *,
    max_items: int,
    country_locked: bool,
    sector_locked: bool,
) -> list[dict]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.get("model_score", 0.0)
            + (2.5 if item.get("in_watchlist") else 0.0)
            + (1.0 if item.get("source") == "watchlist" else 0.0)
        ),
        reverse=True,
    )
    selected: list[dict] = []
    seen: set[str] = set()
    country_counts: dict[str, int] = defaultdict(int)
    sector_counts: dict[str, int] = defaultdict(int)
    country_cap = max_items if country_locked else 3
    sector_cap = max_items if sector_locked else 2

    for candidate in ordered:
        if len(selected) >= max_items:
            break
        if candidate["key"] in seen:
            continue
        minimum_score = 52.0 if candidate.get("execution_bias") in {"reduce_risk", "capital_preservation"} else 56.0
        if float(candidate.get("model_score") or 0.0) < minimum_score:
            continue
        if country_counts[candidate["country_code"]] >= country_cap:
            continue
        if sector_counts[candidate["sector"]] >= sector_cap:
            continue
        selected.append(candidate)
        seen.add(candidate["key"])
        country_counts[candidate["country_code"]] += 1
        sector_counts[candidate["sector"]] += 1

    minimum_fill = min(max_items, max(3, min(4, len(ordered))))
    if len(selected) < minimum_fill:
        for candidate in ordered:
            if len(selected) >= minimum_fill:
                break
            if candidate["key"] in seen:
                continue
            if float(candidate.get("model_score") or 0.0) < 50.0:
                continue
            if country_counts[candidate["country_code"]] >= max(country_cap, 4):
                continue
            selected.append(candidate)
            seen.add(candidate["key"])
            country_counts[candidate["country_code"]] += 1
            sector_counts[candidate["sector"]] += 1
    return selected


def _build_summary(recommendations: list[dict], candidate_count: int, optimization) -> dict:
    total_weight = sum(float(item.get("target_weight_pct") or 0.0) for item in recommendations)
    by_country = portfolio_service._allocation_breakdown(recommendations, "country_code")
    by_sector = portfolio_service._allocation_breakdown(recommendations, "sector")
    return {
        "selected_count": len(recommendations),
        "candidate_count": candidate_count,
        "watchlist_focus_count": sum(1 for item in recommendations if item.get("in_watchlist")),
        "existing_overlap_count": sum(1 for item in recommendations if float(item.get("current_weight_pct") or 0.0) > 0.0),
        "model_up_probability": round(optimization.up_probability_20d if total_weight else 0.0, 2),
        "model_predicted_return_pct": round(optimization.expected_return_pct_20d if total_weight else 0.0, 2),
        "expected_return_pct_20d": round(optimization.expected_return_pct_20d if total_weight else 0.0, 2),
        "expected_excess_return_pct_20d": round(optimization.expected_excess_return_pct_20d if total_weight else 0.0, 2),
        "forecast_volatility_pct_20d": round(optimization.forecast_volatility_pct_20d if total_weight else 0.0, 2),
        "up_probability_20d": round(optimization.up_probability_20d if total_weight else 0.0, 2),
        "down_probability_20d": round(optimization.down_probability_20d if total_weight else 0.0, 2),
        "turnover_pct": round(optimization.turnover_pct if total_weight else 0.0, 2),
        "focus_country": by_country[0]["name"] if by_country else None,
        "focus_sector": by_sector[0]["name"] if by_sector else None,
    }


async def get_conditional_recommendations(
    *,
    user_id: str,
    country_code: str = "KR",
    sector: str = "ALL",
    style: str = "balanced",
    max_items: int = 5,
    min_up_probability: float = 54.0,
    exclude_holdings: bool = True,
    watchlist_only: bool = False,
) -> dict:
    normalized_country = _normalize_country_filter(country_code)
    normalized_sector = _normalize_sector_filter(sector)
    normalized_style = _normalize_style(style)
    capped_items = max(3, min(max_items, 8))
    min_probability = round(_clip(float(min_up_probability), 45.0, 75.0), 1)
    portfolio_rows, watchlist_rows_for_state = await asyncio.gather(
        supabase_client.portfolio_list(user_id),
        supabase_client.watchlist_list(user_id),
    )
    state_signature = _portfolio_state_signature(portfolio_rows, watchlist_rows_for_state)
    cache_key = (
        f"portfolio_conditional_reco:v3:{user_id}:{normalized_country}:{normalized_sector}:{normalized_style}:"
        f"{capped_items}:{min_probability}:{int(bool(exclude_holdings))}:{int(bool(watchlist_only))}:{state_signature}"
    )
    cached = await cache.get(cache_key)
    if cached:
        return cached

    scan_countries = ["KR"]
    _, holdings, watchlist_rows, radar_items, regimes = await _load_recommendation_context(
        scan_countries,
        user_id=user_id,
        watchlist_rows_seed=watchlist_rows_for_state,
    )
    context_maps = build_recommendation_context_maps(holdings, watchlist_rows)
    watchlist_keys = context_maps["watchlist_keys"]
    holding_lookup = context_maps["holding_lookup"]
    country_exposure = context_maps["country_exposure"]
    sector_exposure = context_maps["sector_exposure"]

    filtered_candidates: list[dict] = []
    for opportunity in radar_items:
        if opportunity.get("country_code") != normalized_country:
            continue
        if normalized_sector != "ALL" and opportunity.get("sector") != normalized_sector:
            continue
        if float(opportunity.get("up_probability") or 0.0) < min_probability:
            continue
        candidate = _build_candidate(
            opportunity=opportunity,
            watchlist_keys=watchlist_keys,
            holding_lookup=holding_lookup,
            country_exposure=country_exposure,
            sector_exposure=sector_exposure,
            country_locked=True,
            sector_locked=normalized_sector != "ALL",
        )
        if not candidate:
            continue
        if exclude_holdings and float(candidate.get("current_weight_pct") or 0.0) > 0.0:
            continue
        if watchlist_only and not candidate.get("in_watchlist"):
            continue
        filtered_candidates.append(candidate)

    budget = _budget_for_style(
        style=normalized_style,
        max_items=capped_items,
        country_locked=True,
        sector_locked=normalized_sector != "ALL",
    )
    selected = _select_recommendations(
        filtered_candidates,
        max_items=int(budget["target_position_count"]),
        country_locked=normalized_country != "ALL",
        sector_locked=normalized_sector != "ALL",
    )
    selected = await attach_candidate_return_series(selected, limit=4)
    recommendations, optimization = portfolio_service._allocate_model_weights(selected, budget)
    budget["recommended_equity_pct"] = optimization.actual_equity_pct
    budget["cash_buffer_pct"] = round(100.0 - optimization.actual_equity_pct, 2)

    summary = _build_summary(recommendations, len(filtered_candidates), optimization)
    notes = [
        f"{STYLE_PRESETS[normalized_style]['style_label']} 기준으로 주식 {budget['recommended_equity_pct']:.1f}% / 현금 {budget['cash_buffer_pct']:.1f}%를 제안합니다.",
        f"조건 필터는 국가 `{normalized_country}`, 섹터 `{normalized_sector}`, 20거래일 상승 확률 {min_probability:.1f}% 기준입니다.",
    ]
    if recommendations:
        notes.append(
            f"20거래일 기대수익률 {optimization.expected_return_pct_20d:+.2f}%, 기대초과수익률 {optimization.expected_excess_return_pct_20d:+.2f}%를 기준으로 비중을 계산했습니다."
        )
    if watchlist_only:
        notes.append("이번 결과는 워치리스트에 이미 올려둔 종목만 대상으로 좁혔습니다.")
    if exclude_holdings:
        notes.append("현재 보유 중인 종목은 제외해 신규 자금 투입 후보 위주로 추렸습니다.")
    if summary["focus_country"]:
        notes.append(f"이번 조건에서 가장 비중이 실리는 국가는 {summary['focus_country']}입니다.")
    if summary["focus_sector"]:
        notes.append(f"추천 비중이 가장 높은 섹터는 {summary['focus_sector']}입니다.")
    fallback_notes = sorted({item.get("universe_note") for item in regimes if item.get("universe_note")})
    if fallback_notes:
        notes.append(fallback_notes[0])

    response = {
        "generated_at": datetime.now().isoformat(),
        "filters": {
            "country_code": "KR",
            "sector": normalized_sector,
            "style": normalized_style,
            "max_items": capped_items,
            "min_up_probability": min_probability,
            "exclude_holdings": bool(exclude_holdings),
            "watchlist_only": bool(watchlist_only),
        },
        "options": _recommendation_options(),
        "budget": budget,
        "summary": summary,
        "recommendations": recommendations,
        "notes": notes[:6] if recommendations else ["현재 조건을 모두 만족하는 후보가 부족합니다. 필터를 조금 넓혀 다시 실행해 보세요."],
        "market_view": regimes,
    }
    await cache.set(cache_key, response, 300)
    return response


async def get_optimal_recommendation(user_id: str) -> dict:
    portfolio_rows, watchlist_rows = await asyncio.gather(
        supabase_client.portfolio_list(user_id),
        supabase_client.watchlist_list(user_id),
    )
    state_signature = _portfolio_state_signature(portfolio_rows, watchlist_rows)
    cache_key = f"portfolio_optimal_reco:v3:{user_id}:{state_signature}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    portfolio = await portfolio_service.get_portfolio(user_id)
    holdings = portfolio.get("holdings") or []
    risk = portfolio.get("risk") or {}
    auto_style = _auto_style_from_risk(risk)
    _, holdings, watchlist_rows, radar_items, regimes = await _load_recommendation_context(
        ["KR"],
        user_id=user_id,
        portfolio_snapshot=portfolio,
        watchlist_rows_seed=watchlist_rows,
    )
    context_maps = build_recommendation_context_maps(holdings, watchlist_rows)
    watchlist_keys = context_maps["watchlist_keys"]
    holding_lookup = context_maps["holding_lookup"]
    country_exposure = context_maps["country_exposure"]
    sector_exposure = context_maps["sector_exposure"]

    candidates: list[dict] = []
    for opportunity in radar_items:
        candidate = _build_candidate(
            opportunity=opportunity,
            watchlist_keys=watchlist_keys,
            holding_lookup=holding_lookup,
            country_exposure=country_exposure,
            sector_exposure=sector_exposure,
            country_locked=False,
            sector_locked=False,
        )
        if not candidate:
            continue
        if float(candidate.get("up_probability") or 0.0) < 53.0:
            continue
        if float(candidate.get("current_weight_pct") or 0.0) > 0.0:
            continue
        candidates.append(candidate)

    budget = _budget_for_style(style=auto_style, max_items=6, country_locked=False, sector_locked=False)
    selected = _select_recommendations(
        candidates,
        max_items=int(budget["target_position_count"]),
        country_locked=False,
        sector_locked=False,
    )
    selected = await attach_candidate_return_series(selected, limit=4)
    recommendations, optimization = portfolio_service._allocate_model_weights(selected, budget)
    budget["recommended_equity_pct"] = optimization.actual_equity_pct
    budget["cash_buffer_pct"] = round(100.0 - optimization.actual_equity_pct, 2)
    summary = _build_summary(recommendations, len(candidates), optimization)

    notes = [
        "최적 추천은 현재 포트폴리오 집중도와 시장 체제를 동시에 반영하고, 20거래일 분포 기대초과수익 기준으로 신규 자금에 가장 적합한 후보를 다시 계산합니다.",
        f"현재 포트폴리오 위험 상태를 기준으로 `{budget['style_label']}` 운영을 자동 선택했습니다.",
    ]
    if recommendations:
        notes.append(
            f"예상 변동성 {optimization.forecast_volatility_pct_20d:.2f}%와 회전율 {optimization.turnover_pct:.2f}%를 함께 반영했습니다."
        )
    if summary["focus_country"]:
        notes.append(f"현재 기준 최우선 시장은 {summary['focus_country']}이며, 그 시장 쪽에 신규 비중을 더 배분했습니다.")
    if summary["focus_sector"]:
        notes.append(f"최적 추천의 중심 섹터는 {summary['focus_sector']}입니다.")
    if risk.get("overall_label") in {"aggressive", "elevated"}:
        notes.append("기존 포트폴리오 리스크가 높은 편이라 현금 버퍼와 분산을 조금 더 강하게 유지하도록 설계했습니다.")

    response = {
        "generated_at": datetime.now().isoformat(),
        "objective": "현재 포트폴리오 리스크와 각 시장의 레이더 점수를 함께 고려해 지금 기준으로 가장 효율적인 신규 비중안을 계산한 결과입니다.",
        "style": auto_style,
        "budget": budget,
        "summary": summary,
        "recommendations": recommendations,
        "notes": notes[:6] if recommendations else ["현재 데이터 기준으로 신규 자금에 바로 투입할 만큼 강한 후보가 충분하지 않습니다."],
        "market_view": regimes,
    }
    await cache.set(cache_key, response, 300)
    return response
