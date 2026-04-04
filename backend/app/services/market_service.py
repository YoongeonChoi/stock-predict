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
from app.data.universe_data import (
    UNIVERSE,
    UniverseSelection,
    resolve_opportunity_universe,
    resolve_universe,
)
from app.models.country import COUNTRY_REGISTRY
from app.models.market import OpportunityItem, OpportunityRadarResponse
from app.models.stock import PricePoint, TechnicalIndicators
from app.scoring.selection import regime_alignment_score, score_selection_candidate
from app.services.market.fallbacks import (
    build_placeholder_market_regime as _build_placeholder_market_regime,
    regime_tailwind_label as _regime_tailwind_label,
)
from app.services.market.quick_scan import (
    build_quote_only_opportunity_item as _build_quote_only_opportunity_item,
    resolve_detail_candidate_budget as _resolve_detail_candidate_budget,
    should_skip_detailed_scan as _should_skip_detailed_scan,
)
from app.services.market.shared import (
    clip as _clip,
    safe_float as _safe_float,
    scenario_snapshot as _scenario_snapshot,
)
from app.services.market.universe import (
    build_sector_lookup as _build_sector_lookup,
    build_seeded_quote_screen_from_quick_payload as _build_seeded_quote_screen_from_quick_payload,
    flatten_universe as _flatten_universe,
    sample_universe_pairs as _sample_universe_pairs,
)
from app.scoring.stock_scorer import score_stock
from app.services.portfolio_optimizer import build_horizon_snapshot
from app.utils.async_tools import gather_limited

OPPORTUNITY_SCAN_TIMEOUT_SECONDS = 6
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
QUOTE_SCREEN_CACHE_WAIT_TIMEOUT_SECONDS = 1.6
FULL_OPPORTUNITY_CACHE_WAIT_TIMEOUT_SECONDS = 3.0
QUICK_OPPORTUNITY_CACHE_WAIT_TIMEOUT_SECONDS = 2.5


def _can_reuse_quick_seed_payload(quick_seed_payload: dict | None, universe_selection) -> bool:
    if not quick_seed_payload:
        return False
    expected_source = str(getattr(universe_selection, "source", "") or "").strip()
    cached_source = str(quick_seed_payload.get("universe_source") or "").strip()
    if not expected_source or cached_source != expected_source:
        return False
    expected_size = len(_flatten_universe(getattr(universe_selection, "sectors", {}) or {}))
    cached_size = int(quick_seed_payload.get("universe_size") or 0)
    if expected_size <= 0 or cached_size <= 0:
        return False
    return expected_size == cached_size





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
            total_ranked=len(ranked_quotes),
            sector=item["sector"],
            ticker=item["ticker"],
            current_price=float(item["current_price"]),
            change_pct=float(item["change_pct"]),
            country_code=country_code,
            market_regime=market_regime,
        )
        for idx, item in enumerate(ranked_quotes[:limit], start=1)
    ]
    items.sort(
        key=lambda item: (
            item.opportunity_score,
            item.up_probability,
            item.change_pct,
            item.current_price,
        ),
        reverse=True,
    )
    return [item.model_copy(update={"rank": idx}) for idx, item in enumerate(items[:limit], start=1)]


async def _build_kr_representative_quote_only_opportunities(
    *,
    country_code: str,
    market_regime,
    universe_selection,
    limit: int,
) -> tuple[list[OpportunityItem], int]:
    representative_limit = max(limit * 6, 24)
    representative_quotes = await kr_market_quote_client.get_kr_representative_quotes(limit=representative_limit)
    if not representative_quotes:
        return [], 0

    sector_lookup = _build_sector_lookup(universe_selection.sectors)
    regime_bias = 0.75 if market_regime.stance == "risk_on" else -0.55 if market_regime.stance == "risk_off" else 0.0
    ranked_quotes: list[dict] = []
    for quote in representative_quotes.values():
        ticker = str(quote.get("ticker") or "").upper()
        current_price = _safe_float(quote.get("current_price"), 0.0)
        if current_price <= 0:
            continue
        change_pct = _safe_float(quote.get("change_pct"))
        ranked_quotes.append(
            {
                "sector": sector_lookup.get(ticker, "대표 후보"),
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "change_pct": round(change_pct, 2),
                "quick_score": round(change_pct * 2.2 + regime_bias, 4),
            }
        )

    if not ranked_quotes:
        return [], 0

    ranked_quotes.sort(key=lambda item: (item["quick_score"], item["change_pct"]), reverse=True)
    return (
        _build_quote_only_opportunities(
            ranked_quotes=ranked_quotes,
            country_code=country_code,
            market_regime=market_regime,
            limit=limit,
        ),
        len(ranked_quotes),
    )


