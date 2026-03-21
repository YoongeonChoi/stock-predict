import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app.data import cache
from app.config import get_settings

# Representative tickers per country/sector for screening
UNIVERSE = {
    "US": {
        "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HAL"],
        "Materials": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DOW", "DD", "VMC"],
        "Industrials": ["CAT", "GE", "HON", "UNP", "RTX", "DE", "BA", "LMT", "UPS", "MMM"],
        "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX", "BKNG", "CMG"],
        "Consumer Staples": ["PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "MDLZ", "KHC"],
        "Health Care": ["UNH", "JNJ", "LLY", "PFE", "ABT", "TMO", "MRK", "ABBV", "DHR", "AMGN"],
        "Financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "BLK", "AXP"],
        "Information Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "INTC", "CSCO"],
        "Communication Services": ["META", "GOOGL", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA"],
        "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
        "Real Estate": ["PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL", "DLR", "AVB"],
    },
    "KR": {
        "Information Technology": ["005930.KS", "000660.KS", "035420.KS", "035720.KS", "036570.KS",
                                   "263750.KS", "034730.KS", "066570.KS", "006400.KS", "009150.KS"],
        "Financials": ["105560.KS", "055550.KS", "086790.KS", "316140.KS", "024110.KS",
                       "138930.KS", "003550.KS", "005830.KS", "032830.KS", "071050.KS"],
        "Consumer Discretionary": ["005380.KS", "000270.KS", "012330.KS", "051910.KS", "004020.KS",
                                   "003490.KS", "004170.KS", "069960.KS", "161390.KS", "030200.KS"],
        "Industrials": ["010130.KS", "028260.KS", "009540.KS", "042660.KS", "011200.KS",
                        "010140.KS", "034020.KS", "003490.KS", "047050.KS", "000120.KS"],
        "Materials": ["051910.KS", "005490.KS", "010130.KS", "011170.KS", "006800.KS",
                      "003670.KS", "004000.KS", "001120.KS", "078930.KS", "005300.KS"],
        "Health Care": ["207940.KS", "068270.KS", "128940.KS", "326030.KS", "145020.KS",
                        "091990.KS", "004090.KS", "001630.KS", "195940.KS", "185750.KS"],
        "Energy": ["096770.KS", "010950.KS", "267250.KS", "078930.KS", "006120.KS",
                   "007070.KS", "003620.KS", "011760.KS", "036460.KS", "014680.KS"],
        "Consumer Staples": ["097950.KS", "271560.KS", "004370.KS", "033780.KS", "280360.KS",
                             "005610.KS", "005180.KS", "004990.KS", "014710.KS", "007310.KS"],
        "Communication Services": ["030200.KS", "036570.KS", "035720.KS", "251270.KS", "041510.KS",
                                   "035900.KS", "293490.KS", "352820.KS", "259960.KS", "018260.KS"],
        "Utilities": ["015760.KS", "034590.KS", "017390.KS", "071090.KS", "053210.KS",
                      "006360.KS", "001440.KS", "029780.KS", "025820.KS", "003580.KS"],
        "Real Estate": ["316140.KS", "377300.KS", "395400.KS", "365550.KS", "334890.KS",
                        "448730.KS", "357120.KS", "417310.KS", "432320.KS", "330590.KS"],
    },
    "JP": {
        "Information Technology": ["6758.T", "6861.T", "6857.T", "4063.T", "6723.T",
                                   "6702.T", "7735.T", "6645.T", "6146.T", "4307.T"],
        "Consumer Discretionary": ["7203.T", "7267.T", "7974.T", "9983.T", "7751.T",
                                   "7269.T", "7270.T", "9984.T", "2413.T", "3099.T"],
        "Financials": ["8306.T", "8316.T", "8411.T", "8766.T", "8035.T",
                       "8591.T", "8604.T", "8801.T", "8802.T", "7182.T"],
        "Industrials": ["6301.T", "6501.T", "6503.T", "7011.T", "6902.T",
                        "6273.T", "6367.T", "7012.T", "9020.T", "9022.T"],
        "Health Care": ["4502.T", "4503.T", "4568.T", "4519.T", "4523.T",
                        "6869.T", "4901.T", "4543.T", "6479.T", "2897.T"],
        "Materials": ["4063.T", "3407.T", "4005.T", "4188.T", "5020.T",
                      "5108.T", "3401.T", "4042.T", "4021.T", "3405.T"],
        "Consumer Staples": ["2914.T", "2502.T", "2801.T", "2269.T", "4452.T",
                             "2871.T", "2503.T", "4578.T", "2607.T", "2002.T"],
        "Communication Services": ["9432.T", "9433.T", "9434.T", "4689.T", "9602.T",
                                   "2432.T", "3659.T", "4684.T", "9468.T", "9613.T"],
        "Energy": ["5020.T", "5019.T", "1605.T", "5021.T", "5017.T",
                   "9501.T", "9502.T", "9503.T", "1963.T", "5001.T"],
        "Utilities": ["9501.T", "9502.T", "9503.T", "9531.T", "9532.T",
                      "9504.T", "9505.T", "9506.T", "9507.T", "9508.T"],
        "Real Estate": ["8801.T", "8802.T", "3289.T", "8830.T", "3291.T",
                        "8804.T", "3003.T", "8803.T", "8905.T", "3231.T"],
    },
}


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
    return UNIVERSE.get(country_code, {}).get(sector, [])


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
