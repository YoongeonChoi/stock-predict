import asyncio
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import pandas as pd
from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator, CCIIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.volatility import BollingerBands
from app.analysis.stock_analyzer import (
    analyze_stock,
    build_quick_stock_detail,
    get_cached_quick_stock_detail,
    get_cached_stock_detail,
)
from app.data import yfinance_client, cache
from app.services import archive_service, ticker_resolver_service, forecast_monitor_service
from app.errors import SP_3003, SP_6003, SP_2005, SP_5002, SP_5010, SP_5014, SP_5018

router = APIRouter(prefix="/api", tags=["stock"])
logger = logging.getLogger(__name__)
STOCK_DETAIL_TIMEOUT_SECONDS = 12.0
_STOCK_DETAIL_REFRESH_TASKS: dict[str, asyncio.Task] = {}


def _resolve_kr_ticker(ticker: str) -> str:
    return ticker_resolver_service.resolve_ticker(ticker, "KR")["ticker"] or ticker.upper()


def _build_partial_stock_detail(cached: dict, *, error_code: str | None, fallback_reason: str) -> dict:
    partial = dict(cached)
    errors = list(partial.get("errors") or [])
    if error_code and error_code not in errors:
        errors.append(error_code)
    partial["errors"] = errors
    partial["partial"] = True
    partial["fallback_reason"] = fallback_reason
    partial["generated_at"] = partial.get("generated_at") or datetime.now(timezone.utc).isoformat()
    return partial


async def _archive_stock_report(detail: dict, ticker: str) -> None:
    try:
        await archive_service.save_report("stock", detail, ticker=ticker)
    except Exception as exc:
        SP_5002(str(exc)[:100]).log()


def _schedule_stock_detail_refresh(ticker: str) -> None:
    existing = _STOCK_DETAIL_REFRESH_TASKS.get(ticker)
    if existing and not existing.done():
        return

    async def _run_refresh() -> None:
        try:
            detail = await analyze_stock(ticker)
            await _archive_stock_report(detail, ticker)
        except Exception as exc:
            logger.warning("stock detail background refresh failed for %s: %s", ticker, str(exc)[:180])
        finally:
            _STOCK_DETAIL_REFRESH_TASKS.pop(ticker, None)

    _STOCK_DETAIL_REFRESH_TASKS[ticker] = asyncio.create_task(_run_refresh())


@router.get("/stock/{ticker}/detail")
async def get_stock_detail(ticker: str):
    ticker = _resolve_kr_ticker(ticker)
    cached = await get_cached_stock_detail(ticker, refresh_quote=False)
    if cached:
        return cached

    cached_quick = await get_cached_quick_stock_detail(ticker)
    if cached_quick:
        _schedule_stock_detail_refresh(ticker)
        return _build_partial_stock_detail(
            cached_quick,
            error_code=None,
            fallback_reason="stock_quick_detail",
        )

    try:
        detail = await asyncio.wait_for(build_quick_stock_detail(ticker), timeout=STOCK_DETAIL_TIMEOUT_SECONDS)
        if detail:
            _schedule_stock_detail_refresh(ticker)
            return _build_partial_stock_detail(
                detail,
                error_code=None,
                fallback_reason="stock_quick_detail",
            )
        detail = await asyncio.wait_for(analyze_stock(ticker), timeout=STOCK_DETAIL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        cached_quick = await get_cached_quick_stock_detail(ticker)
        if cached_quick:
            _schedule_stock_detail_refresh(ticker)
            return _build_partial_stock_detail(
                cached_quick,
                error_code="SP-5018",
                fallback_reason="stock_quick_detail",
            )
        cached = await get_cached_stock_detail(ticker, refresh_quote=False)
        if cached:
            return _build_partial_stock_detail(
                cached,
                error_code="SP-5018",
                fallback_reason="stock_cached_detail",
            )
        err = SP_5018(f"Stock detail timed out for {ticker}")
        err.log()
        return JSONResponse(status_code=504, content=err.to_dict())
    except Exception as e:
        cached_quick = await get_cached_quick_stock_detail(ticker)
        if cached_quick:
            _schedule_stock_detail_refresh(ticker)
            return _build_partial_stock_detail(
                cached_quick,
                error_code="SP-3003",
                fallback_reason="stock_quick_detail",
            )
        cached = await get_cached_stock_detail(ticker, refresh_quote=False)
        if cached:
            return _build_partial_stock_detail(
                cached,
                error_code="SP-3003",
                fallback_reason="stock_cached_detail",
            )
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())

    asyncio.create_task(_archive_stock_report(detail, ticker))

    return detail


