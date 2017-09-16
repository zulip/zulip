from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_user, get_stream, get_recipient, Recipient
from zerver.lib.topic_mutes import (
    add_topic_mute,
    get_topic_mutes,
    topic_is_muted,
)

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

        stream = get_stream(u'Verona', user.realm)
        self.assertTrue(topic_is_muted(user, stream, 'Verona3'))
        self.assertTrue(topic_is_muted(user, stream, 'verona3'))

    def test_remove_muted_topic(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        realm = self.user_profile.realm
        stream = get_stream(u'Verona', realm)
        recipient = get_recipient(Recipient.STREAM, stream.id)
        add_topic_mute(
            user_profile=self.user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=u'Verona3',
        )

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'vERONA3', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))

        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertNotIn([[u'Verona', u'Verona3']], get_topic_mutes(user))

    def test_muted_topic_add_invalid(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        realm = self.user_profile.realm
        stream = get_stream(u'Verona', realm)
        recipient = get_recipient(Recipient.STREAM, stream.id)
        add_topic_mute(
            user_profile=self.user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=u'Verona3',
        )

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
        data = {'stream': 'BOGUS', 'topic': 'Verona3', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_error(result, "Topic is not there in the muted_topics list")

        data = {'stream': 'Verona', 'topic': 'BOGUS', 'op': 'remove'}
        result = self.client_patch(url, data, **self.api_auth(email))
        self.assert_json_error(result, "Topic is not there in the muted_topics list")
