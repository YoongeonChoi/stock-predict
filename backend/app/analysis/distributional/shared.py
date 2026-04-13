from __future__ import annotations

from datetime import datetime, timezone
from hashlib import blake2b
from math import exp

import numpy as np


def clip(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return float(max(low, min(high, value)))


def mean_available(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def parse_date(value: str | None) -> datetime | None:
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


def softmax(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    shifted = values - np.max(values)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values)


def sigmoid(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def stable_seed(text: str) -> int:
    return int(blake2b(text.encode("utf-8"), digest_size=8).hexdigest(), 16) % (2 ** 32)

