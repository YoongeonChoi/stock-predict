import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.routers import briefing


class BriefingRouterGuardTests(unittest.TestCase):
    def test_startup_guard_releases_after_stable_window_even_without_prewarm(self):
        with (
            patch("app.routers.briefing.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch(
                "app.routers.briefing.get_runtime_state",
                return_value={
                    "started_at": (
                        datetime.now(timezone.utc)
                        - timedelta(seconds=briefing.PUBLIC_STARTUP_GUARD_STABLE_RELEASE_SECONDS + 10)
                    ).isoformat(),
                    "startup_tasks": [],
                },
            ),
            patch(
                "app.routers.briefing._public_memory_pressure_ratio",
                return_value=briefing.PUBLIC_STARTUP_GUARD_STABLE_RELEASE_PRESSURE_RATIO - 0.01,
            ),
        ):
            self.assertFalse(briefing._should_use_startup_public_route_guard())

    def test_startup_guard_releases_after_prewarm_warning_when_pressure_is_low(self):
        with (
            patch("app.routers.briefing.settings", new=SimpleNamespace(startup_memory_safe_mode=True)),
            patch(
                "app.routers.briefing.get_runtime_state",
                return_value={
                    "started_at": (
                        datetime.now(timezone.utc)
                        - timedelta(seconds=briefing.PUBLIC_STARTUP_GUARD_EARLY_RELEASE_SECONDS + 15)
                    ).isoformat(),
                    "startup_tasks": [{"name": "public_dashboard_prewarm", "status": "warning"}],
                },
            ),
            patch(
                "app.routers.briefing._public_memory_pressure_ratio",
                return_value=briefing.PUBLIC_STARTUP_GUARD_EARLY_RELEASE_PRESSURE_RATIO - 0.01,
            ),
        ):
            self.assertFalse(briefing._should_use_startup_public_route_guard())
