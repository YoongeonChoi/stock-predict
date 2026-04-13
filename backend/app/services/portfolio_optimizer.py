from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from app.analysis.distributional_return_engine import DistributionalForecast
from app.data import yfinance_client
from app.utils.async_tools import gather_limited
from app.utils.market_calendar import trading_days_forward


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_horizon_snapshot(
    forecast: DistributionalForecast | None,
    *,
    horizon_days: int,
    country_code: str | None = None,
    reference_date: str | None = None,
) -> dict[str, float | str | None]:
    """DistributionalForecast에서 특정 horizon의 요약 dict를 추출한다.

    Returns:
        dict -- mean_return, excess_return, vol, p_up/p_flat/p_down, confidence 등.
        forecast가 None이거나 해당 horizon이 없으면 빈 dict.
    """
    if not forecast:
        return {}

    horizon = forecast.horizons.get(horizon_days)
    if not horizon:
        return {}

    target_date = None
    if country_code:
        try:
            target_days = trading_days_forward(country_code, reference_date or forecast.reference_date, horizon_days)
            if target_days:
                target_date = target_days[-1].isoformat()
        except Exception:
            target_date = None

    reference_price = float(forecast.reference_price or 0.0)

    def _price(log_return: float) -> float | None:
        if reference_price <= 0:
            return None
        return round(reference_price * math.exp(float(log_return)), 2)

    return {
        "target_date": target_date,
        "expected_return_pct": round(float(horizon.mean_return_raw) * 100.0, 2),
        "expected_excess_return_pct": round(float(horizon.mean_return_excess) * 100.0, 2),
        "median_return_pct": round(float(horizon.q50) * 100.0, 2),
        "forecast_volatility_pct": round(float(horizon.vol_forecast) * 100.0, 2),
        "up_probability": round(float(horizon.p_up), 2),
        "flat_probability": round(float(horizon.p_flat), 2),
        "down_probability": round(float(horizon.p_down), 2),
        "confidence": round(float(horizon.confidence), 1),
        "raw_confidence": round(float(horizon.raw_confidence), 1) if horizon.raw_confidence is not None else None,
        "calibrated_probability": round(float(horizon.calibrated_probability), 4) if horizon.calibrated_probability is not None else None,
        "probability_edge": round(float(horizon.probability_edge), 4) if horizon.probability_edge is not None else None,
        "analog_support": round(float(horizon.analog_support), 4) if horizon.analog_support is not None else None,
        "regime_support": round(float(horizon.regime_support), 4) if horizon.regime_support is not None else None,
        "agreement_support": round(float(horizon.agreement_support), 4) if horizon.agreement_support is not None else None,
        "data_quality_support": round(float(horizon.data_quality_support), 4) if horizon.data_quality_support is not None else None,
        "volatility_ratio": round(float(horizon.volatility_ratio), 4) if horizon.volatility_ratio is not None else None,
        "confidence_calibrator": horizon.confidence_calibrator,
        "price_q25": _price(horizon.q25),
        "price_q50": _price(horizon.q50),
        "price_q75": _price(horizon.q75),
    }


async def attach_candidate_return_series(
    candidates: list[dict],
    *,
    period: str = "6mo",
    limit: int = 4,
) -> list[dict]:
    """후보 종목에 일별 수익률 시계열을 비동기로 로드해 공분산 계산에 필요한 입력을 붙인다.

    Args:
        candidates: ticker, country_code를 포함하는 후보 dict 리스트.
        period: yfinance history 조회 기간 (기본 6개월).
        limit: 동시 요청 수 상한 (Render 500MB 메모리 보호).
    """
    if not candidates:
        return candidates

    async def _load(candidate: dict) -> tuple[str, list[tuple[str, float]]]:
        existing = candidate.get("return_series")
        if existing:
            return str(candidate.get("key") or ""), list(existing)

        ticker = str(candidate.get("ticker") or "").strip()
        if not ticker:
            return str(candidate.get("key") or ""), []

        history = await yfinance_client.get_price_history(ticker, period=period)
        returns: list[tuple[str, float]] = []
        for prev, curr in zip(history, history[1:]):
            prev_close = float(prev.get("close") or 0.0)
            curr_close = float(curr.get("close") or 0.0)
            if prev_close <= 0:
                continue
            returns.append((str(curr.get("date")), curr_close / prev_close - 1.0))
        return str(candidate.get("key") or ""), returns

    loaded = await gather_limited(candidates, _load, limit=limit)
    by_key = {
        key: series
        for item in loaded
        if not isinstance(item, Exception)
        for key, series in [item]
    }

    for candidate in candidates:
        key = str(candidate.get("key") or "")
        if key and key in by_key:
            candidate["return_series"] = by_key[key]
    return candidates


