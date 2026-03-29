import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.services import research_archive_service as service


class ResearchArchiveHelpersTests(unittest.TestCase):
    def test_strip_html_and_normalize_date(self):
        self.assertEqual(service._strip_html("<p>Hello&nbsp;<b>World</b></p>"), "Hello World")
        self.assertEqual(service._normalize_date("2026.03.23"), "2026-03-23")
        self.assertEqual(service._normalize_date("Mon, 23 Mar 2026 10:30:00 +0000"), "2026-03-23")

    def test_to_absolute_promotes_https(self):
        self.assertEqual(
            service._to_absolute("/paper.pdf", "http://example.com/research/"),
            "https://example.com/paper.pdf",
        )

    def test_filter_status_snapshot_normalizes_regions_and_sources(self):
        snapshot = {
            "total_reports": 10,
            "source_count": 2,
            "regions": [{"region_code": "KR", "total": 6}, {"region_code": "US", "total": 4}],
            "sources": [
                {"source_id": "bok_monetary_policy", "source_name": "한국은행 통화정책", "total": 6},
                {"source_id": "fed_press_monetary", "source_name": "Federal Reserve Monetary Policy", "total": 4},
            ],
        }

        filtered = service._filter_status_snapshot(snapshot)

        self.assertEqual(filtered["total_reports"], 10)
        self.assertEqual(filtered["source_count"], 2)
        self.assertEqual(len(filtered["regions"]), 2)
        self.assertEqual(len(filtered["sources"]), 2)
        self.assertEqual(filtered["regions"], filtered["by_region"])
        self.assertEqual(filtered["sources"], filtered["by_source"])


class ResearchArchiveServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_public_research_reports_aggregates_sources(self):
        source = service.ResearchSource(
            id="unit_source",
            name="Unit Source",
            region_code="KR",
            organization_type="test",
            language="ko",
            category="unit",
            home_url="https://example.com",
            feed_url="https://example.com/feed.xml",
        )
        report = {
            "source_id": source.id,
            "source_name": source.name,
            "region_code": source.region_code,
            "organization_type": source.organization_type,
            "language": source.language,
            "category": source.category,
            "title": "테스트 리포트",
            "summary": "요약",
            "published_at": datetime.now(timezone.utc).date().isoformat(),
            "report_url": "https://example.com/report",
            "pdf_url": "https://example.com/report.pdf",
            "metadata": {},
        }

        with (
            patch.object(service, "SOURCES", (source,)),
            patch.object(service, "_fetch_source_reports", new=AsyncMock(return_value=[report])),
            patch.object(service.db, "cache_get", new=AsyncMock(return_value=None)),
            patch.object(service.db, "research_report_upsert", new=AsyncMock()) as upsert_mock,
            patch.object(service.db, "research_report_status", new=AsyncMock(return_value={"total_reports": 1, "todays_reports": 1, "source_count": 1, "by_region": [], "by_source": []})),
            patch.object(service.db, "cache_set", new=AsyncMock()) as cache_set_mock,
        ):
            status = await service.sync_public_research_reports(force=True)

        self.assertEqual(status["processed_total"], 1)
        self.assertEqual(status["error_count"], 0)
        self.assertEqual(status["source_results"][0]["source_id"], "unit_source")
        upsert_mock.assert_awaited_once()
        cache_set_mock.assert_awaited_once()

    async def test_list_public_research_reports_marks_pdf_and_today(self):
        today_iso = datetime.now(timezone.utc).date().isoformat()
        rows = [
            {
                "id": 1,
                "source_id": "bok_monetary_policy",
                "title": "테스트",
                "summary": "<p>요약&nbsp;<b>강조</b></p>",
                "published_at": today_iso,
                "pdf_url": "https://example.com/file.pdf",
            },
            {
                "id": 2,
                "source_id": "bok_monetary_policy",
                "title": "이전 자료",
                "summary": None,
                "published_at": "2026-03-20",
                "pdf_url": None,
            },
        ]

        with (
            patch.object(service, "sync_public_research_reports", new=AsyncMock()),
            patch.object(service.db, "research_report_list", new=AsyncMock(return_value=rows)),
        ):
            result = await service.list_public_research_reports(region_code="KR", limit=10, auto_refresh=True)

        self.assertTrue(result[0]["is_new_today"])
        self.assertTrue(result[0]["has_pdf"])
        self.assertEqual(result[0]["summary_plain"], "요약 강조")
        self.assertFalse(result[1]["is_new_today"])
        self.assertFalse(result[1]["has_pdf"])
        self.assertEqual(result[1]["summary_plain"], "")

    async def test_list_public_research_reports_filters_out_inactive_sources(self):
        rows = [
            {
                "id": 1,
                "source_id": "fed_feds",
                "title": "이전 실험 소스",
                "published_at": "2026-03-28",
                "pdf_url": None,
            },
            {
                "id": 2,
                "source_id": "fed_press_monetary",
                "title": "활성 소스",
                "published_at": "2026-03-27",
                "pdf_url": None,
            },
        ]

        with (
            patch.object(service, "sync_public_research_reports", new=AsyncMock()),
            patch.object(service.db, "research_report_list", new=AsyncMock(return_value=rows)),
        ):
            result = await service.list_public_research_reports(region_code="US", limit=10, auto_refresh=True)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_id"], "fed_press_monetary")


if __name__ == "__main__":
    unittest.main()
