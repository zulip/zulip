from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_user
from zerver.lib.actions import do_set_muted_topics

class MutedTopicsTests(ZulipTestCase):
    def test_json_set(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'muted_topics': '[["stream", "topic"]]'}
        result = self.client_post(url, data, **self.api_auth(email))
        self.assert_json_success(result)

        user = self.example_user('hamlet')
        self.assertEqual(ujson.loads(user.muted_topics), [["stream", "topic"]])

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'muted_topics': '[["stream2", "topic2"]]'}
        result = self.client_post(url, data, **self.api_auth(email))
        self.assert_json_success(result)

        user = self.example_user('hamlet')
        self.assertEqual(ujson.loads(user.muted_topics), [["stream2", "topic2"]])

    def test_add_muted_topic(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_success(result)

        user = self.example_user('hamlet')
        self.assertIn([u'Verona', u'Verona3'], ujson.loads(user.muted_topics))

    def test_remove_muted_topic(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        do_set_muted_topics(self.user_profile, [[u'Verona', u'Verona3']])
        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))

        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertNotIn([[u'Verona', u'Verona3']], ujson.loads(user.muted_topics))

    def test_muted_topic_add_invalid(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        do_set_muted_topics(self.user_profile, [[u'Verona', u'Verona3']])
        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_error(result, "Topic already muted")

    def test_muted_topic_remove_invalid(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        do_set_muted_topics(self.user_profile, [[u'Denmark', u'Denmark3']])
        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_error(result, "Topic is not there in the muted_topics list")
