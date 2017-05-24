# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from typing import Any, Dict

from django.conf import settings

from zerver.lib.test_helpers import (
    most_recent_message,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    get_system_bot,
    UserProfile
)

import ujson

def fix_params(raw_params):
    # type: (Dict[str, Any]) -> Dict[str, str]
    # A few of our few legacy endpoints need their
    # individual parameters serialized as JSON.
    return {k: ujson.dumps(v) for k, v in raw_params.items()}

class TutorialTests(ZulipTestCase):
    def test_send_message(self):
        # type: () -> None
        user = self.example_user('hamlet')
        email = user.email
        self.login(email)

        welcome_bot = get_system_bot(settings.WELCOME_BOT)

        raw_params = dict(
            type='stream',
            recipient='Denmark',
            topic='welcome',
            content='hello'
        )
        params = fix_params(raw_params)

        result = self.client_post("/json/tutorial_send_message", params)

        self.assert_json_success(result)
        message = most_recent_message(user)
        self.assertEqual(message.content, 'hello')
        self.assertEqual(message.sender, welcome_bot)

        # now test some error cases

        result = self.client_post("/json/tutorial_send_message", {})
        self.assert_json_error(result, "Missing 'type' argument")

        result = self.client_post("/json/tutorial_send_message", raw_params)
        self.assert_json_error(result, 'argument "type" is not valid json.')

        raw_params = dict(
            type='INVALID',
            recipient='Denmark',
            topic='welcome',
            content='hello'
        )
        params = fix_params(raw_params)
        result = self.client_post("/json/tutorial_send_message", params)
        self.assert_json_error(result, 'Bad data passed in to tutorial_send_message')

    def test_tutorial_status(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        cases = [
            ('started', UserProfile.TUTORIAL_STARTED),
            ('finished', UserProfile.TUTORIAL_FINISHED),
        ]
        for incoming_status, expected_db_status in cases:
            raw_params = dict(status=incoming_status)
            params = fix_params(raw_params)
            result = self.client_post('/json/tutorial_status', params)
            self.assert_json_success(result)
            user = self.example_user('hamlet')
            self.assertEqual(user.tutorial_status, expected_db_status)
