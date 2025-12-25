from django.conf import settings
from django.core import mail

from zerver.lib.test_classes import ZulipTestCase


class SupportPageTest(ZulipTestCase):
    def test_support_form_sends_email_self_hosted(self) -> None:
        # Force self-hosted behavior
        self.override_settings(CORPORATE_ENABLED=False)

        self.login("hamlet")

        response = self.client.post(
            "/support/",
            {
                "name": "Hamlet",
                "zulip_url": "https://example.zulipchat.com",
                "message": "Help! Something is broken.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertIn("Zulip support request", email.subject)
        self.assertIn("Hamlet", email.body)
        self.assertIn("https://example.zulipchat.com", email.body)
        self.assertIn("Something is broken", email.body)

    def test_support_form_sends_email_cloud(self) -> None:
        # Force cloud behavior
        self.override_settings(CORPORATE_ENABLED=True, ZULIP_SUPPORT_EMAIL="support@zulip.com")

        self.login("hamlet")

        response = self.client.post(
            "/support/",
            {
                "name": "Hamlet",
                "zulip_url": "https://chat.zulip.com",
                "message": "Cloud support issue",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        email = mail.outbox[0]
        self.assertIn("Cloud support issue", email.body)
        self.assertIn("support@zulip.com", email.to)
