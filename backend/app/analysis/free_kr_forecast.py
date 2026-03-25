"""Free-data KR probabilistic forecast engine kept parallel to the heuristic engine."""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, sqrt

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator

from app.config import get_settings
from app.models.forecast import (
    FlowSignal,
    FreeKrForecast,
    FreeKrForecastDataSource,
    FreeKrForecastEvidence,
    FreeKrForecastHorizon,
)
from app.utils.market_calendar import trading_days_forward

MODEL_VERSION = "kr-free-prob-v0.1"
HORIZONS = (1, 5, 20)

POSITIVE_NEWS_KEYWORDS = {
    "수주", "계약", "증가", "확대", "상승", "반등", "개선", "흑자", "호조", "성장",
    "surge", "beat", "upgrade", "strong", "growth", "contract", "buyback",
}
NEGATIVE_NEWS_KEYWORDS = {
    "감소", "부진", "하락", "경고", "적자", "유증", "소송", "리콜", "중단", "약세",
    "miss", "downgrade", "warning", "lawsuit", "delay", "cut", "selloff",
}
POSITIVE_FILING_KEYWORDS = {
    "단일판매", "공급계약", "자기주식", "실적", "배당", "투자판단", "신규시설", "영업이익",
}
NEGATIVE_FILING_KEYWORDS = {
    "유상증자", "전환사채", "신주인수권", "감자", "횡령", "배임", "영업정지", "불성실",
}


@dataclass
class _Signal:
    key: str
    label: str
    score: float
    detail: str


def build_free_kr_forecast(
    *,
    ticker: str,
    name: str,
    price_history: list[dict],
    market_history: list[dict],
    google_news: list[dict] | None = None,
    naver_news: list[dict] | None = None,
    filings: list[dict] | None = None,
    flow_signal: FlowSignal | None = None,
    analyst_context: dict | None = None,
    ecos_snapshot: dict | None = None,
    kosis_snapshot: dict | None = None,
) -> FreeKrForecast | None:
    prices = _to_frame(price_history)
    if prices.empty:
        return None

    market = _to_frame(market_history)
    reference_date = str(prices["date"].iloc[-1])
    reference_price = float(prices["close"].iloc[-1])
    close = prices["close"].astype(float)
    daily_returns = np.log(close / close.shift(1)).dropna().to_numpy(dtype=float)
    if len(daily_returns) < 15:
        return None

    market_returns = _return_series(market["close"]) if not market.empty else np.array([], dtype=float)
    news_items = _merge_news_items(google_news or [], naver_news or [])
    filings = filings or []
    analyst_context = analyst_context or {}
    ecos_snapshot = ecos_snapshot or {}
    kosis_snapshot = kosis_snapshot or {}

    signals = _build_base_features(
        prices=prices,
        market=market,
        flow_signal=flow_signal,
        analyst_context=analyst_context,
        news_items=news_items,
        filings=filings,
        ecos_snapshot=ecos_snapshot,
        kosis_snapshot=kosis_snapshot,
    )
    regime_probs = _build_regime_probs(
        prices=prices,
        market=market,
        market_returns=market_returns,
        macro_score=signals["macro"].score,
    )
    regime = max(regime_probs, key=regime_probs.get)
    evidence = _build_evidence(signals)
    sources = _build_data_sources(
        google_news=google_news or [],
        naver_news=naver_news or [],
        filings=filings,
        ecos_snapshot=ecos_snapshot,
        kosis_snapshot=kosis_snapshot,
        flow_signal=flow_signal,
    )
    realized_vol = float(np.std(daily_returns[-20:], ddof=1)) if len(daily_returns) >= 20 else float(np.std(daily_returns, ddof=1))
    base_confidence = _estimate_confidence(
        price_count=len(prices),
        news_count=len(news_items),
        filing_count=len(filings),
        flow_signal=flow_signal,
        dominant_regime=max(regime_probs.values()),
        realized_vol=realized_vol,
    )

    horizons = [
        _build_horizon(
            horizon=horizon,
            reference_date=reference_date,
            reference_price=reference_price,
            prices=prices,
            daily_returns=daily_returns,
            market=market,
            market_returns=market_returns,
            signals=signals,
            regime_probs=regime_probs,
            base_confidence=base_confidence,
        )
        for horizon in HORIZONS
    ]

    used_sources = [item.name for item in sources if item.used]
    summary = (
        f"{name}의 무료 KR 확률 엔진입니다. 가격·거래량·상대강도·거시를 중심으로 계산했고, "
        f"보강 소스는 {', '.join(used_sources) if used_sources else '기본 가격 데이터'} 수준으로만 얹었습니다."
    )
    confidence_note = _build_confidence_note(
        dominant_regime=max(regime_probs.values()),
        configured_source_count=len([item for item in sources if item.configured]),
        used_source_count=len(used_sources),
        news_count=len(news_items),
        filing_count=len(filings),
    )

    return FreeKrForecast(
        reference_date=reference_date,
        reference_price=round(reference_price, 2),
        regime=regime,
        regime_probs=regime_probs,
        horizons=horizons,
        evidence=evidence,
        data_sources=sources,
        confidence_note=confidence_note,
        summary=summary,
        model_version=MODEL_VERSION,
    )


