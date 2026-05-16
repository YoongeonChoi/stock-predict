"""Opportunity quality scoring for the radar candidate funnel."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any


@dataclass(frozen=True)
class SectorQualityContext:
    sector: str
    average_change_pct: float = 0.0
    breadth_pct: float = 50.0
    candidate_count: int = 0


@dataclass(frozen=True)
class OpportunityQualityResult:
    quality_score: float
    chase_risk_score: float
    volume_quality_score: float
    flow_accumulation_score: float | None
    sector_catalyst_score: float
    entry_style: str
    recommended_entry_condition: str
    flow_data_status: str
    quality_data_status: str
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    risk_flags: list[str] = field(default_factory=list)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return parsed


def _optional_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return (current / previous - 1.0) * 100.0


def _point_value(point: Any, key: str, default: float = 0.0) -> float:
    if isinstance(point, dict):
        return _safe_float(point.get(key), default)
    return _safe_float(getattr(point, key, default), default)


def _point_date(point: Any) -> str:
    if isinstance(point, dict):
        return str(point.get("date") or "")
    return str(getattr(point, "date", "") or "")


def _average(values: list[float], default: float = 0.0) -> float:
    cleaned = [value for value in values if math.isfinite(value)]
    if not cleaned:
        return default
    return sum(cleaned) / len(cleaned)


def _series_metrics(price_history: list[Any], current_price: float) -> dict[str, float | str]:
    if not price_history:
        return {
            "daily_return_pct": 0.0,
            "return_3d_pct": 0.0,
            "return_5d_pct": 0.0,
            "volume_ratio": 1.0,
            "close_location": 0.5,
            "atr_pct": 0.0,
            "distance_to_ema21_pct": 0.0,
            "distance_to_high_20_pct": 0.0,
            "latest_date": "",
        }

    closes = [_point_value(point, "close", current_price) for point in price_history]
    highs = [_point_value(point, "high", closes[idx]) for idx, point in enumerate(price_history)]
    lows = [_point_value(point, "low", closes[idx]) for idx, point in enumerate(price_history)]
    volumes = [_point_value(point, "volume", 0.0) for point in price_history]
    latest_close = closes[-1] if closes else current_price
    if current_price <= 0:
        current_price = latest_close
    previous_close = closes[-2] if len(closes) >= 2 else latest_close
    daily_return_pct = _pct_change(latest_close, previous_close)
    return_3d_pct = _pct_change(latest_close, closes[-4]) if len(closes) >= 4 else 0.0
    return_5d_pct = _pct_change(latest_close, closes[-6]) if len(closes) >= 6 else 0.0
    last_volume = volumes[-1] if volumes else 0.0
    average_volume_20 = _average(volumes[-20:], default=last_volume or 1.0)
    volume_ratio = last_volume / average_volume_20 if average_volume_20 > 0 else 1.0
    latest_high = highs[-1] if highs else latest_close
    latest_low = lows[-1] if lows else latest_close
    close_location = (latest_close - latest_low) / (latest_high - latest_low) if latest_high > latest_low else 0.5
    high_20 = max(highs[-20:]) if highs else latest_close
    distance_to_high_20_pct = max((high_20 / current_price - 1.0) * 100.0, 0.0) if current_price > 0 else 0.0
    ema_window = closes[-21:] if len(closes) >= 21 else closes
    ema21_proxy = _average(ema_window, default=current_price)
    distance_to_ema21_pct = (current_price / ema21_proxy - 1.0) * 100.0 if ema21_proxy > 0 else 0.0
    ranges = []
    for idx in range(1, len(closes)):
        ranges.append(
            max(
                highs[idx] - lows[idx],
                abs(highs[idx] - closes[idx - 1]),
                abs(lows[idx] - closes[idx - 1]),
            )
        )
    atr_proxy = _average(ranges[-14:], default=0.0)
    atr_pct = atr_proxy / current_price * 100.0 if current_price > 0 else 0.0

    return {
        "daily_return_pct": daily_return_pct,
        "return_3d_pct": return_3d_pct,
        "return_5d_pct": return_5d_pct,
        "volume_ratio": volume_ratio,
        "close_location": close_location,
        "atr_pct": atr_pct,
        "distance_to_ema21_pct": distance_to_ema21_pct,
        "distance_to_high_20_pct": distance_to_high_20_pct,
        "latest_date": _point_date(price_history[-1]),
    }


def build_sector_quality_context(ranked_quotes: list[dict]) -> dict[str, SectorQualityContext]:
    grouped: dict[str, list[float]] = {}
    for item in ranked_quotes:
        sector = str(item.get("sector") or "기타")
        grouped.setdefault(sector, []).append(_safe_float(item.get("change_pct"), 0.0))
    contexts: dict[str, SectorQualityContext] = {}
    for sector, changes in grouped.items():
        count = len(changes)
        average_change = _average(changes, default=0.0)
        breadth = sum(1 for value in changes if value > 0.0) / max(count, 1) * 100.0
        contexts[sector] = SectorQualityContext(
            sector=sector,
            average_change_pct=round(average_change, 4),
            breadth_pct=round(breadth, 4),
            candidate_count=count,
        )
    return contexts


def _sector_score(context: SectorQualityContext | None, market_stance: str = "neutral") -> float:
    if context is None:
        return 55.0 if market_stance == "risk_on" else 47.0 if market_stance == "risk_off" else 50.0
    score = 48.0
    score += _clip(context.average_change_pct, -4.0, 4.0) * 5.0
    score += (context.breadth_pct - 50.0) * 0.28
    if context.candidate_count >= 5:
        score += 4.0
    if market_stance == "risk_on":
        score += 3.0
    elif market_stance == "risk_off":
        score -= 4.0
    return _clip(score, 5.0, 95.0)


def score_quote_candidate(
    item: dict,
    *,
    sector_context: SectorQualityContext | None = None,
    market_stance: str = "neutral",
) -> dict:
    change_pct = _safe_float(item.get("change_pct"), 0.0)
    market_cap = _safe_float(item.get("market_cap"), 0.0)
    volume = _safe_float(item.get("volume"), 0.0)
    avg_volume = _safe_float(item.get("avg_volume"), 0.0)
    sector_score = _sector_score(sector_context, market_stance)
    liquidity_score = 50.0
    if market_cap > 0:
        liquidity_score += _clip(math.log10(max(market_cap, 1.0)) - 10.0, -3.0, 4.0) * 6.0
    if volume > 0 and avg_volume > 0:
        volume_ratio = volume / avg_volume
        liquidity_score += _clip(volume_ratio - 1.0, -0.8, 1.5) * 12.0
    elif volume > 0:
        liquidity_score += 4.0
    liquidity_score = _clip(liquidity_score, 10.0, 90.0)

    chase_risk = 28.0
    if change_pct >= 8.0:
        chase_risk += 45.0
    elif change_pct >= 5.0:
        chase_risk += 31.0
    elif change_pct >= 3.0:
        chase_risk += 18.0
    elif change_pct <= -4.5:
        chase_risk += 10.0
    if volume > 0 and avg_volume > 0 and volume / avg_volume >= 2.2:
        chase_risk += 12.0
    chase_risk = _clip(chase_risk, 5.0, 95.0)

    moderate_momentum = 54.0 + _clip(change_pct, -2.5, 3.0) * 4.2
    if change_pct > 3.0:
        moderate_momentum -= (change_pct - 3.0) * 8.0
    volume_quality = _clip(45.0 + (liquidity_score - 50.0) * 0.55 + (moderate_momentum - 50.0) * 0.35, 5.0, 95.0)
    quick_score = (
        sector_score * 0.34
        + liquidity_score * 0.24
        + volume_quality * 0.22
        + (100.0 - chase_risk) * 0.20
    )
    updated = dict(item)
    updated["quick_score"] = round(_clip(quick_score, 1.0, 99.0), 4)
    updated["quality_score"] = round(_clip(quick_score, 1.0, 99.0), 1)
    updated["chase_risk_score"] = round(chase_risk, 1)
    updated["volume_quality_score"] = round(volume_quality, 1)
    updated["sector_catalyst_score"] = round(sector_score, 1)
    updated["flow_accumulation_score"] = None
    updated["flow_data_status"] = "flow_unavailable"
    updated["quality_data_status"] = "quote_screen"
    updated["entry_style"] = "wait_pullback" if chase_risk >= 70.0 else "breakout_watch" if sector_score >= 65.0 else "selective"
    updated["recommended_entry_condition"] = (
        "당일 급등분을 따라가기보다 VWAP/전일 종가 부근 눌림을 기다립니다."
        if chase_risk >= 70.0
        else "섹터 강도와 거래대금이 유지될 때만 분할 진입합니다."
    )
    updated["score_breakdown"] = {
        "quick_sector": round(sector_score, 1),
        "quick_liquidity": round(liquidity_score, 1),
        "quick_volume": round(volume_quality, 1),
        "quick_chase_risk": round(chase_risk, 1),
        "quick_change_pct": round(change_pct, 2),
    }
    return updated


def rerank_quote_screen(ranked_quotes: list[dict], *, market_stance: str = "neutral") -> list[dict]:
    contexts = build_sector_quality_context(ranked_quotes)
    rescored = [
        score_quote_candidate(
            item,
            sector_context=contexts.get(str(item.get("sector") or "")),
            market_stance=market_stance,
        )
        for item in ranked_quotes
    ]
    rescored.sort(
        key=lambda item: (
            _safe_float(item.get("quick_score"), 0.0),
            _safe_float(item.get("sector_catalyst_score"), 0.0),
            -_safe_float(item.get("chase_risk_score"), 100.0),
            _safe_float(item.get("change_pct"), 0.0),
        ),
        reverse=True,
    )
    return rescored


def _chart_factor_score(chart_analysis: Any, key: str, default: float = 50.0) -> float:
    for factor in list(getattr(chart_analysis, "factors", []) or []):
        if getattr(factor, "key", "") == key:
            return _safe_float(getattr(factor, "score", default), default)
    return default


def _flow_value(flow_signal: Any, *names: str) -> float | None:
    for name in names:
        value = _optional_float(getattr(flow_signal, name, None))
        if value is not None:
            return value
    return None


def _score_flow(flow_signal: Any | None) -> tuple[float | None, str, dict[str, Any], list[str]]:
    if flow_signal is None:
        return None, "flow_unavailable", {}, ["투자자별 수급 데이터가 없어 가격/거래량 품질로만 평가했습니다."]
    status = str(getattr(flow_signal, "data_status", "") or "")
    if status:
        flow_status = status
    elif getattr(flow_signal, "available", False):
        flow_status = "fresh_eod"
    else:
        flow_status = "flow_unavailable"
    if not getattr(flow_signal, "available", False):
        return None, flow_status, {"flow_source": getattr(flow_signal, "source", "")}, [
            "투자자별 수급 데이터가 아직 확보되지 않았습니다."
        ]

    foreign_1d = _flow_value(flow_signal, "foreign_net_buy_1d", "foreign_net_buy")
    foreign_5d = _flow_value(flow_signal, "foreign_net_buy_5d", "foreign_net_buy")
    foreign_20d = _flow_value(flow_signal, "foreign_net_buy_20d")
    inst_1d = _flow_value(flow_signal, "institutional_net_buy_1d", "institutional_net_buy")
    inst_5d = _flow_value(flow_signal, "institutional_net_buy_5d", "institutional_net_buy")
    inst_20d = _flow_value(flow_signal, "institutional_net_buy_20d")
    retail_1d = _flow_value(flow_signal, "retail_net_buy_1d", "retail_net_buy")
    retail_5d = _flow_value(flow_signal, "retail_net_buy_5d", "retail_net_buy")
    retail_20d = _flow_value(flow_signal, "retail_net_buy_20d")
    foreign_total = _safe_float(foreign_1d) + _safe_float(foreign_5d) * 0.7 + _safe_float(foreign_20d) * 0.3
    inst_total = _safe_float(inst_1d) + _safe_float(inst_5d) * 0.7 + _safe_float(inst_20d) * 0.3
    retail_total = _safe_float(retail_1d) + _safe_float(retail_5d) * 0.45 + _safe_float(retail_20d) * 0.15
    scale = abs(foreign_total) + abs(inst_total) + abs(retail_total)
    if scale <= 0:
        return 50.0, flow_status, {"flow_source": getattr(flow_signal, "source", "")}, []

    institutional_pressure = (foreign_total + inst_total) / scale
    retail_pressure = retail_total / scale
    foreign_days = _safe_float(getattr(flow_signal, "foreign_positive_days_20d", 0.0), 0.0)
    inst_days = _safe_float(getattr(flow_signal, "institutional_positive_days_20d", 0.0), 0.0)
    retail_days = _safe_float(getattr(flow_signal, "retail_positive_days_20d", 0.0), 0.0)
    persistence_bonus = (foreign_days + inst_days - retail_days * 0.45) * 0.65
    score = 50.0 + institutional_pressure * 34.0 - max(retail_pressure, 0.0) * 20.0 + persistence_bonus
    flags: list[str] = []
    if institutional_pressure < -0.2 and retail_pressure > 0.2:
        flags.append("개인 매수 우위와 외국인/기관 매도 조합이라 추격 위험을 높게 봅니다.")
    return _clip(score, 5.0, 95.0), flow_status, {
        "foreign_net_buy_1d": foreign_1d,
        "foreign_net_buy_5d": foreign_5d,
        "foreign_net_buy_20d": foreign_20d,
        "institutional_net_buy_1d": inst_1d,
        "institutional_net_buy_5d": inst_5d,
        "institutional_net_buy_20d": inst_20d,
        "retail_net_buy_1d": retail_1d,
        "retail_net_buy_5d": retail_5d,
        "retail_net_buy_20d": retail_20d,
        "flow_source": getattr(flow_signal, "source", ""),
    }, flags


def score_opportunity_quality(
    *,
    price_history: list[Any],
    current_price: float,
    change_pct: float,
    sector_context: SectorQualityContext | None = None,
    market_stance: str = "neutral",
    flow_signal: Any | None = None,
    chart_analysis: Any | None = None,
) -> OpportunityQualityResult:
    metrics = _series_metrics(price_history, current_price)
    daily_return_pct = _safe_float(metrics.get("daily_return_pct"), change_pct)
    return_3d_pct = _safe_float(metrics.get("return_3d_pct"), 0.0)
    return_5d_pct = _safe_float(metrics.get("return_5d_pct"), 0.0)
    volume_ratio = _safe_float(metrics.get("volume_ratio"), 1.0)
    close_location = _safe_float(metrics.get("close_location"), 0.5)
    atr_pct = _safe_float(metrics.get("atr_pct"), 0.0)
    distance_to_ema21_pct = _safe_float(metrics.get("distance_to_ema21_pct"), 0.0)
    distance_to_high_20_pct = _safe_float(metrics.get("distance_to_high_20_pct"), 0.0)

    chase_risk = 22.0
    chase_risk += max(daily_return_pct - 2.2, 0.0) * 8.5
    chase_risk += max(return_3d_pct - 4.5, 0.0) * 4.6
    chase_risk += max(return_5d_pct - 6.5, 0.0) * 3.8
    chase_risk += max(distance_to_ema21_pct - 4.0, 0.0) * 5.0
    chase_risk += max(atr_pct - 4.8, 0.0) * 3.2
    if volume_ratio >= 2.2 and daily_return_pct >= 2.0:
        chase_risk += 14.0
    if close_location < 0.42 and volume_ratio >= 1.4:
        chase_risk += 12.0
    if chart_analysis is not None:
        extension_score = _chart_factor_score(chart_analysis, "extension_discipline", 50.0)
        rsi_score = _chart_factor_score(chart_analysis, "rsi_balance", 50.0)
        if extension_score < 42.0:
            chase_risk += (42.0 - extension_score) * 0.7
        if rsi_score < 43.0 and return_5d_pct > 2.0:
            chase_risk += (43.0 - rsi_score) * 0.45
        chase_risk += max(len(getattr(chart_analysis, "caution_flags", []) or []) - 1, 0) * 5.5
    chase_risk = _clip(chase_risk, 5.0, 95.0)

    volume_quality = 48.0
    if 1.1 <= volume_ratio <= 1.9 and daily_return_pct >= -0.5:
        volume_quality += 18.0
    elif volume_ratio > 1.9 and daily_return_pct >= 0.0 and close_location >= 0.55:
        volume_quality += 12.0
    elif volume_ratio < 0.75 and distance_to_high_20_pct <= 2.5:
        volume_quality -= 14.0
    if daily_return_pct < 0.0 and volume_ratio >= 1.15:
        volume_quality -= 17.0
    if distance_to_high_20_pct <= 2.0 and volume_ratio >= 1.05 and close_location >= 0.55:
        volume_quality += 10.0
    if volume_ratio >= 2.4 and close_location < 0.55:
        volume_quality -= 12.0
    if chart_analysis is not None:
        volume_quality = volume_quality * 0.65 + _chart_factor_score(chart_analysis, "volume_confirmation", 50.0) * 0.35
    volume_quality = _clip(volume_quality, 5.0, 95.0)

    flow_score, flow_status, flow_breakdown, flow_flags = _score_flow(flow_signal)
    sector_score = _sector_score(sector_context, market_stance)
    flow_component = flow_score if flow_score is not None else 50.0
    quality_score = (
        (100.0 - chase_risk) * 0.27
        + volume_quality * 0.24
        + flow_component * 0.24
        + sector_score * 0.25
    )
    quality_score = _clip(quality_score, 5.0, 95.0)

    risk_flags: list[str] = []
    if chase_risk >= 78.0:
        risk_flags.append("당일 급등과 이격 부담이 커서 추격 매수 우선순위를 낮췄습니다.")
    elif chase_risk >= 64.0:
        risk_flags.append("단기 과열 신호가 있어 눌림 확인 전까지 보수적으로 봅니다.")
    if volume_quality <= 42.0:
        risk_flags.append("거래량 품질이 약해 돌파 신뢰도를 낮게 봅니다.")
    risk_flags.extend(flow_flags)

    if chase_risk >= 84.0:
        entry_style = "avoid_chase"
        recommended = "이미 오른 구간은 따라가지 않고 전일 종가/VWAP 회귀 또는 다음 거래일 거래량 재확인을 기다립니다."
    elif chase_risk >= 68.0:
        entry_style = "wait_pullback"
        recommended = "시초가 추격보다 EMA21 또는 전일 종가 근처 눌림과 수급 유지 여부를 확인합니다."
    elif volume_quality >= 66.0 and sector_score >= 62.0:
        entry_style = "breakout_watch"
        recommended = "섹터 강도와 거래량이 유지될 때 고점 돌파 확인 후 분할 대응합니다."
    elif quality_score >= 68.0:
        entry_style = "accumulate"
        recommended = "급등 부담이 낮아 장중 눌림에서 분할 매수 후보로 관리합니다."
    else:
        entry_style = "selective"
        recommended = "수급 또는 거래량 보강 신호가 나올 때까지 관찰 우선으로 둡니다."

    quality_status = "complete" if flow_score is not None else "partial_flow"
    breakdown = {
        "chase_risk": round(chase_risk, 1),
        "volume_quality": round(volume_quality, 1),
        "flow_accumulation": round(flow_score, 1) if flow_score is not None else None,
        "sector_catalyst": round(sector_score, 1),
        "daily_return_pct": round(daily_return_pct, 2),
        "return_3d_pct": round(return_3d_pct, 2),
        "return_5d_pct": round(return_5d_pct, 2),
        "volume_ratio": round(volume_ratio, 2),
        "close_location": round(close_location, 2),
        "atr_pct": round(atr_pct, 2),
        "distance_to_ema21_pct": round(distance_to_ema21_pct, 2),
        "distance_to_high_20_pct": round(distance_to_high_20_pct, 2),
        "latest_price_date": metrics.get("latest_date") or "",
        "flow_data_status": flow_status,
        **flow_breakdown,
    }
    return OpportunityQualityResult(
        quality_score=round(quality_score, 1),
        chase_risk_score=round(chase_risk, 1),
        volume_quality_score=round(volume_quality, 1),
        flow_accumulation_score=round(flow_score, 1) if flow_score is not None else None,
        sector_catalyst_score=round(sector_score, 1),
        entry_style=entry_style,
        recommended_entry_condition=recommended,
        flow_data_status=flow_status,
        quality_data_status=quality_status,
        score_breakdown=breakdown,
        risk_flags=risk_flags[:4],
    )


def adjusted_score_with_quality(base_score: float, quality: OpportunityQualityResult) -> float:
    score = _safe_float(base_score, 0.0) * 0.70 + quality.quality_score * 0.30
    if quality.chase_risk_score >= 84.0:
        cap = 61.0 if _safe_float(quality.flow_accumulation_score, 50.0) < 72.0 else 68.0
        score = min(score, cap)
    elif quality.chase_risk_score >= 70.0:
        score = min(score, 72.0)
    if quality.volume_quality_score <= 38.0:
        score -= 3.0
    return round(_clip(score, 5.0, 95.0), 1)


def radar_action_from_quality(current_action: str, quality: OpportunityQualityResult) -> str:
    if quality.chase_risk_score >= 84.0:
        return "avoid"
    if quality.chase_risk_score >= 68.0:
        return "wait_pullback"
    if quality.entry_style == "breakout_watch":
        return "breakout_watch"
    if quality.entry_style == "accumulate" and current_action not in {"avoid", "reduce_risk"}:
        return "accumulate"
    return current_action if current_action in {"accumulate", "breakout_watch", "wait_pullback", "avoid"} else "wait_pullback"
