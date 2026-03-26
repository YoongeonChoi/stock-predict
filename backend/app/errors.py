"""
Centralized error code registry for Stock Predict.

Format: SP-XYYY
  SP = Stock Predict prefix
  X  = Category digit (1~6)
  YYY = Specific error number

Categories:
  1xxx = Configuration (API keys, env vars)
  2xxx = Data Sources (ECOS, OpenDART/KOSIS-ready, yfinance, FMP, News)
  3xxx = Analysis Pipeline (analyzers, scoring, forecast)
  4xxx = LLM / OpenAI
  5xxx = Services / Database (archive, watchlist, export, cache)
  6xxx = Request Validation (bad params, not found)
  9xxx = Unexpected server/runtime errors
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger("stock_predict.errors")


@dataclass
class AppError:
    code: str
    message: str
    detail: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = {"error_code": self.code, "message": self.message}
        if self.detail:
            d["detail"] = self.detail
        d["timestamp"] = self.timestamp
        return d

    def log(self, level: str = "error"):
        msg = f"[{self.code}] {self.message}"
        if self.detail:
            msg += f" | {self.detail}"
        getattr(log, level, log.error)(msg)


# ---------------------------------------------------------------------------
# 1xxx  Configuration
# ---------------------------------------------------------------------------
SP_1001 = lambda: AppError("SP-1001", "OpenAI API key not configured",
                           "Set OPENAI_API_KEY in backend/.env")
SP_1002 = lambda: AppError("SP-1002", "OpenAI API key invalid",
                           "Check your key at platform.openai.com/api-keys")
SP_1003 = lambda: AppError("SP-1003", "Supplemental public-data API key not configured",
                           "Set additional free KR market/public-data keys only if you use them")
SP_1004 = lambda: AppError("SP-1004", "ECOS API key not configured",
                           "Set ECOS_API_KEY in backend/.env (free)")
SP_1005 = lambda: AppError("SP-1005", "FMP API key not configured",
                           "Set FMP_API_KEY in backend/.env (free, optional)")
SP_1006 = lambda: AppError("SP-1006", "Supabase server key not configured",
                           "Set SUPABASE_SERVER_KEY in backend/.env or deployment env")

# ---------------------------------------------------------------------------
# 2xxx  Data Sources
# ---------------------------------------------------------------------------
SP_2001 = lambda sid="", d="": AppError("SP-2001", f"Supplemental public-data API request failed: {sid}", d)
SP_2002 = lambda d="": AppError("SP-2002", "ECOS (BOK) API request failed", d)
SP_2003 = lambda d="": AppError("SP-2003", "Supplemental statistics API request failed", d)
SP_2004 = lambda t="": AppError("SP-2004", f"Ticker not found or delisted: {t}",
                                "Yahoo Finance returned no data")
SP_2005 = lambda t="": AppError("SP-2005", f"Price data unavailable: {t}",
                                "Check if the market is open or ticker is valid")
SP_2006 = lambda d="": AppError("SP-2006", "FMP API request failed", d)
SP_2007 = lambda d="": AppError("SP-2007", "News feed unavailable", d)
SP_2008 = lambda t="": AppError("SP-2008", f"Financial data unavailable: {t}",
                                "yfinance returned no financials")

# ---------------------------------------------------------------------------
# 3xxx  Analysis Pipeline
# ---------------------------------------------------------------------------
SP_3001 = lambda cc="": AppError("SP-3001", f"Country analysis failed: {cc}")
SP_3002 = lambda s="": AppError("SP-3002", f"Sector analysis failed: {s}")
SP_3003 = lambda t="": AppError("SP-3003", f"Stock analysis failed: {t}")
SP_3004 = lambda d="": AppError("SP-3004", "Forecast engine failed", d)
SP_3005 = lambda: AppError("SP-3005", "Sentiment analysis failed")
SP_3006 = lambda d="": AppError("SP-3006", "Scoring calculation failed", d)
SP_3007 = lambda d="": AppError("SP-3007", "Historical pattern forecast failed", d)

# ---------------------------------------------------------------------------
# 4xxx  LLM / OpenAI
# ---------------------------------------------------------------------------
SP_4001 = lambda: AppError("SP-4001", "OpenAI quota exceeded",
                           "Check your plan and billing at platform.openai.com")
SP_4002 = lambda: AppError("SP-4002", "OpenAI authentication failed",
                           "Your API key is invalid or revoked")
SP_4003 = lambda: AppError("SP-4003", "LLM response parse error",
                           "GPT returned non-JSON output")
SP_4004 = lambda: AppError("SP-4004", "LLM request timeout",
                           "OpenAI did not respond in time")
SP_4005 = lambda d="": AppError("SP-4005", "LLM unknown error", d)

# ---------------------------------------------------------------------------
# 5xxx  Services / Database
# ---------------------------------------------------------------------------
SP_5001 = lambda d="": AppError("SP-5001", "Database connection failed", d)
SP_5002 = lambda d="": AppError("SP-5002", "Archive save failed", d)
SP_5003 = lambda d="": AppError("SP-5003", "Watchlist operation failed", d)
SP_5004 = lambda d="": AppError("SP-5004", "Export generation failed", d)
SP_5005 = lambda d="": AppError("SP-5005", "Cache operation failed", d)
SP_5006 = lambda d="": AppError("SP-5006", "System diagnostics failed", d)
SP_5007 = lambda d="": AppError("SP-5007", "Prediction research query failed", d)
SP_5008 = lambda d="": AppError("SP-5008", "Portfolio analytics failed", d)
SP_5009 = lambda d="": AppError("SP-5009", "External research archive sync failed", d)
SP_5010 = lambda d="": AppError("SP-5010", "Ticker resolution failed", d)
SP_5011 = lambda d="": AppError("SP-5011", "Daily briefing failed", d)
SP_5012 = lambda d="": AppError("SP-5012", "Market session summary failed", d)
SP_5013 = lambda d="": AppError("SP-5013", "Portfolio event radar failed", d)
SP_5014 = lambda d="": AppError("SP-5014", "Forecast drift query failed", d)
SP_5015 = lambda d="": AppError("SP-5015", "Conditional portfolio recommendation failed", d)
SP_5016 = lambda d="": AppError("SP-5016", "Optimal portfolio recommendation failed", d)
SP_5017 = lambda d="": AppError("SP-5017", "Portfolio profile update failed", d)
SP_5018 = lambda d="": AppError(
    "SP-5018",
    "Service request timed out",
    d or "The requested aggregated response took too long. Retry shortly.",
)

# ---------------------------------------------------------------------------
# 6xxx  Request Validation
# ---------------------------------------------------------------------------
SP_6001 = lambda cc="": AppError("SP-6001", f"Country not supported: {cc}")
SP_6002 = lambda sid="": AppError("SP-6002", f"Sector not found: {sid}")
SP_6003 = lambda: AppError("SP-6003", "Invalid period parameter",
                           "Allowed: 1mo, 3mo, 6mo, 1y, 2y")
SP_6004 = lambda: AppError("SP-6004", "Insufficient tickers for comparison",
                           "Provide at least 2 tickers, max 4")
SP_6005 = lambda rid=0: AppError("SP-6005", f"Report not found: #{rid}")
SP_6006 = lambda: AppError("SP-6006", "Invalid export format",
                           "Allowed: pdf, csv")
SP_6007 = lambda field="period": AppError(
    "SP-6007",
    f"Invalid calendar parameter: {field}",
    "Provide month 1-12 and year between 2000 and 2100.",
)
SP_6008 = lambda field="region_code": AppError(
    "SP-6008",
    f"Invalid research archive parameter: {field}",
    "Allowed region_code value is KR.",
)
SP_6009 = lambda d="": AppError(
    "SP-6009",
    "Invalid portfolio holding input",
    d or "Provide a ticker, positive buy price and quantity, and a valid buy date.",
)
SP_6010 = lambda d="": AppError(
    "SP-6010",
    "Request validation failed",
    d or "Check query parameters and request body fields, then try again.",
)
SP_6011 = lambda path="": AppError(
    "SP-6011",
    "API route not found",
    path or "Check the API path and try again.",
)
SP_6012 = lambda method="": AppError(
    "SP-6012",
    "HTTP method not allowed",
    method or "Check the supported HTTP method for this API.",
)
SP_6013 = lambda d="": AppError(
    "SP-6013",
    "Invalid portfolio profile input",
    d or "Provide non-negative total assets, cash balance, and monthly budget values.",
)
SP_6014 = lambda d="": AppError(
    "SP-6014",
    "Authentication required",
    d or "Sign in and retry the requested operation.",
)

# ---------------------------------------------------------------------------
# 9xxx  Unexpected server/runtime errors
# ---------------------------------------------------------------------------
SP_9999 = lambda d="": AppError("SP-9999", "Unexpected server error", d)

