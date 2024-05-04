import os
from unittest import mock

from django.conf import settings

from zerver.lib.test_classes import ZulipTestCase
from zproject.email_backends import get_forward_address


class EmailLogTest(ZulipTestCase):
    def test_generate_and_clear_email_log(self) -> None:
        with self.settings(EMAIL_BACKEND="zproject.email_backends.EmailLogBackEnd"), mock.patch(
            "zproject.email_backends.EmailLogBackEnd._do_send_messages", lambda *args: 1
        ), self.assertLogs(level="INFO") as m, self.settings(DEVELOPMENT_LOG_EMAILS=True):
            with self.captureOnCommitCallbacks(execute=True):
                result = self.client_get("/emails/generate/")
            self.assertEqual(result.status_code, 302)
            self.assertIn("emails", result["Location"])

            result = self.client_get("/emails/")
            self.assert_in_success_response(["All emails sent in the Zulip"], result)

            result = self.client_get("/emails/clear/")
            self.assertEqual(result.status_code, 302)
            result = self.client_get(result["Location"])
            self.assertIn("Manually generate most emails", str(result.content))
            output_log = (
                "INFO:root:Emails sent in development are available at http://testserver/emails"
            )
            self.assertEqual(m.output, [output_log for i in range(18)])

    def test_forward_address_details(self) -> None:
        try:
            forward_address = "forward-to@example.com"
            result = self.client_post("/emails/", {"forward_address": forward_address})
            self.assert_json_success(result)

            self.assertEqual(get_forward_address(), forward_address)

            with self.settings(EMAIL_BACKEND="zproject.email_backends.EmailLogBackEnd"), mock.patch(
                "zproject.email_backends.EmailLogBackEnd._do_send_messages", lambda *args: 1
            ):
                result = self.client_get("/emails/generate/")
                self.assertEqual(result.status_code, 302)
                self.assertIn("emails", result["Location"])
                result = self.client_get(result["Location"])
                self.assert_in_success_response([forward_address], result)
        # Remove this file, even if the test fails, so that it does
        # not impact the state of the development environment.
        finally:
            os.remove(settings.FORWARD_ADDRESS_CONFIG_FILE)
