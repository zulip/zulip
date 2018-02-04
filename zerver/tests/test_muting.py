
import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.stream_topic import StreamTopicTarget

from zerver.models import (
    get_realm,
    get_stream,
    get_stream_recipient,
    get_user,
    Recipient,
    UserProfile,
)

from zerver.lib.topic_mutes import (
    add_topic_mute,
    get_topic_mutes,
    topic_is_muted,
)

class MutedTopicsTests(ZulipTestCase):
    def test_user_ids_muting_topic(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia  = self.example_user('cordelia')
        realm = hamlet.realm
        stream = get_stream(u'Verona', realm)
        recipient = get_stream_recipient(stream.id)
        topic_name = 'teST topic'

        stream_topic_target = StreamTopicTarget(
            stream_id=stream.id,
            topic_name=topic_name,
        )

        user_ids = stream_topic_target.user_ids_muting_topic()
        self.assertEqual(user_ids, set())

        def mute_user(user: UserProfile) -> None:
            add_topic_mute(
                user_profile=user,
                stream_id=stream.id,
                recipient_id=recipient.id,
                topic_name='test TOPIC',
            )

        mute_user(hamlet)
        user_ids = stream_topic_target.user_ids_muting_topic()
        self.assertEqual(user_ids, {hamlet.id})

        mute_user(cordelia)
        user_ids = stream_topic_target.user_ids_muting_topic()
        self.assertEqual(user_ids, {hamlet.id, cordelia.id})

    def test_add_muted_topic(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_success(result)

        user = self.example_user('hamlet')
        self.assertIn([u'Verona', u'Verona3'], get_topic_mutes(user))

        stream = get_stream(u'Verona', user.realm)
        self.assertTrue(topic_is_muted(user, stream.id, 'Verona3'))
        self.assertTrue(topic_is_muted(user, stream.id, 'verona3'))

    def test_remove_muted_topic(self) -> None:
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        realm = self.user_profile.realm
        stream = get_stream(u'Verona', realm)
        recipient = get_stream_recipient(stream.id)
        add_topic_mute(
            user_profile=self.user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=u'Verona3',
        )

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'vERONA3', 'op': 'remove'}
        result = self.api_patch(email, url, data)

        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertNotIn([[u'Verona', u'Verona3']], get_topic_mutes(user))

    def test_muted_topic_add_invalid(self) -> None:
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        realm = self.user_profile.realm
        stream = get_stream(u'Verona', realm)
        recipient = get_stream_recipient(stream.id)
        add_topic_mute(
            user_profile=self.user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=u'Verona3',
        )

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'Verona', 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic already muted")

    def test_muted_topic_remove_invalid(self) -> None:
        self.user_profile = self.example_user('hamlet')
        email = self.user_profile.email
        self.login(email)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'BOGUS', 'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not there in the muted_topics list")

        data = {'stream': 'Verona', 'topic': 'BOGUS', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not there in the muted_topics list")
