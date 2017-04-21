# -*- coding: utf-8 -*-
from typing import Text
from zerver.lib.test_classes import WebhookTestCase

class FourSquareHookTests(WebhookTestCase):
    STREAM_NAME = 'foursquare'
    URL_TEMPLATE = u"/api/v1/external/foursquare?stream={stream}&api_key={api_key}"
    FIXTURE_DIR_NAME = 'foursquare'

    def test_food_found(self):
        # type: () -> None
        expected_subject = 'FourSquare - Chicago, IL, United States'
        expected_message = '''
Food nearby Chicago, IL, United States coming right up:
Millennium Park
201 E Randolph St (btwn Columbus Dr & Michigan Ave), Chicago, IL 60601, United States
This 24.5-acre park features the work of world-renowned architects, planners, artists and designers.

Chicago Riverwalk
Chicago River, Chicago, IL 60601, United States
Urban Kayaks are open for the season! Located at 270 E. Riverwalk South. Mon - Fri 10 a.m. - 6 p.m. and Sat - Sun 9 a.m. - 5 p.m. (312) 965-0035 http://urbankayaks.com/

Chicago Lakefront Trail
Lake Michigan Lakefront (at N Lakeshore Dr), Chicago, IL 60611, United States
Water clears your mind, body and soul'''
        self.send_and_test_stream_message('food_found', expected_subject, expected_message)

    def get_body(self, fixture_name):
        # type: (Text) -> Text
        return self.fixture_data("foursquare", fixture_name, file_type="json")
