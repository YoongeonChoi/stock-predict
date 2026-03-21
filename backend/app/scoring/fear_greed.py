"""Fear & Greed Index composite calculation."""

import numpy as np
from app.models.forecast import FearGreedIndex, FearGreedComponent
from app.scoring.rubric import fear_greed_label


def calculate_fear_greed(
    index_prices: list[dict],
    vix_value: float | None = None,
    news_sentiment: float | None = None,
    treasury_spread: float | None = None,
    country_code: str = "US",
) -> FearGreedIndex:
    components = []

    # 1. Market Momentum: index vs 125-day MA
    momentum_score = _momentum(index_prices)
    components.append(FearGreedComponent(
        name="Market Momentum",
        value=round(momentum_score, 1),
        signal=_signal(momentum_score),
        weight=0.2,
    ))

    # 2. Price Strength: % from 52-week high
    strength_score = _price_strength(index_prices)
    components.append(FearGreedComponent(
        name="Price Strength",
        value=round(strength_score, 1),
        signal=_signal(strength_score),
        weight=0.2,
    ))

    # 3. Volatility (inverted: low vol = greed, high vol = fear)
    vol_score = _volatility_score(vix_value, index_prices)
    components.append(FearGreedComponent(
        name="Volatility",
        value=round(vol_score, 1),
        signal=_signal(vol_score),
        weight=0.2,
    ))

    # 4. Safe Haven Demand (bond spread based)
    haven_score = _safe_haven(treasury_spread)
    components.append(FearGreedComponent(
        name="Safe Haven Demand",
        value=round(haven_score, 1),
        signal=_signal(haven_score),
        weight=0.2,
    ))

    # 5. News Sentiment
    sent_score = _sentiment_score(news_sentiment)
    components.append(FearGreedComponent(
        name="News Sentiment",
        value=round(sent_score, 1),
        signal=_signal(sent_score),
        weight=0.2,
    ))

    total = sum(c.value * c.weight for c in components)
    total = max(0, min(100, round(total, 1)))

    return FearGreedIndex(
        score=total,
        label=fear_greed_label(total),
        components=components,
        country_code=country_code,
    )


def _momentum(prices: list[dict]) -> float:
    if len(prices) < 20:
        return 50
    closes = [p["close"] for p in prices]
    ma_len = min(125, len(closes))
    ma = np.mean(closes[-ma_len:])
    current = closes[-1]
    if ma == 0:
        return 50
    pct = (current - ma) / ma * 100
    return max(0, min(100, 50 + pct * 5))


def _price_strength(prices: list[dict]) -> float:
    if len(prices) < 20:
        return 50
    closes = [p["close"] for p in prices]
    high_252 = max(closes[-min(252, len(closes)):])
    low_252 = min(closes[-min(252, len(closes)):])
    current = closes[-1]
    if high_252 == low_252:
        return 50
    return max(0, min(100, (current - low_252) / (high_252 - low_252) * 100))


def _volatility_score(vix: float | None, prices: list[dict]) -> float:
    if vix is not None:
        if vix <= 12:
            return 90
        if vix <= 18:
            return 65
        if vix <= 25:
            return 40
        if vix <= 35:
            return 20
        return 5
    if len(prices) < 20:
        return 50
    closes = [p["close"] for p in prices]
    returns = np.diff(np.log(closes))
    vol = float(np.std(returns[-20:]) * np.sqrt(252) * 100)
    return max(0, min(100, 100 - vol * 3))


def _safe_haven(spread: float | None) -> float:
    if spread is None:
        return 50
    if spread > 1.0:
        return 70
    if spread > 0:
        return 55
    if spread > -0.5:
        return 40
    return 20


def _sentiment_score(sentiment: float | None) -> float:
    if sentiment is None:
        return 50
    return max(0, min(100, sentiment * 100))


def _signal(score: float) -> str:
    if score >= 60:
        return "Greed"
    if score <= 40:
        return "Fear"
    return "Neutral"
