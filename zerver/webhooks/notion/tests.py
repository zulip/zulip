from zerver.lib.test_classes import WebhookTestCase

class NotionHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/notion?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "notion"

    def test_page_created(self) -> None:
        expected_topic = "Page Created"
        expected_message = "**[Project Alpha](https://notion.so/project-alpha)**"
        self.check_webhook("page_created", expected_topic, expected_message)

    def test_page_updated_no_url(self) -> None:
        expected_topic = "Page Updated"
        expected_message = "**Project Beta**"
        self.check_webhook("page_updated_no_url", expected_topic, expected_message)

    def test_default_event_type(self) -> None:
        # Test implicit event type when "event" is missing from payload
        # Minimal payload: {"title": "Note"}
        expected_topic = "Update"
        expected_message = "**Note**"
        self.check_webhook(
            "minimal_update", 
            expected_topic, 
            expected_message, 
            expect_noop=False
        )