@dataclass
class PortfolioOptimizationResult:
    target_weights: dict[str, float]
    actual_equity_pct: float
    turnover_pct: float
    expected_return_pct_20d: float
    expected_excess_return_pct_20d: float
    forecast_volatility_pct_20d: float
    up_probability_20d: float
    down_probability_20d: float
    active_count: int


def _style_parameters(style: str) -> tuple[float, float]:
    if style == "defensive":
        return 7.8, 0.009
    if style == "offensive":
        return 4.6, 0.004
    return 6.0, 0.006


def _group_indices(values: list[str]) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, value in enumerate(values):
        grouped[str(value or "Other")].append(index)
    return grouped


def _project_weights(
    weights: np.ndarray,
    *,
    target_equity: float,
    single_cap: float,
    country_groups: dict[str, list[int]],
    country_cap: float,
    sector_groups: dict[str, list[int]],
    sector_cap: float,
) -> np.ndarray:
    projected = np.clip(weights.astype(float), 0.0, single_cap)
    for _ in range(8):
        changed = False
        for indices in country_groups.values():
            total = float(projected[indices].sum())
            if total > country_cap + 1e-9:
                projected[indices] *= country_cap / total
                changed = True
        for indices in sector_groups.values():
            total = float(projected[indices].sum())
            if total > sector_cap + 1e-9:
                projected[indices] *= sector_cap / total
                changed = True
        total_weight = float(projected.sum())
        if total_weight > target_equity + 1e-9:
            projected *= target_equity / total_weight
            changed = True
        projected = np.clip(projected, 0.0, single_cap)
        if not changed:
            break
    return projected


def _build_return_matrix(candidates: list[dict], lookback: int = 90) -> tuple[np.ndarray, np.ndarray]:
    series_maps: list[dict[str, float]] = []
    all_dates: set[str] = set()

    for candidate in candidates:
        mapping = {
            str(date): float(value)
            for date, value in list(candidate.get("return_series") or [])[-lookback:]
        }
        series_maps.append(mapping)
        all_dates.update(mapping.keys())

    if not all_dates:
        return np.empty((0, len(candidates))), np.zeros(len(candidates), dtype=float)

    ordered_dates = sorted(all_dates)[-lookback:]
    matrix = np.zeros((len(ordered_dates), len(candidates)), dtype=float)
    missing = np.zeros(len(candidates), dtype=float)

    for column, mapping in enumerate(series_maps):
        if not mapping:
            missing[column] = 1.0
            continue
        missing_count = 0
        for row, date in enumerate(ordered_dates):
            if date in mapping:
                matrix[row, column] = mapping[date]
            else:
                missing_count += 1
        missing[column] = missing_count / max(len(ordered_dates), 1)

    return matrix, missing


def _ewma_shrinkage_covariance(candidates: list[dict], horizon_days: int = 20) -> np.ndarray:
    matrix, missing = _build_return_matrix(candidates)
    count = len(candidates)
    daily_fallback = np.array([
        max(float(candidate.get("forecast_volatility_pct_20d") or 0.0) / 100.0 / math.sqrt(max(horizon_days, 1)), 0.008)
        for candidate in candidates
    ], dtype=float)

    if matrix.shape[0] < 5:
        return np.diag(np.square(daily_fallback * math.sqrt(horizon_days)))

    decay = 0.94
    weights = np.array([decay ** (matrix.shape[0] - row - 1) for row in range(matrix.shape[0])], dtype=float)
    weights /= weights.sum()
    mean = np.average(matrix, axis=0, weights=weights)
    centered = matrix - mean
    ewma_cov = np.zeros((count, count), dtype=float)
    for weight, row in zip(weights, centered):
        ewma_cov += weight * np.outer(row, row)

    diag = np.diag(np.diag(ewma_cov))
    shrinkage = _clip(0.22 + float(missing.mean()) * 0.35, 0.22, 0.68)
    cov_daily = (1.0 - shrinkage) * ewma_cov + shrinkage * diag

    for index, fallback_vol in enumerate(daily_fallback):
        variance_floor = max(float(cov_daily[index, index]), fallback_vol ** 2)
        cov_daily[index, index] = variance_floor

    cov_horizon = cov_daily * horizon_days
    cov_horizon += np.eye(count, dtype=float) * 1e-7
    return cov_horizon


