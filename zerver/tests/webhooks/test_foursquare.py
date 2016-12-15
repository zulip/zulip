# -*- coding: utf-8 -*-
from zerver.lib.test_classes import WebhookTestCase

class FourSquareHookTests(WebhookTestCase):
    STREAM_NAME = 'test'
    URL_TEMPLATE = "/api/v1/external/helloworld?&api_key=vPn5BrdFh9Jw0oUPhYvz1lybi8OBM4wr"
    FIXTURE_DIR_NAME = 'foursquare'
    expected_subject = 'FourSquare'

    # Sends briefing on nearby shops
    def test_food_found(self):
        # type: () -> None
        expected_message = u"Food nearby Chicago coming right up:\n Millennium Park"
        self.send_and_test_stream_message('found-food', expected_subject, expected_message)

    def test_food_not_found(self):
        # type: () -> None
        expected_message = u"Food nearby Chicago coming right up: No results"
        self.send_and_test_stream_message('found-food', expected_subject, expected_message)