def _build_base_features(
    *,
    prices: pd.DataFrame,
    market: pd.DataFrame,
    flow_signal: FlowSignal | None,
    analyst_context: dict,
    news_items: list[dict],
    filings: list[dict],
    ecos_snapshot: dict,
    kosis_snapshot: dict,
) -> dict[str, _Signal]:
    close = prices["close"].astype(float)
    volume = prices["volume"].astype(float)
    market_close = market["close"].astype(float) if not market.empty else pd.Series(dtype=float)

    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else float(close.mean())
    ma60 = float(close.tail(60).mean()) if len(close) >= 60 else ma20
    momentum_20 = _clip(_log_return(close, 20) / 0.08)
    momentum_60 = _clip(_log_return(close, 60) / 0.16)
    momentum_120 = _clip(_log_return(close, 120) / 0.28)
    trend_gap = _clip((((float(close.iloc[-1]) / ma20) - 1.0) / 0.06))
    rsi_series = RSIIndicator(close, window=min(14, max(3, len(close) - 1))).rsi()
    latest_rsi = float(rsi_series.iloc[-1]) if len(rsi_series) else 50.0
    rsi_score = _clip((latest_rsi - 50.0) / 18.0)
    relative_strength = _clip((_log_return(close, 20) - _log_return(market_close, 20)) / 0.05) if len(market_close) else 0.0
    volume_z = _zscore(volume.tail(20).to_numpy(dtype=float))
    volume_score = _clip(volume_z / 2.5)
    daily_returns = _return_series(close)
    vol_20 = float(np.std(daily_returns[-20:], ddof=1)) if len(daily_returns) >= 20 else float(np.std(daily_returns, ddof=1))
    vol_60 = float(np.std(daily_returns[-60:], ddof=1)) if len(daily_returns) >= 60 else max(vol_20, 1e-4)
    volatility_score = _clip(-((vol_20 / max(vol_60, 1e-4)) - 1.0) / 0.7)
    flow_score, flow_detail = _flow_signal_score(flow_signal)
    analyst_score, analyst_detail = _analyst_signal_score(analyst_context, float(close.iloc[-1]))
    news_score, news_detail = _headline_signal_score(news_items)
    filing_score, filing_detail = _filing_signal_score(filings)
    macro_score, macro_detail = _macro_signal_score(ecos_snapshot, kosis_snapshot)

    return {
        "momentum_20": _Signal("momentum_20", "20일 모멘텀", momentum_20, f"20거래일 로그수익률 {_pct(_log_return(close, 20))}"),
        "momentum_60": _Signal("momentum_60", "60일 모멘텀", momentum_60, f"60거래일 로그수익률 {_pct(_log_return(close, 60))}"),
        "momentum_120": _Signal("momentum_120", "120일 모멘텀", momentum_120, f"120거래일 로그수익률 {_pct(_log_return(close, 120))}"),
        "trend_gap": _Signal("trend_gap", "가격-이평 괴리", trend_gap, f"종가 {close.iloc[-1]:.0f}, MA20 {ma20:.0f}, MA60 {ma60:.0f}"),
        "rsi": _Signal("rsi", "RSI 위치", rsi_score, f"RSI {latest_rsi:.1f}"),
        "relative_strength": _Signal("relative_strength", "시장 대비 상대강도", relative_strength, f"시장 대비 20일 상대수익 {_pct(_log_return(close, 20) - _log_return(market_close, 20))}" if len(market_close) else "시장 이력 부족"),
        "volume": _Signal("volume", "거래량 확인", volume_score, f"최근 거래량 z-score {volume_z:.2f}"),
        "volatility": _Signal("volatility", "변동성 체제", volatility_score, f"20일 변동성 {vol_20 * 100:.2f}%, 60일 변동성 {vol_60 * 100:.2f}%"),
        "flow": _Signal("flow", "수급", flow_score, flow_detail),
        "analyst": _Signal("analyst", "애널리스트", analyst_score, analyst_detail),
        "news": _Signal("news", "뉴스 심리", news_score, news_detail),
        "filings": _Signal("filings", "공시 흐름", filing_score, filing_detail),
        "macro": _Signal("macro", "거시 배경", macro_score, macro_detail),
    }


