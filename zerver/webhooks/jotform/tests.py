from zerver.lib.test_classes import WebhookTestCase


class JotformHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/jotform?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "jotform"

    def test_response(self) -> None:
        expected_title = "Form"
        expected_message = """
A new submission (ID 4791133489169827307) was received:
* Name:Gaurav Pandey
* Address:Lampgarden-street wolfsquare Bengaluru Karnataka 165578
* Signature:uploads/gauravguitarrocks/202944822449057/4791133489169827307/4791133489169827307_signature_4.png
""".strip()

        self.check_webhook(
            "response",
            expected_title,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