def _seed_weights(
    *,
    target_equity: float,
    current_weights: np.ndarray,
    expected_excess: np.ndarray,
    expected_total: np.ndarray,
    up_probability: np.ndarray,
    down_probability: np.ndarray,
    model_scores: np.ndarray,
    single_cap: float,
    country_groups: dict[str, list[int]],
    country_cap: float,
    sector_groups: dict[str, list[int]],
    sector_cap: float,
) -> np.ndarray:
    if float(current_weights.sum()) > 0.0:
        seed = current_weights.copy()
    else:
        alpha = (
            np.maximum(expected_excess, -0.002)
            + np.maximum(expected_total, 0.0) * 0.55
            + np.maximum((up_probability - down_probability) / 100.0, 0.0) * 0.04
            + np.maximum(model_scores - 55.0, 0.0) / 5200.0
        )
        alpha = np.maximum(alpha, 0.0)
        if float(alpha.sum()) <= 1e-9:
            alpha = np.maximum(model_scores, 1.0)
        seed = target_equity * alpha / float(alpha.sum())

    return _project_weights(
        seed,
        target_equity=target_equity,
        single_cap=single_cap,
        country_groups=country_groups,
        country_cap=country_cap,
        sector_groups=sector_groups,
        sector_cap=sector_cap,
    )


def _fill_weights(
    weights: np.ndarray,
    *,
    target_equity: float,
    single_cap: float,
    country_groups: dict[str, list[int]],
    country_cap: float,
    sector_groups: dict[str, list[int]],
    sector_cap: float,
    fill_priority: np.ndarray,
    step: float = 0.0025,
) -> np.ndarray:
    ordered = list(np.argsort(fill_priority)[::-1])
    for _ in range(400):
        remaining = target_equity - float(weights.sum())
        if remaining <= 0.001:
            break
        progressed = False
        for index in ordered:
            if fill_priority[index] <= 0.0:
                continue
            trial = weights.copy()
            trial[index] += min(step, remaining)
            trial = _project_weights(
                trial,
                target_equity=target_equity,
                single_cap=single_cap,
                country_groups=country_groups,
                country_cap=country_cap,
                sector_groups=sector_groups,
                sector_cap=sector_cap,
            )
            if float(trial.sum()) > float(weights.sum()) + 1e-8:
                weights = trial
                progressed = True
        if not progressed:
            break
    return weights


