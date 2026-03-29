from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_close_series(price_history: Sequence[dict] | None) -> pd.Series:
    if not price_history:
        return pd.Series(dtype=float)
    values = [float(item.get("close") or 0.0) for item in price_history if item.get("close") is not None]
    return pd.Series(values, dtype=float)


def _window_return(close: pd.Series, window: int) -> float:
    if close.empty or len(close) <= window:
        return 0.0
    start = float(close.iloc[-window - 1])
    end = float(close.iloc[-1])
    if start <= 0:
        return 0.0
    return _clip((end / start) - 1.0, -1.0, 1.0)


def _return_series(close: pd.Series) -> pd.Series:
    if close.empty:
        return pd.Series(dtype=float)
    return close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()


@dataclass(slots=True)
class StockGraphContext:
    used: bool = False
    coverage: float = 0.0
    peer_count: int = 0
    peer_momentum_5d: float = 0.0
    peer_momentum_20d: float = 0.0
    peer_dispersion: float = 0.0
    sector_relative_strength: float = 0.0
    correlation_support: float = 0.0
    news_relation_support: float = 0.0
    graph_context_score: float = 0.0

    def to_dict(self) -> dict[str, float | int | bool]:
        payload = asdict(self)
        return {
            key: round(float(value), 6) if isinstance(value, float) else value
            for key, value in payload.items()
        }


def build_stock_graph_context(
    *,
    price_history: Sequence[dict] | None,
    benchmark_history: Sequence[dict] | None = None,
    analyst_context: Mapping[str, object] | None = None,
    fundamental_context: Mapping[str, object] | None = None,
    graph_seed: Mapping[str, object] | None = None,
) -> StockGraphContext:
    analyst_context = analyst_context or {}
    fundamental_context = fundamental_context or {}
    seed = (
        graph_seed
        or analyst_context.get("graph_context_seed")
        or fundamental_context.get("graph_context_seed")
        or {}
    )
    if not isinstance(seed, Mapping):
        seed = {}

    close = _to_close_series(price_history)
    benchmark_close = _to_close_series(benchmark_history)
    asset_return_20d = _window_return(close, 20)
    benchmark_return_20d = _window_return(benchmark_close, 20)

    peer_snapshots_raw = seed.get("peer_snapshots") or analyst_context.get("peer_snapshots") or []
    peer_snapshots = [item for item in peer_snapshots_raw if isinstance(item, Mapping)]
    peer_count = len(peer_snapshots)

    peer_momentum_5d = float(np.mean([float(item.get("return_5d") or 0.0) for item in peer_snapshots])) if peer_snapshots else 0.0
    peer_momentum_20d = float(np.mean([float(item.get("return_20d") or 0.0) for item in peer_snapshots])) if peer_snapshots else 0.0
    peer_dispersion = float(np.std([float(item.get("return_20d") or 0.0) for item in peer_snapshots], ddof=0)) if len(peer_snapshots) >= 2 else 0.0

    asset_returns = _return_series(close)
    peer_correlations: list[float] = []
    for snapshot in peer_snapshots:
        peer_returns = snapshot.get("return_series")
        if not isinstance(peer_returns, Sequence):
            continue
        peer_series = pd.Series([float(value) for value in peer_returns], dtype=float)
        if len(asset_returns) < 10 or len(peer_series) < 10:
            continue
        aligned = min(len(asset_returns), len(peer_series))
        corr = asset_returns.iloc[-aligned:].corr(peer_series.iloc[-aligned:])
        if pd.notna(corr):
            peer_correlations.append(abs(float(corr)))
    correlation_support = float(np.mean(peer_correlations)) if peer_correlations else 0.0

    news_relation_support = float(seed.get("news_relation_support") or 0.0)
    if not news_relation_support:
        sector = str(fundamental_context.get("sector") or "").strip()
        industry = str(fundamental_context.get("industry") or "").strip()
        if sector or industry:
            news_relation_support = 0.18 + min(peer_count, 5) * 0.06
    news_relation_support = _clip(news_relation_support, 0.0, 1.0)

    sector_relative_strength = _clip(peer_momentum_20d - benchmark_return_20d, -1.0, 1.0)
    used = bool(peer_count or fundamental_context.get("sector") or fundamental_context.get("industry") or peer_correlations)
    if not used:
        return StockGraphContext()

    coverage = _clip(
        min(peer_count, 5) / 5.0 * 0.55
        + _clip(correlation_support, 0.0, 1.0) * 0.25
        + news_relation_support * 0.20,
        0.0,
        1.0,
    )
    graph_context_score = _clip(
        peer_momentum_5d * 0.35
        + peer_momentum_20d * 0.45
        + sector_relative_strength * 0.35
        - peer_dispersion * 0.25
        + correlation_support * 0.12
        + news_relation_support * 0.08,
        -1.0,
        1.0,
    )
    return StockGraphContext(
        used=True,
        coverage=coverage,
        peer_count=peer_count,
        peer_momentum_5d=peer_momentum_5d,
        peer_momentum_20d=peer_momentum_20d,
        peer_dispersion=peer_dispersion,
        sector_relative_strength=sector_relative_strength,
        correlation_support=correlation_support,
        news_relation_support=news_relation_support,
        graph_context_score=graph_context_score,
    )
