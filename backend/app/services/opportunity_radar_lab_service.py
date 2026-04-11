"""Capture and analyze daily opportunity radar cohorts."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import json
from math import exp
from typing import Any

from app.database import db
from app.utils.lazy_module import LazyModuleProxy

RADAR_CAPTURE_LIMIT = 10
RADAR_PROFILE_MIN_SAMPLES = 24
RADAR_FEATURE_MIN_SAMPLES = 8
RADAR_PROFILE_MAX_ROWS = 600
RADAR_PROFILE_DECAY_DAYS = 45.0
RADAR_DIRECTION_FLAT_THRESHOLD_PCT = 0.15
RADAR_MAX_SCORE_ADJUSTMENT_POINTS = 6.0

yfinance_client = LazyModuleProxy("app.data.yfinance_client")

_TAG_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("momentum", ("모멘텀", "추세", "돌파", "breakout", "relative strength", "advance", "rebound")),
    ("liquidity", ("수급", "외국인", "기관", "flow", "turnover", "short covering")),
    ("earnings", ("실적", "가이던스", "earnings", "guidance", "margin", "order backlog")),
    ("valuation", ("저평가", "밸류", "valuation", "multiple", "rerating")),
    ("macro", ("금리", "환율", "정책", "macro", "cpi", "fomc", "yield", "달러")),
    ("sector", ("업황", "섹터", "산업", "peer", "cycle", "theme")),
    ("quality", ("현금흐름", "재무", "quality", "balance sheet", "cash flow", "free cash")),
)

_FEATURE_LABELS = {
    "tag_momentum": "모멘텀",
    "tag_liquidity": "수급",
    "tag_earnings": "실적",
    "tag_valuation": "밸류",
    "tag_macro": "매크로",
    "tag_sector": "업황",
    "tag_quality": "퀄리티",
    "support_confidence_high": "고신뢰",
    "support_probability_edge": "확률 우위",
    "support_regime_strong": "국면 정합",
    "support_analog_strong": "유사 패턴",
    "support_data_quality_weak": "데이터 품질 약함",
    "support_risk_reward": "손익비",
}

_runtime_profile: dict[str, Any] | None = None


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _normalize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value)).isoformat()
    except (TypeError, ValueError):
        return None


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _normalize_thesis(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip() for item in items if str(item).strip()]


def _payload_reference_date(payload: dict) -> str:
    generated_at = str(payload.get("generated_at") or "").strip()
    generated_date = _parse_date(generated_at)
    if generated_date is not None:
        return generated_date.isoformat()
    return datetime.utcnow().date().isoformat()


def _extract_radar_tags(thesis: list[str], sector: str | None = None) -> list[str]:
    text = " ".join(thesis).lower()
    tags: list[str] = []
    for tag, patterns in _TAG_PATTERNS:
        if any(pattern.lower() in text for pattern in patterns):
            tags.append(tag)
    if sector and "sector" not in tags and any(keyword in text for keyword in ("업황", "peer", "cycle", "theme")):
        tags.append("sector")
    if not tags:
        tags.append("momentum")
    return tags[:4]


def _build_support_snapshot(item: dict) -> dict[str, Any]:
    return {
        "up_probability_20d": _safe_float(item.get("up_probability_20d") or item.get("up_probability")),
        "confidence_20d": _safe_float(item.get("distribution_confidence_20d") or item.get("confidence")),
        "probability_edge_20d": _safe_float(item.get("probability_edge_20d")),
        "regime_support_20d": _safe_float(item.get("regime_support_20d")),
        "analog_support_20d": _safe_float(item.get("analog_support_20d")),
        "data_quality_support_20d": _safe_float(item.get("data_quality_support_20d")),
        "risk_reward_estimate": _safe_float(item.get("risk_reward_estimate")),
        "action": item.get("action"),
        "execution_bias": item.get("execution_bias"),
    }


def _feature_names(tags: list[str], support: dict[str, Any]) -> list[str]:
    feature_names: list[str] = []
    for tag in tags:
        feature_names.append(f"tag_{tag}")
    if (_safe_float(support.get("confidence_20d")) or 0.0) >= 66.0:
        feature_names.append("support_confidence_high")
    if ((_safe_float(support.get("up_probability_20d")) or 0.0) >= 60.0) or ((_safe_float(support.get("probability_edge_20d")) or 0.0) >= 4.0):
        feature_names.append("support_probability_edge")
    if (_safe_float(support.get("regime_support_20d")) or 0.0) >= 0.62:
        feature_names.append("support_regime_strong")
    if (_safe_float(support.get("analog_support_20d")) or 0.0) >= 0.55:
        feature_names.append("support_analog_strong")
    if (_safe_float(support.get("data_quality_support_20d")) or 1.0) < 0.45:
        feature_names.append("support_data_quality_weak")
    if (_safe_float(support.get("risk_reward_estimate")) or 0.0) >= 1.2:
        feature_names.append("support_risk_reward")
    return feature_names


def _empty_profile() -> dict[str, Any]:
    return {
        "status": "bootstrapping",
        "sample_count": 0,
        "baseline_success_score": 0.0,
        "feature_weights": {},
        "top_positive": [],
        "top_negative": [],
        "updated_at": None,
    }


def get_profile_summary() -> dict[str, Any]:
    return dict(_runtime_profile or _empty_profile())


async def capture_opportunity_radar_snapshot(
    country_code: str,
    payload: dict,
    *,
    limit: int = RADAR_CAPTURE_LIMIT,
) -> dict:
    if not isinstance(payload, dict):
        return {"captured_snapshots": 0, "reference_date": None}

    reference_date = _payload_reference_date(payload)
    captured = 0
    for rank, item in enumerate(list(payload.get("opportunities") or [])[: max(limit, 0)], start=1):
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("ticker") or "").strip().upper()
        reference_price = _safe_float(item.get("current_price"), 0.0) or 0.0
        if not symbol or reference_price <= 0:
            continue
        thesis = _normalize_thesis(item.get("thesis"))
        tags = _extract_radar_tags(thesis, sector=str(item.get("sector") or "").strip() or None)
        support = _build_support_snapshot(item)
        await db.opportunity_radar_snapshot_upsert(
            country_code=country_code,
            reference_date=reference_date,
            rank=rank,
            symbol=symbol,
            name=str(item.get("name") or "").strip() or None,
            sector=str(item.get("sector") or "").strip() or None,
            reference_price=reference_price,
            base_score=_safe_float(item.get("base_opportunity_score"), _safe_float(item.get("opportunity_score"), 0.0) or 0.0) or 0.0,
            adjusted_score=_safe_float(item.get("opportunity_score")),
            up_probability_20d=_safe_float(item.get("up_probability_20d") or item.get("up_probability")),
            confidence_20d=_safe_float(item.get("distribution_confidence_20d") or item.get("confidence")),
            predicted_close_20d=_safe_float(item.get("price_q50_20d") or item.get("base_case_price")),
            predicted_low_20d=_safe_float(item.get("price_q25_20d") or item.get("bear_case_price")),
            predicted_high_20d=_safe_float(item.get("price_q75_20d") or item.get("bull_case_price")),
            target_date_20d=str(item.get("target_date_20d") or "").strip() or None,
            thesis_json=thesis,
            tags_json=tags,
            support_json=support,
        )
        captured += 1
    return {"captured_snapshots": captured, "reference_date": reference_date}


def _find_anchor_index(history: list[dict], reference_date: str) -> int | None:
    target_date = _parse_date(reference_date)
    if target_date is None:
        return None
    anchor_index: int | None = None
    for index, row in enumerate(history):
        row_date = _parse_date(row.get("date"))
        if row_date is None:
            continue
        if row_date <= target_date:
            anchor_index = index
            continue
        break
    return anchor_index


def _resolve_target_row(
    history: list[dict],
    anchor_index: int,
    *,
    target_date: str | None,
    steps: int,
) -> tuple[dict | None, str | None]:
    if target_date:
        for index, row in enumerate(history):
            if index <= anchor_index:
                continue
            if str(row.get("date") or "") == target_date:
                return row, target_date
    target_index = anchor_index + steps
    if 0 <= target_index < len(history):
        row = history[target_index]
        return row, str(row.get("date") or "") or None
    return None, None


def _evaluate_direction(actual_close: float, reference_price: float) -> tuple[str, bool, float]:
    return_pct = ((actual_close / reference_price) - 1.0) * 100.0 if reference_price > 0 else 0.0
    if return_pct >= RADAR_DIRECTION_FLAT_THRESHOLD_PCT:
        return "up", True, round(return_pct, 2)
    if return_pct <= -RADAR_DIRECTION_FLAT_THRESHOLD_PCT:
        return "down", False, round(return_pct, 2)
    return "flat", False, round(return_pct, 2)


def _build_horizon_payload(
    row: dict | None,
    *,
    reference_price: float,
    predicted_low: float | None = None,
    predicted_high: float | None = None,
) -> dict[str, Any]:
    if row is None:
        return {
            "target_date": None,
            "actual_close": None,
            "return_pct": None,
            "direction_outcome": None,
            "direction_hit": None,
            "within_band": None,
        }
    actual_close = _safe_float(row.get("close"), 0.0) or 0.0
    direction_outcome, direction_hit, return_pct = _evaluate_direction(actual_close, reference_price)
    within_band = None
    if predicted_low is not None and predicted_high is not None:
        within_band = float(predicted_low) <= actual_close <= float(predicted_high)
    return {
        "target_date": str(row.get("date") or "") or None,
        "actual_close": round(actual_close, 2),
        "return_pct": return_pct,
        "direction_outcome": direction_outcome,
        "direction_hit": direction_hit,
        "within_band": within_band,
    }


def _context_labels(tags: list[str], support: dict[str, Any], *, positive: bool) -> list[str]:
    labels: list[str] = []
    if positive:
        if "momentum" in tags:
            labels.append("모멘텀")
        if "liquidity" in tags:
            labels.append("수급")
        if "earnings" in tags:
            labels.append("실적")
        if (_safe_float(support.get("regime_support_20d")) or 0.0) >= 0.62:
            labels.append("시장 국면")
        if (_safe_float(support.get("up_probability_20d")) or 0.0) >= 60.0:
            labels.append("상승 확률 우위")
    else:
        if (_safe_float(support.get("data_quality_support_20d")) or 1.0) < 0.45:
            labels.append("데이터 품질")
        if (_safe_float(support.get("regime_support_20d")) or 1.0) < 0.45:
            labels.append("국면 역풍")
        if (_safe_float(support.get("confidence_20d")) or 0.0) >= 68.0:
            labels.append("고신뢰 미스")
    return labels


def _build_review_payload(
    *,
    symbol: str,
    tags: list[str],
    support: dict[str, Any],
    horizon_1d: dict[str, Any],
    horizon_5d: dict[str, Any],
    horizon_20d: dict[str, Any],
) -> dict[str, str]:
    hit_20d = horizon_20d.get("direction_hit")
    hit_5d = horizon_5d.get("direction_hit")
    band_20d = horizon_20d.get("within_band")
    positive_context = _context_labels(tags, support, positive=True)
    negative_context = _context_labels(tags, support, positive=False)

    if hit_20d is True and band_20d is True:
        summary = f"{symbol}은 20거래일 방향과 밴드를 함께 맞췄습니다."
        detail = (
            f"{', '.join(positive_context[:3])} 신호가 함께 받쳐 주면서 상승 thesis가 끝까지 유지됐습니다."
            if positive_context
            else "상승 thesis가 과하지 않게 유지되면서 실제 종가가 예상 밴드 안에서 마감했습니다."
        )
        return {"kind": "clean-hit", "summary": summary, "detail": detail}
    if hit_20d is True:
        return {
            "kind": "direction-hit",
            "summary": f"{symbol}은 방향은 맞췄지만 20거래일 밴드는 벗어났습니다.",
            "detail": "상승 방향 자체는 유지됐지만 변동성 폭을 다소 좁게 본 구간으로 해석됩니다.",
        }
    if hit_5d is True:
        detail = (
            f"{', '.join(negative_context[:3])} 요인이 뒤늦게 크게 작용해 중기 추세가 꺾였습니다."
            if negative_context
            else "초기 반응은 나쁘지 않았지만 중기 추세가 이어지지 않아 상위 랭크 유지 근거가 약했습니다."
        )
        return {
            "kind": "reversal-miss",
            "summary": f"{symbol}은 초기 1주 흐름은 맞았지만 20거래일 방향은 지키지 못했습니다.",
            "detail": detail,
        }
    if horizon_1d.get("direction_hit") is True:
        return {
            "kind": "early-hit",
            "summary": f"{symbol}은 다음날 반응은 맞았지만 추세 확장까지 이어지지는 않았습니다.",
            "detail": "단기 반응과 중기 유지력을 다른 문제로 보고, 수급/업황 가중을 더 보수적으로 볼 필요가 있습니다.",
        }
    detail = (
        f"{', '.join(negative_context[:3])} 신호를 충분히 깎지 못한 채 상위 후보로 남은 사례입니다."
        if negative_context
        else "초기 확률과 점수는 높았지만 실제로는 상승 쪽 follow-through가 나오지 않았습니다."
    )
    return {
        "kind": "miss",
        "summary": f"{symbol}은 상승 thesis가 유지되지 못해 방향 미스로 끝났습니다.",
        "detail": detail,
    }


def _evaluation_complete(evaluation: dict[str, Any]) -> bool:
    horizon_20d = (evaluation.get("horizons") or {}).get("20d") or {}
    return horizon_20d.get("actual_close") is not None


def _build_evaluation_payload(row: dict, history: list[dict]) -> dict[str, Any] | None:
    reference_date = str(row.get("reference_date") or "").strip()
    reference_price = _safe_float(row.get("reference_price"), 0.0) or 0.0
    if not reference_date or reference_price <= 0 or not history:
        return None
    anchor_index = _find_anchor_index(history, reference_date)
    if anchor_index is None:
        return None
    anchor_row = history[anchor_index]
    horizon_1d_row, resolved_target_1d = _resolve_target_row(history, anchor_index, target_date=row.get("target_date_1d"), steps=1)
    horizon_5d_row, resolved_target_5d = _resolve_target_row(history, anchor_index, target_date=row.get("target_date_5d"), steps=5)
    horizon_20d_row, resolved_target_20d = _resolve_target_row(history, anchor_index, target_date=row.get("target_date_20d"), steps=20)
    predicted_low_20d = _safe_float(row.get("predicted_low_20d"))
    predicted_high_20d = _safe_float(row.get("predicted_high_20d"))
    tags = _parse_json_list(row.get("tags_json"))
    support = _parse_json_dict(row.get("support_json"))

    horizon_1d = _build_horizon_payload(horizon_1d_row, reference_price=reference_price)
    horizon_5d = _build_horizon_payload(horizon_5d_row, reference_price=reference_price)
    horizon_20d = _build_horizon_payload(
        horizon_20d_row,
        reference_price=reference_price,
        predicted_low=predicted_low_20d,
        predicted_high=predicted_high_20d,
    )
    review = _build_review_payload(
        symbol=str(row.get("symbol") or ""),
        tags=tags,
        support=support,
        horizon_1d=horizon_1d,
        horizon_5d=horizon_5d,
        horizon_20d=horizon_20d,
    )
    return {
        "anchor_date": str(anchor_row.get("date") or "") or None,
        "reference_date": reference_date,
        "reference_price": round(reference_price, 2),
        "horizons": {
            "1d": {**horizon_1d, "target_date": resolved_target_1d or horizon_1d.get("target_date")},
            "5d": {**horizon_5d, "target_date": resolved_target_5d or horizon_5d.get("target_date")},
            "20d": {**horizon_20d, "target_date": resolved_target_20d or horizon_20d.get("target_date")},
        },
        "review": review,
    }


def _success_score(evaluation: dict[str, Any]) -> float | None:
    horizons = evaluation.get("horizons") or {}
    components: list[tuple[float, float]] = []
    for key, weight in (("1d", 0.2), ("5d", 0.35), ("20d", 0.45)):
        hit = (horizons.get(key) or {}).get("direction_hit")
        if hit is not None:
            components.append((weight, 1.0 if hit else 0.0))
    band_hit = (horizons.get("20d") or {}).get("within_band")
    if band_hit is not None:
        components.append((0.2, 1.0 if band_hit else 0.0))
    if not components:
        return None
    total_weight = sum(weight for weight, _ in components)
    return sum(weight * value for weight, value in components) / max(total_weight, 1e-6)


def _build_profile_from_rows(rows: list[dict]) -> dict[str, Any]:
    today = date.today()
    samples: list[dict[str, Any]] = []
    for row in rows:
        evaluation = _parse_json_dict(row.get("evaluation_json"))
        score = _success_score(evaluation)
        reference_date = _parse_date(row.get("reference_date"))
        if score is None or reference_date is None:
            continue
        age_days = max((today - reference_date).days, 0)
        sample_weight = exp(-age_days / RADAR_PROFILE_DECAY_DAYS)
        support = _parse_json_dict(row.get("support_json"))
        tags = _parse_json_list(row.get("tags_json"))
        samples.append(
            {
                "score": score,
                "weight": sample_weight,
                "features": _feature_names(tags, support),
            }
        )
    if len(samples) < RADAR_PROFILE_MIN_SAMPLES:
        return {
            **_empty_profile(),
            "sample_count": len(samples),
            "updated_at": datetime.now().isoformat(),
        }

    total_weight = sum(item["weight"] for item in samples)
    baseline_success_score = sum(item["score"] * item["weight"] for item in samples) / max(total_weight, 1e-6)
    feature_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"weighted_score": 0.0, "weight": 0.0, "count": 0.0})
    for sample in samples:
        for feature_name in sample["features"]:
            feature_totals[feature_name]["weighted_score"] += sample["score"] * sample["weight"]
            feature_totals[feature_name]["weight"] += sample["weight"]
            feature_totals[feature_name]["count"] += 1.0

    feature_weights: dict[str, float] = {}
    for feature_name, bucket in feature_totals.items():
        count = int(bucket["count"])
        if count < RADAR_FEATURE_MIN_SAMPLES or bucket["weight"] <= 0:
            continue
        feature_success = bucket["weighted_score"] / bucket["weight"]
        shrinkage = min(count / 48.0, 1.0)
        feature_weights[feature_name] = round(
            _clip((feature_success - baseline_success_score) * shrinkage, -0.12, 0.12),
            4,
        )

    ranked_features = sorted(feature_weights.items(), key=lambda item: item[1], reverse=True)
    top_positive = [
        {"key": key, "label": _FEATURE_LABELS.get(key, key), "delta": value}
        for key, value in ranked_features
        if value > 0
    ][:4]
    top_negative = [
        {"key": key, "label": _FEATURE_LABELS.get(key, key), "delta": value}
        for key, value in sorted(feature_weights.items(), key=lambda item: item[1])
        if value < 0
    ][:4]
    return {
        "status": "active",
        "sample_count": len(samples),
        "baseline_success_score": round(baseline_success_score, 4),
        "feature_weights": feature_weights,
        "top_positive": top_positive,
        "top_negative": top_negative,
        "updated_at": datetime.now().isoformat(),
    }


async def refresh_adjustment_profile(limit: int = RADAR_PROFILE_MAX_ROWS) -> dict[str, Any]:
    global _runtime_profile
    rows = await db.opportunity_radar_snapshot_recent(limit=max(limit, RADAR_CAPTURE_LIMIT))
    _runtime_profile = _build_profile_from_rows(rows)
    return dict(_runtime_profile)


def adjust_opportunity_score(
    *,
    base_score: float,
    thesis: list[str] | None,
    sector: str | None,
    support_snapshot: dict[str, Any],
) -> dict[str, Any]:
    profile = _runtime_profile or _empty_profile()
    if profile.get("status") != "active":
        return {
            "applied": False,
            "adjusted_score": round(base_score, 1),
            "adjustment_points": 0.0,
            "reason": "표본 축적 중",
        }
    feature_names = _feature_names(_extract_radar_tags(thesis or [], sector), support_snapshot)
    contributors: list[tuple[str, float]] = []
    raw_delta = 0.0
    for feature_name in feature_names:
        weight = _safe_float((profile.get("feature_weights") or {}).get(feature_name), 0.0) or 0.0
        if abs(weight) < 1e-6:
            continue
        raw_delta += weight
        contributors.append((feature_name, weight))
    if not contributors:
        return {
            "applied": False,
            "adjusted_score": round(base_score, 1),
            "adjustment_points": 0.0,
            "reason": "활성 프로필은 있지만 현재 후보와 맞는 실측 패턴이 아직 없습니다.",
        }
    strength = min(max((int(profile.get("sample_count") or 0) - RADAR_PROFILE_MIN_SAMPLES) / 120.0, 0.18), 1.0)
    adjustment_points = _clip(raw_delta * 24.0 * strength, -RADAR_MAX_SCORE_ADJUSTMENT_POINTS, RADAR_MAX_SCORE_ADJUSTMENT_POINTS)
    adjusted_score = _clip(float(base_score) + adjustment_points, 0.0, 100.0)
    if base_score < 62.0:
        adjusted_score = min(adjusted_score, 61.5)
    ranked_contributors = sorted(contributors, key=lambda item: abs(item[1]), reverse=True)
    top_labels = [_FEATURE_LABELS.get(name, name) for name, _ in ranked_contributors[:2]]
    reason = (
        f"{', '.join(top_labels)} 패턴이 최근 실측에서 상대적으로 강했습니다."
        if ranked_contributors and ranked_contributors[0][1] > 0
        else f"{', '.join(top_labels)} 패턴은 최근 실측에서 보수 조정 대상이었습니다."
    )
    return {
        "applied": True,
        "adjusted_score": round(adjusted_score, 1),
        "adjustment_points": round(adjustment_points, 2),
        "reason": reason,
    }


async def refresh_opportunity_radar_accuracy(limit: int = 200) -> dict[str, Any]:
    rows = await db.opportunity_radar_snapshot_recent(limit=max(limit, RADAR_CAPTURE_LIMIT))
    pending_rows = []
    today = date.today()
    for row in rows:
        reference_date = _parse_date(row.get("reference_date"))
        if reference_date is None or reference_date > today:
            continue
        if _evaluation_complete(_parse_json_dict(row.get("evaluation_json"))):
            continue
        pending_rows.append(row)

    rows_by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in pending_rows:
        rows_by_symbol[str(row.get("symbol") or "").upper()].append(row)

    updated_rows = 0
    partial_rows = 0
    evaluated_rows = 0
    fetch_errors = 0
    for symbol, symbol_rows in rows_by_symbol.items():
        if not symbol:
            continue
        try:
            history = await yfinance_client.get_price_history(symbol, period="1y")
        except Exception:
            fetch_errors += len(symbol_rows)
            continue
        for row in symbol_rows:
            evaluation = _build_evaluation_payload(row, history)
            if evaluation is None:
                continue
            horizons = evaluation.get("horizons") or {}
            if _evaluation_complete(evaluation):
                evaluated_rows += 1
            elif any((horizons.get(key) or {}).get("actual_close") is not None for key in ("1d", "5d")):
                partial_rows += 1
            await db.opportunity_radar_snapshot_update_evaluation(
                record_id=int(row["id"]),
                anchor_date=evaluation.get("anchor_date"),
                target_date_1d=(horizons.get("1d") or {}).get("target_date"),
                target_date_5d=(horizons.get("5d") or {}).get("target_date"),
                target_date_20d=(horizons.get("20d") or {}).get("target_date"),
                evaluation_json=evaluation,
                evaluation_complete=_evaluation_complete(evaluation),
            )
            updated_rows += 1

    profile = await refresh_adjustment_profile()
    return {
        "checked_rows": len(pending_rows),
        "updated_rows": updated_rows,
        "partial_rows": partial_rows,
        "evaluated_rows": evaluated_rows,
        "fetch_errors": fetch_errors,
        "profile_status": profile.get("status"),
        "profile_sample_count": int(profile.get("sample_count") or 0),
        "checked_at": datetime.now().isoformat(),
    }


async def get_lab_summary(limit: int = 300) -> dict[str, Any]:
    rows = await db.opportunity_radar_snapshot_recent(limit=max(limit, RADAR_CAPTURE_LIMIT))
    if not rows:
        return {
            "stored_snapshots": 0,
            "capture_days": 0,
            "latest_reference_date": None,
            "last_evaluated_at": None,
            "direction_accuracy_1d": 0.0,
            "direction_accuracy_5d": 0.0,
            "direction_accuracy_20d": 0.0,
            "band_hit_rate_20d": 0.0,
            "avg_return_pct_5d": 0.0,
            "avg_return_pct_20d": 0.0,
            "pending_20d": 0,
            "tag_breakdown": [],
            "recent_cohorts": [],
            "review_queue": [],
            "profile": get_profile_summary(),
        }

    latest_reference_date = rows[0].get("reference_date")
    reference_dates = {
        str(row.get("reference_date") or "").strip()
        for row in rows
        if str(row.get("reference_date") or "").strip()
    }
    last_evaluated_at = None
    tag_counts: dict[str, int] = defaultdict(int)
    cohorts: dict[str, dict[str, Any]] = {}
    review_queue: list[dict[str, Any]] = []
    horizon_buckets = {
        "1d": {"hit": 0, "total": 0, "return_sum": 0.0, "return_count": 0},
        "5d": {"hit": 0, "total": 0, "return_sum": 0.0, "return_count": 0},
        "20d": {"hit": 0, "total": 0, "return_sum": 0.0, "return_count": 0},
    }
    band_hits_20d = 0
    band_total_20d = 0
    pending_20d = 0

    for row in rows:
        reference_date = str(row.get("reference_date") or "").strip() or "unknown"
        cohort = cohorts.setdefault(
            reference_date,
            {
                "reference_date": reference_date,
                "capture_count": 0,
                "evaluated_count": 0,
                "pending_count": 0,
                "direction_hits_1d": 0,
                "direction_total_1d": 0,
                "direction_hits_5d": 0,
                "direction_total_5d": 0,
                "direction_hits_20d": 0,
                "direction_total_20d": 0,
                "band_hits_20d": 0,
                "band_total_20d": 0,
                "return_sum_20d": 0.0,
                "return_count_20d": 0,
                "top_symbols": [],
            },
        )
        cohort["capture_count"] += 1
        if row.get("symbol") and len(cohort["top_symbols"]) < 4:
            cohort["top_symbols"].append(str(row["symbol"]))

        evaluated_at = _normalize_timestamp(row.get("evaluated_at"))
        if evaluated_at and (last_evaluated_at is None or evaluated_at > last_evaluated_at):
            last_evaluated_at = evaluated_at

        tags = _parse_json_list(row.get("tags_json"))
        for tag in tags:
            tag_counts[tag] += 1

        evaluation = _parse_json_dict(row.get("evaluation_json"))
        horizons = evaluation.get("horizons") or {}
        review = evaluation.get("review") or {}
        horizon_20d = horizons.get("20d") or {}
        if horizon_20d.get("actual_close") is None:
            pending_20d += 1
            cohort["pending_count"] += 1
        else:
            cohort["evaluated_count"] += 1

        for horizon_key in ("1d", "5d", "20d"):
            horizon = horizons.get(horizon_key) or {}
            hit = horizon.get("direction_hit")
            actual_return_pct = _safe_float(horizon.get("actual_return_pct"))
            if hit is not None:
                horizon_buckets[horizon_key]["total"] += 1
                if hit:
                    horizon_buckets[horizon_key]["hit"] += 1
                cohort[f"direction_total_{horizon_key}"] += 1
                if hit:
                    cohort[f"direction_hits_{horizon_key}"] += 1
            if actual_return_pct is not None:
                horizon_buckets[horizon_key]["return_sum"] += actual_return_pct
                horizon_buckets[horizon_key]["return_count"] += 1
                if horizon_key == "20d":
                    cohort["return_sum_20d"] += actual_return_pct
                    cohort["return_count_20d"] += 1

        within_band = horizon_20d.get("within_band")
        if within_band is not None:
            band_total_20d += 1
            cohort["band_total_20d"] += 1
            if within_band:
                band_hits_20d += 1
                cohort["band_hits_20d"] += 1

        if review and horizon_20d.get("actual_close") is not None:
            review_queue.append(
                {
                    "reference_date": reference_date,
                    "symbol": str(row.get("symbol") or ""),
                    "name": row.get("name") or row.get("symbol") or "",
                    "rank": int(row.get("rank") or 0),
                    "kind": str(review.get("kind") or "review"),
                    "summary": str(review.get("summary") or "").strip(),
                    "detail": str(review.get("detail") or "").strip(),
                    "return_pct_20d": round(_safe_float(horizon_20d.get("actual_return_pct"), 0.0) or 0.0, 2),
                    "direction_hit_20d": horizon_20d.get("direction_hit"),
                    "within_band_20d": horizon_20d.get("within_band"),
                }
            )

    def _ratio(hit: int, total: int) -> float:
        return round(hit / total, 4) if total else 0.0

    def _avg(total_sum: float, total_count: int) -> float:
        return round(total_sum / total_count, 2) if total_count else 0.0

    recent_cohorts = []
    for reference_date in sorted(cohorts.keys(), reverse=True)[:8]:
        cohort = cohorts[reference_date]
        recent_cohorts.append(
            {
                "reference_date": reference_date,
                "capture_count": cohort["capture_count"],
                "evaluated_count": cohort["evaluated_count"],
                "pending_count": cohort["pending_count"],
                "direction_accuracy_1d": _ratio(cohort["direction_hits_1d"], cohort["direction_total_1d"]),
                "direction_accuracy_5d": _ratio(cohort["direction_hits_5d"], cohort["direction_total_5d"]),
                "direction_accuracy_20d": _ratio(cohort["direction_hits_20d"], cohort["direction_total_20d"]),
                "band_hit_rate_20d": _ratio(cohort["band_hits_20d"], cohort["band_total_20d"]),
                "avg_return_pct_20d": _avg(cohort["return_sum_20d"], cohort["return_count_20d"]),
                "top_symbols": cohort["top_symbols"],
            }
        )

    review_queue.sort(
        key=lambda item: (
            0 if item["kind"] in {"miss", "reversal-miss"} else 1 if item["kind"] == "direction-hit" else 2,
            item["rank"],
            item["reference_date"],
        )
    )

    tag_breakdown = [
        {"label": label, "count": count}
        for label, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
    ]

    return {
        "stored_snapshots": len(rows),
        "capture_days": len(reference_dates),
        "latest_reference_date": latest_reference_date,
        "last_evaluated_at": last_evaluated_at,
        "direction_accuracy_1d": _ratio(horizon_buckets["1d"]["hit"], horizon_buckets["1d"]["total"]),
        "direction_accuracy_5d": _ratio(horizon_buckets["5d"]["hit"], horizon_buckets["5d"]["total"]),
        "direction_accuracy_20d": _ratio(horizon_buckets["20d"]["hit"], horizon_buckets["20d"]["total"]),
        "band_hit_rate_20d": _ratio(band_hits_20d, band_total_20d),
        "avg_return_pct_5d": _avg(horizon_buckets["5d"]["return_sum"], horizon_buckets["5d"]["return_count"]),
        "avg_return_pct_20d": _avg(horizon_buckets["20d"]["return_sum"], horizon_buckets["20d"]["return_count"]),
        "pending_20d": pending_20d,
        "tag_breakdown": tag_breakdown,
        "recent_cohorts": recent_cohorts,
        "review_queue": review_queue[:8],
        "profile": get_profile_summary(),
    }
