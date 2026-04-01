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

    def test_export_pdf_handles_multiline_summary_without_layout_error(self):
        payload = {
            "market_summary": "첫 줄 요약입니다.\n둘째 줄 요약입니다.\n셋째 줄도 이어집니다.",
            "institutional_analysis": {
                "consensus_summary": "기관 요약도 여러 줄로 안전하게 렌더되어야 합니다.",
                "policy_institutions": [],
                "sell_side": [],
            },
            "top_stocks": [
                {
                    "rank": 1,
                    "ticker": "005930.KS",
                    "name": "Samsung Electronics",
                    "score": 72.5,
                    "current_price": 81200,
                    "reason": "긴 설명이 있어도 줄바꿈 뒤 커서가 좌측 여백으로 정상 복귀해야 합니다.",
                }
            ],
        }

        rendered = export_service.export_pdf(payload, title="멀티라인 점검")

        self.assertIsInstance(rendered, bytes)
        self.assertTrue(rendered.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
