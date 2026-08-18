import orjson

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.fixtureless_integrations import BO_NAME

ARTICLE_TOPIC_NAME = "Article: Getting started with your account"
ARTICLE_MESSAGE_TEMPLATE = (
    "Getting started with your account was {action}.\n"
    "> A short tour of the first things to set up in your account."
)


class IntercomWebHookTests(WebhookTestCase):
    def test_ping(self) -> None:
        expected_topic_name = "Intercom"
        expected_message = "Intercom webhook has been successfully configured."
        self.check_webhook("ping", expected_topic_name, expected_message)

    def test_admin_activity_log_event_created(self) -> None:
        expected_topic_name = "Admin activity log"
        expected_message = f"{BO_NAME} disabled the AI inbox translation settings."
        self.check_webhook(
            "admin_activity_log_event_created", expected_topic_name, expected_message
        )

    def test_admin_added_to_workspace(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} is now an admin."
        self.check_webhook("admin_added_to_workspace", expected_topic_name, expected_message)

    def test_admin_away_mode_enabled(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} is away."
        self.check_webhook("admin_away_mode_updated", expected_topic_name, expected_message)

        payload = orjson.loads(self.webhook_fixture_data("intercom", "admin_away_mode_updated"))
        payload["data"]["item"]["away_status_reason"] = "😜 On a vacation"
        self.subscribe(self.test_user, self.channel_name)
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=expected_topic_name,
            content=f"{BO_NAME} is away (😜 On a vacation).",
        )

    def test_admin_away_mode_disabled(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = self.webhook_fixture_data(self.webhook_dir_name, "admin_away_mode_updated")
        data = orjson.loads(payload)
        data["data"]["item"]["away_mode_enabled"] = False
        msg = self.send_webhook_payload(
            self.test_user, self.url, orjson.dumps(data).decode(), content_type="application/json"
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=f"Admin: {BO_NAME}",
            content=f"{BO_NAME} is now available.",
        )

    def test_admin_logged_in(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} logged in."
        self.check_webhook("admin_logged_in", expected_topic_name, expected_message)

    def test_admin_logged_out(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} logged out."
        self.check_webhook("admin_logged_out", expected_topic_name, expected_message)

    def test_admin_removed_from_workspace(self) -> None:
        expected_topic_name = f"Admin: {BO_NAME}"
        expected_message = f"{BO_NAME} is no longer an admin."
        self.check_webhook("admin_removed_from_workspace", expected_topic_name, expected_message)

    def test_article_created(self) -> None:
        expected_message = ARTICLE_MESSAGE_TEMPLATE.format(action="created")
        self.check_webhook("article_created", ARTICLE_TOPIC_NAME, expected_message)

    def test_article_deleted(self) -> None:
        expected_message = ARTICLE_MESSAGE_TEMPLATE.format(action="deleted")
        self.check_webhook("article_deleted", ARTICLE_TOPIC_NAME, expected_message)

    def test_article_published(self) -> None:
        expected_message = ARTICLE_MESSAGE_TEMPLATE.format(action="published")
        self.check_webhook("article_published", ARTICLE_TOPIC_NAME, expected_message)

    def test_article_unpublished(self) -> None:
        expected_message = ARTICLE_MESSAGE_TEMPLATE.format(action="unpublished")
        self.check_webhook("article_unpublished", ARTICLE_TOPIC_NAME, expected_message)

    def test_article_updated(self) -> None:
        expected_message = ARTICLE_MESSAGE_TEMPLATE.format(action="updated")
        self.check_webhook("article_updated", ARTICLE_TOPIC_NAME, expected_message)

    def test_article_without_description(self) -> None:
        self.subscribe(self.test_user, self.channel_name)
        payload = self.webhook_fixture_data(self.webhook_dir_name, "article_created")
        data = orjson.loads(payload)
        data["data"]["item"]["description"] = None
        msg = self.send_webhook_payload(
            self.test_user, self.url, orjson.dumps(data).decode(), content_type="application/json"
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=ARTICLE_TOPIC_NAME,
            content="Getting started with your account was created.",
        )
