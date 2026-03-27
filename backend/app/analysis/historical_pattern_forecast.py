"""Historical analog forecast and setup backtest from price history."""

from __future__ import annotations

from math import exp, sqrt

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange

from app.models.forecast import (
    HistoricalAnalogCase,
    HistoricalForecastHorizon,
    HistoricalPathPoint,
    HistoricalPatternForecast,
    SetupBacktest,
)
from app.scoring.confidence import analog_support_score, effective_sample_size
from app.utils.market_calendar import trading_days_forward

MODEL_VERSION = "analog-v1.1"
FEATURE_COLUMNS = [
    "momentum_5",
    "momentum_20",
    "momentum_60",
    "rsi_14",
    "stretch_20",
    "trend_stack",
    "volatility_20",
    "atr_pct",
    "volume_z",
    "breakout_gap",
    "relative_strength_20",
]
FEATURE_WEIGHTS = np.array([1.1, 1.3, 1.0, 0.9, 0.8, 1.1, 0.85, 0.75, 0.55, 0.8, 0.95])
HORIZONS = (5, 20, 60)
LOOKBACK_BARS = 504
MIN_HISTORY_BARS = 220
MAX_ANALOGS = 24


def _clip(value: float, floor: float, ceiling: float) -> float:
    return max(floor, min(ceiling, value))


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    if len(values) == 0:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    threshold = cumulative[-1] * quantile
    index = int(np.searchsorted(cumulative, threshold, side="left"))
    index = max(0, min(index, len(values) - 1))
    return float(values[index])


def _setup_label(latest: pd.Series) -> str:
    momentum_20 = float(latest["momentum_20"])
    momentum_60 = float(latest["momentum_60"])
    rsi = float(latest["rsi_14"])
    stretch = float(latest["stretch_20"])
    trend_stack = float(latest["trend_stack"])
    breakout_gap = float(latest["breakout_gap"])
    rel_strength = float(latest["relative_strength_20"])

    if momentum_20 >= 6 and trend_stack > 1.0 and rel_strength >= 0:
        return "상승 추세 지속형"
    if rsi <= 35 and stretch <= -3:
        return "과매도 반등형"
    if rsi >= 68 and stretch >= 4:
        return "과열 조정 경계형"
    if abs(breakout_gap) <= 1.4 and abs(momentum_20) <= 3:
        return "박스권 돌파 대기형"
    if momentum_20 < 0 and momentum_60 < 0 and trend_stack < 0:
        return "하락 추세 방어형"
    return "중립 추세 전환형"


def _build_summary(
    ticker: str,
    setup_label: str,
    horizons: list[HistoricalForecastHorizon],
    sample_size: int,
) -> str:
    if not horizons:
        return f"{ticker}는 장기 히스토리가 부족해 과거 유사 국면 예측을 생성하지 못했습니다."

    short_term = next((item for item in horizons if item.horizon_days == 20), horizons[0])
    direction = "우세합니다" if short_term.expected_return_pct >= 0 else "조정 가능성이 큽니다"
    return (
        f"현재 셋업은 '{setup_label}'로 분류됐고, 최근 2년 중 유사 국면 {sample_size}건을 기준으로 "
        f"{short_term.horizon_days}거래일 기대 수익률 {short_term.expected_return_pct:.2f}%와 "
        f"상승 확률 {short_term.up_probability:.1f}%가 계산됐습니다. "
        f"과거 기준으로는 단기적으로 {'상승' if short_term.expected_return_pct >= 0 else '하락'} 방향이 {direction}."
    )


