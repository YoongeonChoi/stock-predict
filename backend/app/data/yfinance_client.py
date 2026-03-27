import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from app.config import get_settings
from app.data import cache
from app.data.universe_data import UNIVERSE
from app.utils.market_calendar import (
    latest_closed_trading_day,
    market_country_code_for_ticker,
    market_session_cache_token,
)

log = logging.getLogger("stock_predict.yfinance")
BATCH_QUOTE_PRIME_LIMIT = 40

FINANCIAL_LABELS = {
    "revenue": ("Total Revenue", "Operating Revenue", "Revenue"),
    "operating_income": ("Operating Income", "Operating Profit"),
    "net_income": ("Net Income", "Net Income Common Stockholders", "Net Income Including Noncontrolling Interests"),
    "ebitda": ("EBITDA",),
    "free_cash_flow": ("Free Cash Flow", "Operating Cash Flow"),
}


@dataclass
class _TickerSnapshot:
    ticker: str
    info: dict
    fast_info: object
    metadata: dict
    history_df: pd.DataFrame
    history_rows: list[dict]
    quote: dict


def _empty_market_snapshot(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "price": 0.0,
        "prev_close": 0.0,
        "change_pct": 0.0,
        "market_cap": 0.0,
        "current_price": 0.0,
        "valid": False,
    }


