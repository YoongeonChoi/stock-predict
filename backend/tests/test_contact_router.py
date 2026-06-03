import unittest
from unittest.mock import AsyncMock, patch

from app.services.public_rate_limit_service import reset_public_rate_limit_state
from client_helpers import patched_client


VALID_PAYLOAD = {
    "name": "홍길동",
    "email": "User@Example.com",
    "subject": "협업 문의",
    "message": "프로젝트 협업 가능 여부를 문의드립니다.",
}


class ContactRouterTests(unittest.TestCase):
    def setUp(self):
        reset_public_rate_limit_state()

    def tearDown(self):
        reset_public_rate_limit_state()

    def test_contact_submission_saves_to_supabase(self):
        insert = AsyncMock(return_value={"id": "message-1", **VALID_PAYLOAD})
        notifier = AsyncMock(return_value=None)

        with (
            patch("app.services.contact_service.supabase_client.contact_message_insert", new=insert),
            patch("app.services.contact_notifier.notify_contact_received", new=notifier),
        ):
            with patched_client() as client:
                response = client.post("/api/contact", json=VALID_PAYLOAD, headers={"User-Agent": "contact-test"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["message"], "문의가 정상적으로 접수되었습니다.")

        insert.assert_awaited_once()
        saved = insert.call_args.args[0]
        self.assertEqual(saved["name"], "홍길동")
        self.assertEqual(saved["email"], "user@example.com")
        self.assertEqual(saved["subject"], "협업 문의")
        self.assertEqual(saved["message"], "프로젝트 협업 가능 여부를 문의드립니다.")
        self.assertEqual(saved["status"], "received")
        self.assertEqual(saved["user_agent"], "contact-test")
        self.assertIn("ip_hash", saved)
        self.assertIsNone(saved["ip_hash"])
        self.assertNotIn("ip", saved)
        notifier.assert_awaited_once()

    def test_contact_submission_rejects_invalid_email(self):
        with patch("app.services.contact_service.supabase_client.contact_message_insert", new=AsyncMock()) as insert:
            with patched_client() as client:
                response = client.post("/api/contact", json={**VALID_PAYLOAD, "email": "invalid"})

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error_code"], "SP-6018")
        self.assertIn("이메일 형식", body["error"])
        insert.assert_not_awaited()

    def test_contact_submission_rejects_short_message(self):
        with patch("app.services.contact_service.supabase_client.contact_message_insert", new=AsyncMock()) as insert:
            with patched_client() as client:
                response = client.post("/api/contact", json={**VALID_PAYLOAD, "message": "짧음"})

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6018")
        self.assertIn("메시지", body["error"])
        insert.assert_not_awaited()

    def test_contact_submission_rejects_empty_subject(self):
        with patch("app.services.contact_service.supabase_client.contact_message_insert", new=AsyncMock()) as insert:
            with patched_client() as client:
                response = client.post("/api/contact", json={**VALID_PAYLOAD, "subject": " "})

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6018")
        self.assertIn("제목", body["error"])
        insert.assert_not_awaited()

    def test_contact_submission_rejects_honeypot(self):
        with patch("app.services.contact_service.supabase_client.contact_message_insert", new=AsyncMock()) as insert:
            with patched_client() as client:
                response = client.post("/api/contact", json={**VALID_PAYLOAD, "company": "bot"})

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error_code"], "SP-6018")
        insert.assert_not_awaited()

    def test_contact_submission_rate_limits_fast_repeat(self):
        insert = AsyncMock(return_value={"id": "message-1"})

        with patch("app.services.contact_service.supabase_client.contact_message_insert", new=insert):
            with patched_client() as client:
                first = client.post("/api/contact", json=VALID_PAYLOAD)
                second = client.post("/api/contact", json={**VALID_PAYLOAD, "subject": "두 번째 문의"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        body = second.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error_code"], "SP-6019")
        self.assertIn("Retry-After", second.headers)
        self.assertEqual(insert.await_count, 1)

    def test_contact_submission_save_failure_hides_internal_error(self):
        insert = AsyncMock(side_effect=RuntimeError("supabase secret detail"))

        with patch("app.services.contact_service.supabase_client.contact_message_insert", new=insert):
            with patched_client() as client:
                response = client.post("/api/contact", json=VALID_PAYLOAD)

        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error_code"], "SP-5020")
        self.assertIn("문의 저장 설정", body["error"])
        self.assertNotIn("supabase secret detail", str(body))


if __name__ == "__main__":
    unittest.main()
