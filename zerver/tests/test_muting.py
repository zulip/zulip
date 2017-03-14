from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user_profile_by_email

class MutedTopicsTests(ZulipTestCase):
    def test_json_set(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        url = '/json/users/me/subscriptions/muted_topics'
        data = {'muted_topics': '[["stream", "topic"]]'}
        result = self.client_post(url, data)
        self.assert_json_success(result)

        user = get_user_profile_by_email(email)
        self.assertEqual(ujson.loads(user.muted_topics), [["stream", "topic"]])

        url = '/json/users/me/subscriptions/muted_topics'
        data = {'muted_topics': '[["stream2", "topic2"]]'}
        result = self.client_post(url, data)
        self.assert_json_success(result)

        user = get_user_profile_by_email(email)
        self.assertEqual(ujson.loads(user.muted_topics), [["stream2", "topic2"]])
