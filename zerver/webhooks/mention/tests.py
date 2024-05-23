from zerver.lib.test_classes import WebhookTestCase


class MentionHookTests(WebhookTestCase):
    CHANNEL_NAME = "test"
    URL_TEMPLATE = "/api/v1/external/mention?api_key={api_key}&stream={stream}"
    WEBHOOK_DIR_NAME = "mention"

    def test_mention_webfeed(self) -> None:
        expected_topic_name = "news"
        expected_message = """
**[Historical Sexual Abuse (Football): 29 Nov 2016: House of Commons debates - TheyWorkForYou](https://www.theyworkforyou.com/debates/?id=2016-11-29b.1398.7&p=24887)**:

``` quote
\u2026 Culture, Media and Sport\nNothing is more important than keeping children safe. Child sex abuse is an exceptionally vile crime, and all of Government take it very seriously indeed, as I know this House does.
Children up and down the country are \u2026
```
""".strip()

        # use fixture named mention_webfeeds
        self.check_webhook(
            "webfeeds",
            expected_topic_name,
            expected_message,
            content_type="application/x-www-form-urlencoded",
        )
