import os
import mock
from django.conf import settings

from zerver.lib.test_classes import ZulipTestCase
from zproject.email_backends import get_forward_address

class EmailLogTest(ZulipTestCase):
    def test_generate_and_clear_email_log(self) -> None:
        with self.settings(EMAIL_BACKEND='zproject.email_backends.EmailLogBackEnd'), \
                mock.patch('zproject.email_backends.EmailLogBackEnd.send_email_smtp'), \
                mock.patch('logging.info', return_value=None), \
                self.settings(DEVELOPMENT_LOG_EMAILS=True):
            result = self.client_get('/emails/generate/')
            self.assertEqual(result.status_code, 302)
            self.assertIn('emails', result['Location'])

            result = self.client_get("/emails/")
            self.assert_in_success_response(["All the emails sent in the Zulip"], result)

            result = self.client_get('/emails/clear/')
            self.assertEqual(result.status_code, 302)
            result = self.client_get(result['Location'])
            self.assertIn('manually generate most of the emails by clicking', str(result.content))

    def test_forward_address_details(self) -> None:
        forward_address = "forward-to@example.com"
        result = self.client_post("/emails/", {"forward_address": forward_address})
        self.assert_json_success(result)

        self.assertEqual(get_forward_address(), forward_address)

        with self.settings(EMAIL_BACKEND='zproject.email_backends.EmailLogBackEnd'), \
                mock.patch('logging.info', return_value=None):
            with mock.patch('zproject.email_backends.EmailLogBackEnd.send_email_smtp'):
                result = self.client_get('/emails/generate/')
                self.assertEqual(result.status_code, 302)
                self.assertIn('emails', result['Location'])
                result = self.client_get(result['Location'])
                self.assert_in_success_response([forward_address], result)
        os.remove(settings.FORWARD_ADDRESS_CONFIG_FILE)
