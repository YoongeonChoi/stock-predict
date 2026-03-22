import asyncio
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from app.config import get_settings
from app.data import cache
from app.data.universe_data import UNIVERSE

log = logging.getLogger("stock_predict.yfinance")

FINANCIAL_LABELS = {
    "revenue": ("Total Revenue", "Operating Revenue", "Revenue"),
    "operating_income": ("Operating Income", "Operating Profit"),
    "net_income": ("Net Income", "Net Income Common Stockholders", "Net Income Including Noncontrolling Interests"),
    "ebitda": ("EBITDA",),
    "free_cash_flow": ("Free Cash Flow", "Operating Cash Flow"),
}


def _is_index_like(ticker: str) -> bool:
    return str(ticker).startswith("^")


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
                return df
        except Exception as exc:
            log.debug("history fetch failed for %s with %s: %s", ticker, params, exc)
    return pd.DataFrame()


def _history_based_quote(ticker: str) -> dict:
    df = _history_sync(ticker, period="5d")
    return _quote_from_history_df(df, ticker)


def _quote_from_history_df(df: pd.DataFrame, ticker: str) -> dict:
    if df.empty:
        return {"ticker": ticker, "price": 0.0, "prev_close": 0.0, "change_pct": 0.0}
    closes = df["Close"].dropna()
    if closes.empty:
        return {"ticker": ticker, "price": 0.0, "prev_close": 0.0, "change_pct": 0.0}
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
    return {
        "ticker": ticker,
        "price": round(price, 2),
        "prev_close": round(prev, 2),
        "change_pct": round(((price - prev) / prev * 100.0) if prev else 0.0, 2),
    }


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


