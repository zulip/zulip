# -*- coding: utf-8 -*-

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.opbeat.view import get_value


class OpbeatHookTests(WebhookTestCase):
    STREAM_NAME = 'opbeat'
    URL_TEMPLATE = u"/api/v1/external/opbeat?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = 'opbeat'

    def test_comment(self) -> None:
        expected_topic = "foo commented on E#2"
        expected_message = '''
**[foo commented on E#2](https://opbeat.com/foo/test-flask-app/errors/2/#activity-5df00003ea4e42458db48446692f6d37)**
test comment


**[E#2](https://opbeat.com/foo/test-flask-app/errors/2/)**

>**Most recent Occurrence**
>in app.py
>A warning occurred (42 apples)'''
        self.send_and_test_stream_message('new_comment', expected_topic, expected_message,
                                          content_type="application/json")

    def test_new_app(self) -> None:
        expected_topic = "foo"
        expected_message = '''
**foo**
App foo created

**[foo](https://opbeat.com/bar/foo/)**
>language: nodejs
>framework: custom'''
        self.send_and_test_stream_message('new_app', expected_topic, expected_message,
                                          content_type="application/json")

    def test_get_empty_value(self) -> None:
        self.assertEqual(get_value({'key': 'value'}, 'foo'), '')

    def test_no_subject_type(self) -> None:
        expected_topic = "test title"
        expected_message = '''
**test title**
test summary'''
        self.send_and_test_stream_message(
            'unsupported_object',
            expected_topic,
            expected_message,
            content_type='application/json'
        )

    def test_error_fixed(self) -> None:
        expected_topic = 'foo marked E#2 as fixed'
        expected_message = '''
**[foo marked E#2 as fixed](https://opbeat.com/test_org/test-flask-app/errors/2/#activity-bf991a45d9184b0ca6fb3d48d3db4c38)**
foo marked the error group as fixed

**[E#2](https://opbeat.com/test_org/test-flask-app/errors/2/)**

>**Most recent Occurrence**
>in app.py
>A warning occurred (42 apples)'''
        self.send_and_test_stream_message(
            'error_fixed', expected_topic, expected_message, content_type='application/json')

    def test_error_reopened(self) -> None:
        expected_topic = 'foo reopened E#2'
        expected_message = '''
**[foo reopened E#2](https://opbeat.com/test_org/test-flask-app/errors/2/#activity-38a556dfc0b04a59a586359bbce1463d)**
foo reopened the error group

**[E#2](https://opbeat.com/test_org/test-flask-app/errors/2/)**

>**Most recent Occurrence**
>in app.py
>A warning occurred (42 apples)'''
        self.send_and_test_stream_message(
            'error_reopen', expected_topic, expected_message, content_type='application/json')

    def test_error_regressed(self) -> None:
        expected_topic = 'E#2 regressed'
        expected_message = '''
**[E#2 regressed](https://opbeat.com/test_org/test-flask-app/errors/2/#activity-c0396f38323a4fa7b314f87d5ed9cdd2)**
The error group regressed

**[E#2](https://opbeat.com/test_org/test-flask-app/errors/2/)**

>**Most recent Occurrence**
>in app.py
>A warning occurred (42 apples)'''
        self.send_and_test_stream_message(
            'new_error', expected_topic, expected_message, content_type='application/json')
