import unittest

from app.services import export_service


class ExportServiceTests(unittest.TestCase):
    def test_sanitize_for_pdf_replaces_unsupported_emoji(self):
        sanitized = export_service._sanitize_for_pdf("시장 요약 📉 / 자금 흐름 💸 / 경고 ⚠️")

        self.assertEqual(sanitized, "시장 요약 [하락] / 자금 흐름 [현금유출] / 경고 [주의]")

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

    def test_export_pdf_handles_emoji_summary_without_layout_error(self):
        payload = {
            "market_summary": "시장 충격 📉 이후 현금 유출 💸 이 계속됐습니다.",
            "analysis_summary": "추가 경고 ⚠️ 는 치환 후에도 PDF 렌더가 유지되어야 합니다.",
        }

        rendered = export_service.export_pdf(payload, title="이모지 점검")

        self.assertIsInstance(rendered, bytes)
        self.assertTrue(rendered.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
