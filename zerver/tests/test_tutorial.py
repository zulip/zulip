# -*- coding: utf-8 -*-

from typing import Any, Dict
import ujson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile

class TutorialTests(ZulipTestCase):
    def test_tutorial_status(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        cases = [
            ('started', UserProfile.TUTORIAL_STARTED),
            ('finished', UserProfile.TUTORIAL_FINISHED),
        ]
        for incoming_status, expected_db_status in cases:
            params = dict(status=ujson.dumps(incoming_status))
            result = self.client_post('/json/users/me/tutorial_status', params)
            self.assert_json_success(result)
            user = self.example_user('hamlet')
            self.assertEqual(user.tutorial_status, expected_db_status)