async def get_index_quote(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        def _sync():
            quote = _history_based_quote(ticker)
            ticker_obj = yf.Ticker(ticker)
            try:
                fast_info = ticker_obj.fast_info
            except Exception:
                fast_info = {}

            price = _coalesce(
                _safe_float(_fast_get(fast_info, "lastPrice")),
                quote["price"],
                default=0.0,
            )
            prev = _coalesce(
                _safe_float(_fast_get(fast_info, "previousClose")),
                quote["prev_close"],
                default=0.0,
            )
            return {
                "ticker": ticker,
                "price": round(float(price or 0.0), 2),
                "prev_close": round(float(prev or 0.0), 2),
                "change_pct": round(((float(price or 0.0) - float(prev or 0.0)) / float(prev or 1.0) * 100.0) if prev else 0.0, 2),
            }

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(f"index:{ticker}", _fetch, settings.cache_ttl_price)


async def get_stock_info(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        def _sync():
            ticker_obj = yf.Ticker(ticker)
            history_df = _history_sync(ticker, period="6mo")
            history_rows = _format_rows(history_df)
            quote = _quote_from_history_df(history_df, ticker)

            try:
                info = ticker_obj.info or {}
            except Exception as exc:
                log.debug("info fetch failed for %s: %s", ticker, exc)
                info = {}

            try:
                fast_info = ticker_obj.fast_info
            except Exception:
                fast_info = {}

            try:
                metadata = ticker_obj.history_metadata or {}
            except Exception:
                metadata = {}

            current_price = _coalesce(
                _safe_float(info.get("currentPrice") if isinstance(info, dict) else None),
                _safe_float(info.get("regularMarketPrice") if isinstance(info, dict) else None),
                _safe_float(_fast_get(fast_info, "lastPrice")),
                _safe_float(metadata.get("regularMarketPrice") if isinstance(metadata, dict) else None),
                quote["price"],
                default=0.0,
            )
            prev_close = _coalesce(
                _safe_float(info.get("previousClose") if isinstance(info, dict) else None),
                _safe_float(_fast_get(fast_info, "previousClose")),
                _safe_float(metadata.get("previousClose") if isinstance(metadata, dict) else None),
                quote["prev_close"],
                default=current_price,
            )

            week52_high = _coalesce(
                _safe_float(info.get("fiftyTwoWeekHigh") if isinstance(info, dict) else None),
                _safe_float(metadata.get("fiftyTwoWeekHigh") if isinstance(metadata, dict) else None),
                max((row["high"] for row in history_rows[-252:]), default=None),
            )
            week52_low = _coalesce(
                _safe_float(info.get("fiftyTwoWeekLow") if isinstance(info, dict) else None),
                _safe_float(metadata.get("fiftyTwoWeekLow") if isinstance(metadata, dict) else None),
                min((row["low"] for row in history_rows[-252:]), default=None),
            )
            avg_volume = _coalesce(
                _safe_float(info.get("averageVolume") if isinstance(info, dict) else None),
                _safe_float(info.get("averageVolume10days") if isinstance(info, dict) else None),
                _safe_float(_fast_get(fast_info, "threeMonthAverageVolume")),
                np.mean([row["volume"] for row in history_rows[-20:]]) if history_rows else None,
            )

            return {
                "ticker": ticker,
                "name": _coalesce(
                    info.get("shortName") if isinstance(info, dict) else None,
                    info.get("longName") if isinstance(info, dict) else None,
                    metadata.get("shortName") if isinstance(metadata, dict) else None,
                    metadata.get("longName") if isinstance(metadata, dict) else None,
                    ticker,
                ),
                "sector": (info.get("sector") if isinstance(info, dict) else None) or "N/A",
                "industry": (info.get("industry") if isinstance(info, dict) else None) or "N/A",
                "market_cap": _safe_float(
                    _coalesce(
                        info.get("marketCap") if isinstance(info, dict) else None,
                        _fast_get(fast_info, "marketCap"),
                    ),
                    0.0,
                )
                or 0.0,
                "current_price": round(float(current_price or 0.0), 2),
                "prev_close": round(float(prev_close or 0.0), 2),
                "pe_ratio": _safe_float(info.get("trailingPE") if isinstance(info, dict) else None),
                "forward_pe": _safe_float(info.get("forwardPE") if isinstance(info, dict) else None),
                "pb_ratio": _safe_float(info.get("priceToBook") if isinstance(info, dict) else None),
                "peg_ratio": _safe_float(info.get("pegRatio") if isinstance(info, dict) else None),
                "ev_ebitda": _safe_float(info.get("enterpriseToEbitda") if isinstance(info, dict) else None),
                "dividend_yield": _safe_float(info.get("dividendYield") if isinstance(info, dict) else None),
                "payout_ratio": _safe_float(info.get("payoutRatio") if isinstance(info, dict) else None),
                "beta": _safe_float(info.get("beta") if isinstance(info, dict) else None),
                "52w_high": _safe_float(week52_high),
                "52w_low": _safe_float(week52_low),
                "avg_volume": _safe_float(avg_volume),
                "target_mean": _safe_float(info.get("targetMeanPrice") if isinstance(info, dict) else None),
                "target_median": _safe_float(info.get("targetMedianPrice") if isinstance(info, dict) else None),
                "target_high": _safe_float(info.get("targetHighPrice") if isinstance(info, dict) else None),
                "target_low": _safe_float(info.get("targetLowPrice") if isinstance(info, dict) else None),
                "recommendation": info.get("recommendationKey") if isinstance(info, dict) else None,
                "num_analysts": _safe_int(info.get("numberOfAnalystOpinions") if isinstance(info, dict) else None, 0),
                "roe": _safe_float(info.get("returnOnEquity") if isinstance(info, dict) else None),
                "roa": _safe_float(info.get("returnOnAssets") if isinstance(info, dict) else None),
                "debt_to_equity": _safe_float(info.get("debtToEquity") if isinstance(info, dict) else None),
                "current_ratio": _safe_float(info.get("currentRatio") if isinstance(info, dict) else None),
                "free_cashflow": _safe_float(info.get("freeCashflow") if isinstance(info, dict) else None),
                "operating_margins": _safe_float(info.get("operatingMargins") if isinstance(info, dict) else None),
                "profit_margins": _safe_float(info.get("profitMargins") if isinstance(info, dict) else None),
                "revenue_growth": _safe_float(info.get("revenueGrowth") if isinstance(info, dict) else None),
                "earnings_growth": _safe_float(info.get("earningsGrowth") if isinstance(info, dict) else None),
            }

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"stock_info:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_price_history(ticker: str, period: str = "3mo") -> list[dict]:
    settings = get_settings()

    async def _fetch():
        def _sync():
            return _format_rows(_history_sync(ticker, period=period))

        return await asyncio.to_thread(_sync)

    return await cache.get_or_fetch(
        f"price_hist:{ticker}:{period}", _fetch, settings.cache_ttl_chart
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
    """Daily log-returns for Monte Carlo simulation."""
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
