from unittest.mock import patch

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.confluence_cloud.view import IGNORED_EVENTS


class ConfluenceCloudHookTests(WebhookTestCase):
    WEBHOOK_DIR_NAME = "confluence_cloud"

    def test_page_created(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith created page [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_created", expected_topic_name, expected_message)

    def test_page_updated(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith updated page [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_updated", expected_topic_name, expected_message)

    def test_page_trashed(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith trashed page [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_trashed", expected_topic_name, expected_message)

    def test_page_restored(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith restored page [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_restored", expected_topic_name, expected_message)

    def test_page_removed(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = (
            "John Smith removed page **Architecture Overview** from space **Engineering**."
        )
        self.check_webhook("page_removed", expected_topic_name, expected_message)

    def test_page_moved(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith moved page [Architecture Overview](https://example.atlassian.net/wiki/spaces/ARCH/pages/123456/Architecture+Overview) to space **Architecture**."
        self.check_webhook("page_moved", expected_topic_name, expected_message)

    def test_blog_created(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "Alice Jones created blog post [Q3 Engineering Update](https://example.atlassian.net/wiki/spaces/ENG/pages/234567) in space **Engineering**."
        self.check_webhook("blog_created", expected_topic_name, expected_message)

    def test_blog_updated(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "Alice Jones updated blog post [Q3 Engineering Update](https://example.atlassian.net/wiki/spaces/ENG/pages/234567) in space **Engineering**."
        self.check_webhook("blog_updated", expected_topic_name, expected_message)

    def test_blog_removed(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = (
            "Alice Jones removed blog post **Q3 Engineering Update** from space **Engineering**."
        )
        self.check_webhook("blog_removed", expected_topic_name, expected_message)

    def test_blog_trashed(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "Alice Jones trashed blog post [Q3 Engineering Update](https://example.atlassian.net/wiki/spaces/ENG/pages/234567) in space **Engineering**."
        self.check_webhook("blog_trashed", expected_topic_name, expected_message)

    def test_blog_restored(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "Alice Jones restored blog post [Q3 Engineering Update](https://example.atlassian.net/wiki/spaces/ENG/pages/234567) in space **Engineering**."
        self.check_webhook("blog_restored", expected_topic_name, expected_message)

    def test_comment_page_created(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith commented on [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview)."
        self.check_webhook("comment_page_created", expected_topic_name, expected_message)

    def test_comment_page_updated(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith updated a comment on [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview)."
        self.check_webhook("comment_page_updated", expected_topic_name, expected_message)

    def test_comment_page_removed(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith removed a comment from [Architecture Overview](https://example.atlassian.net/wiki/spaces/ENG/pages/123456/Architecture+Overview)."
        self.check_webhook("comment_page_removed", expected_topic_name, expected_message)

    def test_comment_blog_created(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "Alice Jones commented on [Q3 Engineering Update](https://example.atlassian.net/wiki/spaces/ENG/blog/234567)."
        self.check_webhook("comment_blog_created", expected_topic_name, expected_message)

    def test_ignored_events(self) -> None:
        for action in IGNORED_EVENTS:
            with self.subTest(action=action):
                url = self.build_webhook_url()
                payload = {"webhookEvent": action}
                with patch("zerver.webhooks.confluence_cloud.view.check_send_webhook_message") as m:
                    result = self.client_post(url, payload, content_type="application/json")
                self.assertFalse(m.called)
                self.assert_json_success(result)

    def test_anomalous_webhook_payload_error(self) -> None:
        with self.assertRaises(AssertionError) as e:
            self.check_webhook(
                fixture_name="example_anomalous_payload",
                expected_topic="",
                expected_message="",
                expect_noop=True,
            )

        self.assertIn(
            "Unable to parse request: Did ConfluenceCloud generate this event?",
            e.exception.args[0],
        )
