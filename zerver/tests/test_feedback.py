from unittest.mock import patch, MagicMock
from django.conf import settings
from zerver.lib.test_classes import ZulipTestCase

class TestFeedbackBot(ZulipTestCase):
    @patch('logging.info')
    def test_pm_to_feedback_bot(self, logging_info_mock: MagicMock) -> None:
        with self.settings(ENABLE_FEEDBACK=True):
            user_email = self.example_email("othello")
            self.send_personal_message(user_email, settings.FEEDBACK_BOT,
                                       content="I am a feedback message.")
            logging_info_mock.assert_called_once_with("Received feedback from {}".format(user_email))
