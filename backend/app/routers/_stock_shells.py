"""stock detail 엔드포인트에서 사용하는 빈 스코어/지표 빌더와 JSON 정리 유틸리티."""

from __future__ import annotations

import math
from typing import Any


def blank_score_detail(max_score: float = 20.0) -> dict:
    return {
        "total": 0.0,
        "max_score": max_score,
        "items": [],
    }


def blank_stock_score() -> dict:
    return {
        "total": 0.0,
        "fundamental": blank_score_detail(),
        "valuation": blank_score_detail(),
        "growth_momentum": blank_score_detail(),
        "analyst": blank_score_detail(),
        "risk": blank_score_detail(),
    }


def blank_composite_score() -> dict:
    return {
        "total": 0.0,
        "total_raw": 0.0,
        "max_raw": 100.0,
        "fundamental": blank_score_detail(),
        "valuation": blank_score_detail(),
        "growth_momentum": blank_score_detail(),
        "analyst": blank_score_detail(),
        "risk": blank_score_detail(),
        "technical": blank_score_detail(),
    }


def blank_technical_indicators() -> dict:
    return {
        "ma_20": [],
        "ma_60": [],
        "rsi_14": [],
        "macd": [],
        "macd_signal": [],
        "macd_hist": [],
        "dates": [],
    }


def sanitize_json_value(value: Any) -> Any:
    """NaN/Infinity를 None으로, dict/list/tuple/set을 재귀 정리한다."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_json_value(item) for item in value]
    return value
