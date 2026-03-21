import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.data import cache
from app.data.universe_data import UNIVERSE
from app.config import get_settings


async def get_index_quote(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        info = t.fast_info
        try:
            price = info.last_price
            prev = info.previous_close
        except Exception:
            price = prev = 0
        return {
            "ticker": ticker,
            "price": round(price or 0, 2),
            "prev_close": round(prev or 0, 2),
            "change_pct": round(((price - prev) / prev * 100) if prev else 0, 2),
        }

    return await cache.get_or_fetch(f"index:{ticker}", _fetch, settings.cache_ttl_price)


async def get_stock_info(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "prev_close": info.get("previousClose", 0),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": info.get("priceToBook"),
            "peg_ratio": info.get("pegRatio"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "target_mean": info.get("targetMeanPrice"),
            "target_median": info.get("targetMedianPrice"),
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "recommendation": info.get("recommendationKey"),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_margins": info.get("operatingMargins"),
            "profit_margins": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
        }

    return await cache.get_or_fetch(
        f"stock_info:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_price_history(ticker: str, period: str = "3mo") -> list[dict]:
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return []
        rows = []
        for date, row in df.iterrows():
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        return rows

    return await cache.get_or_fetch(
        f"price_hist:{ticker}:{period}", _fetch, settings.cache_ttl_chart
    )


async def get_financials(ticker: str) -> list[dict]:
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        results = []
        try:
            inc = t.quarterly_income_stmt
            cf = t.quarterly_cashflow
            if inc is not None and not inc.empty:
                for col in inc.columns[:8]:
                    try:
                        period_str = col.strftime("%Y") + "-Q" + str((col.month - 1) // 3 + 1)
                    except Exception:
                        period_str = str(col)[:10]
                    row = {"period": period_str}
                    row["revenue"] = _safe_val(inc, "Total Revenue", col)
                    row["operating_income"] = _safe_val(inc, "Operating Income", col)
                    row["net_income"] = _safe_val(inc, "Net Income", col)
                    row["ebitda"] = _safe_val(inc, "EBITDA", col)
                    if cf is not None and not cf.empty and col in cf.columns:
                        row["free_cash_flow"] = _safe_val(cf, "Free Cash Flow", col)
                    else:
                        row["free_cash_flow"] = None
                    results.append(row)
        except Exception:
            pass
        return results

    return await cache.get_or_fetch(
        f"financials:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_analyst_ratings(ticker: str) -> dict:
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        rec = t.recommendations
        ratings = {"buy": 0, "hold": 0, "sell": 0}
        if rec is not None and not rec.empty:
            recent = rec.tail(20)
            for _, r in recent.iterrows():
                grade = str(r.get("To Grade", "")).lower()
                if any(w in grade for w in ["buy", "outperform", "overweight", "strong buy"]):
                    ratings["buy"] += 1
                elif any(w in grade for w in ["sell", "underperform", "underweight"]):
                    ratings["sell"] += 1
                else:
                    ratings["hold"] += 1
        return ratings

    return await cache.get_or_fetch(
        f"analyst:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_earnings_history(ticker: str) -> list[dict]:
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        try:
            earn = t.earnings_dates
            if earn is None or earn.empty:
                return []
            results = []
            for date, row in earn.head(12).iterrows():
                results.append({
                    "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)[:10],
                    "eps_estimate": _to_float(row.get("EPS Estimate")),
                    "eps_actual": _to_float(row.get("Reported EPS")),
                    "surprise_pct": _to_float(row.get("Surprise(%)")),
                })
            return results
        except Exception:
            return []

    return await cache.get_or_fetch(
        f"earnings:{ticker}", _fetch, settings.cache_ttl_fundamentals
    )


async def get_sector_tickers(country_code: str, sector: str) -> list[str]:
    from app.data.universe_data import get_universe
    universe = await get_universe(country_code)
    return universe.get(sector, UNIVERSE.get(country_code, {}).get(sector, []))


async def get_historical_returns(ticker: str, days: int = 60) -> list[float]:
    """Daily log-returns for Monte Carlo simulation."""
    settings = get_settings()

    async def _fetch():
        t = yf.Ticker(ticker)
        end = datetime.now()
        start = end - timedelta(days=days + 30)
        df = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if df.empty or len(df) < 10:
            return []
        closes = df["Close"].values
        returns = list(np.diff(np.log(closes)))
        return [round(r, 6) for r in returns[-days:]]

    return await cache.get_or_fetch(
        f"hist_returns:{ticker}:{days}", _fetch, settings.cache_ttl_chart
    )


def _safe_val(df, row_label: str, col):
    try:
        v = df.loc[row_label, col]
        if pd.isna(v):
            return None
        return float(v)
    except (KeyError, TypeError):
        return None


def _to_float(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return round(float(v), 4)
    except (ValueError, TypeError):
        return None