@router.get("/stock/{ticker}/chart")
async def get_stock_chart(ticker: str, period: str = "3mo"):
    ticker = _resolve_kr_ticker(ticker)
    allowed = {"1mo", "3mo", "6mo", "1y", "2y"}
    if period not in allowed:
        err = SP_6003()
        err.log()
        return JSONResponse(status_code=400, content=err.to_dict())

    prices = await yfinance_client.get_price_history(ticker, period)
    if not prices:
        err = SP_2005(ticker)
        err.log()
        return JSONResponse(status_code=404, content=err.to_dict())

    return {"ticker": ticker, "period": period, "data": prices}


def _determine_signal(buy: int, neutral: int, sell: int) -> str:
    if buy > sell * 1.5:
        return "Strong Buy"
    if buy > sell:
        return "Buy"
    if sell > buy * 1.5:
        return "Strong Sell"
    if sell > buy:
        return "Sell"
    return "Neutral"


@router.get("/stock/{ticker}/technical-summary")
async def get_technical_summary(ticker: str):
    ticker = _resolve_kr_ticker(ticker)
    cache_key = f"tech_summary:{ticker}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        prices = await yfinance_client.get_price_history(ticker, "6mo")
        if not prices:
            err = SP_2005(ticker)
            err.log()
            return JSONResponse(status_code=404, content=err.to_dict())

        df = pd.DataFrame(prices)
        close = df["close"]
        high = df["high"]
        low = df["low"]
        current_price = close.iloc[-1]

        ma_results = []
        for period in [5, 10, 20, 50, 100, 200]:
            if len(close) < period:
                continue
            sma_val = SMAIndicator(close, window=period).sma_indicator().iloc[-1]
            ema_val = EMAIndicator(close, window=period).ema_indicator().iloc[-1]

            sma_signal = "Buy" if current_price > sma_val else ("Sell" if current_price < sma_val else "Neutral")
            ema_signal = "Buy" if current_price > ema_val else ("Sell" if current_price < ema_val else "Neutral")

            ma_results.append({"name": f"SMA ({period})", "value": round(sma_val, 2), "signal": sma_signal})
            ma_results.append({"name": f"EMA ({period})", "value": round(ema_val, 2), "signal": ema_signal})

        oscillator_results = []

        rsi_val = RSIIndicator(close, window=14).rsi().iloc[-1]
        rsi_signal = "Buy" if rsi_val < 30 else ("Sell" if rsi_val > 70 else "Neutral")
        oscillator_results.append({"name": "RSI (14)", "value": round(rsi_val, 2), "signal": rsi_signal})

        macd_ind = MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_val = macd_ind.macd().iloc[-1]
        macd_signal_val = macd_ind.macd_signal().iloc[-1]
        macd_signal = "Buy" if macd_val > macd_signal_val else "Sell"
        oscillator_results.append({"name": "MACD (12,26,9)", "value": round(macd_val, 2), "signal": macd_signal})

        stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
        stoch_k = stoch.stoch().iloc[-1]
        stoch_d = stoch.stoch_signal().iloc[-1]
        stoch_signal = "Buy" if stoch_k < 20 else ("Sell" if stoch_k > 80 else "Neutral")
        oscillator_results.append({"name": "Stochastic %K (14,3)", "value": round(stoch_k, 2), "signal": stoch_signal})
        oscillator_results.append({"name": "Stochastic %D", "value": round(stoch_d, 2), "signal": stoch_signal})

        cci_val = CCIIndicator(high, low, close, window=20).cci().iloc[-1]
        cci_signal = "Buy" if cci_val < -100 else ("Sell" if cci_val > 100 else "Neutral")
        oscillator_results.append({"name": "CCI (20)", "value": round(cci_val, 2), "signal": cci_signal})

        adx_ind = ADXIndicator(high, low, close, window=14)
        adx_val = adx_ind.adx().iloc[-1]
        price_rising = close.iloc[-1] > close.iloc[-5] if len(close) >= 5 else True
        if adx_val > 25:
            adx_signal = "Buy" if price_rising else "Sell"
        else:
            adx_signal = "Neutral"
        oscillator_results.append({"name": "ADX (14)", "value": round(adx_val, 2), "signal": adx_signal})

        wr_val = WilliamsRIndicator(high, low, close, lbp=14).williams_r().iloc[-1]
        wr_signal = "Buy" if wr_val < -80 else ("Sell" if wr_val > -20 else "Neutral")
        oscillator_results.append({"name": "Williams %R (14)", "value": round(wr_val, 2), "signal": wr_signal})

        bb = BollingerBands(close, window=20, window_dev=2)
        bb_upper = bb.bollinger_hband().iloc[-1]
        bb_lower = bb.bollinger_lband().iloc[-1]
        bb_middle = bb.bollinger_mavg().iloc[-1]
        bb_signal = "Buy" if current_price < bb_lower else ("Sell" if current_price > bb_upper else "Neutral")
        oscillator_results.append({"name": "Bollinger Bands (20,2)", "value": round(bb_middle, 2), "signal": bb_signal})

        ma_buy = sum(1 for m in ma_results if m["signal"] == "Buy")
        ma_neutral = sum(1 for m in ma_results if m["signal"] == "Neutral")
        ma_sell = sum(1 for m in ma_results if m["signal"] == "Sell")

        osc_buy = sum(1 for o in oscillator_results if o["signal"] == "Buy")
        osc_neutral = sum(1 for o in oscillator_results if o["signal"] == "Neutral")
        osc_sell = sum(1 for o in oscillator_results if o["signal"] == "Sell")

        total_buy = ma_buy + osc_buy
        total_neutral = ma_neutral + osc_neutral
        total_sell = ma_sell + osc_sell

        result = {
            "ticker": ticker.upper(),
            "summary": {
                "overall": {
                    "buy": total_buy, "neutral": total_neutral, "sell": total_sell,
                    "signal": _determine_signal(total_buy, total_neutral, total_sell),
                },
                "moving_averages": {
                    "buy": ma_buy, "neutral": ma_neutral, "sell": ma_sell,
                    "signal": _determine_signal(ma_buy, ma_neutral, ma_sell),
                },
                "oscillators": {
                    "buy": osc_buy, "neutral": osc_neutral, "sell": osc_sell,
                    "signal": _determine_signal(osc_buy, osc_neutral, osc_sell),
                },
            },
            "moving_averages": ma_results,
            "oscillators": oscillator_results,
        }

        await cache.set(cache_key, result, ttl=900)
        return result

    except Exception as e:
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/stock/{ticker}/pivot-points")
async def get_pivot_points(ticker: str):
    ticker = _resolve_kr_ticker(ticker)
    cache_key = f"pivot_points:{ticker}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        prices = await yfinance_client.get_price_history(ticker, "5d")
        if not prices or len(prices) < 2:
            err = SP_2005(ticker)
            err.log()
            return JSONResponse(status_code=404, content=err.to_dict())

        last_day = prices[-2]
        h = last_day["high"]
        l = last_day["low"]
        c = last_day["close"]

        p = (h + l + c) / 3
        hl = h - l

        classic = {
            "pivot": round(p, 2),
            "r1": round(2 * p - l, 2),
            "r2": round(p + hl, 2),
            "r3": round(h + 2 * (p - l), 2),
            "s1": round(2 * p - h, 2),
            "s2": round(p - hl, 2),
            "s3": round(l - 2 * (h - p), 2),
        }

        fibonacci = {
            "pivot": round(p, 2),
            "r1": round(p + 0.382 * hl, 2),
            "r2": round(p + 0.618 * hl, 2),
            "r3": round(p + hl, 2),
            "s1": round(p - 0.382 * hl, 2),
            "s2": round(p - 0.618 * hl, 2),
            "s3": round(p - hl, 2),
        }

        result = {
            "ticker": ticker.upper(),
            "classic": classic,
            "fibonacci": fibonacci,
        }

        await cache.set(cache_key, result, ttl=3600)
        return result

    except Exception as e:
        err = SP_3003(ticker)
        err.detail = str(e)[:200]
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/search")
async def search_stocks(q: str = Query(..., min_length=1)):
    results = await ticker_resolver_service.search_candidates(q, country_code="KR", limit=15)
    for item in results[:10]:
        try:
            info = await yfinance_client.get_stock_info(item["ticker"])
            item["name"] = info.get("name", item["ticker"])
        except Exception:
            item["name"] = item["ticker"]

    return results[:15]


@router.get("/ticker/resolve")
async def resolve_ticker(query: str = Query(..., min_length=1), country_code: str = "KR"):
    try:
        resolution = ticker_resolver_service.resolve_ticker(query, country_code)
        if resolution.get("ticker"):
            try:
                info = await yfinance_client.get_stock_info(resolution["ticker"])
                resolution["name"] = info.get("name", resolution["ticker"])
            except Exception:
                resolution["name"] = resolution["ticker"]
        return resolution
    except Exception as exc:
        err = SP_5010(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())


@router.get("/stock/{ticker}/forecast-delta")
async def get_stock_forecast_delta(ticker: str, limit: int = 8):
    try:
        resolution = ticker_resolver_service.resolve_ticker(ticker, "KR")
        return await forecast_monitor_service.get_stock_forecast_delta(resolution["ticker"], limit=limit)
    except Exception as exc:
        err = SP_5014(str(exc)[:200])
        err.log()
        return JSONResponse(status_code=500, content=err.to_dict())
