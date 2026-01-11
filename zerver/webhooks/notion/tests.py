from zerver.lib.test_classes import WebhookTestCase

class NotionHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/notion?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "notion"

    def test_page_created(self) -> None:
        expected_topic = "Page Created"
        expected_message = "**[Project Alpha](https://notion.so/project-alpha)**"
        self.check_webhook("page_created", expected_topic, expected_message)
