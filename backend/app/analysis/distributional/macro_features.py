from __future__ import annotations

from app.models.forecast import FlowSignal

from .shared import clip, mean_available


def compress_macro(ecos_snapshot: dict, kosis_snapshot: dict) -> dict:
    merged = {**ecos_snapshot, **{f"kosis_{key}": value for key, value in kosis_snapshot.items()}}

    def present(name: str, default: float = 0.0) -> float:
        value = merged.get(name)
        return float(value) if value is not None else default

    monetary_inputs = [
        clip(-(present("base_rate", 2.75) - 2.75) / 1.25),
        clip(-(present("cpi_yoy", present("kosis_cpi", 2.2)) - 2.2) / 2.0),
    ]
    labor_inputs = [
        clip((present("kosis_employment", 61.5) - 61.5) / 3.0),
        clip(-(present("unemployment", 3.2) - 3.2) / 1.0),
    ]
    activity_inputs = [
        clip(present("export_growth", 0.0) / 12.0),
        clip(present("industrial_production", present("kosis_industrial_production", 0.0)) / 6.0),
        clip(present("gdp_growth", 0.0) / 4.0),
    ]
    demand_inputs = [
        clip((present("consumer_sentiment", 100.0) - 100.0) / 10.0),
        clip((present("housing_price_index", 100.0) - 100.0) / 12.0),
    ]

    factors = {
        "monetary": mean_available(monetary_inputs),
        "labor": mean_available(labor_inputs),
        "activity": mean_available(activity_inputs),
        "demand": mean_available(demand_inputs),
    }
    score = (
        factors["monetary"] * 0.26
        + factors["labor"] * 0.14
        + factors["activity"] * 0.34
        + factors["demand"] * 0.26
    )
    return {
        "available": any(value is not None for value in merged.values()),
        "factors": {key: round(value, 4) for key, value in factors.items()},
        "score": round(float(score), 4),
        "detail": (
            f"통화 {factors['monetary']:.2f}, 노동 {factors['labor']:.2f}, "
            f"실물 {factors['activity']:.2f}, 수요 {factors['demand']:.2f}"
        ),
    }


def compress_fundamentals(
    *,
    analyst_context: dict,
    fundamental_context: dict,
    current_price: float,
) -> dict:
    features: list[tuple[float, str]] = []
    target_mean = analyst_context.get("target_mean") or fundamental_context.get("target_mean")
    if target_mean and current_price > 0:
        target_gap = (float(target_mean) / current_price) - 1.0
        features.append((clip(target_gap / 0.2), f"목표가 괴리 {target_gap * 100:.1f}%"))

    buy = float(analyst_context.get("buy") or 0.0)
    hold = float(analyst_context.get("hold") or 0.0)
    sell = float(analyst_context.get("sell") or 0.0)
    total = buy + hold + sell
    if total > 0:
        features.append((clip((buy - sell) / total), f"매수 {buy:.0f} / 보유 {hold:.0f} / 매도 {sell:.0f}"))

    pe_ratio = fundamental_context.get("pe_ratio")
    if pe_ratio:
        features.append((clip((18.0 - float(pe_ratio)) / 18.0), f"P/E {float(pe_ratio):.1f}"))
    pb_ratio = fundamental_context.get("pb_ratio")
    if pb_ratio:
        features.append((clip((2.4 - float(pb_ratio)) / 2.0), f"P/B {float(pb_ratio):.1f}"))
    roe = fundamental_context.get("return_on_equity") or fundamental_context.get("roe")
    if roe:
        features.append((clip((float(roe) - 10.0) / 12.0), f"ROE {float(roe):.1f}%"))

    if not features:
        return {"available": False, "score": 0.0, "detail": "애널리스트/기본 펀더멘털 입력 부족"}

    score = sum(item[0] for item in features) / len(features)
    return {
        "available": True,
        "score": round(float(score), 4),
        "detail": ", ".join(detail for _, detail in features[:4]),
    }


def flow_signal_score(flow_signal: FlowSignal | None) -> tuple[float, str]:
    if not flow_signal or not flow_signal.available:
        return 0.0, "검증 가능한 수급 입력이 없어 수급 게이트를 닫았습니다."
    foreign = float(flow_signal.foreign_net_buy or 0.0)
    institutional = float(flow_signal.institutional_net_buy or 0.0)
    retail = float(flow_signal.retail_net_buy or 0.0)
    denominator = max(abs(foreign) + abs(institutional) + abs(retail), 1.0)
    score = (foreign + institutional * 0.9 - retail * 0.35) / denominator
    return clip(score), f"외국인 {foreign:,.0f}, 기관 {institutional:,.0f}, 개인 {retail:,.0f}"
