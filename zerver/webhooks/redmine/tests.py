import orjson

from zerver.lib.test_classes import WebhookTestCase


class RedmineHookTests(WebhookTestCase):
    CHANNEL_NAME = "redmine"
    URL_TEMPLATE = "/api/v1/external/redmine?&api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "redmine"
    TOPIC_NAME = "Issue #191 Found a bug"

    def test_issue_opened(self) -> None:
        expected_message = """**test user** opened [#191 Found a bug](https://example.com) for **test user**.

~~~ quote
I'm having a problem with this.
~~~"""
        self.check_webhook("issue_opened", self.TOPIC_NAME, expected_message)

    def test_issue_opened_without_assignee(self) -> None:
        expected_message = """**test user** opened [#191 Found a bug](https://example.com).

~~~ quote
I'm having a problem with this.
~~~"""
        self.check_webhook("issue_opened_without_assignee", self.TOPIC_NAME, expected_message)

    def test_issue_updated(self) -> None:
        expected_message = """**test2 user2** updated [#191 Found a bug](https://example.com).

~~~ quote
I've started working on this issue. The problem seems to be in the authentication module.
~~~"""
        self.check_webhook("issue_updated", self.TOPIC_NAME, expected_message)

    def test_issue_opened_with_bracket_in_subject(self) -> None:
        # Brackets in the Redmine subject must not break Markdown link parsing.
        payload = orjson.loads(self.get_body("issue_opened"))
        payload["payload"]["issue"]["subject"] = "Extra ]"
        expected_topic_name = "Issue #191 Extra ]"
        expected_message = """**test user** opened [#191 Extra](https://example.com) for **test user**.

~~~ quote
I'm having a problem with this.
~~~"""
        self.check_webhook(
            "issue_opened",
            expected_topic_name,
            expected_message,
            custom_payload=payload,
        )
