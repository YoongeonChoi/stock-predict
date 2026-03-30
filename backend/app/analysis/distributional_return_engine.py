from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import blake2b
from math import exp, log, sqrt

import numpy as np
import pandas as pd

from app.analysis.learned_fusion import apply_learned_fusion, build_fusion_feature_map
from app.analysis.llm_client import ask_json
from app.analysis.stock_graph_context import build_stock_graph_context
from app.models.forecast import FlowSignal
from app.scoring.confidence import calibrate_direction_confidence
from app.services import learned_fusion_profile_service

MODEL_VERSION = "dist-studentt-v3.3-lfgraph"
PERIODS = (20, 60, 120, 252)
DEFAULT_HORIZONS = (1, 5, 20)
MAX_EVENT_ITEMS = 12
EVENT_RESPONSE_SCHEMA = {
    "name": "structured_event_features",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "sentiment": {"type": "number"},
                        "surprise": {"type": "number"},
                        "uncertainty": {"type": "number"},
                        "relevance": {"type": "number"},
                        "event_type": {
                            "type": "string",
                            "enum": [
                                "earnings",
                                "guidance",
                                "mna",
                                "buyback",
                                "dividend",
                                "litigation",
                                "regulation",
                                "suspension",
                                "product",
                                "management",
                                "contract",
                                "issuance",
                                "macro",
                                "other",
                            ],
                        },
                        "horizon": {
                            "type": "string",
                            "enum": ["short", "medium", "long"],
                        },
                    },
                    "required": [
                        "id",
                        "sentiment",
                        "surprise",
                        "uncertainty",
                        "relevance",
                        "event_type",
                        "horizon",
                    ],
                },
            }
        },
        "required": ["items"],
    },
}

POSITIVE_EVENT_KEYWORDS = {
    "beat": ("earnings", 0.75, 0.8, 0.2, "short"),
    "beats": ("earnings", 0.75, 0.8, 0.2, "short"),
    "upgrade": ("guidance", 0.7, 0.7, 0.2, "medium"),
    "buyback": ("buyback", 0.7, 0.65, 0.15, "medium"),
    "dividend": ("dividend", 0.4, 0.35, 0.1, "medium"),
    "contract": ("contract", 0.6, 0.55, 0.15, "medium"),
    "growth": ("guidance", 0.35, 0.2, 0.15, "medium"),
    "surge": ("product", 0.35, 0.2, 0.2, "short"),
    "resilient": ("guidance", 0.3, 0.15, 0.1, "medium"),
    "상향": ("guidance", 0.75, 0.75, 0.15, "medium"),
    "호조": ("earnings", 0.7, 0.65, 0.15, "short"),
    "반등": ("macro", 0.35, 0.2, 0.2, "short"),
    "흑자": ("earnings", 0.8, 0.8, 0.15, "short"),
    "수주": ("contract", 0.65, 0.6, 0.15, "medium"),
    "계약": ("contract", 0.55, 0.45, 0.15, "medium"),
    "배당": ("dividend", 0.4, 0.35, 0.1, "medium"),
    "자사주": ("buyback", 0.65, 0.55, 0.1, "medium"),
}

NEGATIVE_EVENT_KEYWORDS = {
    "miss": ("earnings", -0.8, -0.8, 0.35, "short"),
    "misses": ("earnings", -0.8, -0.8, 0.35, "short"),
    "downgrade": ("guidance", -0.75, -0.7, 0.3, "medium"),
    "warning": ("guidance", -0.8, -0.65, 0.45, "short"),
    "selloff": ("macro", -0.55, -0.35, 0.45, "short"),
    "lawsuit": ("litigation", -0.75, -0.55, 0.7, "long"),
    "delay": ("product", -0.45, -0.3, 0.45, "medium"),
    "cut": ("guidance", -0.55, -0.45, 0.4, "medium"),
    "recession": ("macro", -0.65, -0.35, 0.6, "medium"),
    "하향": ("guidance", -0.75, -0.75, 0.3, "medium"),
    "부진": ("earnings", -0.7, -0.65, 0.35, "short"),
    "적자": ("earnings", -0.8, -0.8, 0.3, "short"),
    "유상증자": ("issuance", -0.85, -0.75, 0.45, "long"),
    "소송": ("litigation", -0.75, -0.55, 0.7, "long"),
    "영업정지": ("suspension", -0.95, -0.9, 0.8, "long"),
    "중단": ("suspension", -0.7, -0.55, 0.6, "medium"),
    "악화": ("guidance", -0.6, -0.45, 0.4, "medium"),
    "경고": ("guidance", -0.75, -0.6, 0.45, "short"),
}

SOURCE_RELIABILITY = {
    "dart": 1.0,
    "opendart": 1.0,
    "press": 0.9,
    "fmp press": 0.88,
    "fmp news": 0.78,
    "google news": 0.72,
    "naver search": 0.68,
    "news": 0.7,
}

HORIZON_DECAY = {"short": 18.0, "medium": 45.0, "long": 90.0}


@dataclass
class EventFeatures:
    sentiment: float = 0.0
    surprise: float = 0.0
    uncertainty: float = 0.0
    relevance: float = 0.0
    event_type_scores: dict[str, float] = field(default_factory=dict)
    horizon_scores: dict[str, float] = field(default_factory=dict)
    item_count: int = 0
    summary: str = ""


@dataclass
class DistributionalEvidence:
    key: str
    label: str
    value: float
    weight: float
    contribution: float
    detail: str


@dataclass
class DistributionalHorizon:
    horizon_days: int
    mean_return_raw: float
    mean_return_excess: float
    q10: float
    q25: float
    q50: float
    q75: float
    q90: float
    p_down: float
    p_flat: float
    p_up: float
    vol_forecast: float
    confidence: float
    raw_confidence: float | None = None
    calibrated_probability: float | None = None
    probability_edge: float | None = None
    analog_support: float | None = None
    distribution_support: float | None = None
    regime_support: float | None = None
    agreement_support: float | None = None
    data_quality_support: float | None = None
    uncertainty_support: float | None = None
    volatility_support: float | None = None
    volatility_ratio: float | None = None
    confidence_calibrator: str | None = None
    calibration_snapshot: dict[str, object] | None = None
    fusion_method: str | None = None
    fusion_profile_sample_count: int | None = None
    fusion_blend_weight: float | None = None
    graph_context_used: bool | None = None
    graph_context_score: float | None = None
    graph_coverage: float | None = None
    fusion_profile_fitted_at: str | None = None


