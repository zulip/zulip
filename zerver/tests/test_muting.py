from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_user
from zerver.lib.actions import do_update_muted_topic
from zerver.lib.topic_mutes import get_topic_mutes

class MutedTopicsTests(ZulipTestCase):
    def test_add_muted_topic(self):
        # type: () -> None
        email = self.example_email('hamlet')
        self.login(email)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_success(result)

        user = self.example_user('hamlet')
        self.assertIn([u'Verona', u'Verona3'], get_topic_mutes(user))

    def test_remove_muted_topic(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        do_update_muted_topic(self.user_profile, u'Verona', u'Verona3', op='add')
        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))

        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertNotIn([[u'Verona', u'Verona3']], get_topic_mutes(user))

    def test_muted_topic_add_invalid(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        do_update_muted_topic(self.user_profile, u'Verona', u'Verona3', op='add')
        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_error(result, "Topic already muted")

    def test_muted_topic_remove_invalid(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_error(result, "Topic is not there in the muted_topics list")