def _is_index_like(ticker: str) -> bool:
    return str(ticker).startswith("^")


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_float(value, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    parsed = _safe_float(value)
    if parsed is None:
        return default
    try:
        return int(parsed)
    except (TypeError, ValueError):
        return default


def _fast_get(container, key: str):
    if container is None:
        return None
    if isinstance(container, dict):
        return container.get(key)
    snake_key = []
    for index, char in enumerate(key):
        if char.isupper() and index > 0:
            snake_key.append("_")
        snake_key.append(char.lower())
    return getattr(container, "".join(snake_key), getattr(container, key, None))


def _coalesce(*values, default=None):
    for value in values:
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except TypeError:
            pass
        if value != "":
            return value
    return default


def _fresh_price_ttl(default_ttl: int) -> int:
    return max(60, min(default_ttl, 300))


def _batch_quote_chunk_size(total_tickers: int) -> int:
    if total_tickers >= 160:
        return 240
    if total_tickers >= 80:
        return 120
    return max(1, min(40, total_tickers))


def _format_rows(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    rows = []
    for date, row in df.iterrows():
        rows.append(
            {
                "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                "open": round(_safe_float(row.get("Open"), 0.0) or 0.0, 2),
                "high": round(_safe_float(row.get("High"), 0.0) or 0.0, 2),
                "low": round(_safe_float(row.get("Low"), 0.0) or 0.0, 2),
                "close": round(_safe_float(row.get("Close"), 0.0) or 0.0, 2),
                "volume": _safe_int(row.get("Volume")),
            }
        )
    return rows


def _completed_history_df(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    latest_closed = latest_closed_trading_day(market_country_code_for_ticker(ticker))
    mask = [pd.Timestamp(index).date() <= latest_closed for index in df.index]
    return df.loc[mask]


def _last_history_date(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    return pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d")


def _history_sync(
    ticker: str,
    *,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    ticker_obj = yf.Ticker(ticker)
    attempts = [
        {"period": period, "start": start, "end": end, "auto_adjust": False, "actions": False, "interval": "1d"},
        {"period": period, "start": start, "end": end, "auto_adjust": False, "actions": False},
        {"period": period or "6mo", "start": None, "end": None, "auto_adjust": False, "actions": False, "interval": "1d"},
    ]

    for params in attempts:
        try:
            df = ticker_obj.history(**{k: v for k, v in params.items() if v is not None})
            if df is not None and not df.empty:
                return _completed_history_df(df, ticker)
        except Exception as exc:
            log.debug("history fetch failed for %s with %s: %s", ticker, params, exc)
    return pd.DataFrame()


def _quote_from_history_df(df: pd.DataFrame, ticker: str) -> dict:
    if df.empty:
        return {"ticker": ticker, "price": 0.0, "prev_close": 0.0, "change_pct": 0.0, "session_date": None}
    closes = df["Close"].dropna()
    if closes.empty:
        return {"ticker": ticker, "price": 0.0, "prev_close": 0.0, "change_pct": 0.0, "session_date": None}
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
    return {
        "ticker": ticker,
        "price": round(price, 2),
        "prev_close": round(prev, 2),
        "change_pct": round(((price - prev) / prev * 100.0) if prev else 0.0, 2),
        "session_date": _last_history_date(df),
    }


def _extract_download_frame(downloaded: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if downloaded is None or getattr(downloaded, "empty", True):
        return pd.DataFrame()
    if isinstance(downloaded.columns, pd.MultiIndex):
        level_0 = set(downloaded.columns.get_level_values(0))
        level_1 = set(downloaded.columns.get_level_values(1))
        if ticker in level_0:
            frame = downloaded[ticker]
        elif ticker in level_1:
            frame = downloaded.xs(ticker, axis=1, level=1)
        else:
            return pd.DataFrame()
    else:
        frame = downloaded
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(-1)
    normalized = frame.copy()
    normalized.columns = [str(column) for column in normalized.columns]
    return normalized.dropna(how="all")


def _load_snapshot(ticker: str, *, history_period: str = "6mo", include_info: bool = True) -> _TickerSnapshot:
    ticker_obj = yf.Ticker(ticker)
    history_df = _history_sync(ticker, period=history_period)
    history_rows = _format_rows(history_df)
    quote = _quote_from_history_df(history_df, ticker)

    if include_info:
        try:
            info = _as_dict(ticker_obj.info or {})
        except Exception as exc:
            log.debug("info fetch failed for %s: %s", ticker, exc)
            info = {}
    else:
        info = {}

    try:
        fast_info = ticker_obj.fast_info
    except Exception as exc:
        log.debug("fast_info fetch failed for %s: %s", ticker, exc)
        fast_info = {}

    try:
        metadata = _as_dict(ticker_obj.history_metadata or {})
    except Exception as exc:
        log.debug("history_metadata fetch failed for %s: %s", ticker, exc)
        metadata = {}

    return _TickerSnapshot(
        ticker=ticker,
        info=info,
        fast_info=fast_info,
        metadata=metadata,
        history_df=history_df,
        history_rows=history_rows,
        quote=quote,
    )


def _resolve_number(
    snapshot: _TickerSnapshot,
    *,
    info_keys: tuple[str, ...] = (),
    fast_key: str | None = None,
    metadata_keys: tuple[str, ...] = (),
    fallback=None,
) -> float | None:
    values = []
    for key in info_keys:
        values.append(_safe_float(snapshot.info.get(key)))
    if fast_key:
        values.append(_safe_float(_fast_get(snapshot.fast_info, fast_key)))
    for key in metadata_keys:
        values.append(_safe_float(snapshot.metadata.get(key)))
    if fallback is not None:
        values.append(_safe_float(fallback))
    return _coalesce(*values, default=_safe_float(fallback))


def _resolve_market_number(
    snapshot: _TickerSnapshot,
    *,
    info_keys: tuple[str, ...] = (),
    fast_key: str | None = None,
    metadata_keys: tuple[str, ...] = (),
    fallback=None,
) -> float | None:
    values = []
    if fast_key:
        values.append(_safe_float(_fast_get(snapshot.fast_info, fast_key)))
    for key in metadata_keys:
        values.append(_safe_float(snapshot.metadata.get(key)))
    if fallback is not None:
        values.append(_safe_float(fallback))
    for key in info_keys:
        values.append(_safe_float(snapshot.info.get(key)))
    return _coalesce(*values, default=_safe_float(fallback))


def _resolve_text(
    snapshot: _TickerSnapshot,
    *,
    info_keys: tuple[str, ...] = (),
    metadata_keys: tuple[str, ...] = (),
    fallback: str,
) -> str:
    values = []
    for key in info_keys:
        values.append(snapshot.info.get(key))
    for key in metadata_keys:
        values.append(snapshot.metadata.get(key))
    return str(_coalesce(*values, default=fallback))


def _history_stat(rows: list[dict], key: str, *, window: int, reducer):
    values = [float(item.get(key, 0) or 0) for item in rows[-window:] if item.get(key) is not None]
    if not values:
        return None
    return reducer(values)


def _snapshot_to_market_snapshot(snapshot: _TickerSnapshot) -> dict:
    current_price = _resolve_market_number(
        snapshot,
        info_keys=("currentPrice", "regularMarketPrice"),
        fast_key="lastPrice",
        metadata_keys=("regularMarketPrice",),
        fallback=snapshot.quote["price"],
    ) or 0.0
    prev_close = _resolve_market_number(
        snapshot,
        info_keys=("previousClose",),
        fast_key="previousClose",
        metadata_keys=("previousClose",),
        fallback=snapshot.quote["prev_close"],
    ) or current_price
    market_cap = _resolve_number(
        snapshot,
        info_keys=("marketCap",),
        fast_key="marketCap",
        fallback=0.0,
    ) or 0.0

    return {
        "ticker": snapshot.ticker,
        "name": _resolve_text(
            snapshot,
            info_keys=("shortName", "longName"),
            metadata_keys=("shortName", "longName"),
            fallback=snapshot.ticker,
        ),
        "price": round(float(current_price), 2),
        "prev_close": round(float(prev_close), 2),
        "change_pct": round(((float(current_price) - float(prev_close)) / float(prev_close) * 100.0) if prev_close else 0.0, 2),
        "market_cap": round(float(market_cap), 2),
        "current_price": round(float(current_price), 2),
        "session_date": snapshot.quote.get("session_date"),
        "valid": bool(current_price > 0),
    }


async def get_market_snapshot(ticker: str, *, period: str = "6mo") -> dict:
    settings = get_settings()
    session_token = market_session_cache_token(ticker=ticker)

    async def _fetch():
        def _sync():
            snapshot = _load_snapshot(ticker, history_period=period, include_info=True)
            market_snapshot = _snapshot_to_market_snapshot(snapshot)
            if not market_snapshot["valid"] and not snapshot.history_rows:
                return _empty_market_snapshot(ticker)
            return market_snapshot

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"market_snapshot:{ticker}:{period}:{session_token}",
        _fetch,
        _fresh_price_ttl(settings.cache_ttl_price),
    )


async def get_index_quote(ticker: str) -> dict:
    settings = get_settings()
    session_token = market_session_cache_token(ticker=ticker)

    async def _fetch():
        def _sync():
            snapshot = _load_snapshot(ticker, history_period="5d", include_info=False)
            price = _resolve_number(snapshot, fast_key="lastPrice", fallback=snapshot.quote["price"]) or 0.0
            prev = _resolve_number(snapshot, fast_key="previousClose", fallback=snapshot.quote["prev_close"]) or 0.0
            if price <= 0 and not snapshot.history_rows:
                return {"ticker": ticker, "price": 0.0, "prev_close": 0.0, "change_pct": 0.0}
            return {
                "ticker": ticker,
                "price": round(price, 2),
                "prev_close": round(prev, 2),
                "change_pct": round(((price - prev) / prev * 100.0) if prev else 0.0, 2),
            }

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"index:{ticker}:{session_token}",
        _fetch,
        _fresh_price_ttl(settings.cache_ttl_price),
    )


async def get_stock_quote(ticker: str) -> dict:
    settings = get_settings()
    session_token = market_session_cache_token(ticker=ticker)

    async def _fetch():
        def _sync():
            snapshot = _load_snapshot(ticker, history_period="5d", include_info=False)
            market_snapshot = _snapshot_to_market_snapshot(snapshot)
            if not market_snapshot["valid"] and not snapshot.history_rows:
                return {
                    "ticker": ticker,
                    "current_price": 0.0,
                    "prev_close": 0.0,
                    "change_pct": 0.0,
                    "session_date": None,
                }
            return {
                "ticker": ticker,
                "current_price": market_snapshot["current_price"],
                "prev_close": market_snapshot["prev_close"],
                "change_pct": market_snapshot["change_pct"],
                "session_date": market_snapshot.get("session_date"),
            }

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"stock_quote:{ticker}:{session_token}",
        _fetch,
        _fresh_price_ttl(settings.cache_ttl_price),
    )


async def get_batch_stock_quotes(tickers: list[str], period: str = "5d") -> dict[str, dict]:
    settings = get_settings()
    unique_tickers = list(dict.fromkeys(str(ticker).upper() for ticker in tickers if ticker))
    if not unique_tickers:
        return {}
    session_token = market_session_cache_token(ticker=unique_tickers[0])
    tickers_digest = hashlib.sha1(",".join(sorted(unique_tickers)).encode("utf-8")).hexdigest()[:16]

    async def _fetch():
        def _sync():
            quotes: dict[str, dict] = {}
            chunk_size = _batch_quote_chunk_size(len(unique_tickers))
            for index in range(0, len(unique_tickers), chunk_size):
                chunk = unique_tickers[index : index + chunk_size]
                try:
                    downloaded = yf.download(
                        tickers=" ".join(chunk),
                        period=period,
                        interval="1d",
                        group_by="ticker",
                        auto_adjust=False,
                        progress=False,
                        threads=True,
                        timeout=12,
                    )
                except Exception as exc:
                    log.warning("batch quote download failed for %s tickers: %s", len(chunk), exc)
                    downloaded = pd.DataFrame()
                for ticker in chunk:
                    quote = _quote_from_history_df(_extract_download_frame(downloaded, ticker), ticker)
                    quotes[ticker] = {
                        "ticker": ticker,
                        "current_price": round(_safe_float(quote.get("price"), 0.0) or 0.0, 2),
                        "prev_close": round(_safe_float(quote.get("prev_close"), 0.0) or 0.0, 2),
                        "change_pct": round(_safe_float(quote.get("change_pct"), 0.0) or 0.0, 2),
                        "session_date": quote.get("session_date"),
                    }
            return quotes

        quotes = await asyncio.to_thread(_sync)
        if len(unique_tickers) <= BATCH_QUOTE_PRIME_LIMIT:
            ttl = _fresh_price_ttl(settings.cache_ttl_price)
            for ticker, quote in quotes.items():
                await cache.set(
                    f"stock_quote:{ticker}:{market_session_cache_token(ticker=ticker)}",
                    quote,
                    ttl,
                )
        return quotes

    return await cache.get_or_fetch(
        f"stock_batch_quotes:{tickers_digest}:{period}:{session_token}",
        _fetch,
        _fresh_price_ttl(settings.cache_ttl_price),
    )


async def _get_stock_fundamentals(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        def _sync():
            snapshot = _load_snapshot(ticker, history_period="6mo", include_info=True)
            week52_high = _resolve_number(
                snapshot,
                info_keys=("fiftyTwoWeekHigh",),
                metadata_keys=("fiftyTwoWeekHigh",),
                fallback=_history_stat(snapshot.history_rows, "high", window=252, reducer=max),
            )
            week52_low = _resolve_number(
                snapshot,
                info_keys=("fiftyTwoWeekLow",),
                metadata_keys=("fiftyTwoWeekLow",),
                fallback=_history_stat(snapshot.history_rows, "low", window=252, reducer=min),
            )
            avg_volume = _resolve_number(
                snapshot,
                info_keys=("averageVolume", "averageVolume10days"),
                fast_key="threeMonthAverageVolume",
                fallback=_history_stat(snapshot.history_rows, "volume", window=20, reducer=np.mean),
            )

            return {
                "ticker": ticker,
                "name": _resolve_text(
                    snapshot,
                    info_keys=("shortName", "longName"),
                    metadata_keys=("shortName", "longName"),
                    fallback=ticker,
                ),
                "sector": snapshot.info.get("sector") or "N/A",
                "industry": snapshot.info.get("industry") or "N/A",
                "market_cap": _resolve_number(snapshot, info_keys=("marketCap",), fast_key="marketCap", fallback=0.0) or 0.0,
                "pe_ratio": _resolve_number(snapshot, info_keys=("trailingPE",)),
                "forward_pe": _resolve_number(snapshot, info_keys=("forwardPE",)),
                "pb_ratio": _resolve_number(snapshot, info_keys=("priceToBook",)),
                "peg_ratio": _resolve_number(snapshot, info_keys=("pegRatio",)),
                "ev_ebitda": _resolve_number(snapshot, info_keys=("enterpriseToEbitda",)),
                "dividend_yield": _resolve_number(snapshot, info_keys=("dividendYield",)),
                "payout_ratio": _resolve_number(snapshot, info_keys=("payoutRatio",)),
                "beta": _resolve_number(snapshot, info_keys=("beta",)),
                "52w_high": week52_high,
                "52w_low": week52_low,
                "avg_volume": avg_volume,
                "target_mean": _resolve_number(snapshot, info_keys=("targetMeanPrice",)),
                "target_median": _resolve_number(snapshot, info_keys=("targetMedianPrice",)),
                "target_high": _resolve_number(snapshot, info_keys=("targetHighPrice",)),
                "target_low": _resolve_number(snapshot, info_keys=("targetLowPrice",)),
                "recommendation": snapshot.info.get("recommendationKey"),
                "num_analysts": _safe_int(snapshot.info.get("numberOfAnalystOpinions"), 0),
                "roe": _resolve_number(snapshot, info_keys=("returnOnEquity",)),
                "roa": _resolve_number(snapshot, info_keys=("returnOnAssets",)),
                "debt_to_equity": _resolve_number(snapshot, info_keys=("debtToEquity",)),
                "current_ratio": _resolve_number(snapshot, info_keys=("currentRatio",)),
                "free_cashflow": _resolve_number(snapshot, info_keys=("freeCashflow",)),
                "operating_margins": _resolve_number(snapshot, info_keys=("operatingMargins",)),
                "profit_margins": _resolve_number(snapshot, info_keys=("profitMargins",)),
                "revenue_growth": _resolve_number(snapshot, info_keys=("revenueGrowth",)),
                "earnings_growth": _resolve_number(snapshot, info_keys=("earningsGrowth",)),
            }

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"stock_fundamentals:{ticker}",
        _fetch,
        settings.cache_ttl_fundamentals,
    )


async def get_stock_info(ticker: str) -> dict:
    fundamentals, quote = await asyncio.gather(
        _get_stock_fundamentals(ticker),
        get_stock_quote(ticker),
    )
    current_price = float(quote.get("current_price") or 0.0)
    prev_close = float(quote.get("prev_close") or current_price)
    return {
        **fundamentals,
        "current_price": round(current_price, 2),
        "prev_close": round(prev_close, 2),
        "change_pct": round(((current_price - prev_close) / prev_close * 100.0) if prev_close else 0.0, 2),
        "quote_session_date": quote.get("session_date"),
    }


async def get_price_history(ticker: str, period: str = "3mo") -> list[dict]:
    settings = get_settings()
    session_token = market_session_cache_token(ticker=ticker)

    async def _fetch():
        def _sync():
            return _format_rows(_history_sync(ticker, period=period))

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"price_hist:{ticker}:{period}:{session_token}",
        _fetch,
        _fresh_price_ttl(settings.cache_ttl_chart),
    )


def _safe_statement_value(df: pd.DataFrame, labels: tuple[str, ...], col) -> float | None:
    for label in labels:
        try:
            value = df.loc[label, col]
        except (KeyError, TypeError):
            continue
        parsed = _safe_float(value)
        if parsed is not None:
            return parsed
    return None


async def get_financials(ticker: str) -> list[dict]:
    settings = get_settings()

    async def _fetch():
        def _sync():
            if _is_index_like(ticker):
                return []
            ticker_obj = yf.Ticker(ticker)
            results = []
            try:
                inc = ticker_obj.quarterly_income_stmt
                cf = ticker_obj.quarterly_cashflow
                if inc is None or inc.empty:
                    return []
                for col in inc.columns[:8]:
                    try:
                        period_str = col.strftime("%Y") + "-Q" + str((col.month - 1) // 3 + 1)
                    except Exception:
                        period_str = str(col)[:10]
                    row = {"period": period_str}
                    row["revenue"] = _safe_statement_value(inc, FINANCIAL_LABELS["revenue"], col)
                    row["operating_income"] = _safe_statement_value(inc, FINANCIAL_LABELS["operating_income"], col)
                    row["net_income"] = _safe_statement_value(inc, FINANCIAL_LABELS["net_income"], col)
                    row["ebitda"] = _safe_statement_value(inc, FINANCIAL_LABELS["ebitda"], col)
                    if cf is not None and not cf.empty and col in cf.columns:
                        row["free_cash_flow"] = _safe_statement_value(cf, FINANCIAL_LABELS["free_cash_flow"], col)
                    else:
                        row["free_cash_flow"] = None
                    results.append(row)
            except Exception as exc:
                log.debug("financial fetch failed for %s: %s", ticker, exc)
            return results

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"financials:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_analyst_ratings(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        def _sync():
            if _is_index_like(ticker):
                return {"buy": 0, "hold": 0, "sell": 0}
            ticker_obj = yf.Ticker(ticker)
            ratings = {"buy": 0, "hold": 0, "sell": 0}
            try:
                rec = ticker_obj.recommendations
            except Exception as exc:
                log.debug("recommendations fetch failed for %s: %s", ticker, exc)
                rec = None

            if rec is not None and not rec.empty:
                recent = rec.tail(20)
                for _, row in recent.iterrows():
                    grade = str(row.get("To Grade", "")).lower()
                    if any(word in grade for word in ["buy", "outperform", "overweight", "strong buy"]):
                        ratings["buy"] += 1
                    elif any(word in grade for word in ["sell", "underperform", "underweight"]):
                        ratings["sell"] += 1
                    else:
                        ratings["hold"] += 1
            return ratings

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"analyst:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


def _calendar_to_rows(calendar) -> list[dict]:
    if not calendar:
        return []
    date_values = calendar.get("Earnings Date") or calendar.get("Ex-Dividend Date")
    if date_values is None:
        return []
    if not isinstance(date_values, (list, tuple, pd.Series, np.ndarray)):
        date_values = [date_values]
    rows = []
    for value in date_values:
        if value is None:
            continue
        try:
            parsed = pd.Timestamp(value).strftime("%Y-%m-%d")
        except Exception:
            parsed = str(value)[:10]
        rows.append(
            {
                "date": parsed,
                "eps_estimate": _safe_float(calendar.get("EPS Estimate")),
                "eps_actual": _safe_float(calendar.get("Reported EPS")),
                "surprise_pct": _safe_float(calendar.get("Surprise(%)")),
            }
        )
    return rows


async def get_earnings_history(ticker: str) -> list[dict]:
    settings = get_settings()

    async def _fetch():
        def _sync():
            if _is_index_like(ticker):
                return []
            ticker_obj = yf.Ticker(ticker)
            try:
                earnings = ticker_obj.earnings_dates
                if earnings is not None and not earnings.empty:
                    results = []
                    for date, row in earnings.head(12).iterrows():
                        results.append(
                            {
                                "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10],
                                "eps_estimate": _safe_float(row.get("EPS Estimate")),
                                "eps_actual": _safe_float(row.get("Reported EPS")),
                                "surprise_pct": _safe_float(row.get("Surprise(%)")),
                            }
                        )
                    if results:
                        return results
            except ImportError:
                log.debug("earnings_dates requires lxml for %s; falling back to calendar.", ticker)
            except Exception as exc:
                log.debug("earnings_dates fetch failed for %s: %s", ticker, exc)

            try:
                calendar = ticker_obj.calendar
            except Exception as exc:
                log.debug("calendar fetch failed for %s: %s", ticker, exc)
                return []
            return _calendar_to_rows(calendar)

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"earnings:v2:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_sector_tickers(country_code: str, sector: str) -> list[str]:
    from app.data.universe_data import get_universe

    universe = await get_universe(country_code)
    return universe.get(sector, UNIVERSE.get(country_code, {}).get(sector, []))


async def get_historical_returns(ticker: str, days: int = 60) -> list[float]:
    """Daily log-returns for distributional forecasting and backtests."""
    settings = get_settings()

    async def _fetch():
        def _sync():
            end = datetime.now()
            start = end - timedelta(days=days + 60)
            df = _history_sync(
                ticker,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
            )
            if df.empty or len(df) < 10:
                return []
            closes = df["Close"].dropna().to_numpy(dtype=float)
            if len(closes) < 10:
                return []
            returns = list(np.diff(np.log(closes)))
            return [round(value, 6) for value in returns[-days:]]

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"hist_returns:{ticker}:{days}", _fetch, settings.cache_ttl_chart
    )