def _build_feature_frame(
    price_history: list[dict],
    market_history: list[dict] | None = None,
) -> pd.DataFrame:
    df = pd.DataFrame(price_history).copy()
    if df.empty:
        return df

    df = df.sort_values("date").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]
    daily_return = close.pct_change()

    ma20 = SMAIndicator(close, window=20).sma_indicator()
    ma60 = SMAIndicator(close, window=60).sma_indicator()
    rolling_high_60 = high.rolling(60).max()
    rolling_volume_mean = volume.rolling(20).mean()
    rolling_volume_std = volume.rolling(20).std()

    df["momentum_5"] = close.pct_change(5) * 100.0
    df["momentum_20"] = close.pct_change(20) * 100.0
    df["momentum_60"] = close.pct_change(60) * 100.0
    df["rsi_14"] = RSIIndicator(close, window=14).rsi()
    df["stretch_20"] = (close / ma20 - 1.0) * 100.0
    df["trend_stack"] = (ma20 / ma60 - 1.0) * 100.0
    df["volatility_20"] = daily_return.rolling(20).std() * sqrt(252) * 100.0
    df["atr_pct"] = (
        AverageTrueRange(high, low, close, window=14).average_true_range() / close
    ) * 100.0
    df["volume_z"] = (volume - rolling_volume_mean) / rolling_volume_std.replace(0, np.nan)
    df["breakout_gap"] = (close / rolling_high_60 - 1.0) * 100.0
    df["max_drawdown_20"] = (
        close.shift(-20).rolling(20).min() / close - 1.0
    ) * 100.0
    df["future_vol_20"] = daily_return.shift(-1).rolling(20).std() * sqrt(252) * 100.0

    for horizon in HORIZONS:
        df[f"forward_return_{horizon}"] = (close.shift(-horizon) / close - 1.0) * 100.0

    if market_history:
        market_df = pd.DataFrame(market_history).copy()
        if not market_df.empty:
            market_df["date"] = market_df["date"].astype(str)
            market_df["market_close"] = pd.to_numeric(market_df["close"], errors="coerce")
            market_df["market_momentum_20"] = market_df["market_close"].pct_change(20) * 100.0
            market_df = market_df[["date", "market_momentum_20"]]
            df["date"] = df["date"].astype(str)
            df = df.merge(market_df, on="date", how="left")
            df["relative_strength_20"] = df["momentum_20"] - df["market_momentum_20"].fillna(0.0)
        else:
            df["relative_strength_20"] = 0.0
    else:
        df["relative_strength_20"] = 0.0

    return df


def _select_analogs(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series] | tuple[None, None]:
    if len(df) < MIN_HISTORY_BARS:
        return None, None

    min_start = 130
    max_horizon = max(HORIZONS)
    max_index = len(df) - max_horizon - 1
    if max_index <= min_start:
        return None, None

    candidates = df.iloc[min_start:max_index + 1].copy()
    candidates = candidates.dropna(subset=FEATURE_COLUMNS + [f"forward_return_{h}" for h in HORIZONS])
    if len(candidates) < 12:
        return None, None

    latest = df.iloc[-1]
    if latest[FEATURE_COLUMNS].isna().any():
        return None, None

    reference_start = max(0, len(df) - LOOKBACK_BARS)
    candidates = candidates[candidates.index >= reference_start]
    if len(candidates) < 12:
        return None, None

    current_features = latest[FEATURE_COLUMNS].astype(float)
    feature_matrix = candidates[FEATURE_COLUMNS].astype(float)
    means = feature_matrix.mean()
    scales = feature_matrix.std().replace(0, 1.0).fillna(1.0)
    current_norm = (current_features - means) / scales
    candidate_norm = (feature_matrix - means) / scales

    distances = np.sqrt(((candidate_norm - current_norm) ** 2 * FEATURE_WEIGHTS).sum(axis=1))
    similarities = np.exp(-distances * 0.7)

    ranked = candidates.assign(distance=distances.values, similarity=similarities.values)
    ranked = ranked.sort_values(["distance", "date"]).head(MAX_ANALOGS).copy()
    if ranked.empty:
        return None, None

    ranked["weight"] = ranked["similarity"] / ranked["similarity"].sum()
    return ranked, latest