def _build_regime_probs(
    *,
    prices: pd.DataFrame,
    market: pd.DataFrame,
    market_returns: np.ndarray,
    macro_score: float,
) -> dict[str, float]:
    market_close = market["close"].astype(float) if not market.empty else prices["close"].astype(float)
    market_momentum = _clip(_log_return(market_close, 20) / 0.08)
    market_trend = _clip((((float(market_close.iloc[-1]) / float(market_close.tail(60).mean())) - 1.0) / 0.06)) if len(market_close) >= 20 else 0.0
    market_vol_20 = float(np.std(market_returns[-20:], ddof=1)) if len(market_returns) >= 20 else 0.012
    market_vol_60 = float(np.std(market_returns[-60:], ddof=1)) if len(market_returns) >= 60 else max(market_vol_20, 0.012)
    stress = max((market_vol_20 / max(market_vol_60, 1e-4)) - 1.0, 0.0)
    scores = {
        "risk_on": 1.2 * market_momentum + 0.9 * market_trend + 0.6 * macro_score - 0.9 * stress,
        "neutral": 0.25 - abs(market_momentum + macro_score) * 0.35,
        "risk_off": -1.1 * market_momentum - 0.8 * market_trend - 0.5 * macro_score + 1.2 * stress,
    }
    return _softmax_scores(scores)