def _quick_opportunity_cache_key(country_code: str, limit: int) -> str:
    return f"opportunity_radar_quick:v2:{country_code.upper()}:{int(limit)}"


def _normalize_cached_quick_payload(payload: dict, *, requested_limit: int) -> dict:
    normalized = dict(payload)
    opportunities = list(normalized.get("opportunities") or [])
    clipped = opportunities[: max(int(requested_limit), 1)]
    normalized["opportunities"] = clipped
    normalized["actionable_count"] = sum(1 for item in clipped if item.get("action") != "avoid")
    normalized["bullish_count"] = sum(
        1
        for item in clipped
        if float(item.get("up_probability_20d") or item.get("up_probability") or 0.0) >= 55.0
    )
    return normalized


def _cached_quick_limit_candidates(limit: int) -> list[int]:
    candidates: list[int] = []
    for candidate in [limit, 12, 8, 20, 24, 10, 6, 5]:
        normalized = max(int(candidate), 1)
        if normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _empty_quote_screen(universe_size: int, scanned_count: int) -> dict:
    return {
        "universe_size": int(universe_size),
        "scanned_count": int(scanned_count),
        "quote_available_count": 0,
        "ranked": [],
    }


def _build_opportunity_snapshot_id(
    *,
    country_code: str,
    fallback_tier: str,
    generated_at: str,
) -> str:
    normalized = (
        generated_at.replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("T", "")
    )
    return f"{country_code.upper()}:{fallback_tier}:{normalized}"


def _full_opportunity_cache_key(
    country_code: str,
    limit: int,
    *,
    max_candidates: int | None = None,
) -> str:
    return f"opportunity_radar:v16:{country_code.upper()}:{int(limit)}:{max_candidates or 'auto'}"


async def _build_quote_screen(
    *,
    country_code: str,
    universe_selection,
    market_regime,
    max_pairs: int | None = None,
) -> dict:
    full_universe_pairs = _flatten_universe(universe_selection.sectors)
    if max_pairs is not None and max_pairs > 0:
        universe_pairs = _sample_universe_pairs(universe_selection.sectors, max_pairs)
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

    return await cache.get_or_fetch(
        cache_key,
        _fetch_quotes,
        ttl=900,
        wait_timeout=QUOTE_SCREEN_CACHE_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=lambda: _empty_quote_screen(
            universe_size=len(full_universe_pairs),
            scanned_count=len(universe_pairs),
        ),
    )


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


def _with_quote_recovery_note(selection: UniverseSelection) -> UniverseSelection:
    recovery_note = (
        "KRX 전종목 1차 시세 확보가 비어 응답 안정성이 검증된 대체 종목군으로 즉시 전환했습니다."
    )
    note = f"{selection.note} {recovery_note}".strip() if selection.note else recovery_note
    return UniverseSelection(
        sectors=selection.sectors,
        source=selection.source,
        note=note,
    )


def _with_sampled_quote_recovery_note(selection: UniverseSelection, sample_size: int) -> UniverseSelection:
    recovery_note = (
        f"전종목 시세 확보가 계속 비어 대표 종목 {sample_size}개를 분산 샘플링한 1차 후보 화면으로 즉시 축소했습니다."
    )
    note = f"{selection.note} {recovery_note}".strip() if selection.note else recovery_note
    return UniverseSelection(
        sectors=selection.sectors,
        source=selection.source,
        note=note,
    )