def _path_distribution(
    full_df: pd.DataFrame,
    analogs: pd.DataFrame,
    current_price: float,
    country_code: str,
    reference_date: str,
) -> list[HistoricalPathPoint]:
    trading_days = trading_days_forward(country_code, reference_date, max(HORIZONS))
    path_returns: list[np.ndarray] = []
    weights: list[float] = []

    for _, row in analogs.iterrows():
        start_idx = int(row.name)
        close_slice = full_df["close"].iloc[start_idx : start_idx + max(HORIZONS) + 1].to_numpy(dtype=float)
        if len(close_slice) < max(HORIZONS) + 1:
            continue
        path = (close_slice[1:] / close_slice[0] - 1.0) * 100.0
        path_returns.append(path)
        weights.append(float(row["weight"]))

    if not path_returns:
        return []

    matrix = np.vstack(path_returns)
    weights_array = np.array(weights, dtype=float)
    points: list[HistoricalPathPoint] = []
    for offset in range(1, max(HORIZONS) + 1):
        returns = matrix[:, offset - 1]
        expected = float(np.average(returns, weights=weights_array))
        low = _weighted_quantile(returns, weights_array, 0.2)
        high = _weighted_quantile(returns, weights_array, 0.8)
        points.append(
            HistoricalPathPoint(
                offset=offset,
                target_date=trading_days[offset - 1].isoformat(),
                expected_price=round(current_price * (1.0 + expected / 100.0), 2),
                band_low=round(current_price * (1.0 + low / 100.0), 2),
                band_high=round(current_price * (1.0 + high / 100.0), 2),
            )
        )
    return points


