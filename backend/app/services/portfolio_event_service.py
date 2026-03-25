from __future__ import annotations

from datetime import datetime, timedelta

from app.services import calendar_service, portfolio_service


def _holding_key(ticker: str) -> str:
    upper = str(ticker or "").upper()
    return upper.split(".")[0]


def _event_rank(event: dict) -> tuple:
    impact_rank = {"high": 0, "medium": 1, "low": 2}.get(event.get("impact", "medium"), 1)
    return (event.get("date", "9999-12-31"), impact_rank, -float(event.get("portfolio_weight") or 0), event.get("title", ""))


async def get_portfolio_event_radar(days: int = 14) -> dict:
    window_days = max(3, min(days, 30))
    portfolio = await portfolio_service.get_portfolio()
    holdings = portfolio.get("holdings") or []
    if not holdings:
        return {
            "generated_at": datetime.now().isoformat(),
            "window_days": window_days,
            "events": [],
        }

    today = datetime.now().date()
    horizon = today + timedelta(days=window_days)
    country_weights: dict[str, float] = {}
    holdings_by_country: dict[str, list[dict]] = {}
    holding_index: dict[str, dict] = {}

    for holding in holdings:
        country_code = str(holding.get("country_code") or "KR").upper()
        country_weights[country_code] = country_weights.get(country_code, 0.0) + float(holding.get("weight_pct") or 0.0)
        holdings_by_country.setdefault(country_code, []).append(holding)
        holding_index[_holding_key(holding.get("ticker", ""))] = holding

    months = {(today.year, today.month)}
    if horizon.month != today.month or horizon.year != today.year:
        months.add((horizon.year, horizon.month))

    events: list[dict] = []
    for country_code in sorted(country_weights):
        for year, month in sorted(months):
            calendar = await calendar_service.get_calendar(country_code, year, month)
            for event in calendar.get("events", []):
                event_date = str(event.get("date") or "")
                if not event_date or event_date < today.isoformat() or event_date > horizon.isoformat():
                    continue

                related_holdings: list[dict] = []
                if event.get("type") == "earnings" and event.get("symbol"):
                    matched = holding_index.get(_holding_key(event["symbol"]))
                    if matched:
                        related_holdings.append(matched)
                    else:
                        continue
                else:
                    related_holdings.extend(holdings_by_country.get(country_code, []))
                    if event.get("impact") not in {"high", "medium"}:
                        continue

                portfolio_weight = round(sum(float(item.get("weight_pct") or 0.0) for item in related_holdings), 2)
                events.append(
                    {
                        "id": event.get("id"),
                        "date": event_date,
                        "country_code": country_code,
                        "title": event.get("title"),
                        "subtitle": event.get("subtitle"),
                        "impact": event.get("impact"),
                        "type": event.get("type"),
                        "portfolio_weight": portfolio_weight,
                        "country_weight": round(country_weights.get(country_code, 0.0), 2),
                        "affected_holdings": [
                            {
                                "ticker": item.get("ticker"),
                                "name": item.get("name"),
                                "weight_pct": round(float(item.get("weight_pct") or 0.0), 2),
                            }
                            for item in related_holdings[:4]
                        ],
                        "summary": (
                            f"{country_code} 익스포저 {country_weights.get(country_code, 0.0):.1f}% 중 {portfolio_weight:.1f}%가 이 일정의 직접 영향권에 있습니다."
                            if event.get("type") == "earnings"
                            else f"{country_code} 시장 비중 {country_weights.get(country_code, 0.0):.1f}%에 영향을 줄 수 있는 거시 일정입니다."
                        ),
                    }
                )

    deduped: list[dict] = []
    seen: set[str] = set()
    for event in sorted(events, key=_event_rank):
        key = f"{event['id']}:{event['country_code']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)

    return {
        "generated_at": datetime.now().isoformat(),
        "window_days": window_days,
        "events": deduped[:12],
    }