async def _resolve_resilient_quote_screen(
    *,
    country_code: str,
    universe_selection,
    market_regime,
    max_pairs: int | None = None,
) -> tuple[UniverseSelection | SimpleNamespace, dict]:
    quote_screen = await _build_quote_screen(
        country_code=country_code,
        universe_selection=universe_selection,
        market_regime=market_regime,
        max_pairs=max_pairs,
    )
    if (
        country_code != "KR"
        or universe_selection.source != "krx_listing"
        or int(quote_screen.get("quote_available_count") or 0) > 0
    ):
        return universe_selection, quote_screen

    fallback_selection = _with_quote_recovery_note(await resolve_universe(country_code))
    fallback_quote_screen = await _build_quote_screen(
        country_code=country_code,
        universe_selection=fallback_selection,
        market_regime=market_regime,
        max_pairs=max_pairs,
    )
    if (
        country_code == "KR"
        and max_pairs is None
        and int(fallback_quote_screen.get("quote_available_count") or 0) <= 0
    ):
        sampled_selection = _with_sampled_quote_recovery_note(
            fallback_selection,
            QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP,
        )
        sampled_quote_screen = await _build_quote_screen(
            country_code=country_code,
            universe_selection=sampled_selection,
            market_regime=market_regime,
            max_pairs=QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP,
        )
        if int(sampled_quote_screen.get("quote_available_count") or 0) > 0:
            return sampled_selection, sampled_quote_screen
    return fallback_selection, fallback_quote_screen


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
    cache_key = _full_opportunity_cache_key(
        country_code,
        limit,
        max_candidates=max_candidates,
    )

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

        quick_seed_limit = max(limit * 2, MIN_DETAILED_OPPORTUNITY_CANDIDATES)
        universe_selection = await resolve_opportunity_universe(country_code)
        quick_seed_payload = await get_cached_market_opportunities_quick(country_code, quick_seed_limit)
        seeded_quick = None
        if _can_reuse_quick_seed_payload(quick_seed_payload, universe_selection):
            seeded_quick = _build_seeded_quote_screen_from_quick_payload(
                quick_seed_payload,
                candidate_limit=quick_seed_limit,
            )
        if seeded_quick is not None:
            universe_selection, quote_screen = seeded_quick
        else:
            universe_selection, quote_screen = await _resolve_resilient_quote_screen(
                country_code=country_code,
                universe_selection=universe_selection,
                market_regime=market_regime,
            )
        ranked_quotes = list(quote_screen.get("ranked") or [])
        detail_budget = _resolve_detail_candidate_budget(
            limit=limit,
            available=len(ranked_quotes),
            max_candidates=max_candidates,
            min_candidates=MIN_DETAILED_OPPORTUNITY_CANDIDATES,
            large_universe_cap=LARGE_UNIVERSE_DETAILED_SCAN_CAP,
            max_detailed_candidates=MAX_DETAILED_OPPORTUNITY_CANDIDATES,
        )
        candidates: list[tuple[str, str]] = [
            (item["sector"], item["ticker"])
            for item in ranked_quotes[:detail_budget]
        ]
        lightweight_candidates: list[tuple[str, str]] = (
            candidates
            or _sample_universe_pairs(universe_selection.sectors, LIGHTWEIGHT_OPPORTUNITY_MAX_CANDIDATES)
        )

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
            raw_confidence_20d = horizon_20.get("raw_confidence")
            calibrated_probability_20d = horizon_20.get("calibrated_probability")
            probability_edge_20d = horizon_20.get("probability_edge")
            analog_support_20d = horizon_20.get("analog_support")
            regime_support_20d = horizon_20.get("regime_support")
            agreement_support_20d = horizon_20.get("agreement_support")
            data_quality_support_20d = horizon_20.get("data_quality_support")
            volatility_ratio_20d = horizon_20.get("volatility_ratio")
            confidence_calibrator_20d = horizon_20.get("confidence_calibrator")
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
            regime_tailwind = "tailwind" if market_regime.stance == "risk_on" else "headwind" if market_regime.stance == "risk_off" else "mixed"
            selection = score_selection_candidate(
                expected_excess_return_pct=expected_excess_return_pct_20d,
                calibrated_confidence=distribution_confidence_20d,
                probability_edge=signal_profile["probability_edge"],
                tail_ratio=signal_profile["tail_ratio"],
                regime_alignment=regime_alignment_score(
                    regime_tailwind=regime_tailwind,
                    market_stance=market_regime.stance,
                ),
                analog_support=analog_support_20d,
                data_quality_support=data_quality_support_20d,
                downside_pct=signal_profile["downside_pct"],
                forecast_volatility_pct=forecast_volatility_pct_20d,
                action=trade_plan.action,
                execution_bias=forecast.execution_bias,
                legacy_score=(
                    float(quant_score.total)
                    + min(max(trade_plan.risk_reward_estimate, 0.0), 4.0) * 6.0
                    + max(_clip(valuation_gap, -20.0, 20.0), 0.0) * 0.12
                ),
            )
            opportunity_score = selection.score

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
                raw_confidence_20d=round(float(raw_confidence_20d), 1) if raw_confidence_20d is not None else None,
                calibrated_probability_20d=round(float(calibrated_probability_20d), 4) if calibrated_probability_20d is not None else None,
                probability_edge_20d=round(float(probability_edge_20d), 4) if probability_edge_20d is not None else None,
                analog_support_20d=round(float(analog_support_20d), 4) if analog_support_20d is not None else None,
                regime_support_20d=round(float(regime_support_20d), 4) if regime_support_20d is not None else None,
                agreement_support_20d=round(float(agreement_support_20d), 4) if agreement_support_20d is not None else None,
                data_quality_support_20d=round(float(data_quality_support_20d), 4) if data_quality_support_20d is not None else None,
                volatility_ratio_20d=round(float(volatility_ratio_20d), 4) if volatility_ratio_20d is not None else None,
                confidence_calibrator_20d=confidence_calibrator_20d,
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
            quote_only_threshold=LARGE_UNIVERSE_QUOTE_ONLY_THRESHOLD,
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
            quote_only_threshold=LARGE_UNIVERSE_QUOTE_ONLY_THRESHOLD,
        ):
            skip_hint = "운영 환경에서는 응답 안정성을 위해 1차 스캔 상위 후보를 우선 반환합니다."
            if skip_hint not in resolved_universe_note:
                resolved_universe_note = f"{resolved_universe_note} {skip_hint}".strip()

        generated_at = datetime.now().isoformat()
        return OpportunityRadarResponse(
            country_code=country_code,
            snapshot_id=_build_opportunity_snapshot_id(
                country_code=country_code,
                fallback_tier="full",
                generated_at=generated_at,
            ),
            generated_at=generated_at,
            fallback_tier="full",
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

    async def _timeout_fallback() -> dict:
        cached_quick = await get_cached_market_opportunities_quick(country_code, limit)
        if cached_quick:
            return cached_quick
        return build_market_opportunities_placeholder(
            country_code,
            note="정밀 후보 계산 캐시를 기다리는 중이라 최근 usable quick 후보 또는 시장 국면만 먼저 표시합니다.",
        )

    return await cache.get_or_fetch(
        cache_key,
        _build_response,
        ttl=900,
        wait_timeout=FULL_OPPORTUNITY_CACHE_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=_timeout_fallback,
    )


async def get_market_opportunities_quick(country_code: str, limit: int = 12) -> dict:
    country_code = country_code.upper()
    cache_key = _quick_opportunity_cache_key(country_code, limit)

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
        quote_screen = {
            "universe_size": len(_flatten_universe(universe_selection.sectors)),
            "scanned_count": 0,
            "quote_available_count": 0,
            "ranked": [],
        }
        ranked: list[OpportunityItem] = []
        representative_scanned_count = 0
        if country_code == "KR":
            ranked, representative_scanned_count = await _build_kr_representative_quote_only_opportunities(
                country_code=country_code,
                market_regime=market_regime,
                universe_selection=universe_selection,
                limit=limit,
            )
        if not ranked:
            universe_selection, quote_screen = await _resolve_resilient_quote_screen(
                country_code=country_code,
                universe_selection=universe_selection,
                market_regime=market_regime,
                max_pairs=QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP,
            )
            ranked_quotes = list(quote_screen.get("ranked") or [])
            ranked = _build_quote_only_opportunities(
                ranked_quotes=ranked_quotes,
                country_code=country_code,
                market_regime=market_regime,
                limit=limit,
            )
        scanned_count = int(quote_screen.get("scanned_count") or 0)
        if representative_scanned_count > 0:
            scanned_count = representative_scanned_count
        if not ranked:
            ranked = await _build_lightweight_opportunities(
                candidates=_sample_universe_pairs(
                    universe_selection.sectors,
                    max(limit, LIGHTWEIGHT_OPPORTUNITY_MAX_CANDIDATES),
                ),
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
        if representative_scanned_count > 0:
            note_parts.append(
                f"yfinance quick 시세가 비어 KOSPI/KOSDAQ 대표 시총 페이지 기준 {representative_scanned_count}개 1차 후보로 즉시 전환했습니다."
            )
        note_parts.append("상세 분포 계산이 길어져 1차 시세 스캔 후보를 먼저 반환합니다.")
        note_parts.append("같은 화면을 다시 열면 fresh quick 스냅샷과 정밀 후보 계산을 새로 시도합니다.")
        resolved_universe_note = " ".join(part for part in note_parts if part).strip()
        resolved_quote_available_count = int(quote_screen.get("quote_available_count") or 0)
        if representative_scanned_count > 0:
            resolved_quote_available_count = max(resolved_quote_available_count, representative_scanned_count)

        generated_at = datetime.now().isoformat()
        return OpportunityRadarResponse(
            country_code=country_code,
            snapshot_id=_build_opportunity_snapshot_id(
                country_code=country_code,
                fallback_tier="quick",
                generated_at=generated_at,
            ),
            generated_at=generated_at,
            fallback_tier="quick",
            market_regime=market_regime,
            universe_size=resolved_universe_size,
            total_scanned=scanned_count,
            quote_available_count=resolved_quote_available_count,
            detailed_scanned_count=0,
            actionable_count=sum(1 for item in ranked if item.action != "avoid"),
            bullish_count=sum(1 for item in ranked if (item.up_probability_20d or item.up_probability) >= 55),
            universe_source=universe_selection.source,
            universe_note=resolved_universe_note,
            opportunities=ranked,
        ).model_dump()

    async def _timeout_fallback() -> dict:
        cached_quick = await get_cached_market_opportunities_quick(country_code, limit)
        if cached_quick:
            return cached_quick
        return build_market_opportunities_placeholder(
            country_code,
            note="빠른 후보 캐시를 기다리는 중이라 이번 응답에서는 시장 국면만 먼저 표시합니다.",
        )

    return await cache.get_or_fetch(
        cache_key,
        _build_response,
        ttl=QUICK_OPPORTUNITY_CACHE_TTL_SECONDS,
        wait_timeout=QUICK_OPPORTUNITY_CACHE_WAIT_TIMEOUT_SECONDS,
        timeout_fallback=_timeout_fallback,
    )


async def get_cached_market_opportunities_quick(country_code: str, limit: int = 12) -> dict | None:
    for candidate_limit in _cached_quick_limit_candidates(limit):
        cached = await cache.get(_quick_opportunity_cache_key(country_code, candidate_limit))
        if not cached:
            continue
        opportunities = list(cached.get("opportunities") or [])
        quote_available_count = int(cached.get("quote_available_count") or 0)
        if quote_available_count <= 0 or not opportunities:
            continue
        normalized = _normalize_cached_quick_payload(cached, requested_limit=limit)
        if candidate_limit != limit:
            existing_note = str(normalized.get("universe_note") or "").strip()
            reused_note = "이번 응답은 최근 usable quick 후보를 먼저 재사용했습니다."
            normalized["universe_note"] = " ".join(
                part for part in [existing_note, reused_note] if part
            ).strip()
        return normalized
    return None


async def get_cached_market_opportunities(
    country_code: str,
    limit: int = 12,
    *,
    max_candidates: int | None = None,
) -> dict | None:
    cached = await cache.get(
        _full_opportunity_cache_key(
            country_code,
            limit,
            max_candidates=max_candidates,
        )
    )
    if not cached:
        return None
    opportunities = list(cached.get("opportunities") or [])
    quote_available_count = int(cached.get("quote_available_count") or 0)
    detailed_scanned_count = int(cached.get("detailed_scanned_count") or 0)
    if quote_available_count <= 0 or not opportunities or detailed_scanned_count <= 0:
        return None
    return cached


def build_market_opportunities_placeholder(country_code: str, *, note: str) -> dict:
    country_code = country_code.upper()
    country = COUNTRY_REGISTRY.get(country_code)
    index_name = country.indices[0].name if country and country.indices else country_code
    fallback_universe = UNIVERSE.get(country_code, {})
    fallback_universe_size = len(_flatten_universe(fallback_universe))
    placeholder_note = note.strip() or "대표 1차 스캔 준비가 길어져 현재는 시장 국면만 먼저 표시합니다."
    generated_at = datetime.now().isoformat()
    return OpportunityRadarResponse(
        country_code=country_code,
        snapshot_id=_build_opportunity_snapshot_id(
            country_code=country_code,
            fallback_tier="placeholder",
            generated_at=generated_at,
        ),
        generated_at=generated_at,
        fallback_tier="placeholder",
        market_regime=_build_placeholder_market_regime(
            country_code=country_code,
            index_name=index_name,
            note=placeholder_note,
        ),
        universe_size=fallback_universe_size,
        total_scanned=0,
        quote_available_count=0,
        detailed_scanned_count=0,
        actionable_count=0,
        bullish_count=0,
        universe_source="fallback",
        universe_note=placeholder_note,
        opportunities=[],
    ).model_dump()