@dataclass
class DistributionalForecast:
    reference_date: str
    reference_price: float
    regime: str
    regime_probs: dict[str, float]
    period_weights: dict[int, float]
    horizons: dict[int, DistributionalHorizon]
    evidence: list[DistributionalEvidence]
    raw_signal: float
    event_features: EventFeatures
    confidence_note: str
    summary: str
    model_version: str = MODEL_VERSION


async def build_structured_event_context(
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
    candidate_items = _prepare_event_items(
        news_items=news_items,
        filings=filings,
        reference_date=reference_date,
    )
    if not candidate_items:
        return heuristic

    system = (
        "You are an event-structuring model for an equity return forecaster.\n"
        "Return JSON only.\n"
        "Do not predict prices, returns, or portfolio weights.\n"
        "For each item, extract only numeric event features using the provided schema.\n"
        "Sentiment and surprise must be in [-1, 1].\n"
        "Uncertainty and relevance must be in [0, 1].\n"
        "event_type must be one of: earnings, guidance, mna, buyback, dividend, litigation, regulation, suspension, product, management, contract, issuance, macro, other.\n"
        "horizon must be one of: short, medium, long."
    )
    user = (
        f"Asset: {asset_name} ({ticker})\n"
        f"Country: {country_code}\n"
        f"Reference date: {reference_date}\n"
        "Extract structured event features from the following news headlines, press releases, and filings.\n\n"
        "Return this JSON shape exactly:\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "item id",\n'
        '      "sentiment": 0.0,\n'
        '      "surprise": 0.0,\n'
        '      "uncertainty": 0.0,\n'
        '      "relevance": 0.0,\n'
        '      "event_type": "earnings",\n'
        '      "horizon": "short"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        f"Items:\n{_event_items_prompt(candidate_items)}"
    )
    result = await ask_json(system, user, temperature=0.0, json_schema=EVENT_RESPONSE_SCHEMA)
    if "error_code" in result or "error" in result:
        return heuristic

    llm_items = result.get("items")
    if not isinstance(llm_items, list):
        return heuristic

    weighted_items: list[tuple[float, dict[str, float | str]]] = []
    reference_dt = _parse_date(reference_date) or datetime.now(timezone.utc)
    for item in candidate_items:
        structured = next((entry for entry in llm_items if str(entry.get("id")) == item["id"]), None)
        if not structured:
            continue
        sentiment = _clip(float(structured.get("sentiment", 0.0) or 0.0))
        surprise = _clip(float(structured.get("surprise", 0.0) or 0.0))
        uncertainty = _clip(float(structured.get("uncertainty", 0.0) or 0.0), 0.0, 1.0)
        relevance = _clip(float(structured.get("relevance", 0.0) or 0.0), 0.0, 1.0)
        event_type = str(structured.get("event_type") or "other").strip().lower()
        if event_type not in {
            "earnings",
            "guidance",
            "mna",
            "buyback",
            "dividend",
            "litigation",
            "regulation",
            "suspension",
            "product",
            "management",
            "contract",
            "issuance",
            "macro",
            "other",
        }:
            event_type = "other"
        horizon = str(structured.get("horizon") or "short").strip().lower()
        if horizon not in HORIZON_DECAY:
            horizon = "short"

        published_dt = _parse_date(str(item["published"])) or reference_dt
        age_days = max((reference_dt - published_dt).total_seconds() / 86400.0, 0.0)
        source_weight = SOURCE_RELIABILITY.get(str(item["source"]).strip().lower(), 0.72)
        weight = max(
            source_weight
            * exp(-age_days / HORIZON_DECAY[horizon])
            * max(relevance, 0.15),
            1e-6,
        )
        weighted_items.append(
            (
                weight,
                {
                    "sentiment": sentiment,
                    "surprise": surprise,
                    "uncertainty": uncertainty,
                    "relevance": relevance,
                    "event_type": event_type,
                    "horizon": horizon,
                },
            )
        )

    aggregated = _aggregate_weighted_event_items(weighted_items)
    if aggregated is None:
        return heuristic
    aggregated.summary = (
        f"GPT 구조화 이벤트 {aggregated.item_count}건을 숫자화했고, "
        f"{max(aggregated.event_type_scores, key=aggregated.event_type_scores.get)} 비중이 가장 높습니다."
        if aggregated.item_count and aggregated.event_type_scores
        else heuristic.summary
    )
    return aggregated


def build_distributional_forecast(
    *,
    price_history: list[dict],
    benchmark_history: list[dict] | None = None,
    macro_snapshot: dict | None = None,
    kosis_snapshot: dict | None = None,
    analyst_context: dict | None = None,
    fundamental_context: dict | None = None,
    flow_signal: FlowSignal | None = None,
    news_items: list[dict] | None = None,
    filings: list[dict] | None = None,
    event_context: EventFeatures | dict | None = None,
    breadth_context: dict | None = None,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    asset_type: str = "stock",
) -> DistributionalForecast | None:
    prices = _to_frame(price_history)
    if prices.empty or len(prices) < 30:
        return None

    benchmark = _to_frame(benchmark_history or [])
    macro = _compress_macro(macro_snapshot or {}, kosis_snapshot or {})
    news_items = news_items or []
    filings = filings or []
    events = _coerce_event_features(
        event_context,
        news_items=news_items,
        filings=filings,
        reference_date=str(prices["date"].iloc[-1]),
    )
    price_block = _encode_price_block(prices, benchmark, macro, events, asset_type)
    fundamental = _compress_fundamentals(
        analyst_context=analyst_context or {},
        fundamental_context=fundamental_context or {},
        current_price=float(prices["close"].iloc[-1]),
    )
    flow_score, flow_detail = _flow_signal_score(flow_signal)
    gates = _build_gates(
        price_score=price_block["fused_score"],
        macro_score=macro["score"],
        fundamental_score=fundamental["score"],
        event_score=events.sentiment + events.surprise - events.uncertainty * 0.4,
        has_macro=macro["available"],
        has_fundamental=fundamental["available"],
        has_event=events.item_count > 0,
        has_flow=flow_signal is not None and flow_signal.available,
    )
    prior_fused_score = (
        price_block["fused_score"]
        + gates["fundamental"] * fundamental["score"] * 0.52
        + gates["macro"] * macro["score"] * 0.44
        + gates["event"] * (events.sentiment * 0.55 + events.surprise * 0.45 - events.uncertainty * 0.25)
        + gates["flow"] * flow_score * 0.22
    )
    regime_probs = _build_regime_probs(
        prices=prices,
        benchmark=benchmark,
        macro=macro,
        fused_score=prior_fused_score,
        events=events,
        breadth_context=breadth_context or {},
    )
    graph_context = build_stock_graph_context(
        price_history=price_history,
        benchmark_history=benchmark_history or [],
        analyst_context=analyst_context or {},
        fundamental_context=fundamental_context or {},
    ).to_dict()
    fusion_features = build_fusion_feature_map(
        prior_fused_score=prior_fused_score,
        fundamental_score=float(fundamental["score"]),
        macro_score=float(macro["score"]),
        event_sentiment=float(events.sentiment),
        event_surprise=float(events.surprise),
        event_uncertainty=float(events.uncertainty),
        flow_score=float(flow_score),
        coverage_naver=_source_coverage(news_items, "naver"),
        coverage_opendart=1.0 if filings else 0.0,
        regime_spread=(regime_probs["risk_on"] - regime_probs["risk_off"]) / 100.0,
    )
    regime = max(regime_probs, key=regime_probs.get)
    base_confidence = _estimate_base_confidence(
        prices=prices,
        regime_probs=regime_probs,
        macro=macro,
        fundamental=fundamental,
        events=events,
        flow_signal=flow_signal,
    )

    horizons_map: dict[int, DistributionalHorizon] = {}
    fusion_methods: set[str] = set()
    for horizon in horizons:
        fusion_profile = learned_fusion_profile_service.get_profile_for_horizon(horizon)
        fusion_result = apply_learned_fusion(
            horizon_days=horizon,
            prior_fused_score=prior_fused_score,
            feature_map=fusion_features,
            profile=fusion_profile,
            graph_context=graph_context,
            history_bars=len(prices),
            macro_available=macro["available"],
            fundamental_available=fundamental["available"],
            flow_available=bool(flow_signal and flow_signal.available),
            event_count=events.item_count,
            event_uncertainty=events.uncertainty,
        )
        fusion_methods.add(fusion_result.method)
        horizons_map[horizon] = _build_horizon_distribution(
            prices=prices,
            benchmark=benchmark,
            horizon=horizon,
            regime_probs=regime_probs,
            prior_fused_score=prior_fused_score,
            fused_score=fusion_result.fused_score,
            price_block=price_block,
            macro=macro,
            fundamental=fundamental,
            flow_signal=flow_signal,
            flow_score=flow_score,
            events=events,
            base_confidence=base_confidence,
            fusion_result=fusion_result,
            fusion_features=fusion_features,
            graph_context=graph_context,
        )

    evidence = _build_evidence(
        price_block=price_block,
        macro=macro,
        fundamental=fundamental,
        events=events,
        flow_score=flow_score,
        flow_detail=flow_detail,
        gates=gates,
        regime_probs=regime_probs,
        fused_score=prior_fused_score,
    )
    confidence_note = _build_confidence_note(
        base_confidence=base_confidence,
        period_weights=price_block["period_weights"],
        regime_probs=regime_probs,
        events=events,
        macro=macro,
        gates=gates,
        fusion_methods=fusion_methods,
        graph_context=graph_context,
    )
    summary = (
        "다중 기간 가격 인코더와 공개시차 안전 거시 압축을 prior backbone으로 유지하고, "
        "실측 prediction log 기반 learned fusion과 경량 graph context를 horizon별 분포 입력에 선택적으로 더한 확률 예측입니다."
    )

    return DistributionalForecast(
        reference_date=str(prices["date"].iloc[-1]),
        reference_price=round(float(prices["close"].iloc[-1]), 2),
        regime=regime,
        regime_probs=regime_probs,
        period_weights=price_block["period_weights"],
        horizons=horizons_map,
        evidence=evidence,
        raw_signal=round(prior_fused_score, 4),
        event_features=events,
        confidence_note=confidence_note,
        summary=summary,
    )


def build_heuristic_event_context(
    *,
    news_items: list[dict],
    filings: list[dict],
    reference_date: str,
) -> EventFeatures:
    reference_dt = _parse_date(reference_date)
    weighted_items: list[tuple[float, dict[str, float | str]]] = []
    type_scores: dict[str, float] = {}
    horizon_scores = {"short": 0.0, "medium": 0.0, "long": 0.0}

    for item in filings[:8]:
        parsed = _score_event_text(
            text=f"{item.get('report_name', '')} {item.get('remark', '')}",
            source=str(item.get("source") or "OpenDART"),
            published=str(item.get("receipt_date") or reference_date),
            reference_dt=reference_dt,
        )
        if parsed:
            weighted_items.append(parsed)

    for item in news_items[:12]:
        parsed = _score_event_text(
            text=f"{item.get('title', '')} {item.get('description', '')}",
            source=str(item.get("source") or "news"),
            published=str(item.get("published") or reference_date),
            reference_dt=reference_dt,
        )
        if parsed:
            weighted_items.append(parsed)

    aggregated = _aggregate_weighted_event_items(weighted_items)
    if aggregated is None:
        return EventFeatures(summary="헤드라인/공시 이벤트 입력 없음")
    aggregated.summary = (
        f"최근 이벤트 {aggregated.item_count}건을 구조화했고, "
        f"{max(aggregated.event_type_scores, key=aggregated.event_type_scores.get)} 비중이 가장 높습니다."
    )
    return aggregated


def _coerce_event_features(
    event_context: EventFeatures | dict | None,
    *,
    news_items: list[dict],
    filings: list[dict],
    reference_date: str,
) -> EventFeatures:
    if isinstance(event_context, EventFeatures):
        return event_context
    if isinstance(event_context, dict):
        return EventFeatures(
            sentiment=float(event_context.get("sentiment", 0.0) or 0.0),
            surprise=float(event_context.get("surprise", 0.0) or 0.0),
            uncertainty=float(event_context.get("uncertainty", 0.0) or 0.0),
            relevance=float(event_context.get("relevance", 0.0) or 0.0),
            event_type_scores=dict(event_context.get("event_type_scores") or {}),
            horizon_scores=dict(event_context.get("horizon_scores") or {}),
            item_count=int(event_context.get("item_count", 0) or 0),
            summary=str(event_context.get("summary", "") or ""),
        )
    return build_heuristic_event_context(
        news_items=news_items,
        filings=filings,
        reference_date=reference_date,
    )


def _encode_price_block(
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    macro: dict,
    events: EventFeatures,
    asset_type: str,
) -> dict:
    close = prices["close"].astype(float)
    returns = _return_series(close)
    volume = prices["volume"].astype(float) if "volume" in prices else pd.Series(np.zeros(len(prices)))
    benchmark_close = benchmark["close"].astype(float) if not benchmark.empty else pd.Series(dtype=float)
    reference_price = float(close.iloc[-1])
    long_vol = max(_window_realized_vol(returns, min(120, len(returns))), 0.008 if asset_type == "index" else 0.012)

    period_rows: list[dict] = []
    for window in PERIODS:
        usable = min(window, len(close) - 1)
        if usable < 12:
            continue
        momentum = _log_return(close, usable)
        relative_strength = momentum - _log_return(benchmark_close, usable) if len(benchmark_close) > usable else 0.0
        rv = _window_realized_vol(returns, usable)
        gk = _garman_klass_vol(prices.tail(usable))
        trend_gap = (reference_price / max(float(close.tail(usable).mean()), 1e-6)) - 1.0
        vwap_gap = _proxy_vwap_gap(prices.tail(min(usable, 20)))
        volume_z = _window_log_volume_z(volume, usable)
        stress = (rv / max(long_vol, 1e-6)) - 1.0
        score = (
            _clip(momentum / 0.12) * 0.34
            + _clip(relative_strength / 0.08) * 0.22
            + _clip(trend_gap / 0.06) * 0.14
            + _clip(vwap_gap / 0.03) * 0.08
            + _clip(volume_z / 2.4) * 0.08
            - _clip(stress / 1.3) * 0.10
            - _clip((gk - rv) / max(rv, 1e-6) / 1.8) * 0.04
        )
        period_rows.append(
            {
                "window": usable,
                "score": float(score),
                "momentum": float(momentum),
                "relative_strength": float(relative_strength),
                "rv": float(rv),
                "detail": (
                    f"{usable}일 모멘텀 {momentum * 100:.2f}%, 상대강도 {relative_strength * 100:.2f}%, "
                    f"실현변동성 {rv * 100:.2f}%"
                ),
            }
        )

    event_heat = abs(events.sentiment) + abs(events.surprise) + events.uncertainty
    macro_persistence = float(macro["score"]) + float(macro["factors"].get("activity", 0.0)) * 0.4
    logits = []
    for row in period_rows:
        window = row["window"]
        logits.append(
            abs(row["score"]) * 0.75
            + (0.55 if window <= 60 else 0.0) * event_heat
            + (0.35 if window >= 120 else -0.05) * macro_persistence
            - (0.18 if window >= 120 and asset_type == "index" and event_heat > 1.0 else 0.0)
        )
    weights = _softmax(np.array(logits, dtype=float))
    period_weights = {int(row["window"]): round(float(weight), 4) for row, weight in zip(period_rows, weights)}
    fused_score = sum(row["score"] * float(weight) for row, weight in zip(period_rows, weights))
    fused_vol = sum(row["rv"] * float(weight) for row, weight in zip(period_rows, weights))
    return {
        "period_rows": period_rows,
        "period_weights": period_weights,
        "fused_score": float(fused_score),
        "fused_vol": float(fused_vol),
        "long_vol": long_vol,
    }


def _compress_macro(ecos_snapshot: dict, kosis_snapshot: dict) -> dict:
    merged = {**ecos_snapshot, **{f"kosis_{key}": value for key, value in kosis_snapshot.items()}}

    def present(name: str, default: float = 0.0) -> float:
        value = merged.get(name)
        return float(value) if value is not None else default

    monetary_inputs = [
        _clip(-(present("base_rate", 2.75) - 2.75) / 1.25),
        _clip(-(present("cpi_yoy", present("kosis_cpi", 2.2)) - 2.2) / 2.0),
    ]
    labor_inputs = [
        _clip((present("kosis_employment", 61.5) - 61.5) / 3.0),
        _clip(-(present("unemployment", 3.2) - 3.2) / 1.0),
    ]
    activity_inputs = [
        _clip(present("export_growth", 0.0) / 12.0),
        _clip(present("industrial_production", present("kosis_industrial_production", 0.0)) / 6.0),
        _clip(present("gdp_growth", 0.0) / 4.0),
    ]
    demand_inputs = [
        _clip((present("consumer_sentiment", 100.0) - 100.0) / 10.0),
        _clip((present("housing_price_index", 100.0) - 100.0) / 12.0),
    ]

    factors = {
        "monetary": _mean_available(monetary_inputs),
        "labor": _mean_available(labor_inputs),
        "activity": _mean_available(activity_inputs),
        "demand": _mean_available(demand_inputs),
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


def _compress_fundamentals(
    *,
    analyst_context: dict,
    fundamental_context: dict,
    current_price: float,
) -> dict:
    features: list[tuple[float, str]] = []
    target_mean = analyst_context.get("target_mean") or fundamental_context.get("target_mean")
    if target_mean and current_price > 0:
        target_gap = (float(target_mean) / current_price) - 1.0
        features.append((_clip(target_gap / 0.2), f"목표가 괴리 {target_gap * 100:.1f}%"))

    buy = float(analyst_context.get("buy") or 0.0)
    hold = float(analyst_context.get("hold") or 0.0)
    sell = float(analyst_context.get("sell") or 0.0)
    total = buy + hold + sell
    if total > 0:
        features.append((_clip((buy - sell) / total), f"매수 {buy:.0f} / 보유 {hold:.0f} / 매도 {sell:.0f}"))

    pe_ratio = fundamental_context.get("pe_ratio")
    if pe_ratio:
        features.append((_clip((18.0 - float(pe_ratio)) / 18.0), f"P/E {float(pe_ratio):.1f}"))
    pb_ratio = fundamental_context.get("pb_ratio")
    if pb_ratio:
        features.append((_clip((2.4 - float(pb_ratio)) / 2.0), f"P/B {float(pb_ratio):.1f}"))
    roe = fundamental_context.get("return_on_equity") or fundamental_context.get("roe")
    if roe:
        features.append((_clip((float(roe) - 10.0) / 12.0), f"ROE {float(roe):.1f}%"))

    if not features:
        return {"available": False, "score": 0.0, "detail": "애널리스트/기본 펀더멘털 입력 부족"}

    score = sum(item[0] for item in features) / len(features)
    return {
        "available": True,
        "score": round(float(score), 4),
        "detail": ", ".join(detail for _, detail in features[:4]),
    }


def _flow_signal_score(flow_signal: FlowSignal | None) -> tuple[float, str]:
    if not flow_signal or not flow_signal.available:
        return 0.0, "검증 가능한 수급 입력이 없어 수급 게이트를 닫았습니다."
    foreign = float(flow_signal.foreign_net_buy or 0.0)
    institutional = float(flow_signal.institutional_net_buy or 0.0)
    retail = float(flow_signal.retail_net_buy or 0.0)
    denominator = max(abs(foreign) + abs(institutional) + abs(retail), 1.0)
    score = (foreign + institutional * 0.9 - retail * 0.35) / denominator
    return _clip(score), f"외국인 {foreign:,.0f}, 기관 {institutional:,.0f}, 개인 {retail:,.0f}"


def _build_gates(
    *,
    price_score: float,
    macro_score: float,
    fundamental_score: float,
    event_score: float,
    has_macro: bool,
    has_fundamental: bool,
    has_event: bool,
    has_flow: bool,
) -> dict[str, float]:
    return {
        "macro": round((1.0 if has_macro else 0.0) * _sigmoid(abs(macro_score) * 1.6 + abs(price_score) * 0.35), 4),
        "fundamental": round((1.0 if has_fundamental else 0.0) * _sigmoid(abs(fundamental_score) * 1.7 + abs(price_score) * 0.25), 4),
        "event": round((1.0 if has_event else 0.0) * _sigmoid(abs(event_score) * 1.55 + 0.2), 4),
        "flow": round((1.0 if has_flow else 0.0) * _sigmoid(abs(price_score) * 0.6 + 0.25), 4),
    }


def _build_regime_probs(
    *,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    macro: dict,
    fused_score: float,
    events: EventFeatures,
    breadth_context: dict,
) -> dict[str, float]:
    close = prices["close"].astype(float)
    benchmark_close = benchmark["close"].astype(float) if not benchmark.empty else close
    benchmark_returns = _return_series(benchmark_close)
    market_momentum = _clip(_log_return(benchmark_close, min(60, len(benchmark_close) - 1)) / 0.12)
    market_vol_fast = _window_realized_vol(benchmark_returns, min(20, len(benchmark_returns)))
    market_vol_slow = max(_window_realized_vol(benchmark_returns, min(120, len(benchmark_returns))), 0.008)
    stress = _clip((market_vol_fast / max(market_vol_slow, 1e-6) - 1.0) / 0.8)
    breadth = float(breadth_context.get("breadth_ratio", 0.5) or 0.5)
    ad_line = float(breadth_context.get("advance_decline", breadth * 2.0 - 1.0) or 0.0)
    dispersion = float(breadth_context.get("dispersion", max(abs(fused_score) * 0.18, market_vol_fast)) or 0.0)
    breadth_norm = _clip((breadth - 0.5) / 0.22)
    dispersion_norm = _clip((dispersion - max(market_vol_slow, 0.012)) / max(market_vol_slow, 0.012))
    treasury_change = float(breadth_context.get("treasury_change", 0.0) or 0.0)
    mrp = float(breadth_context.get("market_risk_premium", 0.0) or 0.0)

    logits = {
        "risk_on": (
            macro["score"] * 1.1
            + market_momentum * 0.95
            + fused_score * 0.65
            + breadth_norm * 0.75
            + ad_line * 0.28
            - dispersion_norm * 0.35
            - stress * 0.8
            - events.uncertainty * 0.25
            - treasury_change * 0.12
            - mrp * 0.08
        ),
        "neutral": 0.18 - abs(fused_score) * 0.25 - abs(macro["score"]) * 0.18 - abs(breadth_norm) * 0.1,
        "risk_off": (
            -macro["score"] * 0.95
            - market_momentum * 0.85
            - fused_score * 0.5
            - breadth_norm * 0.65
            + dispersion_norm * 0.52
            + stress * 1.0
            + events.uncertainty * 0.55
            + treasury_change * 0.15
            + mrp * 0.1
        ),
    }
    probs = _softmax(np.array([logits["risk_on"], logits["neutral"], logits["risk_off"]], dtype=float))
    return {
        "risk_on": round(float(probs[0] * 100.0), 2),
        "neutral": round(float(probs[1] * 100.0), 2),
        "risk_off": round(float(probs[2] * 100.0), 2),
    }


def _estimate_base_confidence(
    *,
    prices: pd.DataFrame,
    regime_probs: dict[str, float],
    macro: dict,
    fundamental: dict,
    events: EventFeatures,
    flow_signal: FlowSignal | None,
) -> float:
    history_bonus = min(len(prices) / 252.0, 1.0) * 18.0
    regime_clarity = max(regime_probs.values()) - sorted(regime_probs.values())[1]
    source_bonus = (5.0 if macro["available"] else 0.0) + (4.0 if fundamental["available"] else 0.0) + min(events.item_count, 6) * 0.22
    source_bonus += 3.0 if flow_signal and flow_signal.available else 0.0
    uncertainty_penalty = events.uncertainty * 10.0
    return _clip(46.0 + history_bonus + regime_clarity * 0.18 + source_bonus - uncertainty_penalty, 36.0, 90.0)


def _source_coverage(items: list[dict], keyword: str) -> float:
    if not items or not keyword:
        return 0.0
    lowered_keyword = keyword.lower().strip()
    matches = 0
    for item in items:
        haystack = " ".join(
            str(item.get(field) or "")
            for field in ("source", "provider", "publisher", "origin", "title", "link")
        ).lower()
        if lowered_keyword in haystack:
            matches += 1
    return _clip(matches / max(len(items), 1), 0.0, 1.0)


def _build_horizon_distribution(
    *,
    prices: pd.DataFrame,
    benchmark: pd.DataFrame,
    horizon: int,
    regime_probs: dict[str, float],
    prior_fused_score: float,
    fused_score: float,
    price_block: dict,
    macro: dict,
    fundamental: dict,
    flow_signal: FlowSignal | None,
    flow_score: float,
    events: EventFeatures,
    base_confidence: float,
    fusion_result,
    fusion_features: dict[str, float],
    graph_context: dict[str, object],
) -> DistributionalHorizon:
    close = prices["close"].astype(float)
    benchmark_close = benchmark["close"].astype(float) if not benchmark.empty else pd.Series(dtype=float)
    horizon_returns = _horizon_returns(close, horizon)
    if len(horizon_returns) < 8:
        returns = _return_series(close)
        horizon_returns = returns * sqrt(max(horizon, 1))
    benchmark_returns = _horizon_returns(benchmark_close, horizon) if len(benchmark_close) > horizon else np.array([], dtype=float)

    hist_mean = float(np.mean(horizon_returns)) if len(horizon_returns) else 0.0
    hist_vol = max(float(np.std(horizon_returns, ddof=1)) if len(horizon_returns) >= 2 else price_block["fused_vol"] * sqrt(horizon), 0.0035 * sqrt(horizon))
    benchmark_mean = float(np.mean(benchmark_returns)) if len(benchmark_returns) else 0.0

    signal_tilt = (
        fused_score * hist_vol * 0.55
        + macro["score"] * hist_vol * 0.16
        + fundamental["score"] * hist_vol * 0.18
        + flow_score * hist_vol * 0.09
        + (events.sentiment * 0.42 + events.surprise * 0.36 - events.uncertainty * 0.18) * hist_vol * 0.22
    )
    base_loc = hist_mean * 0.45 + signal_tilt
    skew = _clip(events.sentiment * 0.35 + events.surprise * 0.28 + fused_score * 0.22 + fundamental["score"] * 0.15)
    regime_shift = {
        "risk_on": hist_vol * 0.34,
        "neutral": 0.0,
        "risk_off": -hist_vol * 0.4,
    }
    regime_scale = {
        "risk_on": 0.92,
        "neutral": 1.0,
        "risk_off": 1.18 + events.uncertainty * 0.18,
    }
    component_weights = _softmax(np.array([0.34 + max(-skew, 0.0) * 0.45, 0.58 - abs(skew) * 0.22, 0.34 + max(skew, 0.0) * 0.45], dtype=float))
    component_offsets = np.array([-0.72 - max(-skew, 0.0) * 0.18, 0.02 * skew, 0.78 + max(skew, 0.0) * 0.18], dtype=float)
    component_scales = np.array([1.14, 0.84, 1.08], dtype=float)

    sample_count = 4096
    rng = np.random.default_rng(_stable_seed(f"{prices['date'].iloc[-1]}:{horizon}:{prices['close'].iloc[-1]}"))
    samples = []
    weights = []
    for regime_name, regime_prob in regime_probs.items():
        for index in range(3):
            weight = max(regime_prob / 100.0 * float(component_weights[index]), 1e-6)
            weights.append(weight)
            loc = base_loc + regime_shift[regime_name] + component_offsets[index] * hist_vol
            scale = max(hist_vol * regime_scale[regime_name] * component_scales[index], 0.002)
            df = 3.6 + (1.0 - min(events.uncertainty, 1.0)) * 4.5 + max(0.0, 0.8 - abs(skew))
            samples.append((loc, scale, df))

    norm_weights = np.array(weights, dtype=float) / sum(weights)
    counts = np.floor(norm_weights * sample_count).astype(int)
    while counts.sum() < sample_count:
        counts[np.argmax(norm_weights - counts / sample_count)] += 1

    draws = []
    for count, (loc, scale, df) in zip(counts, samples):
        if count <= 0:
            continue
        draws.append(loc + scale * rng.standard_t(df, size=count))
    distribution = np.concatenate(draws) if draws else np.array([base_loc], dtype=float)

    q10, q25, q50, q75, q90 = np.quantile(distribution, [0.1, 0.25, 0.5, 0.75, 0.9])
    delta = max(0.0032 * sqrt(horizon), float(np.std(distribution)) * 0.18)
    p_up = float(np.mean(distribution > delta) * 100.0)
    p_down = float(np.mean(distribution < -delta) * 100.0)
    p_flat = max(0.0, 100.0 - p_up - p_down)
    total = p_up + p_flat + p_down or 1.0
    p_up, p_flat, p_down = p_up / total * 100.0, p_flat / total * 100.0, p_down / total * 100.0

    raw_confidence = _clip(
        base_confidence
        - (5.0 if horizon == 20 else 1.5 if horizon == 5 else 0.0)
        + (max(regime_probs.values()) - 34.0) * 0.08
        - float(np.std(distribution)) * 18.0
        - events.uncertainty * 5.5,
        34.0,
        90.0,
    )
    calibrated = calibrate_direction_confidence(
        horizon_days=horizon,
        distribution_confidence=raw_confidence,
        analog_support=None,
        regime_probs=regime_probs,
        p_up=p_up,
        p_down=p_down,
        median_return_pct=q50 * 100.0,
        analog_expected_return_pct=None,
        history_bars=len(prices),
        macro_available=macro["available"],
        fundamental_available=fundamental["available"],
        flow_available=bool(flow_signal and flow_signal.available),
        event_count=events.item_count,
        event_uncertainty=events.uncertainty,
        forecast_volatility_pct=max(float(np.std(distribution, ddof=1)) * 100.0, 0.0),
        realized_volatility_reference_pct=max(hist_vol * 100.0, 1e-6),
        prediction_type=f"distributional_{horizon}d" if horizon > 1 else "next_day",
    )
    calibration_snapshot = dict(calibrated.calibration_snapshot or {})
    calibration_snapshot["fusion_features"] = fusion_features
    calibration_snapshot["graph_context"] = {
        "used": bool(graph_context.get("used")),
        "coverage": round(float(graph_context.get("coverage") or 0.0), 6),
        "peer_count": int(graph_context.get("peer_count") or 0),
        "peer_momentum_5d": round(float(graph_context.get("peer_momentum_5d") or 0.0), 6),
        "peer_momentum_20d": round(float(graph_context.get("peer_momentum_20d") or 0.0), 6),
        "peer_dispersion": round(float(graph_context.get("peer_dispersion") or 0.0), 6),
        "sector_relative_strength": round(float(graph_context.get("sector_relative_strength") or 0.0), 6),
        "correlation_support": round(float(graph_context.get("correlation_support") or 0.0), 6),
        "news_relation_support": round(float(graph_context.get("news_relation_support") or 0.0), 6),
        "graph_context_score": round(float(graph_context.get("graph_context_score") or 0.0), 6),
    }
    calibration_snapshot["fusion_metadata"] = {
        "method": fusion_result.method,
        "profile_bucket": "default",
        "profile_sample_count": int(fusion_result.sample_count),
        "blend_weight": round(float(fusion_result.blend_weight), 6),
        "profile_fitted_at": fusion_result.profile_fitted_at,
        "prior_fused_score": round(float(prior_fused_score), 6),
        "learned_score": round(float(fusion_result.learned_score), 6),
        "graph_context_score": round(float(fusion_result.graph_context_score), 6),
        "graph_coverage": round(float(fusion_result.graph_coverage), 6),
    }

    return DistributionalHorizon(
        horizon_days=horizon,
        mean_return_raw=round(float(np.mean(distribution)), 6),
        mean_return_excess=round(float(np.mean(distribution)) - benchmark_mean, 6),
        q10=round(float(q10), 6),
        q25=round(float(q25), 6),
        q50=round(float(q50), 6),
        q75=round(float(q75), 6),
        q90=round(float(q90), 6),
        p_down=round(p_down, 2),
        p_flat=round(p_flat, 2),
        p_up=round(p_up, 2),
        vol_forecast=round(float(np.std(distribution, ddof=1)), 6),
        confidence=round(calibrated.display_confidence, 1),
        raw_confidence=round(raw_confidence, 1),
        calibrated_probability=round(calibrated.calibrated_probability, 4),
        probability_edge=round((p_up - p_down) / 100.0, 4),
        analog_support=None,
        distribution_support=round(calibrated.distribution_support, 4),
        regime_support=round(calibrated.regime_support, 4),
        agreement_support=round(calibrated.agreement_support, 4) if calibrated.agreement_support is not None else None,
        data_quality_support=round(calibrated.data_quality_support, 4),
        uncertainty_support=round(calibrated.uncertainty_support, 4),
        volatility_support=round(calibrated.volatility_support, 4),
        volatility_ratio=round(calibrated.volatility_ratio, 4),
        confidence_calibrator=calibrated.calibrator_method,
        calibration_snapshot=calibration_snapshot,
        fusion_method=fusion_result.method,
        fusion_profile_sample_count=int(fusion_result.sample_count),
        fusion_blend_weight=round(float(fusion_result.blend_weight), 4),
        graph_context_used=bool(fusion_result.graph_context_used),
        graph_context_score=round(float(fusion_result.graph_context_score), 4),
        graph_coverage=round(float(fusion_result.graph_coverage), 4),
        fusion_profile_fitted_at=fusion_result.profile_fitted_at,
    )


def _build_evidence(
    *,
    price_block: dict,
    macro: dict,
    fundamental: dict,
    events: EventFeatures,
    flow_score: float,
    flow_detail: str,
    gates: dict[str, float],
    regime_probs: dict[str, float],
    fused_score: float,
) -> list[DistributionalEvidence]:
    evidence = [
        DistributionalEvidence(
            key=f"period_{row['window']}",
            label=f"{row['window']}일 가격 인코더",
            value=round(float(row["score"]), 4),
            weight=float(price_block["period_weights"].get(int(row["window"]), 0.0)),
            contribution=round(float(row["score"]) * float(price_block["period_weights"].get(int(row["window"]), 0.0)), 4),
            detail=row["detail"],
        )
        for row in price_block["period_rows"]
    ]
    evidence.extend(
        [
            DistributionalEvidence("macro", "거시 압축 요인", macro["score"], gates["macro"], round(macro["score"] * gates["macro"], 4), macro["detail"]),
            DistributionalEvidence("fundamental", "펀더멘털/애널리스트", fundamental["score"], gates["fundamental"], round(fundamental["score"] * gates["fundamental"], 4), fundamental["detail"]),
            DistributionalEvidence("event", "이벤트 게이트", events.sentiment + events.surprise - events.uncertainty * 0.4, gates["event"], round((events.sentiment + events.surprise - events.uncertainty * 0.4) * gates["event"], 4), events.summary or "구조화 이벤트 없음"),
            DistributionalEvidence("flow", "수급 보정", flow_score, gates["flow"], round(flow_score * gates["flow"], 4), flow_detail),
            DistributionalEvidence("regime", "시장 체제", (regime_probs["risk_on"] - regime_probs["risk_off"]) / 100.0, 1.0, round((regime_probs["risk_on"] - regime_probs["risk_off"]) / 100.0, 4), f"risk_on {regime_probs['risk_on']:.1f}%, risk_off {regime_probs['risk_off']:.1f}%"),
            DistributionalEvidence("fused", "기본 결합 점수", fused_score, 1.0, round(fused_score, 4), "가격 블록 중심으로 거시·펀더멘털·이벤트·수급을 결합한 prior backbone입니다."),
        ]
    )
    evidence.sort(key=lambda item: abs(item.contribution), reverse=True)
    return evidence[:8]


def _build_confidence_note(
    *,
    base_confidence: float,
    period_weights: dict[int, float],
    regime_probs: dict[str, float],
    events: EventFeatures,
    macro: dict,
    gates: dict[str, float],
    fusion_methods: set[str],
    graph_context: dict[str, object],
) -> str:
    dominant_period = max(period_weights, key=period_weights.get) if period_weights else 20
    dominant_regime = max(regime_probs, key=regime_probs.get)
    parts = [
        f"주된 가격 창은 {dominant_period}일 구간이며, 시장 체제는 {dominant_regime} 쪽 확률이 가장 높습니다.",
        f"기본 raw 신뢰도는 {base_confidence:.1f}점이며, 표시 신뢰도는 이 값을 horizon별 sigmoid calibrator로 보정해 실제 적중률과 맞추도록 설계했습니다.",
    ]
    if fusion_methods and fusion_methods != {"prior_only"}:
        parts.append("표본이 충분한 horizon은 learned fusion이 prior backbone 위에 얹히고, graph context가 있으면 blend weight가 더 높아집니다.")
    else:
        parts.append("아직 표본이 부족한 horizon은 learned fusion 대신 prior backbone을 그대로 사용합니다.")
    if bool(graph_context.get("used")):
        parts.append(
            f"graph context는 peer {int(graph_context.get('peer_count') or 0)}건, coverage {float(graph_context.get('coverage') or 0.0):.2f} 수준으로 반영했습니다."
        )
    if events.item_count:
        parts.append(f"이벤트 {events.item_count}건을 구조화해 sentiment {events.sentiment:.2f}, uncertainty {events.uncertainty:.2f}로 반영했습니다.")
    elif not macro["available"]:
        parts.append("거시 입력이 비어 있어 가격 블록 비중을 더 높였습니다.")
    return " ".join(parts)


def _score_event_text(
    *,
    text: str,
    source: str,
    published: str,
    reference_dt: datetime,
) -> tuple[float, dict[str, float | str]] | None:
    lower = str(text or "").lower()
    if not lower.strip():
        return None

    sentiment = 0.0
    surprise = 0.0
    uncertainty = 0.0
    event_type = "macro"
    horizon = "short"

    for keyword, (etype, sent, shock, uncert, horizon_name) in POSITIVE_EVENT_KEYWORDS.items():
        if keyword.lower() in lower:
            event_type, horizon = etype, horizon_name
            sentiment += sent
            surprise += shock
            uncertainty += uncert
    for keyword, (etype, sent, shock, uncert, horizon_name) in NEGATIVE_EVENT_KEYWORDS.items():
        if keyword.lower() in lower:
            event_type, horizon = etype, horizon_name
            sentiment += sent
            surprise += shock
            uncertainty += uncert

    if abs(sentiment) < 0.05 and abs(surprise) < 0.05 and uncertainty < 0.05:
        return None

    source_weight = SOURCE_RELIABILITY.get(str(source).strip().lower(), 0.72)
    published_dt = _parse_date(published) or reference_dt
    age_days = max((reference_dt - published_dt).total_seconds() / 86400.0, 0.0)
    decay = exp(-age_days / HORIZON_DECAY[horizon])
    relevance = _clip(0.62 + min(abs(sentiment) + abs(surprise), 1.0) * 0.25, 0.0, 1.0)
    weight = max(source_weight * decay * max(relevance, 0.15), 1e-6)
    return (
        weight,
        {
            "sentiment": _clip(sentiment),
            "surprise": _clip(surprise),
            "uncertainty": _clip(uncertainty, 0.0, 1.0),
            "relevance": relevance,
            "event_type": event_type,
            "horizon": horizon,
        },
    )


def _prepare_event_items(
    *,
    news_items: list[dict],
    filings: list[dict],
    reference_date: str,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for index, item in enumerate(filings[: min(len(filings), 6)], start=1):
        title = str(item.get("report_name") or item.get("title") or "").strip()
        description = str(item.get("remark") or item.get("description") or "").strip()
        if not title and not description:
            continue
        items.append(
            {
                "id": f"filing_{index}",
                "source": str(item.get("source") or "OpenDART"),
                "published": str(item.get("receipt_date") or item.get("published") or reference_date),
                "title": title,
                "description": description,
            }
        )
    for index, item in enumerate(news_items[: min(len(news_items), MAX_EVENT_ITEMS - len(items))], start=1):
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if not title and not description:
            continue
        items.append(
            {
                "id": f"news_{index}",
                "source": str(item.get("source") or "news"),
                "published": str(item.get("published") or reference_date),
                "title": title,
                "description": description,
            }
        )
    return items[:MAX_EVENT_ITEMS]


def _event_items_prompt(items: list[dict[str, str]]) -> str:
    return "\n".join(
        f"- id={item['id']} | source={item['source']} | published={item['published']} | "
        f"title={item['title']} | description={item['description']}"
        for item in items
    )


def _aggregate_weighted_event_items(
    weighted_items: list[tuple[float, dict[str, float | str]]],
) -> EventFeatures | None:
    if not weighted_items:
        return None

    total_weight = sum(weight for weight, _ in weighted_items) or 1.0
    sentiment = sum(weight * float(item["sentiment"]) for weight, item in weighted_items) / total_weight
    surprise = sum(weight * float(item["surprise"]) for weight, item in weighted_items) / total_weight
    uncertainty = sum(weight * float(item["uncertainty"]) for weight, item in weighted_items) / total_weight
    relevance = sum(weight * float(item["relevance"]) for weight, item in weighted_items) / total_weight

    type_scores: dict[str, float] = {}
    horizon_scores = {"short": 0.0, "medium": 0.0, "long": 0.0}
    for weight, item in weighted_items:
        event_type = str(item["event_type"])
        horizon = str(item["horizon"])
        type_scores[event_type] = type_scores.get(event_type, 0.0) + weight / total_weight
        horizon_scores[horizon] = horizon_scores.get(horizon, 0.0) + weight / total_weight

    return EventFeatures(
        sentiment=round(_clip(sentiment), 4),
        surprise=round(_clip(surprise), 4),
        uncertainty=round(_clip(uncertainty, 0.0, 1.0), 4),
        relevance=round(_clip(relevance, 0.0, 1.0), 4),
        event_type_scores={key: round(value, 4) for key, value in type_scores.items()},
        horizon_scores={key: round(value, 4) for key, value in horizon_scores.items()},
        item_count=len(weighted_items),
        summary="",
    )


def _to_frame(price_history: list[dict]) -> pd.DataFrame:
    if not price_history:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(price_history).copy()
    if "date" not in frame:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    for column in ("open", "high", "low", "close", "volume", "vwap"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = np.nan if column == "vwap" else 0.0
    return frame.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def _return_series(close: pd.Series) -> np.ndarray:
    if close.empty:
        return np.array([], dtype=float)
    return np.log(close.astype(float) / close.astype(float).shift(1)).dropna().to_numpy(dtype=float)


def _horizon_returns(close: pd.Series, horizon: int) -> np.ndarray:
    if close.empty or len(close) <= horizon:
        return np.array([], dtype=float)
    return np.log(close.astype(float) / close.astype(float).shift(horizon)).dropna().to_numpy(dtype=float)


def _window_realized_vol(returns: np.ndarray, window: int) -> float:
    if len(returns) < 2:
        return 0.0
    clipped = returns[-window:] if len(returns) >= window else returns
    return float(np.std(clipped, ddof=1))


def _garman_klass_vol(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    high = frame["high"].astype(float).replace(0, np.nan)
    low = frame["low"].astype(float).replace(0, np.nan)
    open_ = frame["open"].astype(float).replace(0, np.nan)
    close = frame["close"].astype(float).replace(0, np.nan)
    term = 0.5 * np.log(high / low) ** 2 - (2 * log(2) - 1) * np.log(close / open_) ** 2
    term = term.replace([np.inf, -np.inf], np.nan).dropna()
    if term.empty:
        return 0.0
    return float(np.sqrt(max(term.mean(), 0.0)))


def _window_log_volume_z(volume: pd.Series, window: int) -> float:
    if volume.empty or len(volume) < 5:
        return 0.0
    clipped = np.log(np.maximum(volume.tail(window).to_numpy(dtype=float), 1.0))
    if len(clipped) < 2:
        return 0.0
    std = float(np.std(clipped, ddof=1))
    if std <= 1e-8:
        return 0.0
    return float((clipped[-1] - float(np.mean(clipped))) / std)


def _proxy_vwap_gap(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    last = frame.iloc[-1]
    proxy = float(last.get("vwap") or 0.0)
    if proxy <= 0.0:
        typical = ((frame["high"].astype(float) + frame["low"].astype(float) + frame["close"].astype(float)) / 3.0).tail(min(len(frame), 10))
        proxy = float(typical.mean()) if not typical.empty else float(last["close"])
    reference_price = float(last["close"])
    return (reference_price - proxy) / max(reference_price, 1e-6)


def _log_return(close: pd.Series, window: int) -> float:
    if close.empty or len(close) <= 1:
        return 0.0
    usable = min(window, len(close) - 1)
    start = float(close.iloc[-usable - 1])
    end = float(close.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    return float(log(end / start))


def _mean_available(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        for fmt, usable_length in (("%Y-%m-%d", 10), ("%Y%m%d", 8)):
            try:
                return datetime.strptime(text[:usable_length], fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _softmax(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    shifted = values - np.max(values)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values)


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def _stable_seed(text: str) -> int:
    return int(blake2b(text.encode("utf-8"), digest_size=8).hexdigest(), 16) % (2 ** 32)


def _clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(max(low, min(high, value)))
