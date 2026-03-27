"""High-level market radar and opportunity scanning."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.analysis.distributional_return_engine import build_distributional_forecast
from app.analysis.market_regime import build_market_regime
from app.analysis.next_day_forecast import forecast_next_day
from app.analysis.trade_planner import build_trade_plan
from app.analysis.valuation_blend import build_quick_buy_sell
from app.analysis.stock_analyzer import _calc_technicals
from app.data import cache, ecos_client, kosis_client, kr_market_quote_client, yfinance_client
from app.data.universe_data import UNIVERSE, resolve_opportunity_universe, resolve_universe
from app.models.country import COUNTRY_REGISTRY
from app.models.market import MarketRegime, OpportunityItem, OpportunityRadarResponse
from app.models.stock import PricePoint, TechnicalIndicators
from app.scoring.stock_scorer import score_stock
from app.services.portfolio_optimizer import build_horizon_snapshot
from app.utils.async_tools import gather_limited

OPPORTUNITY_SCAN_TIMEOUT_SECONDS = 4
OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS = 4
OPPORTUNITY_CONCURRENCY = 4
LIGHTWEIGHT_OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS = 2
LIGHTWEIGHT_OPPORTUNITY_MAX_CANDIDATES = 12
QUICK_UNIVERSE_QUOTE_TIMEOUT_SECONDS = 1.2
QUICK_UNIVERSE_QUOTE_CONCURRENCY = 18
QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP = 120
MIN_DETAILED_OPPORTUNITY_CANDIDATES = 12
MAX_DETAILED_OPPORTUNITY_CANDIDATES = 24
LARGE_UNIVERSE_DETAILED_SCAN_CAP = 4
LARGE_UNIVERSE_QUOTE_ONLY_THRESHOLD = 120
QUICK_OPPORTUNITY_CACHE_TTL_SECONDS = 300


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _scenario_snapshot(forecast) -> dict:
    scenarios = {item.name: item for item in getattr(forecast, "scenarios", [])}
    bull = scenarios.get("Bull")
    base = scenarios.get("Base")
    bear = scenarios.get("Bear")
    return {
        "bull_case_price": bull.price if bull else None,
        "base_case_price": base.price if base else None,
        "bear_case_price": bear.price if bear else None,
        "bull_probability": bull.probability if bull else None,
        "base_probability": base.probability if base else None,
        "bear_probability": bear.probability if bear else None,
    }


def _safe_float(value: float | None, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _regime_tailwind_label(stance: str) -> str:
    if stance == "risk_on":
        return "tailwind"
    if stance == "risk_off":
        return "headwind"
    return "mixed"


def _build_placeholder_market_regime(
    *,
    country_code: str,
    index_name: str,
    note: str,
) -> MarketRegime:
    return MarketRegime(
        label=f"{country_code} 빠른 스냅샷",
        stance="neutral",
        trend="range",
        volatility="normal",
        breadth="mixed",
        score=50.0,
        conviction=38.0,
        summary=note,
        playbook=[
            f"{index_name} 정밀 국면 계산이 완료되기 전까지 1차 시세 스캔 후보를 우선 제공합니다.",
            "강한 후보를 먼저 확인하고, 잠시 뒤 다시 열어 정밀 분포 신호를 확인해 주세요.",
        ],
        warnings=["시장 국면과 분포 신호는 백그라운드 계산이 끝난 뒤 더 정교하게 갱신됩니다."],
        signals=[],
    )


def _flatten_universe(universe: dict[str, list[str]]) -> list[tuple[str, str]]:
    flattened: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sector, tickers in universe.items():
        for ticker in tickers:
            if ticker in seen:
                continue
            seen.add(ticker)
            flattened.append((sector, ticker))
    return flattened


def _resolve_detail_candidate_budget(*, limit: int, available: int, max_candidates: int | None) -> int:
    if available <= 0:
        return 0
    if max_candidates is not None:
        return max(1, min(available, max_candidates))
    preferred = max(limit * 2, MIN_DETAILED_OPPORTUNITY_CANDIDATES)
    if available >= 120:
        preferred = min(preferred, LARGE_UNIVERSE_DETAILED_SCAN_CAP)
    return max(1, min(available, min(preferred, MAX_DETAILED_OPPORTUNITY_CANDIDATES)))


def _should_skip_detailed_scan(
    *,
    country_code: str,
    universe_source: str,
    ranked_count: int,
    limit: int,
) -> bool:
    return (
        country_code == "KR"
        and universe_source in {"fallback", "krx_listing"}
        and ranked_count >= max(limit, LARGE_UNIVERSE_QUOTE_ONLY_THRESHOLD)
    )


def _build_quote_only_opportunity_item(
    *,
    rank: int,
    sector: str,
    ticker: str,
    current_price: float,
    change_pct: float,
    country_code: str,
    market_regime,
) -> OpportunityItem:
    regime_bias = 4.0 if market_regime.stance == "risk_on" else -4.0 if market_regime.stance == "risk_off" else 0.0
    opportunity_score = _clip(55.0 + change_pct * 3.4 + regime_bias, 15.0, 90.0)
    up_probability = _clip(50.0 + change_pct * 1.9 + regime_bias * 0.7, 34.0, 77.0)
    predicted_return_pct = round(_clip(change_pct * 0.55, -5.0, 6.5), 2)
    target_date = (datetime.now() + timedelta(days=20)).date().isoformat()
    bull_case_price = round(current_price * 1.04, 2)
    base_case_price = round(current_price * (1.0 + predicted_return_pct / 100.0), 2)
    bear_case_price = round(current_price * 0.97, 2)
    action = "accumulate" if predicted_return_pct >= 1.4 else "breakout_watch" if predicted_return_pct >= 0.2 else "wait_pullback"
    return OpportunityItem(
        rank=rank,
        ticker=ticker,
        name=ticker.split(".")[0],
        sector=sector,
        country_code=country_code,
        current_price=round(current_price, 2),
        change_pct=round(change_pct, 2),
        opportunity_score=round(opportunity_score, 1),
        quant_score=round(_clip(50.0 + change_pct * 1.8, 22.0, 78.0), 1),
        up_probability=round(up_probability, 1),
        confidence=41.0,
        predicted_return_pct=predicted_return_pct,
        target_horizon_days=20,
        target_date_20d=target_date,
        expected_return_pct_20d=predicted_return_pct,
        expected_excess_return_pct_20d=round(predicted_return_pct * 0.72, 2),
        median_return_pct_20d=predicted_return_pct,
        forecast_volatility_pct_20d=round(max(abs(change_pct) * 1.4, 2.4), 2),
        up_probability_20d=round(up_probability, 1),
        flat_probability_20d=round(max(100.0 - up_probability - 20.0, 6.0), 1),
        down_probability_20d=round(max(100.0 - up_probability - max(100.0 - up_probability - 20.0, 6.0), 6.0), 1),
        distribution_confidence_20d=41.0,
        price_q25_20d=bear_case_price,
        price_q50_20d=base_case_price,
        price_q75_20d=bull_case_price,
        bull_case_price=bull_case_price,
        base_case_price=base_case_price,
        bear_case_price=bear_case_price,
        bull_probability=round(up_probability, 1),
        base_probability=20.0,
        bear_probability=round(max(100.0 - up_probability - 20.0, 6.0), 1),
        setup_label="전수 1차 스캔",
        action=action,
        execution_bias="stay_selective",
        execution_note="현재 KR 레이더 유니버스를 1차 스캔했고, 상세 분포 계산이 지연된 종목은 시세 스냅샷 기준으로 먼저 정리했습니다.",
        regime_tailwind=_regime_tailwind_label(market_regime.stance),
        entry_low=round(current_price * 0.99, 2),
        entry_high=round(current_price * 1.01, 2),
        stop_loss=round(current_price * 0.96, 2),
        take_profit_1=round(current_price * 1.03, 2),
        take_profit_2=round(current_price * 1.06, 2),
        risk_reward_estimate=1.15,
        thesis=["현재 KR 레이더 유니버스를 1차로 훑은 뒤 상위 종목을 먼저 정렬한 결과입니다."],
        risk_flags=["상세 분포 계산이 지연돼 시세 스냅샷 기반 후보로 표시합니다."],
        forecast_date=target_date,
    )


def _build_lightweight_opportunity_item(
    *,
    rank: int,
    sector: str,
    ticker: str,
    snapshot: dict,
    country_code: str,
    market_regime,
) -> OpportunityItem | None:
    current_price = _safe_float(snapshot.get("current_price") or snapshot.get("price"), 0.0)
    if current_price <= 0:
        return None
    change_pct = _safe_float(snapshot.get("change_pct"))
    market_cap = _safe_float(snapshot.get("market_cap"))
    regime_bias = 4.0 if market_regime.stance == "risk_on" else -4.0 if market_regime.stance == "risk_off" else 0.0
    opportunity_score = _clip(56.0 + change_pct * 2.8 + regime_bias + min(market_cap / 1_000_000_000_000, 8.0), 15.0, 92.0)
    up_probability = _clip(50.0 + change_pct * 1.8 + regime_bias * 0.8, 32.0, 78.0)
    predicted_return_pct = round(_clip(change_pct * 0.45, -6.0, 6.0), 2)
    target_date = (datetime.now() + timedelta(days=20)).date().isoformat()
    bull_case_price = round(current_price * 1.04, 2)
    base_case_price = round(current_price * (1.0 + predicted_return_pct / 100.0), 2)
    bear_case_price = round(current_price * 0.97, 2)
    action = "accumulate" if predicted_return_pct >= 1.2 else "breakout_watch" if predicted_return_pct >= 0.3 else "wait_pullback"
    setup_label = "축약 스캔"
    return OpportunityItem(
        rank=rank,
        ticker=ticker,
        name=snapshot.get("name") or ticker,
        sector=sector,
        country_code=country_code,
        current_price=round(current_price, 2),
        change_pct=round(change_pct, 2),
        opportunity_score=round(opportunity_score, 1),
        quant_score=round(_clip(50.0 + change_pct * 1.6, 20.0, 80.0), 1),
        up_probability=round(up_probability, 1),
        confidence=44.0,
        predicted_return_pct=predicted_return_pct,
        target_horizon_days=20,
        target_date_20d=target_date,
        expected_return_pct_20d=predicted_return_pct,
        expected_excess_return_pct_20d=round(predicted_return_pct * 0.75, 2),
        median_return_pct_20d=predicted_return_pct,
        forecast_volatility_pct_20d=round(max(abs(change_pct) * 1.5, 2.5), 2),
        up_probability_20d=round(up_probability, 1),
        flat_probability_20d=round(max(100.0 - up_probability - 20.0, 5.0), 1),
        down_probability_20d=round(max(100.0 - up_probability - max(100.0 - up_probability - 20.0, 5.0), 5.0), 1),
        distribution_confidence_20d=44.0,
        price_q25_20d=bear_case_price,
        price_q50_20d=base_case_price,
        price_q75_20d=bull_case_price,
        bull_case_price=bull_case_price,
        base_case_price=base_case_price,
        bear_case_price=bear_case_price,
        bull_probability=round(up_probability, 1),
        base_probability=20.0,
        bear_probability=round(max(100.0 - up_probability - 20.0, 5.0), 1),
        setup_label=setup_label,
        action=action,
        execution_bias="stay_selective",
        execution_note="외부 시세 응답이 느려 대표 종목군 중심의 축약 스캔 결과를 먼저 제공합니다.",
        regime_tailwind=_regime_tailwind_label(market_regime.stance),
        entry_low=round(current_price * 0.99, 2),
        entry_high=round(current_price * 1.01, 2),
        stop_loss=round(current_price * 0.96, 2),
        take_profit_1=round(current_price * 1.03, 2),
        take_profit_2=round(current_price * 1.06, 2),
        risk_reward_estimate=1.2,
        thesis=["실시간 상세 계산이 지연돼 대표 종목군 기반의 축약 레이더를 우선 제공합니다."],
        risk_flags=["상세 분포 계산이 지연돼 요약 신호로 표시합니다."],
        forecast_date=target_date,
    )


async def _build_lightweight_opportunities(
    *,
    candidates: list[tuple[str, str]],
    country_code: str,
    market_regime,
    limit: int,
) -> list[OpportunityItem]:
    async def _scan_snapshot(candidate: tuple[str, str]) -> OpportunityItem | None:
        sector, ticker = candidate
        try:
            snapshot = await asyncio.wait_for(
                yfinance_client.get_market_snapshot(ticker, period="3mo"),
                timeout=LIGHTWEIGHT_OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS,
            )
        except Exception:
            return None
        if not snapshot.get("valid"):
            return None
        return _build_lightweight_opportunity_item(
            rank=0,
            sector=sector,
            ticker=ticker,
            snapshot=snapshot,
            country_code=country_code,
            market_regime=market_regime,
        )

    scanned = await gather_limited(
        candidates[: min(max(limit, 4), LIGHTWEIGHT_OPPORTUNITY_MAX_CANDIDATES)],
        _scan_snapshot,
        limit=OPPORTUNITY_CONCURRENCY,
    )
    items = [item for item in scanned if not isinstance(item, Exception) and item is not None]
    items.sort(key=lambda item: item.opportunity_score, reverse=True)
    return [item.model_copy(update={"rank": idx}) for idx, item in enumerate(items[:limit], start=1)]


def _build_quote_only_opportunities(
    *,
    ranked_quotes: list[dict],
    country_code: str,
    market_regime,
    limit: int,
) -> list[OpportunityItem]:
    items = [
        _build_quote_only_opportunity_item(
            rank=idx,
            sector=item["sector"],
            ticker=item["ticker"],
            current_price=float(item["current_price"]),
            change_pct=float(item["change_pct"]),
            country_code=country_code,
            market_regime=market_regime,
        )
        for idx, item in enumerate(ranked_quotes[:limit], start=1)
    ]
    items.sort(key=lambda item: item.opportunity_score, reverse=True)
    return [item.model_copy(update={"rank": idx}) for idx, item in enumerate(items[:limit], start=1)]


async def _build_quote_screen(
    *,
    country_code: str,
    universe_selection,
    market_regime,
    max_pairs: int | None = None,
) -> dict:
    full_universe_pairs = _flatten_universe(universe_selection.sectors)
    if max_pairs is not None and max_pairs > 0:
        universe_pairs = full_universe_pairs[:max_pairs]
        scope_token = f"cap{max_pairs}"
    else:
        universe_pairs = full_universe_pairs
        scope_token = "full"
    cache_key = (
        f"opportunity_quote_screen:v3:{country_code}:{universe_selection.source}:"
        f"{len(full_universe_pairs)}:{scope_token}"
    )

    async def _fetch_quotes():
        if country_code == "KR":
            try:
                batch_quotes = await asyncio.wait_for(
                    kr_market_quote_client.get_kr_bulk_quotes(
                        [ticker for _, ticker in universe_pairs],
                        skip_full_market_fallback=max_pairs is not None,
                    ),
                    timeout=9,
                )
            except Exception:
                batch_quotes = {}
            ranked: list[dict] = []
            for sector, ticker in universe_pairs:
                quote = batch_quotes.get(ticker) or {}
                current_price = _safe_float(quote.get("current_price"), 0.0)
                if current_price <= 0:
                    continue
                change_pct = _safe_float(quote.get("change_pct"))
                regime_bias = 0.75 if market_regime.stance == "risk_on" else -0.55 if market_regime.stance == "risk_off" else 0.0
                quick_score = change_pct * 2.2 + regime_bias
                ranked.append(
                    {
                        "sector": sector,
                        "ticker": ticker,
                        "current_price": round(current_price, 2),
                        "change_pct": round(change_pct, 2),
                        "quick_score": round(quick_score, 4),
                    }
                )
            if ranked:
                ranked.sort(key=lambda item: (item["quick_score"], item["change_pct"]), reverse=True)
                return {
                    "universe_size": len(full_universe_pairs),
                    "scanned_count": len(universe_pairs),
                    "quote_available_count": len(ranked),
                    "ranked": ranked,
                }

        async def _scan_quote(candidate: tuple[str, str]) -> dict | None:
            sector, ticker = candidate
            try:
                quote = await asyncio.wait_for(
                    yfinance_client.get_stock_quote(ticker),
                    timeout=QUICK_UNIVERSE_QUOTE_TIMEOUT_SECONDS,
                )
            except Exception:
                return None
            current_price = _safe_float(quote.get("current_price"), 0.0)
            if current_price <= 0:
                return None
            change_pct = _safe_float(quote.get("change_pct"))
            regime_bias = 0.75 if market_regime.stance == "risk_on" else -0.55 if market_regime.stance == "risk_off" else 0.0
            quick_score = change_pct * 2.2 + regime_bias
            return {
                "sector": sector,
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "change_pct": round(change_pct, 2),
                "quick_score": round(quick_score, 4),
            }

        scanned = await gather_limited(
            universe_pairs,
            _scan_quote,
            limit=QUICK_UNIVERSE_QUOTE_CONCURRENCY,
        )
        ranked = [item for item in scanned if not isinstance(item, Exception) and item is not None]
        ranked.sort(key=lambda item: (item["quick_score"], item["change_pct"]), reverse=True)
        return {
            "universe_size": len(full_universe_pairs),
            "scanned_count": len(universe_pairs),
            "quote_available_count": len(ranked),
            "ranked": ranked,
        }

    return await cache.get_or_fetch(cache_key, _fetch_quotes, ttl=900)


async def _resolve_quick_opportunity_universe(country_code: str):
    country_code = country_code.upper()
    if country_code == "KR":
        cached = await cache.get("krx_listing_universe:KR")
        if cached and isinstance(cached, dict):
            sectors = {
                sector: list(dict.fromkeys(str(ticker or "").upper() for ticker in tickers if ticker))
                for sector, tickers in (cached.get("sectors") or {}).items()
            }
            total = int(cached.get("total") or sum(len(tickers) for tickers in sectors.values()))
            if total > 0:
                return SimpleNamespace(
                    sectors=sectors,
                    source="krx_listing",
                    note=f"KRX 상장사 목록 기준 전종목 {total}개를 1차 스캔합니다. 상세 분포 계산은 백그라운드에서 이어집니다.",
                )
        fallback_sectors = {
            sector: list(dict.fromkeys(str(ticker or "").upper() for ticker in tickers if ticker))
            for sector, tickers in UNIVERSE.get(country_code, {}).items()
        }
        fallback_total = sum(len(tickers) for tickers in fallback_sectors.values())
        if fallback_total > 0:
            return SimpleNamespace(
                sectors=fallback_sectors,
                source="fallback",
                note=(
                    f"KRX 상장사 목록 캐시가 아직 준비되지 않아 운영용 기본 종목군 {fallback_total}개를 먼저 1차 스캔합니다. "
                    "정식 전종목 스캔은 캐시가 준비되는 즉시 이어집니다."
                ),
            )
    return await resolve_universe(country_code)


def build_distributional_signal_profile(
    *,
    current_price: float,
    bull_case_price: float | None,
    base_case_price: float | None,
    bear_case_price: float | None,
    bull_probability: float | None,
    base_probability: float | None,
    bear_probability: float | None,
    predicted_return_pct: float,
    up_probability: float,
    confidence: float,
) -> dict[str, float]:
    price = max(_safe_float(current_price, 0.0), 1e-6)
    bull_return_pct = ((_safe_float(bull_case_price, price) / price) - 1.0) * 100.0
    base_return_pct = ((_safe_float(base_case_price, price) / price) - 1.0) * 100.0
    bear_return_pct = ((_safe_float(bear_case_price, price) / price) - 1.0) * 100.0
    bull_prob = _safe_float(bull_probability, up_probability)
    base_prob = _safe_float(base_probability, max(100.0 - up_probability - _safe_float(bear_probability, 0.0), 0.0))
    bear_prob = _safe_float(bear_probability, max(100.0 - up_probability, 0.0))
    probability_total = bull_prob + base_prob + bear_prob
    if probability_total <= 0:
        bull_prob, base_prob, bear_prob = up_probability, max(100.0 - up_probability, 0.0), 0.0
        probability_total = bull_prob + base_prob + bear_prob
    bull_prob /= probability_total
    base_prob /= probability_total
    bear_prob /= probability_total

    expected_return_pct = bull_return_pct * bull_prob + base_return_pct * base_prob + bear_return_pct * bear_prob
    if abs(expected_return_pct) < 0.05:
        expected_return_pct = _safe_float(predicted_return_pct, 0.0)

    upside_pct = max(bull_return_pct, base_return_pct, 0.0)
    downside_pct = max(-bear_return_pct, -base_return_pct, 0.0)
    range_width_pct = max(bull_return_pct - bear_return_pct, 0.0)
    probability_edge = _safe_float(up_probability, 50.0) - (bear_prob * 100.0)
    tail_ratio = upside_pct / max(downside_pct, 0.35)
    uncertainty_penalty = max(range_width_pct - 6.0, 0.0) * 0.45 + max(bear_prob * 100.0 - 24.0, 0.0) * 0.28
    directional_score = (
        50.0
        + expected_return_pct * 7.2
        + probability_edge * 0.48
        + (_safe_float(confidence, 50.0) - 50.0) * 0.34
        + min(tail_ratio, 3.0) * 5.2
        - downside_pct * 1.85
        - uncertainty_penalty
    )
    return {
        "bull_return_pct": round(bull_return_pct, 2),
        "base_return_pct": round(base_return_pct, 2),
        "bear_return_pct": round(bear_return_pct, 2),
        "expected_return_pct": round(expected_return_pct, 2),
        "upside_pct": round(upside_pct, 2),
        "downside_pct": round(downside_pct, 2),
        "range_width_pct": round(range_width_pct, 2),
        "probability_edge": round(probability_edge, 2),
        "tail_ratio": round(tail_ratio, 2),
        "directional_score": round(_clip(directional_score, 0.0, 100.0), 2),
    }


async def get_market_opportunities(
    country_code: str,
    limit: int = 12,
    *,
    max_candidates: int | None = None,
) -> dict:
    country_code = country_code.upper()
    cache_key = f"opportunity_radar:v15:{country_code}:{limit}:{max_candidates or 'auto'}"

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        return {
            "country_code": country_code,
            "generated_at": datetime.now().isoformat(),
            "market_regime": None,
            "universe_size": 0,
            "total_scanned": 0,
            "quote_available_count": 0,
            "detailed_scanned_count": 0,
            "actionable_count": 0,
            "bullish_count": 0,
            "universe_source": "fallback",
            "universe_note": "",
            "opportunities": [],
        }

    async def _build_response() -> dict:
        primary_index = country.indices[0]
        index_history = await yfinance_client.get_price_history(primary_index.ticker, period="6mo")
        macro_snapshot = await ecos_client.get_kr_economic_snapshot() if country_code == "KR" else {}
        kosis_snapshot = await kosis_client.get_kr_macro_snapshot() if country_code == "KR" else {}
        regime_forecast = forecast_next_day(
            ticker=primary_index.ticker,
            name=primary_index.name,
            country_code=country_code,
            price_history=index_history,
            benchmark_history=index_history,
            macro_snapshot=macro_snapshot,
            kosis_snapshot=kosis_snapshot,
            asset_type="index",
        )
        market_regime = build_market_regime(
            country_code=country_code,
            name=primary_index.name,
            price_history=index_history,
            next_day_forecast=regime_forecast,
        )

        universe_selection = await resolve_opportunity_universe(country_code)
        quote_screen = await _build_quote_screen(
            country_code=country_code,
            universe_selection=universe_selection,
            market_regime=market_regime,
        )
        ranked_quotes = list(quote_screen.get("ranked") or [])
        detail_budget = _resolve_detail_candidate_budget(
            limit=limit,
            available=len(ranked_quotes),
            max_candidates=max_candidates,
        )
        candidates: list[tuple[str, str]] = [
            (item["sector"], item["ticker"])
            for item in ranked_quotes[:detail_budget]
        ]
        lightweight_candidates: list[tuple[str, str]] = candidates or _flatten_universe(universe_selection.sectors)

        async def _scan(candidate: tuple[str, str]) -> OpportunityItem | None:
            sector, ticker = candidate
            snapshot = await asyncio.wait_for(
                yfinance_client.get_market_snapshot(ticker, period="6mo"),
                timeout=OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS,
            )
            if not snapshot.get("valid"):
                return None

            info, prices, analyst_raw = await asyncio.gather(
                asyncio.wait_for(yfinance_client.get_stock_info(ticker), timeout=OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS),
                asyncio.wait_for(yfinance_client.get_price_history(ticker, period="6mo"), timeout=OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS),
                asyncio.wait_for(yfinance_client.get_analyst_ratings(ticker), timeout=OPPORTUNITY_CANDIDATE_TIMEOUT_SECONDS),
            )
            current_price = float(info.get("current_price") or snapshot.get("current_price") or 0)
            if current_price <= 0 or len(prices) < 40:
                return None

            quant_score = score_stock(info, price_hist=prices, analyst_counts=analyst_raw)
            buy_sell = build_quick_buy_sell(info)
            technical: TechnicalIndicators = _calc_technicals(prices)
            forecast = forecast_next_day(
                ticker=ticker,
                name=info.get("name", ticker),
                country_code=country_code,
                price_history=prices,
                analyst_context={
                    **analyst_raw,
                    "target_mean": info.get("target_mean"),
                    "target_median": info.get("target_median"),
                    "target_high": info.get("target_high"),
                    "target_low": info.get("target_low"),
                },
                context_bias=((quant_score.total - 50.0) / 50.0) + (0.18 if market_regime.stance == "risk_on" else -0.18 if market_regime.stance == "risk_off" else 0.0),
                asset_type="stock",
                benchmark_history=index_history,
                macro_snapshot=macro_snapshot,
                kosis_snapshot=kosis_snapshot,
                fundamental_context=info,
            )
            distributional_forecast = build_distributional_forecast(
                price_history=prices,
                benchmark_history=index_history,
                macro_snapshot=macro_snapshot,
                kosis_snapshot=kosis_snapshot,
                analyst_context={
                    **analyst_raw,
                    "target_mean": info.get("target_mean"),
                    "target_median": info.get("target_median"),
                    "target_high": info.get("target_high"),
                    "target_low": info.get("target_low"),
                },
                fundamental_context=info,
                asset_type="stock",
            )
            price_points = [PricePoint(**point) for point in prices]
            trade_plan = build_trade_plan(
                ticker=ticker,
                current_price=current_price,
                price_history=price_points,
                technical=technical,
                buy_sell_guide=buy_sell,
                next_day_forecast=forecast,
                market_regime=market_regime,
            )

            prev_close = float(info.get("prev_close") or current_price)
            change_pct = ((current_price - prev_close) / prev_close * 100.0) if prev_close else 0.0
            valuation_gap = ((buy_sell.fair_value / current_price) - 1.0) * 100.0 if current_price else 0.0
            scenario_snapshot = _scenario_snapshot(forecast)
            horizon_20 = build_horizon_snapshot(
                distributional_forecast,
                horizon_days=20,
                country_code=country_code,
            )
            expected_return_pct_20d = float(horizon_20.get("expected_return_pct") or forecast.predicted_return_pct)
            expected_excess_return_pct_20d = float(horizon_20.get("expected_excess_return_pct") or 0.0)
            median_return_pct_20d = float(horizon_20.get("median_return_pct") or expected_return_pct_20d)
            forecast_volatility_pct_20d = float(horizon_20.get("forecast_volatility_pct") or 0.0)
            up_probability_20d = float(horizon_20.get("up_probability") or forecast.up_probability)
            flat_probability_20d = float(horizon_20.get("flat_probability") or 0.0)
            down_probability_20d = float(horizon_20.get("down_probability") or max(100.0 - up_probability_20d, 0.0))
            distribution_confidence_20d = float(horizon_20.get("confidence") or forecast.confidence)
            price_q25_20d = horizon_20.get("price_q25")
            price_q50_20d = horizon_20.get("price_q50")
            price_q75_20d = horizon_20.get("price_q75")
            signal_profile = build_distributional_signal_profile(
                current_price=current_price,
                bull_case_price=price_q75_20d or scenario_snapshot["bull_case_price"],
                base_case_price=price_q50_20d or scenario_snapshot["base_case_price"],
                bear_case_price=price_q25_20d or scenario_snapshot["bear_case_price"],
                bull_probability=up_probability_20d or scenario_snapshot["bull_probability"],
                base_probability=flat_probability_20d or scenario_snapshot["base_probability"],
                bear_probability=down_probability_20d or scenario_snapshot["bear_probability"],
                predicted_return_pct=expected_return_pct_20d,
                up_probability=up_probability_20d,
                confidence=distribution_confidence_20d,
            )
            opportunity_score = (
                signal_profile["directional_score"] * 0.58
                + quant_score.total * 0.14
                + min(max(trade_plan.risk_reward_estimate, 0.0), 4.0) * 5.5
                + signal_profile["expected_return_pct"] * 4.8
                + signal_profile["probability_edge"] * 0.18
                + signal_profile["tail_ratio"] * 2.8
                + (5.0 if market_regime.stance == "risk_on" else -3.5 if market_regime.stance == "risk_off" else 1.0)
                + (4.0 if current_price <= buy_sell.buy_zone_high * 1.02 else 1.0)
                + _clip(valuation_gap, -20.0, 20.0) * 0.12
            )
            execution_bias_bonus = {
                "press_long": 7.0,
                "lean_long": 4.0,
                "stay_selective": 1.0,
                "reduce_risk": -4.0,
                "capital_preservation": -8.0,
            }.get(forecast.execution_bias, 0.0)
            opportunity_score += execution_bias_bonus
            opportunity_score -= len(forecast.risk_flags[:2]) * 1.2
            opportunity_score = round(_clip(opportunity_score, 0.0, 100.0), 1)
            regime_tailwind = "tailwind" if market_regime.stance == "risk_on" else "headwind" if market_regime.stance == "risk_off" else "mixed"

            return OpportunityItem(
                rank=0,
                ticker=ticker,
                name=info.get("name") or snapshot.get("name") or ticker,
                sector=sector,
                country_code=country_code,
                current_price=round(current_price, 2),
                change_pct=round(change_pct, 2),
                opportunity_score=opportunity_score,
                quant_score=round(quant_score.total, 1),
                up_probability=round(up_probability_20d, 1),
                confidence=round(distribution_confidence_20d, 1),
                predicted_return_pct=round(expected_return_pct_20d, 2),
                target_horizon_days=20,
                target_date_20d=horizon_20.get("target_date"),
                expected_return_pct_20d=round(expected_return_pct_20d, 2),
                expected_excess_return_pct_20d=round(expected_excess_return_pct_20d, 2),
                median_return_pct_20d=round(median_return_pct_20d, 2),
                forecast_volatility_pct_20d=round(forecast_volatility_pct_20d, 2),
                up_probability_20d=round(up_probability_20d, 1),
                flat_probability_20d=round(flat_probability_20d, 1),
                down_probability_20d=round(down_probability_20d, 1),
                distribution_confidence_20d=round(distribution_confidence_20d, 1),
                price_q25_20d=round(float(price_q25_20d), 2) if price_q25_20d is not None else None,
                price_q50_20d=round(float(price_q50_20d), 2) if price_q50_20d is not None else None,
                price_q75_20d=round(float(price_q75_20d), 2) if price_q75_20d is not None else None,
                bull_case_price=round(float(price_q75_20d), 2) if price_q75_20d is not None else scenario_snapshot["bull_case_price"],
                base_case_price=round(float(price_q50_20d), 2) if price_q50_20d is not None else scenario_snapshot["base_case_price"],
                bear_case_price=round(float(price_q25_20d), 2) if price_q25_20d is not None else scenario_snapshot["bear_case_price"],
                bull_probability=round(up_probability_20d, 1),
                base_probability=round(flat_probability_20d, 1),
                bear_probability=round(down_probability_20d, 1),
                setup_label=trade_plan.setup_label,
                action=trade_plan.action,
                execution_bias=forecast.execution_bias,
                execution_note=forecast.execution_note,
                regime_tailwind=regime_tailwind,
                entry_low=trade_plan.entry_low,
                entry_high=trade_plan.entry_high,
                stop_loss=trade_plan.stop_loss,
                take_profit_1=trade_plan.take_profit_1,
                take_profit_2=trade_plan.take_profit_2,
                risk_reward_estimate=trade_plan.risk_reward_estimate,
                thesis=trade_plan.thesis[:2],
                risk_flags=forecast.risk_flags[:2],
                forecast_date=horizon_20.get("target_date") or forecast.target_date,
            )

        detailed_ranked: list[OpportunityItem] = []
        quote_only_ranked = _build_quote_only_opportunities(
            ranked_quotes=ranked_quotes,
            country_code=country_code,
            market_regime=market_regime,
            limit=max(limit, min(detail_budget, MAX_DETAILED_OPPORTUNITY_CANDIDATES)),
        )

        def _rank_items(items: list[OpportunityItem]) -> list[OpportunityItem]:
            items.sort(key=lambda item: item.opportunity_score, reverse=True)
            return [item.model_copy(update={"rank": idx}) for idx, item in enumerate(items[:limit], start=1)]

        def _merge_items(primary: list[OpportunityItem], secondary: list[OpportunityItem]) -> list[OpportunityItem]:
            merged: list[OpportunityItem] = []
            seen: set[str] = set()
            for item in [*primary, *secondary]:
                if item.ticker in seen:
                    continue
                seen.add(item.ticker)
                merged.append(item)
                if len(merged) >= limit:
                    break
            return [item.model_copy(update={"rank": idx}) for idx, item in enumerate(merged[:limit], start=1)]

        if not _should_skip_detailed_scan(
            country_code=country_code,
            universe_source=universe_selection.source,
            ranked_count=len(ranked_quotes),
            limit=limit,
        ):
            try:
                scanned = await asyncio.wait_for(
                    gather_limited(candidates, _scan, limit=OPPORTUNITY_CONCURRENCY),
                    timeout=OPPORTUNITY_SCAN_TIMEOUT_SECONDS,
                )
                opportunities = [item for item in scanned if not isinstance(item, Exception) and item is not None]
                detailed_ranked = _rank_items(opportunities)
            except asyncio.TimeoutError:
                detailed_ranked = []

        ranked = _merge_items(detailed_ranked, quote_only_ranked)
        if not ranked:
            ranked = await _build_lightweight_opportunities(
                candidates=lightweight_candidates,
                country_code=country_code,
                market_regime=market_regime,
                limit=limit,
            )

        resolved_universe_size = int(quote_screen.get("universe_size") or len(_flatten_universe(universe_selection.sectors)))
        scanned_count = int(quote_screen.get("scanned_count") or resolved_universe_size)
        resolved_universe_note = universe_selection.note
        if universe_selection.source == "fallback" and resolved_universe_size > 0:
            scope_hint = f"현재 레이더는 운영용 기본 종목군 {resolved_universe_size}개를 1차 스캔합니다."
            if scope_hint not in resolved_universe_note:
                resolved_universe_note = f"{resolved_universe_note} {scope_hint}".strip()
        if _should_skip_detailed_scan(
            country_code=country_code,
            universe_source=universe_selection.source,
            ranked_count=len(ranked_quotes),
            limit=limit,
        ):
            skip_hint = "운영 환경에서는 응답 안정성을 위해 1차 스캔 상위 후보를 우선 반환합니다."
            if skip_hint not in resolved_universe_note:
                resolved_universe_note = f"{resolved_universe_note} {skip_hint}".strip()

        return OpportunityRadarResponse(
            country_code=country_code,
            generated_at=datetime.now().isoformat(),
            market_regime=market_regime,
            universe_size=resolved_universe_size,
            total_scanned=scanned_count,
            quote_available_count=int(quote_screen.get("quote_available_count") or 0),
            detailed_scanned_count=len(detailed_ranked),
            actionable_count=sum(1 for item in ranked if item.action != "avoid"),
            bullish_count=sum(1 for item in ranked if (item.up_probability_20d or item.up_probability) >= 55),
            universe_source=universe_selection.source,
            universe_note=resolved_universe_note,
            opportunities=ranked,
        ).model_dump()

    return await cache.get_or_fetch(cache_key, _build_response, ttl=900)


async def get_market_opportunities_quick(country_code: str, limit: int = 12) -> dict:
    country_code = country_code.upper()
    cache_key = f"opportunity_radar_quick:v2:{country_code}:{limit}"

    country = COUNTRY_REGISTRY.get(country_code)
    if not country:
        return {
            "country_code": country_code,
            "generated_at": datetime.now().isoformat(),
            "market_regime": None,
            "universe_size": 0,
            "total_scanned": 0,
            "quote_available_count": 0,
            "detailed_scanned_count": 0,
            "actionable_count": 0,
            "bullish_count": 0,
            "universe_source": "fallback",
            "universe_note": "",
            "opportunities": [],
        }

    async def _build_response() -> dict:
        market_regime = _build_placeholder_market_regime(
            country_code=country_code,
            index_name=country.indices[0].name,
            note="정밀 시장 국면 계산이 길어져 1차 시세 스캔 후보를 먼저 제공합니다.",
        )
        universe_selection = await _resolve_quick_opportunity_universe(country_code)
        quote_screen = await _build_quote_screen(
            country_code=country_code,
            universe_selection=universe_selection,
            market_regime=market_regime,
            max_pairs=QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP,
        )
        ranked_quotes = list(quote_screen.get("ranked") or [])
        scanned_count = int(quote_screen.get("scanned_count") or len(ranked_quotes))
        ranked = _build_quote_only_opportunities(
            ranked_quotes=ranked_quotes,
            country_code=country_code,
            market_regime=market_regime,
            limit=limit,
        )
        if not ranked:
            ranked = await _build_lightweight_opportunities(
                candidates=_flatten_universe(universe_selection.sectors)[: max(scanned_count, limit)],
                country_code=country_code,
                market_regime=market_regime,
                limit=limit,
            )

        resolved_universe_size = int(quote_screen.get("universe_size") or len(_flatten_universe(universe_selection.sectors)))
        note_parts = [universe_selection.note.strip()]
        if 0 < scanned_count < resolved_universe_size:
            note_parts.append(
                f"현재 응답은 전체 {resolved_universe_size}개 중 대표 1차 스캔 {scanned_count}개를 기준으로 먼저 계산했습니다."
            )
        note_parts.append("상세 분포 계산이 길어져 1차 시세 스캔 후보를 먼저 반환합니다.")
        note_parts.append("같은 조건으로 다시 열면 백그라운드 계산이 끝난 정밀 후보가 바로 보일 수 있습니다.")
        resolved_universe_note = " ".join(part for part in note_parts if part).strip()

        return OpportunityRadarResponse(
            country_code=country_code,
            generated_at=datetime.now().isoformat(),
            market_regime=market_regime,
            universe_size=resolved_universe_size,
            total_scanned=scanned_count,
            quote_available_count=int(quote_screen.get("quote_available_count") or 0),
            detailed_scanned_count=0,
            actionable_count=sum(1 for item in ranked if item.action != "avoid"),
            bullish_count=sum(1 for item in ranked if (item.up_probability_20d or item.up_probability) >= 55),
            universe_source=universe_selection.source,
            universe_note=resolved_universe_note,
            opportunities=ranked,
        ).model_dump()

    return await cache.get_or_fetch(cache_key, _build_response, ttl=QUICK_OPPORTUNITY_CACHE_TTL_SECONDS)
