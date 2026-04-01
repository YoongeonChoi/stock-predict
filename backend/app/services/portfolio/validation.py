from __future__ import annotations

from datetime import datetime

from app.models.country import COUNTRY_REGISTRY
from app.services import ticker_resolver_service


def normalize_country_code(country_code: str | None) -> str:
    return ticker_resolver_service.normalize_country_code(country_code)


def normalize_kr_portfolio_ticker(raw_ticker: str) -> str:
    return ticker_resolver_service.resolve_ticker(raw_ticker, "KR")["ticker"]


def normalize_portfolio_ticker(ticker: str, country_code: str = "KR") -> str:
    resolution = ticker_resolver_service.resolve_ticker(ticker, country_code)
    return resolution["ticker"]


def validate_portfolio_holding_input(
    ticker: str,
    buy_price: float,
    quantity: float,
    buy_date: str,
    country_code: str = "KR",
) -> dict[str, str | float]:
    normalized_country = normalize_country_code(country_code)
    if normalized_country not in COUNTRY_REGISTRY:
        raise ValueError("지원하지 않는 국가 코드입니다. 한국(KR)만 지원합니다.")

    resolution = ticker_resolver_service.resolve_ticker(ticker, normalized_country)
    normalized_ticker = resolution["ticker"]
    if not normalized_ticker:
        raise ValueError("티커를 입력해 주세요.")

    try:
        parsed_buy_price = float(buy_price)
    except (TypeError, ValueError) as exc:
        raise ValueError("매수가는 0보다 큰 숫자로 입력해 주세요.") from exc
    if parsed_buy_price <= 0:
        raise ValueError("매수가는 0보다 큰 숫자로 입력해 주세요.")

    try:
        parsed_quantity = float(quantity)
    except (TypeError, ValueError) as exc:
        raise ValueError("수량은 0보다 큰 숫자로 입력해 주세요.") from exc
    if parsed_quantity <= 0:
        raise ValueError("수량은 0보다 큰 숫자로 입력해 주세요.")

    normalized_buy_date = str(buy_date or "").strip()[:10]
    try:
        datetime.fromisoformat(normalized_buy_date)
    except ValueError as exc:
        raise ValueError("매수일은 YYYY-MM-DD 형식으로 입력해 주세요.") from exc

    return {
        "ticker": normalized_ticker,
        "buy_price": parsed_buy_price,
        "quantity": parsed_quantity,
        "buy_date": normalized_buy_date,
        "country_code": resolution["country_code"],
    }


def validate_portfolio_profile_input(
    total_assets: float,
    cash_balance: float,
    monthly_budget: float,
) -> dict[str, float]:
    try:
        parsed_total_assets = float(total_assets)
        parsed_cash_balance = float(cash_balance)
        parsed_monthly_budget = float(monthly_budget)
    except (TypeError, ValueError) as exc:
        raise ValueError("총자산, 예수금, 월 추가 자금은 숫자로 입력해 주세요.") from exc

    if parsed_total_assets < 0:
        raise ValueError("총자산은 0 이상으로 입력해 주세요.")
    if parsed_cash_balance < 0:
        raise ValueError("예수금은 0 이상으로 입력해 주세요.")
    if parsed_monthly_budget < 0:
        raise ValueError("월 추가 자금은 0 이상으로 입력해 주세요.")

    return {
        "total_assets": parsed_total_assets,
        "cash_balance": parsed_cash_balance,
        "monthly_budget": parsed_monthly_budget,
    }

