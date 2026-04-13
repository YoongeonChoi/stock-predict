from datetime import datetime, timezone

STOCK_DETAIL_CACHE_VERSION = "v9"
STOCK_DETAIL_LATEST_CACHE_VERSION = "latest-v9"
STOCK_DETAIL_QUICK_CACHE_VERSION = "quick-v1"


def _latest_price_stamp(prices: list[dict]) -> str:
    if not prices:
        return datetime.now(timezone.utc).date().isoformat()
    return str(prices[-1].get("date") or datetime.now(timezone.utc).date().isoformat())


def stock_detail_cache_key(ticker: str, prices: list[dict]) -> str:
    return f"stock_detail:{STOCK_DETAIL_CACHE_VERSION}:{ticker}:{_latest_price_stamp(prices)}"


def stock_detail_latest_cache_key(ticker: str) -> str:
    return f"stock_detail:{STOCK_DETAIL_LATEST_CACHE_VERSION}:{ticker}"


def stock_detail_quick_cache_key(ticker: str) -> str:
    return f"stock_detail:{STOCK_DETAIL_QUICK_CACHE_VERSION}:{ticker}"
