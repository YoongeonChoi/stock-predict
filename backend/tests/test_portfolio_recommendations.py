import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from client_helpers import patched_client
from app.services import portfolio_recommendation_service


def _sample_opportunity(
    *,
    ticker: str,
    country_code: str,
    sector: str,
    up_probability: float,
    predicted_return_pct: float,
    opportunity_score: float,
    action: str = "accumulate",
    execution_bias: str = "lean_long",
) -> dict:
    return {
        "ticker": ticker,
        "name": ticker,
        "country_code": country_code,
        "sector": sector,
        "up_probability": up_probability,
        "predicted_return_pct": predicted_return_pct,
        "opportunity_score": opportunity_score,
        "confidence": 67.0,
        "execution_bias": execution_bias,
        "setup_label": "추세 재개",
        "action": action,
        "entry_low": 100.0,
        "entry_high": 103.0,
        "stop_loss": 96.0,
        "take_profit_1": 110.0,
        "take_profit_2": 116.0,
        "risk_reward_estimate": 2.1,
        "risk_flags": [],
        "thesis": ["수급과 추세가 동시에 양호합니다."],
    }


class PortfolioRecommendationTests(unittest.TestCase):
    def test_conditional_recommendation_filters_country_sector_and_existing_holding(self):
        portfolio_snapshot = {
            "holdings": [
                {
                    "ticker": "005930.KS",
                    "name": "Samsung Electronics",
                    "country_code": "KR",
                    "sector": "Information Technology",
                    "weight_pct": 42.0,
                }
            ],
            "risk": {"overall_label": "moderate"},
        }
        kr_response = {
            "country_code": "KR",
            "market_regime": {"label": "완만한 위험 선호", "stance": "risk_on"},
            "actionable_count": 3,
            "universe_note": "",
            "opportunities": [
                _sample_opportunity(
                    ticker="005930.KS",
                    country_code="KR",
                    sector="Information Technology",
                    up_probability=58.0,
                    predicted_return_pct=2.0,
                    opportunity_score=71.0,
                ),
                _sample_opportunity(
                    ticker="000660.KS",
                    country_code="KR",
                    sector="Information Technology",
                    up_probability=61.0,
                    predicted_return_pct=3.2,
                    opportunity_score=79.0,
                ),
                _sample_opportunity(
                    ticker="035420.KS",
                    country_code="KR",
                    sector="Communication Services",
                    up_probability=63.0,
                    predicted_return_pct=2.8,
                    opportunity_score=77.0,
                ),
            ],
        }

        with (
            patch("app.services.portfolio_recommendation_service.portfolio_service.get_portfolio", new=AsyncMock(return_value=portfolio_snapshot)),
            patch("app.services.portfolio_recommendation_service.supabase_client.watchlist_list", new=AsyncMock(return_value=[])),
            patch("app.services.portfolio_recommendation_service.supabase_client.portfolio_list", new=AsyncMock(return_value=[])),
            patch("app.services.portfolio_recommendation_service.market_service.get_market_opportunities", new=AsyncMock(return_value=kr_response)),
        ):
            result = asyncio.run(
                portfolio_recommendation_service.get_conditional_recommendations(
                    user_id="user-123",
                    country_code="KR",
                    sector="Information Technology",
                    style="balanced",
                    max_items=4,
                    min_up_probability=55.0,
                    exclude_holdings=True,
                    watchlist_only=False,
                )
            )

        tickers = [item["ticker"] for item in result["recommendations"]]
        self.assertIn("000660.KS", tickers)
        self.assertNotIn("005930.KS", tickers)
        self.assertTrue(all(item["country_code"] == "KR" for item in result["recommendations"]))
        self.assertTrue(all(item["sector"] == "Information Technology" for item in result["recommendations"]))

    def test_conditional_recommendation_cache_key_tracks_portfolio_state(self):
        empty_portfolio_rows: list[dict] = []
        invested_portfolio_rows = [
            {
                "ticker": "000660.KS",
                "country_code": "KR",
                "buy_price": 180000.0,
                "quantity": 3.0,
                "buy_date": "2026-03-20",
            }
        ]
        empty_snapshot = {"holdings": [], "risk": {"overall_label": "moderate"}}
        invested_snapshot = {
            "holdings": [
                {
                    "ticker": "000660.KS",
                    "name": "SK hynix",
                    "country_code": "KR",
                    "sector": "Information Technology",
                    "weight_pct": 38.0,
                }
            ],
            "risk": {"overall_label": "moderate"},
        }
        kr_response = {
            "country_code": "KR",
            "market_regime": {"label": "완만한 위험 선호", "stance": "risk_on"},
            "actionable_count": 2,
            "universe_note": "",
            "opportunities": [
                _sample_opportunity(
                    ticker="000660.KS",
                    country_code="KR",
                    sector="Information Technology",
                    up_probability=61.0,
                    predicted_return_pct=3.2,
                    opportunity_score=79.0,
                ),
            ],
        }

        async def run_once(portfolio_rows, portfolio_snapshot):
            with (
                patch("app.services.portfolio_recommendation_service.supabase_client.portfolio_list", new=AsyncMock(return_value=portfolio_rows)),
                patch("app.services.portfolio_recommendation_service.supabase_client.watchlist_list", new=AsyncMock(return_value=[])),
                patch("app.services.portfolio_recommendation_service.portfolio_service.get_portfolio", new=AsyncMock(return_value=portfolio_snapshot)),
                patch("app.services.portfolio_recommendation_service.market_service.get_market_opportunities", new=AsyncMock(return_value=kr_response)),
                patch("app.services.portfolio_recommendation_service.cache.get", new=AsyncMock(return_value=None)) as cache_get,
                patch("app.services.portfolio_recommendation_service.cache.set", new=AsyncMock()),
            ):
                result = await portfolio_recommendation_service.get_conditional_recommendations(
                    user_id="user-123",
                    country_code="KR",
                    sector="Information Technology",
                    style="balanced",
                    max_items=4,
                    min_up_probability=55.0,
                    exclude_holdings=True,
                    watchlist_only=False,
                )
                return cache_get.await_args.args[0], result

        key_empty, result_empty = asyncio.run(run_once(empty_portfolio_rows, empty_snapshot))
        key_invested, result_invested = asyncio.run(run_once(invested_portfolio_rows, invested_snapshot))

        self.assertNotEqual(key_empty, key_invested)
        self.assertEqual(len(result_empty["recommendations"]), 1)
        self.assertEqual(result_invested["recommendations"], [])

    def test_conditional_recommendation_keeps_defensive_candidates_visible(self):
        portfolio_snapshot = {
            "holdings": [],
            "risk": {"overall_label": "elevated"},
        }
        kr_response = {
            "country_code": "KR",
            "market_regime": {"label": "리스크오프 경계", "stance": "risk_off"},
            "actionable_count": 2,
            "universe_note": "",
            "opportunities": [
                _sample_opportunity(
                    ticker="005930.KS",
                    country_code="KR",
                    sector="Information Technology",
                    up_probability=56.0,
                    predicted_return_pct=1.8,
                    opportunity_score=78.0,
                    action="reduce_risk",
                    execution_bias="capital_preservation",
                ),
                _sample_opportunity(
                    ticker="035420.KS",
                    country_code="KR",
                    sector="Communication Services",
                    up_probability=61.0,
                    predicted_return_pct=2.2,
                    opportunity_score=74.0,
                ),
            ],
        }

        with (
            patch("app.services.portfolio_recommendation_service.portfolio_service.get_portfolio", new=AsyncMock(return_value=portfolio_snapshot)),
            patch("app.services.portfolio_recommendation_service.supabase_client.watchlist_list", new=AsyncMock(return_value=[])),
            patch("app.services.portfolio_recommendation_service.supabase_client.portfolio_list", new=AsyncMock(return_value=[])),
            patch("app.services.portfolio_recommendation_service.market_service.get_market_opportunities", new=AsyncMock(return_value=kr_response)),
        ):
            result = asyncio.run(
                portfolio_recommendation_service.get_conditional_recommendations(
                    user_id="user-123",
                    country_code="KR",
                    sector="ALL",
                    style="defensive",
                    max_items=4,
                    min_up_probability=50.0,
                    exclude_holdings=False,
                    watchlist_only=False,
                )
            )

        defensive = next((item for item in result["recommendations"] if item["ticker"] == "005930.KS"), None)
        self.assertIsNotNone(defensive)
        self.assertEqual(defensive["execution_bias"], "capital_preservation")

    def _authenticated_client(self):
        return patched_client(authenticated=True)

    def test_portfolio_recommendation_routes_exist(self):
        conditional_payload = {
            "generated_at": "2026-03-24T00:00:00",
            "filters": {
                "country_code": "KR",
                "sector": "ALL",
                "style": "balanced",
                "max_items": 5,
                "min_up_probability": 54.0,
                "exclude_holdings": True,
                "watchlist_only": False,
            },
            "options": {
                "countries": ["KR"],
                "sectors": ["ALL", "Information Technology"],
                "styles": ["defensive", "balanced", "offensive"],
            },
            "budget": {
                "style": "balanced",
                "style_label": "균형형",
                "recommended_equity_pct": 82.0,
                "cash_buffer_pct": 18.0,
                "target_position_count": 5,
                "max_single_weight_pct": 14.5,
                "max_country_weight_pct": 100.0,
                "max_sector_weight_pct": 28.0,
            },
            "summary": {
                "selected_count": 1,
                "candidate_count": 2,
                "watchlist_focus_count": 0,
                "existing_overlap_count": 0,
                "model_up_probability": 60.0,
                "model_predicted_return_pct": 2.5,
                "focus_country": "KR",
                "focus_sector": "Information Technology",
            },
            "recommendations": [],
            "notes": [],
            "market_view": [],
        }
        optimal_payload = {
            "generated_at": "2026-03-24T00:00:00",
            "objective": "자동 최적화",
            "style": "balanced",
            "budget": conditional_payload["budget"],
            "summary": conditional_payload["summary"],
            "recommendations": [],
            "notes": [],
            "market_view": [],
        }

        with (
            patch("app.routers.portfolio.portfolio_recommendation_service.get_conditional_recommendations", new=AsyncMock(return_value=conditional_payload)),
            patch("app.routers.portfolio.portfolio_recommendation_service.get_optimal_recommendation", new=AsyncMock(return_value=optimal_payload)),
        ):
            with self._authenticated_client() as client:
                conditional = client.get("/api/portfolio/recommendations/conditional?country_code=KR&max_items=5")
                optimal = client.get("/api/portfolio/recommendations/optimal")

        self.assertEqual(conditional.status_code, 200)
        self.assertEqual(optimal.status_code, 200)
        self.assertEqual(conditional.json()["filters"]["country_code"], "KR")
        self.assertEqual(optimal.json()["style"], "balanced")


if __name__ == "__main__":
    unittest.main()
