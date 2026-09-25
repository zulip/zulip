import json
from collections.abc import Callable
from functools import wraps
from typing import Concatenate
from unittest.mock import patch

import requests
import responses
from typing_extensions import ParamSpec, override

from zerver.lib.bot_config import set_bot_config
from zerver.lib.test_classes import WebhookTestCase
from zerver.models import BotConfigData
from zerver.webhooks.confluence.view import IGNORED_EVENTS

BASE_URL = "https://wiki.example.com"
TOKEN = "test_token"

ParamT = ParamSpec("ParamT")


def mock_confluence_api(
    content_fixture: str | None = None,
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
            responses.add(
                responses.GET,
                f"{BASE_URL}/rest/api/user",
                body=self.webhook_fixture_data("confluence", "user_api_response"),
            )
            if content_status >= 400:
                with self.assertLogs("zerver.lib.webhooks.common", level="WARNING"):
                    test_func(self, *args, **kwargs)
            else:
                test_func(self, *args, **kwargs)

        return _wrapped

    return decorator


class ConfluenceHookTests(WebhookTestCase):
    URL_TEMPLATE = (
        f"/api/v1/external/confluence?stream={{stream}}&api_key={{api_key}}&base_url={BASE_URL}"
    )

    @override
    def setUp(self) -> None:
        super().setUp()
        set_bot_config(self.test_user, "confluence_token", TOKEN)
        self.url = self.build_webhook_url(base_url=BASE_URL)

    @mock_confluence_api(content_fixture="page_api_response")
    def test_page_created(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith created page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_created", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="page_api_response")
    def test_page_updated(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith updated page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_updated", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="page_api_response",
        content_status=404,
    )
    def test_page_updated_api_error(self) -> None:
        expected_topic_name = "Page unknown"
        expected_message = "John Smith updated a page. Unable to fetch the specific content."
        self.check_webhook("page_updated", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="page_api_response")
    def test_page_restored(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith restored page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_restored", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="page_api_response",
        content_status=404,
    )
    def test_page_restored_api_error(self) -> None:
        expected_topic_name = "Page unknown"
        expected_message = "John Smith restored a page. Unable to fetch the specific content."
        self.check_webhook("page_restored", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="page_api_response")
    def test_page_trashed(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith trashed page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        self.check_webhook("page_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="page_api_response",
        content_status=404,
    )
    def test_page_trashed_api_error(self) -> None:
        expected_topic_name = "Page unknown"
        expected_message = "John Smith trashed a page. Unable to fetch the specific content."
        self.check_webhook("page_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="moved_page_api_response")
    def test_page_moved(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith moved page [Architecture Overview](https://wiki.example.com/spaces/ARCH/pages/123456/Architecture+Overview) to space **Architecture**."
        self.check_webhook("page_moved", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="moved_page_api_response",
        content_status=404,
    )
    def test_page_moved_api_error(self) -> None:
        expected_topic_name = "Page unknown"
        expected_message = "John Smith moved a page. Unable to fetch the specific content."
        self.check_webhook("page_moved", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response")
    def test_blog_created(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "John Smith created blog [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_created", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        content_status=404,
    )
    def test_blog_created_api_error(self) -> None:
        expected_topic_name = "Blog unknown"
        expected_message = "John Smith created a blog. Unable to fetch the specific content."
        self.check_webhook("blog_created", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response")
    def test_blog_updated(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "John Smith updated blog [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_updated", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        content_status=404,
    )
    def test_blog_updated_api_error(self) -> None:
        expected_topic_name = "Blog unknown"
        expected_message = "John Smith updated a blog. Unable to fetch the specific content."
        self.check_webhook("blog_updated", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response")
    def test_blog_restored(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "John Smith restored blog [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_restored", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        content_status=404,
    )
    def test_blog_restored_api_error(self) -> None:
        expected_topic_name = "Blog unknown"
        expected_message = "John Smith restored a blog. Unable to fetch the specific content."
        self.check_webhook("blog_restored", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="blog_api_response")
    def test_blog_trashed(self) -> None:
        expected_topic_name = "Blog: Q3 Engineering Update"
        expected_message = "John Smith trashed blog [Q3 Engineering Update](https://wiki.example.com/spaces/ENG/blog/2019/08/16/234567/Q3+Engineering+Update) in space **Engineering**."
        self.check_webhook("blog_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="blog_api_response",
        content_status=404,
    )
    def test_blog_trashed_api_error(self) -> None:
        expected_topic_name = "Blog unknown"
        expected_message = "John Smith trashed a blog. Unable to fetch the specific content."
        self.check_webhook("blog_trashed", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="comment_api_response")
    def test_comment_created(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith commented on [Page: Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview?focusedCommentId=789012#comment-789012)."
        self.check_webhook("comment_created", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="comment_api_response",
        content_status=404,
    )
    def test_comment_created_api_error(self) -> None:
        expected_topic_name = "Comment unknown"
        expected_message = "John Smith created a comment. Unable to fetch the specific content."
        self.check_webhook("comment_created", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="comment_api_response")
    def test_comment_updated(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith updated a comment on [Page: Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview?focusedCommentId=789012#comment-789012)."
        self.check_webhook("comment_updated", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="comment_api_response",
        content_status=404,
    )
    def test_comment_updated_api_error(self) -> None:
        expected_topic_name = "Comment unknown"
        expected_message = "John Smith updated a comment. Unable to fetch the specific content."
        self.check_webhook("comment_updated", expected_topic_name, expected_message)

    @mock_confluence_api(content_fixture="comment_api_response")
    def test_comment_removed(self) -> None:
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "John Smith removed a comment from [Page: Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview?focusedCommentId=789012#comment-789012)."
        self.check_webhook("comment_removed", expected_topic_name, expected_message)

    @mock_confluence_api(
        content_fixture="comment_api_response",
        content_status=404,
    )
    def test_comment_removed_api_error(self) -> None:
        expected_topic_name = "Comment unknown"
        expected_message = "John Smith removed a comment. Unable to fetch the specific content."
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
        expected_topic_name = "Page unknown"
        expected_message = "John Smith created a page. Unable to fetch the specific content."
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
        expected_topic_name = "Page: Architecture Overview"
        expected_message = "Unknown user created page [Architecture Overview](https://wiki.example.com/spaces/ENG/pages/123456/Architecture+Overview) in space **Engineering**."
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING"):
            self.check_webhook("page_created", expected_topic_name, expected_message)

    @responses.activate
    def test_webhook_without_bot_config(self) -> None:
        BotConfigData.objects.filter(bot_profile=self.test_user).delete()
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/content/123456",
            status=401,
        )
        responses.add(
            responses.GET,
            f"{BASE_URL}/rest/api/user",
            status=401,
        )
        expected_topic_name = "Page unknown"
        expected_message = "Unknown user created a page. Unable to fetch the specific content."
        with (
            self.assertLogs("root", level="WARNING") as config_logs,
            self.assertLogs("zerver.lib.webhooks.common", level="WARNING"),
        ):
            self.check_webhook("page_created", expected_topic_name, expected_message)

        self.assertEqual(
            config_logs.output,
            [
                f"WARNING:root:Confluence webhook for bot {self.test_user.id} has no "
                "confluence_token configured; unable to fetch the specific content for the events."
            ],
        )
        # The API calls should have been made with an empty bearer token.
        for call in responses.calls:
            self.assertEqual(call.request.headers.get("Authorization"), "Bearer ")

    def test_ignored_events(self) -> None:
        url = self.build_webhook_url(base_url=BASE_URL)
        for action in IGNORED_EVENTS:
            with self.subTest(action=action):
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