def _build_horizon(
    *,
    horizon: int,
    reference_date: str,
    reference_price: float,
    prices: pd.DataFrame,
    daily_returns: np.ndarray,
    market: pd.DataFrame,
    market_returns: np.ndarray,
    signals: dict[str, _Signal],
    regime_probs: dict[str, float],
    base_confidence: float,
) -> FreeKrForecastHorizon:
    close = prices["close"].astype(float)
    hist_returns = _horizon_returns(close, horizon)
    hist_mean = float(np.mean(hist_returns)) if len(hist_returns) else float(np.mean(daily_returns)) * horizon
    hist_vol = float(np.std(hist_returns, ddof=1)) if len(hist_returns) >= 2 else float(np.std(daily_returns, ddof=1)) * sqrt(horizon)
    hist_vol = max(hist_vol, 0.0035 * sqrt(horizon))

    market_hist = _horizon_returns(market["close"].astype(float), horizon) if not market.empty else np.array([], dtype=float)
    market_mean = float(np.mean(market_hist)) if len(market_hist) else (float(np.mean(market_returns)) * horizon if len(market_returns) else 0.0)

    signal_score = _signal_mix_for_horizon(signals, horizon)
    regime_bias = (regime_probs["risk_on"] - regime_probs["risk_off"]) / 100.0
    skew_score = _clip(signals["news"].score * 0.45 + signals["filings"].score * 0.35 + signals["relative_strength"].score * 0.2)

    adjusted_mean = hist_mean + (signal_score * hist_vol * 0.45) + (regime_bias * hist_vol * 0.3)
    adjusted_vol = hist_vol * (1.0 + (regime_probs["risk_off"] / 100.0) * 0.2 + max(-signals["volatility"].score, 0.0) * 0.15)
    adjusted_vol = max(adjusted_vol, 0.0025 * sqrt(horizon))

    q10, q25, q50, q75, q90 = _skewed_quantiles(adjusted_mean, adjusted_vol, skew_score)
    delta = max(0.0035 * sqrt(horizon), adjusted_vol * 0.35)
    p_up = (1.0 - _normal_cdf((delta - adjusted_mean) / adjusted_vol)) * 100.0
    p_down = _normal_cdf((-delta - adjusted_mean) / adjusted_vol) * 100.0
    p_flat = max(0.0, 100.0 - p_up - p_down)
    p_up, p_flat, p_down = _normalize_probabilities(p_up, p_flat, p_down)

    target_days = trading_days_forward("KR", reference_date, horizon)
    target_date = target_days[-1].isoformat() if target_days else reference_date
    horizon_confidence = _clip_confidence(base_confidence + (1.5 if horizon == 5 else 0.0) - (3.0 if horizon == 20 else 0.0) - abs(signal_score - regime_bias) * 6.0)

    return FreeKrForecastHorizon(
        horizon_days=horizon,
        target_date=target_date,
        mean_return_raw=round(adjusted_mean, 6),
        mean_return_excess=round(adjusted_mean - market_mean, 6),
        q10=round(q10, 6),
        q25=round(q25, 6),
        q50=round(q50, 6),
        q75=round(q75, 6),
        q90=round(q90, 6),
        price_q10=round(reference_price * exp(q10), 2),
        price_q25=round(reference_price * exp(q25), 2),
        price_q50=round(reference_price * exp(q50), 2),
        price_q75=round(reference_price * exp(q75), 2),
        price_q90=round(reference_price * exp(q90), 2),
        p_down=round(p_down, 2),
        p_flat=round(p_flat, 2),
        p_up=round(p_up, 2),
        vol_forecast=round(adjusted_vol, 6),
        confidence=round(horizon_confidence, 1),
    )


def _build_evidence(signals: dict[str, _Signal]) -> list[FreeKrForecastEvidence]:
    weights = {
        "momentum_20": 0.12,
        "momentum_60": 0.12,
        "momentum_120": 0.09,
        "trend_gap": 0.08,
        "rsi": 0.05,
        "relative_strength": 0.11,
        "volume": 0.06,
        "volatility": 0.07,
        "flow": 0.08,
        "analyst": 0.07,
        "news": 0.07,
        "filings": 0.05,
        "macro": 0.13,
    }
    items = []
    for key, signal in signals.items():
        contribution = signal.score * weights.get(key, 0.0)
        items.append(
            FreeKrForecastEvidence(
                key=key,
                label=signal.label,
                contribution=round(contribution, 4),
                signal="bullish" if contribution > 0.015 else "bearish" if contribution < -0.015 else "neutral",
                detail=signal.detail,
            )
        )
    items.sort(key=lambda item: abs(item.contribution), reverse=True)
    return items[:6]


