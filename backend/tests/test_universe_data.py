import unittest
from unittest.mock import AsyncMock, patch

from app.data import universe_data


class UniverseDataTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_krx_listing_universe_returns_full_selection(self):
        rows = []
        for index in range(1200):
            market = "유가" if index % 3 == 0 else "코스닥" if index % 3 == 1 else "코넥스"
            industry = "반도체 제조업" if index % 3 == 0 else "일반 목적용 기계 제조업" if index % 3 == 1 else "기타 금융업"
            suffix = ".KS" if market == "유가" else ".KQ"
            rows.append((market, industry, f"{index:06d}{suffix}"))

        with (
            patch("app.data.cache.get", new=AsyncMock(return_value=None)),
            patch("app.data.cache.set", new=AsyncMock()),
            patch("app.data.universe_data._fetch_krx_listing_sync", return_value=rows),
        ):
            selection = await universe_data.fetch_krx_listing_universe("KR")

        self.assertIsNotNone(selection)
        self.assertEqual(selection.source, "krx_listing")
        self.assertGreaterEqual(sum(len(tickers) for tickers in selection.sectors.values()), 1000)
        self.assertIn("KRX 상장사 목록 기준 전종목", selection.note)

    async def test_resolve_opportunity_universe_prefers_krx_listing_for_kr(self):
        krx_listing = universe_data.UniverseSelection(
            sectors={"반도체 제조업": ["005930.KS"]},
            source="krx_listing",
            note="KRX 상장사 목록 기준 전종목 1개를 1차 스캔합니다.",
        )

        with (
            patch("app.data.universe_data.fetch_krx_listing_universe", new=AsyncMock(return_value=krx_listing)),
            patch("app.data.universe_data.resolve_universe", new=AsyncMock()),
        ):
            selection = await universe_data.resolve_opportunity_universe("KR")

        self.assertEqual(selection.source, "krx_listing")
        self.assertEqual(selection.sectors["반도체 제조업"], ["005930.KS"])


if __name__ == "__main__":
    unittest.main()
