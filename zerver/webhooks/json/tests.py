import json

from zerver.lib.test_classes import WebhookTestCase


class JsonHookTests(WebhookTestCase):
    CHANNEL_NAME = "json"
    URL_TEMPLATE = "/api/v1/external/json?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "json"

    def test_json_github_push__1_commit_message(self) -> None:
        """
        Tests if json github push 1 commit is handled correctly
        """
        with open("zerver/webhooks/json/fixtures/json_github_push__1_commit.json") as f:
            original_fixture = json.load(f)

        expected_topic_name = "JSON"
        expected_message = f"""```json
{json.dumps(original_fixture, indent=2)}
```"""
        self.check_webhook("json_github_push__1_commit", expected_topic_name, expected_message)

    def test_json_pingdom_http_up_to_down_message(self) -> None:
        """
        Tests if json pingdom http up to down is handled correctly
        """
        with open("zerver/webhooks/json/fixtures/json_pingdom_http_up_to_down.json") as f:
            original_fixture = json.load(f)

        expected_topic_name = "JSON"
        expected_message = f"""```json
{json.dumps(original_fixture, indent=2)}
```"""
        self.check_webhook("json_pingdom_http_up_to_down", expected_topic_name, expected_message)

    def test_json_sentry_event_for_exception_js_message(self) -> None:
        """
        Tests if json sentry event for exception js is handled correctly
        """
        with open("zerver/webhooks/json/fixtures/json_sentry_event_for_exception_js.json") as f:
            original_fixture = json.load(f)

        expected_topic_name = "JSON"
        expected_message = f"""```json
{json.dumps(original_fixture, indent=2)}
```"""
        self.check_webhook(
            "json_sentry_event_for_exception_js", expected_topic_name, expected_message
        )