def _build_data_sources(
    *,
    google_news: list[dict],
    naver_news: list[dict],
    filings: list[dict],
    ecos_snapshot: dict,
    kosis_snapshot: dict,
    flow_signal: FlowSignal | None,
) -> list[FreeKrForecastDataSource]:
    settings = get_settings()
    kosis_configured = bool(
        settings.kosis_api_key
        and (
            settings.kosis_cpi_user_stats_id
            or settings.kosis_employment_user_stats_id
            or settings.kosis_industrial_production_user_stats_id
        )
    )
    return [
        FreeKrForecastDataSource(name="Yahoo Finance", configured=True, used=True, item_count=1, note="가격과 기본 펀더멘털 백본"),
        FreeKrForecastDataSource(name="Google News RSS", configured=True, used=bool(google_news), item_count=len(google_news), note="무료 헤드라인 흐름"),
        FreeKrForecastDataSource(name="Naver Search API", configured=bool(settings.naver_client_id and settings.naver_client_secret), used=bool(naver_news), item_count=len(naver_news), note="국내 뉴스 보강"),
        FreeKrForecastDataSource(name="OpenDART", configured=bool(settings.opendart_api_key), used=bool(filings), item_count=len(filings), note="최근 공시 이벤트 보강"),
        FreeKrForecastDataSource(name="ECOS", configured=bool(settings.ecos_api_key), used=bool(ecos_snapshot), item_count=len([value for value in ecos_snapshot.values() if value is not None]), note="한국은행 거시 수치"),
        FreeKrForecastDataSource(name="KOSIS", configured=kosis_configured, used=bool(kosis_snapshot and any(value is not None for value in kosis_snapshot.values())), item_count=len([value for value in kosis_snapshot.values() if value is not None]), note="정부 통계 보강"),
        FreeKrForecastDataSource(name="PyKRX flow", configured=True, used=bool(flow_signal and flow_signal.available), item_count=1 if flow_signal and flow_signal.available else 0, note="외국인/기관 수급 best effort"),
    ]


def _estimate_confidence(
    *,
    price_count: int,
    news_count: int,
    filing_count: int,
    flow_signal: FlowSignal | None,
    dominant_regime: float,
    realized_vol: float,
) -> float:
    history_score = min(price_count / 252.0, 1.0) * 20.0
    source_score = min(news_count, 10) * 0.7 + min(filing_count, 6) * 0.8 + (4.0 if flow_signal and flow_signal.available else 0.0)
    stability_penalty = max(0.0, (realized_vol * 100.0) - 2.5) * 2.0
    regime_bonus = max(0.0, dominant_regime - 40.0) * 0.12
    return _clip_confidence(46.0 + history_score + source_score + regime_bonus - stability_penalty)


def _build_confidence_note(
    *,
    dominant_regime: float,
    configured_source_count: int,
    used_source_count: int,
    news_count: int,
    filing_count: int,
) -> str:
    parts = [
        f"지배적 장세 확률은 {dominant_regime:.1f}% 수준입니다.",
        f"구성된 무료 소스 {configured_source_count}개 중 {used_source_count}개가 이번 계산에 실제 반영됐습니다.",
    ]
    if news_count:
        parts.append(f"뉴스 {news_count}건을 이벤트 민감도 보정에 사용했습니다.")
    if filing_count:
        parts.append(f"OpenDART 공시 {filing_count}건을 보조 신호로 반영했습니다.")
    if not filing_count:
        parts.append("공시 원문이 비어 있으면 가격·거래량 신호 비중이 더 커집니다.")
    return " ".join(parts)


def _signal_mix_for_horizon(signals: dict[str, _Signal], horizon: int) -> float:
    if horizon == 1:
        weights = {"momentum_20": 0.16, "trend_gap": 0.10, "relative_strength": 0.12, "volume": 0.10, "volatility": 0.10, "flow": 0.10, "analyst": 0.05, "news": 0.12, "filings": 0.08, "macro": 0.07}
    elif horizon == 5:
        weights = {"momentum_20": 0.14, "momentum_60": 0.14, "trend_gap": 0.08, "relative_strength": 0.12, "volume": 0.06, "volatility": 0.10, "flow": 0.08, "analyst": 0.06, "news": 0.09, "filings": 0.05, "macro": 0.08}
    else:
        weights = {"momentum_20": 0.08, "momentum_60": 0.16, "momentum_120": 0.14, "trend_gap": 0.05, "relative_strength": 0.12, "volatility": 0.10, "flow": 0.05, "analyst": 0.09, "news": 0.05, "filings": 0.04, "macro": 0.12}
    return _clip(sum(signals[key].score * weight for key, weight in weights.items()))


