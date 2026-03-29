import unittest

from app.analysis.stock_graph_context import build_stock_graph_context


def _price_history(start: float = 100.0, step: float = 1.0, days: int = 60) -> list[dict]:
    rows = []
    for index in range(days):
        close = start + step * index
        rows.append(
            {
                "date": f"2026-02-{(index % 28) + 1:02d}",
                "open": close - 0.6,
                "high": close + 1.1,
                "low": close - 1.2,
                "close": close,
                "volume": 1_000_000 + index * 1200,
            }
        )
    return rows


class StockGraphContextTests(unittest.TestCase):
    def test_graph_context_gracefully_returns_empty_without_context(self):
        context = build_stock_graph_context(
            price_history=_price_history(),
            benchmark_history=[],
            analyst_context={},
            fundamental_context={},
        )

        self.assertFalse(context.used)
        self.assertEqual(context.coverage, 0.0)
        self.assertEqual(context.peer_count, 0)
        self.assertEqual(context.graph_context_score, 0.0)

    def test_graph_context_falls_back_to_sector_when_peers_are_missing(self):
        context = build_stock_graph_context(
            price_history=_price_history(),
            benchmark_history=_price_history(start=95.0, step=0.7),
            analyst_context={},
            fundamental_context={
                "sector": "Communication Services",
                "industry": "Interactive Media",
            },
        )

        self.assertTrue(context.used)
        self.assertEqual(context.peer_count, 0)
        self.assertGreater(context.coverage, 0.0)
        self.assertGreater(context.news_relation_support, 0.0)
        self.assertGreaterEqual(context.graph_context_score, -1.0)
        self.assertLessEqual(context.graph_context_score, 1.0)

    def test_graph_context_uses_peer_snapshots_and_clips_coverage(self):
        asset_history = _price_history(start=110.0, step=0.8, days=80)
        asset_returns = [0.0015 + 0.0002 * (index % 4) for index in range(70)]
        context = build_stock_graph_context(
            price_history=asset_history,
            benchmark_history=_price_history(start=108.0, step=0.45, days=80),
            analyst_context={
                "graph_context_seed": {
                    "peer_snapshots": [
                        {
                            "return_5d": 0.045,
                            "return_20d": 0.14,
                            "return_series": asset_returns,
                        },
                        {
                            "return_5d": 0.03,
                            "return_20d": 0.11,
                            "return_series": [value * 0.9 for value in asset_returns],
                        },
                    ],
                    "news_relation_support": 3.5,
                }
            },
            fundamental_context={"sector": "Technology"},
        )

        self.assertTrue(context.used)
        self.assertEqual(context.peer_count, 2)
        self.assertGreater(context.correlation_support, 0.0)
        self.assertGreater(context.coverage, 0.0)
        self.assertLessEqual(context.coverage, 1.0)
        self.assertLessEqual(context.news_relation_support, 1.0)
        self.assertGreaterEqual(context.graph_context_score, -1.0)
        self.assertLessEqual(context.graph_context_score, 1.0)


if __name__ == "__main__":
    unittest.main()
