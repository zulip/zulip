import json
from collections.abc import Callable
from functools import wraps
from typing import Concatenate
from unittest.mock import patch

import requests
import responses
from typing_extensions import ParamSpec, override

from zerver.lib.test_classes import WebhookTestCase

BASE_URL = "https://wiki.example.com"
TOKEN = "test_token"

ParamT = ParamSpec("ParamT")


def mock_confluence_api(
    content_fixture: str | None = None,
    user_fixture: str | None = None,
    content_status: int = 200,
) -> Callable[
    [Callable[Concatenate["ConfluenceHookTests", ParamT], None]],
    Callable[Concatenate["ConfluenceHookTests", ParamT], None],
]:
    def decorator(
        test_func: Callable[Concatenate["ConfluenceHookTests", ParamT], None],
    ) -> Callable[Concatenate["ConfluenceHookTests", ParamT], None]:
        @wraps(test_func)
        @responses.activate
        def _wrapped(
            self: "ConfluenceHookTests", /, *args: ParamT.args, **kwargs: ParamT.kwargs
        ) -> None:
            if content_fixture is not None:
                body = self.webhook_fixture_data("confluence", content_fixture)
                content_id = json.loads(body)["id"]
                responses.add(
                    responses.GET,
                    f"{BASE_URL}/rest/api/content/{content_id}",
                    body=body,
                    status=content_status,
                )
            if user_fixture is not None:
                responses.add(
                    responses.GET,
                    f"{BASE_URL}/rest/api/user",
                    body=self.webhook_fixture_data("confluence", user_fixture),
                )
            if content_status >= 400:
                with self.assertLogs("zerver.lib.webhooks.common", level="WARNING"):
                    test_func(self, *args, **kwargs)
            else:
                test_func(self, *args, **kwargs)

        return _wrapped

    return decorator


