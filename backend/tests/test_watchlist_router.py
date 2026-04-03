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


if __name__ == "__main__":
    unittest.main()
