from zerver.lib.test_classes import WebhookTestCase, ZulipTestCase
from zerver.webhooks.appfollow.view import convert_markdown


class AppFollowHookTests(WebhookTestCase):
    CHANNEL_NAME = "appfollow"
    URL_TEMPLATE = "/api/v1/external/appfollow?stream={stream}&api_key={api_key}"
    WEBHOOK_DIR_NAME = "appfollow"

    def test_sample(self) -> None:
        expected_topic_name = "Webhook integration was successful."
        expected_message = """Webhook integration was successful.
Test User / Acme (Google Play)"""
        self.check_webhook(
            "sample",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_reviews(self) -> None:
        expected_topic_name = "Acme - Group chat"
        expected_message = """Acme - Group chat
App Store, Acme Technologies, Inc.
★★★★★ United States
**Great for Information Management**
Acme enables me to manage the flow of information quite well. I only wish I could create and edit my Acme Post files in the iOS app.
*by* **Mr RESOLUTIONARY** *for v3.9*
[Permalink](http://appfollow.io/permalink) · [Add tag](http://watch.appfollow.io/add_tag)"""
        self.check_webhook(
            "review",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )

    def test_reviews_with_topic(self) -> None:
        # This temporary patch of URL_TEMPLATE is code smell but required due to the way
        # WebhookTestCase is built.
        original_url_template = self.URL_TEMPLATE
        self.URL_TEMPLATE = original_url_template + "&topic=foo"
        self.url = self.build_webhook_url()
        expected_topic_name = "foo"
        expected_message = """Acme - Group chat
App Store, Acme Technologies, Inc.
★★★★★ United States
**Great for Information Management**
Acme enables me to manage the flow of information quite well. I only wish I could create and edit my Acme Post files in the iOS app.
*by* **Mr RESOLUTIONARY** *for v3.9*
[Permalink](http://appfollow.io/permalink) · [Add tag](http://watch.appfollow.io/add_tag)"""
        self.check_webhook(
            "review",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
        self.URL_TEMPLATE = original_url_template


class ConvertMarkdownTest(ZulipTestCase):
    def test_convert_bold(self) -> None:
        self.assertEqual(convert_markdown("*test message*"), "**test message**")

    def test_convert_italics(self) -> None:
        self.assertEqual(convert_markdown("_test message_"), "*test message*")
        self.assertEqual(convert_markdown("_  spaced message _"), "  *spaced message* ")

    def test_convert_strikethrough(self) -> None:
        self.assertEqual(convert_markdown("~test message~"), "~~test message~~")
