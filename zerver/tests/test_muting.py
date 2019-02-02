from typing import Any, Dict

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.stream_topic import StreamTopicTarget

from zerver.models import (
    get_stream,
    get_stream_recipient,
    UserProfile,
)

from zerver.lib.topic_mutes import (
    add_topic_mute,
    get_topic_mutes,
    remove_topic_mute,
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
        user = self.example_user('hamlet')
        self.login(user.email)

        stream = get_stream('Verona', user.realm)

        url = '/api/v1/users/me/subscriptions/muted_topics'

        payloads = [
            {'stream': stream.name, 'topic': 'Verona3', 'op': 'add'},
            {'stream_id': stream.id, 'topic': 'Verona3', 'op': 'add'},
        ]

        for data in payloads:
            result = self.api_patch(user.email, url, data)
            self.assert_json_success(result)

            self.assertIn([stream.name, 'Verona3'], get_topic_mutes(user))

            self.assertTrue(topic_is_muted(user, stream.id, 'Verona3'))
            self.assertTrue(topic_is_muted(user, stream.id, 'verona3'))

            remove_topic_mute(
                user_profile=user,
                stream_id=stream.id,
                topic_name='Verona3',
            )

    def test_remove_muted_topic(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        realm = user.realm
        self.login(email)

        stream = get_stream(u'Verona', realm)
        recipient = get_stream_recipient(stream.id)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        payloads = [
            {'stream': stream.name, 'topic': 'vERONA3', 'op': 'remove'},
            {'stream_id': stream.id, 'topic': 'vEroNA3', 'op': 'remove'},
        ]

        for data in payloads:
            add_topic_mute(
                user_profile=user,
                stream_id=stream.id,
                recipient_id=recipient.id,
                topic_name='Verona3',
            )
            self.assertIn([stream.name, 'Verona3'], get_topic_mutes(user))

            result = self.api_patch(email, url, data)

            self.assert_json_success(result)
            self.assertNotIn([stream.name, 'Verona3'], get_topic_mutes(user))
            self.assertFalse(topic_is_muted(user, stream.id, 'verona3'))

    def test_muted_topic_add_invalid(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        realm = user.realm
        self.login(email)

        stream = get_stream('Verona', realm)
        recipient = get_stream_recipient(stream.id)
        add_topic_mute(
            user_profile=user,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=u'Verona3',
        )

        url = '/api/v1/users/me/subscriptions/muted_topics'

        data = {'stream': stream.name, 'topic': 'Verona3', 'op': 'add'}  # type: Dict[str, Any]
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic already muted")

        data = {'stream_id': 999999999, 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Invalid stream id")

        data = {'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Please supply 'stream'.")

        data = {'stream': stream.name, 'stream_id': stream.id, 'topic': 'Verona3', 'op': 'add'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Please choose one: 'stream' or 'stream_id'.")

    def test_muted_topic_remove_invalid(self) -> None:
        user = self.example_user('hamlet')
        email = user.email
        realm = user.realm
        self.login(email)
        stream = get_stream('Verona', realm)

        url = '/api/v1/users/me/subscriptions/muted_topics'
        data = {'stream': 'BOGUS', 'topic': 'Verona3', 'op': 'remove'}  # type: Dict[str, Any]
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not muted")

        data = {'stream': stream.name, 'topic': 'BOGUS', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not muted")

        data = {'stream_id': 999999999, 'topic': 'BOGUS', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Topic is not muted")

        data = {'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Please supply 'stream'.")

        data = {'stream': stream.name, 'stream_id': stream.id, 'topic': 'Verona3', 'op': 'remove'}
        result = self.api_patch(email, url, data)
        self.assert_json_error(result, "Please choose one: 'stream' or 'stream_id'.")
