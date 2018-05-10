# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase

class MentionHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/mention?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'mention'

    def test_mention_webfeed(self) -> None:
        expected_topic = u"news"
        expected_message = (u"**[Historical Sexual Abuse (Football): 29 Nov 2016: House of Commons debates - TheyWorkForYou]"
                            u"(https://www.theyworkforyou.com/debates/?id=2016-11-29b.1398.7&p=24887)**:\n"
                            u"\u2026 Culture, Media and Sport\nNothing is more important than keeping children safe."
                            u" Child sex abuse is an exceptionally vile crime, and all of Government take it very seriously indeed,"
                            u" as I know this House does.\nChildren up and down the country are \u2026"
                            )

        # use fixture named mention_webfeeds
        self.send_and_test_stream_message('webfeeds', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("mention", fixture_name, file_type="json")
