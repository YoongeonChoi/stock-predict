import unittest

from app.models.forecast import ForecastScenario, NextDayForecast


class RootAppImportTests(unittest.TestCase):
    def test_root_level_imports_can_resolve_backend_app_package(self) -> None:
        self.assertIsNotNone(ForecastScenario)
        self.assertIsNotNone(NextDayForecast)


if __name__ == "__main__":
    unittest.main()
