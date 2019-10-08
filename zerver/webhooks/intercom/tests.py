from zerver.lib.test_classes import WebhookTestCase

class IntercomWebHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/intercom?&api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'intercom'

    def test_user_created_message(self) -> None:
        expected_topic = u"user tag created"
        expected_message = ('*10:43:22 2017-12-17* **user tag created**: \n'
                            ' - User Name: John Doe\n'
                            ' - User Email: john.doe@gmail.com\n'
                            ' - User Phone: 9876543211')

        self.send_and_test_stream_message('user_created', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data('intercom', fixture_name, file_type="json")