def build_historical_pattern_forecast(
    *,
    ticker: str,
    name: str,
    country_code: str,
    price_history: list[dict],
    market_history: list[dict] | None = None,
) -> tuple[HistoricalPatternForecast | None, SetupBacktest | None]:
    df = _build_feature_frame(price_history, market_history=market_history)
    analogs, latest = _select_analogs(df)
    if analogs is None or latest is None:
        return None, None

    current_price = float(latest["close"])
    reference_date = str(latest["date"])
    weights = analogs["weight"].to_numpy(dtype=float)
    setup_label = _setup_label(latest)

    horizons: list[HistoricalForecastHorizon] = []
    for horizon in HORIZONS:
        forward_returns = analogs[f"forward_return_{horizon}"].to_numpy(dtype=float)
        expected_return = float(np.average(forward_returns, weights=weights))
        median_return = _weighted_quantile(forward_returns, weights, 0.5)
        low_band = _weighted_quantile(forward_returns, weights, 0.2)
        high_band = _weighted_quantile(forward_returns, weights, 0.8)
        up_probability = float(np.average((forward_returns > 0).astype(float), weights=weights) * 100.0)
        drawdowns = []
        realized_vols = []

        for _, row in analogs.iterrows():
            start_idx = int(row.name)
            closes = df["close"].iloc[start_idx : start_idx + horizon + 1].to_numpy(dtype=float)
            if len(closes) < horizon + 1:
                continue
            path_returns = (closes[1:] / closes[0] - 1.0) * 100.0
            drawdowns.append(float(path_returns.min()))
            realized_vols.append(float(np.std(np.diff(np.log(closes))) * sqrt(252) * 100.0))

        avg_drawdown = float(np.average(drawdowns, weights=weights[: len(drawdowns)])) if drawdowns else 0.0
        avg_vol = float(np.average(realized_vols, weights=weights[: len(realized_vols)])) if realized_vols else 0.0
        dispersion = float(np.sqrt(np.average((forward_returns - expected_return) ** 2, weights=weights)))
        weighted_win_rate = float(np.average((forward_returns > 0).astype(float), weights=weights) * 100.0)
        ess = float(effective_sample_size(weights.tolist()))
        gains = np.clip(forward_returns, 0.0, None)
        losses = np.clip(-forward_returns, 0.0, None)
        weighted_gain = float(np.average(gains, weights=weights)) if np.any(gains > 0) else 0.0
        weighted_loss = float(np.average(losses, weights=weights)) if np.any(losses > 0) else 0.0
        profit_factor = float(weighted_gain / weighted_loss) if weighted_loss > 1e-6 else (2.5 if weighted_gain > 0 else 1.0)
        analog_support = analog_support_score(
            win_rate_pct=weighted_win_rate,
            ess=ess,
            profit_factor=profit_factor,
            dispersion_pct=dispersion,
            reference_volatility_pct=max(avg_vol, 1.0),
        )
        confidence = _clip(36.0 + analog_support * 52.0, 36.0, 88.0)

        horizons.append(
            HistoricalForecastHorizon(
                horizon_days=horizon,
                sample_size=len(analogs),
                up_probability=round(up_probability, 2),
                expected_return_pct=round(expected_return, 2),
                median_return_pct=round(median_return, 2),
                predicted_price=round(current_price * (1.0 + expected_return / 100.0), 2),
                range_low=round(current_price * (1.0 + low_band / 100.0), 2),
                range_high=round(current_price * (1.0 + high_band / 100.0), 2),
                realized_volatility_pct=round(avg_vol, 2),
                avg_max_drawdown_pct=round(avg_drawdown, 2),
                confidence=round(confidence, 2),
                analog_support=round(analog_support, 4),
                effective_sample_size=round(ess, 2),
                profit_factor=round(profit_factor, 3),
            )
        )

    analog_cases = []
    for _, row in analogs.head(5).iterrows():
        analog_cases.append(
            HistoricalAnalogCase(
                date=str(row["date"]),
                similarity=round(float(row["similarity"]), 3),
                return_5d=round(float(row["forward_return_5"]), 2),
                return_20d=round(float(row["forward_return_20"]), 2),
                return_60d=round(float(row["forward_return_60"]), 2),
            )
        )

    projected_path = _path_distribution(
        df,
        analogs,
        current_price=current_price,
        country_code=country_code,
        reference_date=reference_date,
    )

    backtest_horizon = next((item for item in horizons if item.horizon_days == 20), horizons[0])
    returns_20 = analogs["forward_return_20"].to_numpy(dtype=float)
    profits = returns_20[returns_20 > 0]
    losses = returns_20[returns_20 < 0]
    profit_factor = None
    if len(losses) > 0:
        profit_factor = float(profits.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else None

    setup_backtest = SetupBacktest(
        setup_label=setup_label,
        forward_horizon_days=backtest_horizon.horizon_days,
        sample_size=len(analogs),
        win_rate=round(float(np.average((returns_20 > 0).astype(float), weights=weights) * 100.0), 2),
        avg_return_pct=round(float(np.average(returns_20, weights=weights)), 2),
        median_return_pct=round(_weighted_quantile(returns_20, weights, 0.5), 2),
        avg_max_drawdown_pct=round(backtest_horizon.avg_max_drawdown_pct, 2),
        best_return_pct=round(float(np.max(returns_20)), 2),
        worst_return_pct=round(float(np.min(returns_20)), 2),
        profit_factor=round(profit_factor, 2) if profit_factor is not None else None,
        confidence=round(backtest_horizon.confidence, 2),
        summary=(
            f"현재와 비슷한 '{setup_label}' 셋업 {len(analogs)}건을 20거래일 기준으로 되돌려보면 "
            f"승률 {float(np.average((returns_20 > 0).astype(float), weights=weights) * 100.0):.1f}%, "
            f"평균 수익 {float(np.average(returns_20, weights=weights)):.2f}%, "
            f"평균 최대 낙폭 {backtest_horizon.avg_max_drawdown_pct:.2f}%였습니다."
        ),
    )

    forecast = HistoricalPatternForecast(
        reference_date=reference_date,
        reference_price=round(current_price, 2),
        lookback_window_days=LOOKBACK_BARS,
        analog_count=len(analogs),
        feature_regime=setup_label,
        summary=_build_summary(ticker, setup_label, horizons, len(analogs)),
        horizons=horizons,
        analog_cases=analog_cases,
        projected_path=projected_path,
        model_version=MODEL_VERSION,
    )
    return forecast, setup_backtest
