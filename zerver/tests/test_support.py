from django.conf import settings
from django.core import mail

from zerver.lib.test_classes import ZulipTestCase


class SupportPageTest(ZulipTestCase):
    def test_support_form_sends_email_on_cloud(self) -> None:
        # Ensure we are in cloud mode
        self.assertTrue(settings.CORPORATE_ENABLED)

        response = self.client_post(
            "/support/",
            {
                "name": "Test User",
                "zulip_url": "https://example.zulipchat.com",
                "message": "This is a test support message.",
            },
        )

        # Form submission should redirect
        self.assertEqual(response.status_code, 302)

        # Exactly one email should be sent
        self.assert_length(mail.outbox, 1)

        email = mail.outbox[0]

        # Verify recipient
        self.assertEqual(email.to, ["support@zulip.com"])

        # Subject comes from template
        self.assertIn("Support request for", email.subject)

        # Body should contain submitted content
        self.assertIn("Support request", email.subject)
        self.assertIn("Message", email.body)