class ConfluenceHookTests(WebhookTestCase):
    URL_TEMPLATE = f"/api/v1/external/confluence?stream={{stream}}&api_key={{api_key}}&base_url={BASE_URL}&token={TOKEN}"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.url = self.build_webhook_url(base_url=BASE_URL, token=TOKEN)

    @mock_confluence_api(content_fixture="page_api_response", user_fixture="user_api_response")
    def test_page_created(self) -> None:
        expected_topic_name = "Architecture Overview"
        expected_message = "John Smith created page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_created", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="page_api_response", user_fixture="user_api_response")
    def test_page_updated(self) -> None:
        expected_topic_name = "Architecture Overview"
        expected_message = "John Smith updated page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_updated", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="page_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_page_updated_api_error(self) -> None:
        expected_topic_name = "Page 123456"
        expected_message = "John Smith permanently removed a page."
        self.check_webhook("page_updated", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="page_api_response", user_fixture="user_api_response")
    def test_page_restored(self) -> None:
        expected_topic_name = "Architecture Overview"
        expected_message = "John Smith restored page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_restored", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="page_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_page_restored_api_error(self) -> None:
        expected_topic_name = "Page 123456"
        expected_message = "John Smith permanently removed a page."
        self.check_webhook("page_restored", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="page_api_response", user_fixture="user_api_response")
    def test_page_trashed(self) -> None:
        expected_topic_name = "Architecture Overview"
        expected_message = (
            "John Smith removed page **Architecture Overview** from space **Engineering**."
        )
        self.check_webhook("page_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="page_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_page_trashed_api_error(self) -> None:
        expected_topic_name = "Page 123456"
        expected_message = "John Smith permanently removed a page."
        self.check_webhook("page_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="moved_page_api_response", user_fixture="user_api_response"
    )
    def test_page_moved(self) -> None:
        expected_topic_name = "Architecture Overview"
        expected_message = "John Smith moved page [Architecture Overview](https://wiki.example.com/spaces/ARCH/pages/123456/Architecture+Overview) to space **Architecture**."
        self.check_webhook("page_moved", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="moved_page_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_page_moved_api_error(self) -> None:
        expected_topic_name = "Page 123456"
        expected_message = "John Smith permanently removed a page."
        self.check_webhook("page_moved", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response", user_fixture="blog_user_api_response")
    def test_blog_created(self) -> None:
        expected_topic_name = "Q3 Engineering Update"
        expected_message = "Alice Jones created blog post [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_created", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        user_fixture="blog_user_api_response",
        content_status=404,
    )
    def test_blog_created_api_error(self) -> None:
        expected_topic_name = "Page 234567"
        expected_message = "Alice Jones permanently removed a page."
        self.check_webhook("blog_created", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response", user_fixture="blog_user_api_response")
    def test_blog_updated(self) -> None:
        expected_topic_name = "Q3 Engineering Update"
        expected_message = "Alice Jones updated blog post [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_updated", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        user_fixture="blog_user_api_response",
        content_status=404,
    )
    def test_blog_updated_api_error(self) -> None:
        expected_topic_name = "Page 234567"
        expected_message = "Alice Jones permanently removed a page."
        self.check_webhook("blog_updated", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response", user_fixture="blog_user_api_response")
    def test_blog_restored(self) -> None:
        expected_topic_name = "Q3 Engineering Update"
        expected_message = "Alice Jones restored blog post [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_restored", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        user_fixture="blog_user_api_response",
        content_status=404,
    )
    def test_blog_restored_api_error(self) -> None:
        expected_topic_name = "Page 234567"
        expected_message = "Alice Jones permanently removed a page."
        self.check_webhook("blog_restored", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response", user_fixture="blog_user_api_response")
    def test_blog_trashed(self) -> None:
        expected_topic_name = "Q3 Engineering Update"
        expected_message = (
            "Alice Jones removed blog post **Q3 Engineering Update** from space **Engineering**."
        )
        self.check_webhook("blog_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        user_fixture="blog_user_api_response",
        content_status=404,
    )
    def test_blog_trashed_api_error(self) -> None:
        expected_topic_name = "Page 234567"
        expected_message = "Alice Jones permanently removed a page."
        self.check_webhook("blog_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="comment_api_response", user_fixture="user_api_response")
    def test_comment_created(self) -> None:
        expected_topic_name = "Architecture Overview (comments)"
        expected_message = "John Smith commented on [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview)."
        self.check_webhook("comment_created", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="comment_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_comment_created_api_error(self) -> None:
        expected_topic_name = "Comment 789012"
        expected_message = "John Smith removed a comment."
        self.check_webhook("comment_created", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="comment_api_response", user_fixture="user_api_response")
    def test_comment_updated(self) -> None:
        expected_topic_name = "Architecture Overview (comments)"
        expected_message = "John Smith updated a comment on [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview)."
        self.check_webhook("comment_updated", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="comment_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_comment_updated_api_error(self) -> None:
        expected_topic_name = "Comment 789012"
        expected_message = "John Smith removed a comment."
        self.check_webhook("comment_updated", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="comment_api_response", user_fixture="user_api_response")
    def test_comment_removed(self) -> None:
        expected_topic_name = "Architecture Overview (comments)"
        expected_message = "John Smith removed a comment on [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview)."
        self.check_webhook("comment_removed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="comment_api_response",
        user_fixture="user_api_response",
        content_status=404,
    )
    def test_comment_removed_api_error(self) -> None:
        expected_topic_name = "Comment 789012"
        expected_message = "John Smith removed a comment."
        self.check_webhook("comment_removed", expected_topic_name, expected_message)

    @responses.activate
    def test_fetch_content_network_error(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/123456",
            body=requests.ConnectionError(),
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/user",
            body=self.webhook_fixture_data("confluence", "user_api_response"),
        )
        expected_topic_name = "Page 123456"
        expected_message = "John Smith permanently removed a page."
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING"):
            self.check_webhook("page_created", expected_topic_name, expected_message)

    @responses.activate
    def test_fetch_user_network_error(self) -> None:
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/123456",
            body=self.webhook_fixture_data("confluence", "page_api_response"),
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/user",
            body=requests.ConnectionError(),
        )
        expected_topic_name = "Architecture Overview"
        expected_message = "abc123 created page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING"):
            self.check_webhook("page_created", expected_topic_name, expected_message)

    def test_ignored_events(self) -> None:
        ignored_actions = [
            "attachment_created",
            "attachment_removed",
            "attachment_restored",
            "attachment_trashed",
            "attachment_updated",
            "blueprint_page_created",
            "content_created",
            "content_permissions_updated",
            "content_restored",
            "content_trashed",
            "content_updated",
            "group_created",
            "group_removed",
            "label_added",
            "label_created",
            "label_deleted",
            "label_removed",
            "page_children_reordered",
            "relation_created",
            "relation_deleted",
            "space_created",
            "space_logo_updated",
            "space_permissions_updated",
            "space_removed",
            "space_updated",
            "theme_enabled",
            "user_created",
            "user_deactivated",
            "user_followed",
            "user_reactivated",
            "user_removed",
            "page_removed",
            "blog_removed",
        ]
        for action in ignored_actions:
            url = self.build_webhook_url(base_url=BASE_URL, token=TOKEN)
            payload = {"event": action}
            with patch("zerver.webhooks.confluence.view.check_send_webhook_message") as m:
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
            "Unable to parse request: Did Confluence generate this event?",
            e.exception.args[0],
        )
