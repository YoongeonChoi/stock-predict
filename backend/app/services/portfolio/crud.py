from __future__ import annotations

from app.data import cache


def default_portfolio_profile() -> dict[str, float | None]:
    return {
        "total_assets": 0.0,
        "cash_balance": 0.0,
        "monthly_budget": 0.0,
        "updated_at": None,
    }


def portfolio_cache_key(user_id: str) -> str:
    return f"portfolio_overview:v8:{user_id}"


async def invalidate_portfolio_cache(user_id: str | None = None) -> None:
    if user_id:
        await cache.invalidate(f"%:{user_id}")
    await cache.invalidate("portfolio_overview:%")

