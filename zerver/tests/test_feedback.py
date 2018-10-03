from datetime import datetime

from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core import mail
import mock

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.redis_utils import get_redis_client

class TestFeedbackBot(ZulipTestCase):
    @patch('logging.info')
    def test_pm_to_feedback_bot(self, logging_info_mock: MagicMock) -> None:
        with self.settings(ENABLE_FEEDBACK=True):
            user_email = self.example_email("othello")
            self.send_personal_message(user_email, settings.FEEDBACK_BOT,
                                       content="I am a feedback message.")
            logging_info_mock.assert_called_once_with("Received feedback from {}".format(user_email))

class TestContactForm(ZulipTestCase):
    # Test to make sure that a maximum of only 100 submissions are made through
    # contact form a in day.
    def test_contact_form(self) -> None:
        client = get_redis_client()
        date1 = datetime(2017, 11, 22)
        day1 = date1.day

        date2 = datetime(2017, 11, 23)
        day2 = date2.day

        client.delete(day1)
        client.delete(day2)

        with mock.patch("zerver.lib.feedback.datetime", mock.Mock(today=lambda: date1)):
            response = self.client_get("/contact/")
            self.assert_in_success_response(["Submit"], response)

            user = self.example_user("hamlet")

            self.login(user.email)
            response = self.client_get("/contact/")

            for i in range(0, 11):
                response = self.client_get("/contact/")
                self.assert_in_success_response([user.email, user.full_name], response)

                response = self.client_post("/contact/", {
                    "email": user.email,
                    "full_name": user.full_name,
                    "content": "I love Zulip threading!"
                })
                self.assert_in_success_response(["Thanks for reaching out!"], response)
            self.assertEqual(int(client.get(day1)), 11)
            self.assertEqual(len(mail.outbox), 11)
            self.assertEqual(mail.outbox[10].subject, "Zulip support request from {}".format(user.email))
            self.assertEqual(mail.outbox[10].body, "I love Zulip threading!")

            client.set(day1, 100)

            response = self.client_get("/contact/")
            self.assert_in_success_response(["Please email at zulip-admin@example.com"], response)

            response = self.client_post("/contact/", {
                "email": user.email,
                "full_name": user.full_name,
                "content": "I love Zulip threading!"
            })
            self.assert_in_success_response(["Please email at zulip-admin@example.com"], response)
            client.delete(day1)

        with mock.patch("zerver.lib.feedback.datetime", mock.Mock(today=lambda: date2)):
            response = self.client_post("/contact/", {
                "email": user.email,
                "full_name": user.full_name,
                "content": "I love markdown support!"
            })

            self.assert_in_success_response(["Thanks for reaching out!"], response)
            self.assertEqual(int(client.get(day2)), 1)
            self.assertEqual(len(mail.outbox), 12)
            self.assertEqual(mail.outbox[11].subject, "Zulip support request from {}".format(user.email))
            self.assertEqual(mail.outbox[11].body, "I love markdown support!")
            client.delete(day2)
