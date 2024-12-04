from zerver.lib.test_classes import WebhookTestCase


class MentionHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/mention?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "mention"

    def test_mention_webfeed(self) -> None:
        expected_topic_name = "news"
        expected_message = """
**[Travel Industry Sees Surge in Eco-Tourism (Travel): 29 Nov 2024: Global Tourism - TheyWorkForYou](https://www.theyworkforyou.com/debates/?id=2016-11-29b.1398.7&p=24887)**:

``` quote
\u2026 Tourism, Culture and Heritage\nMore travelers prioritize environmental sustainability, driving growth in eco-friendly accommodations and activities. Popular destinations include Costa Rica and \u2026
```
""".strip()

        # use fixture named mention_webfeeds
        self.check_webhook(
            "webfeeds",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