def _headline_signal_score(news_items: list[dict]) -> tuple[float, str]:
    if not news_items:
        return 0.0, "무료 뉴스 보강 데이터 없음"
    score = 0.0
    for item in news_items[:18]:
        title = f"{item.get('title', '')} {item.get('description', '')}".lower()
        positive = sum(1 for keyword in POSITIVE_NEWS_KEYWORDS if keyword.lower() in title)
        negative = sum(1 for keyword in NEGATIVE_NEWS_KEYWORDS if keyword.lower() in title)
        score += positive * 0.35
        score -= negative * 0.35
    score /= max(len(news_items[:18]), 1)
    return _clip(score), f"헤드라인 {len(news_items[:18])}건 평균 심리 {_pct(score * 0.04)}"


def _filing_signal_score(filings: list[dict]) -> tuple[float, str]:
    if not filings:
        return 0.0, "최근 OpenDART 공시 없음 또는 미설정"
    score = 0.0
    for filing in filings[:10]:
        title = str(filing.get("report_name", "")).lower()
        positive = sum(1 for keyword in POSITIVE_FILING_KEYWORDS if keyword.lower() in title)
        negative = sum(1 for keyword in NEGATIVE_FILING_KEYWORDS if keyword.lower() in title)
        score += positive * 0.45
        score -= negative * 0.55
    score /= max(len(filings[:10]), 1)
    return _clip(score), f"공시 {len(filings[:10])}건 기준 이벤트 편향"


def _flow_signal_score(flow_signal: FlowSignal | None) -> tuple[float, str]:
    if not flow_signal or not flow_signal.available:
        return 0.0, "검증 가능한 수급 데이터 부족"
    foreign = float(flow_signal.foreign_net_buy or 0.0)
    institutional = float(flow_signal.institutional_net_buy or 0.0)
    retail = float(flow_signal.retail_net_buy or 0.0)
    denominator = max(abs(foreign) + abs(institutional) + abs(retail), 1.0)
    score = (foreign + institutional - retail * 0.35) / denominator
    return _clip(score * 1.4), f"외국인 {foreign:,.0f}, 기관 {institutional:,.0f}, 개인 {retail:,.0f}"


def _analyst_signal_score(analyst_context: dict, current_price: float) -> tuple[float, str]:
    buy = float(analyst_context.get("buy") or 0.0)
    hold = float(analyst_context.get("hold") or 0.0)
    sell = float(analyst_context.get("sell") or 0.0)
    total = max(buy + hold + sell, 1.0)
    target_mean = analyst_context.get("target_mean")
    target_gap = 0.0
    if target_mean and current_price > 0:
        target_gap = (float(target_mean) / current_price) - 1.0
    score = ((buy - sell) / total) * 0.7 + _clip(target_gap / 0.2) * 0.3
    detail = f"매수 {buy:.0f}, 보유 {hold:.0f}, 매도 {sell:.0f}"
    if target_mean:
        detail += f", 평균 목표가 괴리 {target_gap * 100:.1f}%"
    return _clip(score), detail


def _macro_signal_score(ecos_snapshot: dict, kosis_snapshot: dict) -> tuple[float, str]:
    snapshots = {**ecos_snapshot, **{f"kosis_{k}": v for k, v in kosis_snapshot.items()}}
    if not snapshots:
        return 0.0, "거시 스냅샷 미설정"
    score = 0.0
    details: list[str] = []
    consumer_sentiment = ecos_snapshot.get("consumer_sentiment")
    if consumer_sentiment is not None:
        score += _clip((float(consumer_sentiment) - 100.0) / 10.0) * 0.22
        details.append(f"심리지수 {float(consumer_sentiment):.1f}")
    export_growth = ecos_snapshot.get("export_growth")
    if export_growth is not None:
        score += _clip(float(export_growth) / 12.0) * 0.24
        details.append(f"수출증가율 {float(export_growth):.1f}")
    industrial = ecos_snapshot.get("industrial_production")
    if industrial is not None:
        score += _clip(float(industrial) / 6.0) * 0.18
        details.append(f"광공업생산 {float(industrial):.1f}")
    base_rate = ecos_snapshot.get("base_rate")
    if base_rate is not None:
        score -= _clip((float(base_rate) - 2.75) / 1.25) * 0.16
        details.append(f"기준금리 {float(base_rate):.2f}")
    cpi = ecos_snapshot.get("cpi_yoy") or kosis_snapshot.get("cpi")
    if cpi is not None:
        score -= _clip((float(cpi) - 2.2) / 2.0) * 0.12
        details.append(f"물가 {float(cpi):.1f}")
    employment = kosis_snapshot.get("employment")
    if employment is not None:
        score += _clip((float(employment) - 61.0) / 3.5) * 0.08
        details.append(f"고용률 {float(employment):.1f}")
    return _clip(score), ", ".join(details[:4]) if details else "거시 스냅샷 비어 있음"


