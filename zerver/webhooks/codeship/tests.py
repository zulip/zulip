# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class CodeshipHookTests(WebhookTestCase):
    STREAM_NAME = 'codeship'
    URL_TEMPLATE = u"/api/v1/external/codeship?stream={stream}&api_key={api_key}"
    SUBJECT = u"codeship/docs"
    FIXTURE_DIR_NAME = 'codeship'

    def test_codeship_build_in_testing_status_message(self) -> None:
        """
        Tests if codeship testing status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch started."
        self.send_and_test_stream_message('testing_build', self.SUBJECT, expected_message)

    def test_codeship_build_in_error_status_message(self) -> None:
        """
        Tests if codeship error status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch failed."
        self.send_and_test_stream_message('error_build', self.SUBJECT, expected_message)

    def test_codeship_build_in_success_status_message(self) -> None:
        """
        Tests if codeship success status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch succeeded."
        self.send_and_test_stream_message('success_build', self.SUBJECT, expected_message)

    def test_codeship_build_in_other_status_status_message(self) -> None:
        """
        Tests if codeship other status is mapped correctly
        """
        expected_message = u"[Build](https://www.codeship.com/projects/10213/builds/973711) triggered by beanieboi on master branch has some_other_status status."
        self.send_and_test_stream_message('other_status_build', self.SUBJECT, expected_message)
