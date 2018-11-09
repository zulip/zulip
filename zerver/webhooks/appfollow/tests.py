# -*- coding: utf-8 -*-

from django.test import TestCase

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.appfollow.view import convert_markdown

class AppFollowHookTests(WebhookTestCase):
    STREAM_NAME = 'appfollow'
    URL_TEMPLATE = u"/api/v1/external/appfollow?stream={stream}&api_key={api_key}"

    def test_sample(self) -> None:
        expected_topic = "Webhook integration was successful."
        expected_message = u"""Webhook integration was successful.
Test User / Acme (Google Play)"""
        self.send_and_test_stream_message('sample', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_reviews(self) -> None:
        expected_topic = "Acme - Group chat"
        expected_message = u"""Acme - Group chat
App Store, Acme Technologies, Inc.
★★★★★ United States
**Great for Information Management**
Acme enables me to manage the flow of information quite well. I only wish I could create and edit my Acme Post files in the iOS app.
*by* **Mr RESOLUTIONARY** *for v3.9*
[Permalink](http://appfollow.io/permalink) · [Add tag](http://watch.appfollow.io/add_tag)"""
        self.send_and_test_stream_message('review', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")

    def test_reviews_with_topic(self) -> None:
        # This temporary patch of URL_TEMPLATE is code smell but required due to the way
        # WebhookTestCase is built.
        original_url_template = self.URL_TEMPLATE
        self.URL_TEMPLATE = original_url_template + "&topic=foo"
        self.url = self.build_webhook_url()
        expected_topic = "foo"
        expected_message = u"""Acme - Group chat
App Store, Acme Technologies, Inc.
★★★★★ United States
**Great for Information Management**
Acme enables me to manage the flow of information quite well. I only wish I could create and edit my Acme Post files in the iOS app.
*by* **Mr RESOLUTIONARY** *for v3.9*
[Permalink](http://appfollow.io/permalink) · [Add tag](http://watch.appfollow.io/add_tag)"""
        self.send_and_test_stream_message('review', expected_topic, expected_message,
                                          content_type="application/x-www-form-urlencoded")
        self.URL_TEMPLATE = original_url_template

    def get_body(self, fixture_name: str) -> str:
        return self.webhook_fixture_data("appfollow", fixture_name, file_type="json")

class ConvertMarkdownTest(TestCase):
    def test_convert_bold(self) -> None:
        self.assertEqual(convert_markdown("*test message*"), "**test message**")

    def test_convert_italics(self) -> None:
        self.assertEqual(convert_markdown("_test message_"), "*test message*")
        self.assertEqual(convert_markdown("_  spaced message _"), "  *spaced message* ")

    def test_convert_strikethrough(self) -> None:
        self.assertEqual(convert_markdown("~test message~"), "~~test message~~")
