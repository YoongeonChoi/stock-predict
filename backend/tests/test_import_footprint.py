import json
import subprocess
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _imported_modules(module_name: str) -> set[str]:
    script = (
        "import json, sys\n"
        "before = set(sys.modules)\n"
        f"import {module_name}\n"
        "after = {name for name in sys.modules if name not in before}\n"
        "print(json.dumps(sorted(after)))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(json.loads(result.stdout))


class ImportFootprintTests(unittest.TestCase):
    def test_country_router_import_defers_heavy_services(self):
        imported = _imported_modules("app.routers.country")

        self.assertNotIn("app.services.market_service", imported)
        self.assertNotIn("app.data.yfinance_client", imported)
        self.assertNotIn("app.utils.market_calendar", imported)
        self.assertNotIn("app.analysis.stock_analyzer", imported)
        self.assertNotIn("pandas", imported)
        self.assertNotIn("yfinance", imported)
        self.assertNotIn("pandas_market_calendars", imported)

    def test_main_import_defers_public_route_heavy_dependencies(self):
        imported = _imported_modules("app.main")

        self.assertNotIn("app.services.market_service", imported)
        self.assertNotIn("app.services.prediction_capture_service", imported)
        self.assertNotIn("app.data.yfinance_client", imported)
        self.assertNotIn("app.analysis.stock_analyzer", imported)
        self.assertNotIn("pandas", imported)
        self.assertNotIn("yfinance", imported)
        self.assertNotIn("pandas_market_calendars", imported)


if __name__ == "__main__":
    unittest.main()
