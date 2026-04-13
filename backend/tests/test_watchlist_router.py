import unittest
from unittest.mock import AsyncMock, patch

from client_helpers import patched_client


class WatchlistRouterTests(unittest.TestCase):
    def test_add_watchlist_records_auth_write_trace(self):
        with (
            patch(
                "app.routers.watchlist.watchlist_service.add_to_watchlist",
                new=AsyncMock(return_value={"ticker": "005930.KS", "country_code": "KR", "note": "normalized"}),
            ),
            patch("app.routers.watchlist.route_stability_service.record_route_trace") as record_trace,
        ):
            with patched_client(authenticated=True) as client:
                response = client.post("/api/watchlist/005930?country_code=KR")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "added")
        trace = record_trace.call_args.args[1]
        self.assertEqual(trace["operation_kind"], "auth-write")
        self.assertEqual(trace["panel_key"], "watchlist_mutation")
        self.assertEqual(trace["dependency_key"], "supabase")
        self.assertEqual(trace["served_state"], "fresh")

    def test_add_watchlist_records_write_failed_trace(self):
        with (
            patch(
                "app.routers.watchlist.watchlist_service.add_to_watchlist",
                new=AsyncMock(side_effect=RuntimeError("write failed")),
            ),
            patch("app.routers.watchlist.route_stability_service.record_route_trace") as record_trace,
        ):
            with patched_client(authenticated=True) as client:
                response = client.post("/api/watchlist/005930?country_code=KR")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error_code"], "SP-5003")
        trace = record_trace.call_args.args[1]
        self.assertEqual(trace["operation_kind"], "auth-write")
        self.assertEqual(trace["failure_class"], "write_failed")
        self.assertEqual(trace["fallback_reason"], "watchlist_write_error")
        self.assertEqual(trace["served_state"], "degraded")

    def test_enable_tracking_records_auth_write_trace(self):
        with (
            patch(
                "app.routers.watchlist.watchlist_tracking_service.set_tracking_enabled",
                new=AsyncMock(
                    return_value={
                        "ticker": "005930.KS",
                        "country_code": "KR",
                        "tracking_started_at": "2026-04-04T00:00:00",
                        "tracking_updated_at": "2026-04-04T00:00:00",
                    }
                ),
            ),
            patch("app.routers.watchlist.route_stability_service.record_route_trace") as record_trace,
        ):
            with patched_client(authenticated=True) as client:
                response = client.post("/api/watchlist/005930/tracking?country_code=KR")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "tracking_enabled")
        trace = record_trace.call_args.args[1]
        self.assertEqual(trace["operation_kind"], "auth-write")
        self.assertEqual(trace["panel_key"], "watchlist_tracking")
        self.assertEqual(trace["dependency_key"], "supabase")

    def test_tracking_detail_returns_sp6017_when_watchlist_item_is_missing(self):
        with (
            patch(
                "app.routers.watchlist.watchlist_tracking_service.get_tracking_detail",
                new=AsyncMock(return_value=None),
            ),
            patch("app.routers.watchlist.route_stability_service.record_route_trace") as record_trace,
        ):
            with patched_client(authenticated=True) as client:
                response = client.get("/api/watchlist/005930/tracking-detail?country_code=KR")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error_code"], "SP-6017")
        trace = record_trace.call_args.args[1]
        self.assertEqual(trace["operation_kind"], "auth-read")
        self.assertEqual(trace["failure_class"], "contract_mismatch")
        self.assertEqual(trace["panel_key"], "watchlist_tracking_detail")

    def test_tracking_detail_returns_inactive_payload_without_error(self):
        with (
            patch(
                "app.routers.watchlist.watchlist_tracking_service.get_tracking_detail",
                new=AsyncMock(
                    return_value={
                        "watchlist_meta": {"ticker": "005930.KS", "tracking_enabled": False},
                        "tracking_state": "inactive",
                        "latest_snapshot": {"available": True},
                        "prediction_change_summary": {"available": False, "message": "기록 축적 중"},
                        "prediction_history": [],
                        "realized_accuracy_summary": {"available": False, "message": "기록 축적 중"},
                        "current_context_summary": {"available": True, "summary": "현재 판단 근거"},
                        "partial": False,
                        "fallback_reason": None,
                        "panel_states": {
                            "latest_snapshot": "ready",
                            "prediction_history": "inactive",
                            "realized_accuracy": "inactive",
                            "current_context": "ready",
                        },
                    }
                ),
            ),
            patch("app.routers.watchlist.route_stability_service.record_route_trace") as record_trace,
        ):
            with patched_client(authenticated=True) as client:
                response = client.get("/api/watchlist/005930/tracking-detail?country_code=KR")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["tracking_state"], "inactive")
        trace = record_trace.call_args.args[1]
        self.assertEqual(trace["operation_kind"], "auth-read")
        self.assertEqual(trace["panel_key"], "watchlist_tracking_detail")
        self.assertEqual(trace["served_state"], "fresh")


if __name__ == "__main__":
    unittest.main()