def _to_frame(price_history: list[dict]) -> pd.DataFrame:
    if not price_history:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(price_history).copy()
    if "date" not in df:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = df["date"].astype(str)
    for column in ("open", "high", "low", "close", "volume"):
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        else:
            df[column] = 0.0
    return df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def _merge_news_items(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in [*primary, *secondary]:
        key = (str(item.get("title") or "").strip().lower(), str(item.get("url") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=lambda item: str(item.get("published") or ""), reverse=True)
    return merged[:18]


def _return_series(close: pd.Series) -> np.ndarray:
    if close is None or close.empty:
        return np.array([], dtype=float)
    return np.log(close.astype(float) / close.astype(float).shift(1)).dropna().to_numpy(dtype=float)


def _horizon_returns(close: pd.Series, horizon: int) -> np.ndarray:
    if close is None or close.empty or len(close) <= horizon:
        return np.array([], dtype=float)
    return np.log(close.astype(float) / close.astype(float).shift(horizon)).dropna().to_numpy(dtype=float)


def _log_return(close: pd.Series, window: int) -> float:
    if close is None or close.empty:
        return 0.0
    start = float(close.iloc[0]) if len(close) <= window else float(close.iloc[-window - 1])
    end = float(close.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    return float(np.log(end / start))


def _zscore(values: np.ndarray) -> float:
    if len(values) < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    if std <= 0:
        return 0.0
    return float((values[-1] - float(np.mean(values))) / std)


def _softmax_scores(values: dict[str, float]) -> dict[str, float]:
    keys = list(values.keys())
    array = np.array([values[key] for key in keys], dtype=float)
    array = array - np.max(array)
    exp_values = np.exp(array)
    probs = exp_values / np.sum(exp_values)
    return {key: round(float(prob * 100.0), 2) for key, prob in zip(keys, probs)}


def _skewed_quantiles(mean_value: float, volatility: float, skew: float) -> tuple[float, float, float, float, float]:
    lower_10 = 1.28 * (1.0 + max(-skew, 0.0) * 0.35)
    lower_25 = 0.67 * (1.0 + max(-skew, 0.0) * 0.22)
    upper_25 = 0.67 * (1.0 + max(skew, 0.0) * 0.22)
    upper_10 = 1.28 * (1.0 + max(skew, 0.0) * 0.35)
    quantiles = [
        mean_value - lower_10 * volatility,
        mean_value - lower_25 * volatility,
        mean_value + skew * volatility * 0.12,
        mean_value + upper_25 * volatility,
        mean_value + upper_10 * volatility,
    ]
    ordered = sorted(quantiles)
    return tuple(float(item) for item in ordered)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def _normalize_probabilities(p_up: float, p_flat: float, p_down: float) -> tuple[float, float, float]:
    total = max(p_up + p_flat + p_down, 1e-6)
    return ((p_up / total) * 100.0, (p_flat / total) * 100.0, (p_down / total) * 100.0)


def _clip(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    return float(max(lower, min(upper, value)))


def _clip_confidence(value: float) -> float:
    return float(max(38.0, min(88.0, value)))


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"
