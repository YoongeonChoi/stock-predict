import unittest

from app.services import export_service


class ExportServiceTests(unittest.TestCase):
    def test_export_pdf_returns_bytes_payload(self):
        payload = {
            "market_summary": "테스트 PDF 내보내기",
            "score": {"total": 72.5},
            "top_stocks": [{"rank": 1, "ticker": "005930.KS", "name": "Samsung Electronics", "score": 72.5, "current_price": 81200}],
        }

        rendered = export_service.export_pdf(payload, title="내보내기 점검")

        self.assertIsInstance(rendered, bytes)
        self.assertTrue(rendered.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
