# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

class HelloSignHookTests(WebhookTestCase):
    STREAM_NAME = 'hellosign'
    URL_TEMPLATE = "/api/v1/external/hellosign?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'hellosign'

    def test_signatures_message(self) -> None:
        expected_topic = "NDA with Acme Co."
        expected_message = ("The `NDA with Acme Co.` document is awaiting the signature of "
                            "Jack, and was just signed by Jill.")
        self.send_and_test_stream_message('signatures', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_signatures_message_signed_by_one(self) -> None:
        expected_topic = "NDA with Acme Co."
        expected_message = ("The `NDA with Acme Co.` document was just signed by Jill.")
        self.send_and_test_stream_message('signatures_signed_by_one_signatory',
                                          expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_signatures_message_with_four_signatories(self) -> None:
        expected_topic = "Signature doc"
        expected_message = ("The `Signature doc` document is awaiting the signature of "
                            "Eeshan Garg, John Smith, Jane Doe, and Stephen Strange.")
        self.send_and_test_stream_message('signatures_with_four_signatories', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_signatures_message_with_own_subject(self) -> None:
        expected_topic = "Our own subject."
        self.url = self.build_webhook_url(topic=expected_topic)
        expected_message = ("The `NDA with Acme Co.` document is awaiting the signature of "
                            "Jack, and was just signed by Jill.")
        self.send_and_test_stream_message('signatures_with_own_subject', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded", topic=expected_topic)

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("hellosign", fixture_name, file_type="json")