def optimize_portfolio_weights(candidates: list[dict], budget: dict) -> PortfolioOptimizationResult:
    """기대수익 최대화 - 리스크 패널티 - 회전율 패널티 목적함수로 포트폴리오 비중을 최적화한다.

    EWMA+shrinkage 공분산, single/country/sector cap, 투영 반복 GD로 해를 구한다.
    candidates가 비어 있으면 빈 결과를 반환한다.
    """
    if not candidates:
        return PortfolioOptimizationResult(
            target_weights={},
            actual_equity_pct=0.0,
            turnover_pct=0.0,
            expected_return_pct_20d=0.0,
            expected_excess_return_pct_20d=0.0,
            forecast_volatility_pct_20d=0.0,
            up_probability_20d=0.0,
            down_probability_20d=0.0,
            active_count=0,
        )

    target_equity = max(float(budget.get("recommended_equity_pct") or 0.0) / 100.0, 0.0)
    single_cap = max(float(budget.get("max_single_weight_pct") or 0.0) / 100.0, 0.0)
    country_cap = max(float(budget.get("max_country_weight_pct") or 0.0) / 100.0, 0.0)
    sector_cap = max(float(budget.get("max_sector_weight_pct") or 0.0) / 100.0, 0.0)
    style = str(budget.get("style") or "balanced")
    risk_aversion, turnover_penalty = _style_parameters(style)

    model_scores = np.array([float(candidate.get("model_score") or 0.0) for candidate in candidates], dtype=float)
    expected_total = np.array([float(candidate.get("expected_return_pct_20d") or candidate.get("predicted_return_pct") or 0.0) / 100.0 for candidate in candidates], dtype=float)
    expected_excess = np.array([float(candidate.get("expected_excess_return_pct_20d") or 0.0) / 100.0 for candidate in candidates], dtype=float)
    up_probability = np.array([float(candidate.get("up_probability_20d") or candidate.get("up_probability") or 50.0) for candidate in candidates], dtype=float)
    down_probability = np.array([
        float(candidate.get("down_probability_20d") or candidate.get("bear_probability") or max(100.0 - float(candidate.get("up_probability") or 50.0), 0.0))
        for candidate in candidates
    ], dtype=float)
    current_weights = np.array([max(float(candidate.get("current_weight_pct") or 0.0), 0.0) / 100.0 for candidate in candidates], dtype=float)
    country_groups = _group_indices([str(candidate.get("country_code") or "KR") for candidate in candidates])
    sector_groups = _group_indices([str(candidate.get("sector") or "Other") for candidate in candidates])
    covariance = _ewma_shrinkage_covariance(candidates)

    objective_mean = expected_excess + expected_total * 0.35
    weights = _seed_weights(
        target_equity=target_equity,
        current_weights=current_weights,
        expected_excess=expected_excess,
        expected_total=expected_total,
        up_probability=up_probability,
        down_probability=down_probability,
        model_scores=model_scores,
        single_cap=single_cap,
        country_groups=country_groups,
        country_cap=country_cap,
        sector_groups=sector_groups,
        sector_cap=sector_cap,
    )

    def _objective(candidate_weights: np.ndarray) -> float:
        mean_term = float(objective_mean @ candidate_weights)
        risk_term = float(candidate_weights @ covariance @ candidate_weights)
        turnover_term = float(np.abs(candidate_weights - current_weights).sum())
        return mean_term - risk_aversion * risk_term - turnover_penalty * turnover_term

    learning_rate = 0.85
    best_weights = weights.copy()
    best_score = _objective(weights)
    for _ in range(140):
        gradient = objective_mean - 2.0 * risk_aversion * (covariance @ weights) - turnover_penalty * np.sign(weights - current_weights)
        gradient += np.maximum(model_scores - 55.0, 0.0) / 12000.0
        trial = _project_weights(
            weights + learning_rate * gradient,
            target_equity=target_equity,
            single_cap=single_cap,
            country_groups=country_groups,
            country_cap=country_cap,
            sector_groups=sector_groups,
            sector_cap=sector_cap,
        )
        score = _objective(trial)
        if score >= best_score - 1e-9:
            weights = trial
            if score > best_score:
                best_score = score
                best_weights = trial.copy()
        else:
            learning_rate *= 0.65
            if learning_rate < 0.03:
                break

    weights = best_weights
    min_active_weight = 0.01
    tiny_positions = np.where((weights > 0.0) & (weights < min_active_weight))[0]
    if tiny_positions.size:
        weights[tiny_positions] = 0.0
        weights = _project_weights(
            weights,
            target_equity=target_equity,
            single_cap=single_cap,
            country_groups=country_groups,
            country_cap=country_cap,
            sector_groups=sector_groups,
            sector_cap=sector_cap,
        )

    fill_priority = (
        objective_mean
        + np.maximum(model_scores - 50.0, 0.0) / 18000.0
        - np.diag(covariance) * (risk_aversion * 0.6)
    )
    weights = _fill_weights(
        weights,
        target_equity=target_equity,
        single_cap=single_cap,
        country_groups=country_groups,
        country_cap=country_cap,
        sector_groups=sector_groups,
        sector_cap=sector_cap,
        fill_priority=fill_priority,
    )

    actual_equity = float(weights.sum())
    active_mask = weights >= min_active_weight
    invested = float(weights[active_mask].sum()) if np.any(active_mask) else 0.0
    if invested > 0.0:
        norm_weights = weights / invested
        expected_return_pct = float(norm_weights @ (expected_total * 100.0))
        expected_excess_pct = float(norm_weights @ (expected_excess * 100.0))
        up_probability_pct = float(norm_weights @ up_probability)
        down_probability_pct = float(norm_weights @ down_probability)
        volatility_pct = math.sqrt(max(float(norm_weights @ covariance @ norm_weights), 0.0)) * 100.0
    else:
        expected_return_pct = 0.0
        expected_excess_pct = 0.0
        up_probability_pct = 0.0
        down_probability_pct = 0.0
        volatility_pct = 0.0

    return PortfolioOptimizationResult(
        target_weights={
            str(candidate.get("key") or index): round(float(weight) * 100.0, 2)
            for index, (candidate, weight) in enumerate(zip(candidates, weights))
        },
        actual_equity_pct=round(actual_equity * 100.0, 2),
        turnover_pct=round(float(np.abs(weights - current_weights).sum()) * 100.0, 2),
        expected_return_pct_20d=round(expected_return_pct, 2),
        expected_excess_return_pct_20d=round(expected_excess_pct, 2),
        forecast_volatility_pct_20d=round(volatility_pct, 2),
        up_probability_20d=round(up_probability_pct, 2),
        down_probability_20d=round(down_probability_pct, 2),
        active_count=int(np.count_nonzero(active_mask)),
    )
