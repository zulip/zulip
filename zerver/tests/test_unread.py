from typing import Any, List, Mapping
from unittest import mock

import ujson
from django.db import connection

from zerver.lib.fix_unreads import fix, fix_pre_pointer, fix_unsubscribed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_subscription, tornado_redirected_to_list
from zerver.lib.topic_mutes import add_topic_mute
from zerver.models import Subscription, UserMessage, UserProfile, get_realm, get_stream, get_user


class PointerTest(ZulipTestCase):

    def test_update_pointer(self) -> None:
        """
        Posting a pointer to /update (in the form {"pointer": pointer}) changes
        the pointer we store for your UserProfile.
        """
        self.login('hamlet')
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        msg_id = self.send_stream_message(self.example_user("othello"), "Verona")
        result = self.client_post("/json/users/me/pointer", {"pointer": msg_id})
        self.assert_json_success(result)
        self.assertEqual(self.example_user('hamlet').pointer, msg_id)

    def test_api_update_pointer(self) -> None:
        """
        Same as above, but for the API view
        """
        user = self.example_user('hamlet')
        email = user.email
        self.assertEqual(user.pointer, -1)
        msg_id = self.send_stream_message(self.example_user("othello"), "Verona")
        result = self.api_post(user, "/api/v1/users/me/pointer", {"pointer": msg_id})
        self.assert_json_success(result)
        self.assertEqual(get_user(email, user.realm).pointer, msg_id)

    def test_missing_pointer(self) -> None:
        """
        Posting json to /json/users/me/pointer which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login('hamlet')
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        result = self.client_post("/json/users/me/pointer", {"foo": 1})
        self.assert_json_error(result, "Missing 'pointer' argument")
        self.assertEqual(self.example_user('hamlet').pointer, -1)

    def test_invalid_pointer(self) -> None:
        """
        Posting json to /json/users/me/pointer with an invalid pointer returns a 400 and error
        message.
        """
        self.login('hamlet')
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        result = self.client_post("/json/users/me/pointer", {"pointer": "foo"})
        self.assert_json_error(result, "Bad value for 'pointer': foo")
        self.assertEqual(self.example_user('hamlet').pointer, -1)

    def test_pointer_out_of_range(self) -> None:
        """
        Posting json to /json/users/me/pointer with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login('hamlet')
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        result = self.client_post("/json/users/me/pointer", {"pointer": -2})
        self.assert_json_error(result, "Bad value for 'pointer': -2")
        self.assertEqual(self.example_user('hamlet').pointer, -1)

    def test_use_first_unread_anchor_interaction_with_pointer(self) -> None:
        """
        Getting old messages (a get request to /json/messages) should never
        return an unread message older than the current pointer, when there's
        no narrow set.
        """
        self.login('hamlet')
        # Ensure the pointer is not set (-1)
        self.assertEqual(self.example_user('hamlet').pointer, -1)

        # Mark all existing messages as read
        result = self.client_post("/json/mark_all_as_read")
        self.assert_json_success(result)

        # Send a new message (this will be unread)
        new_message_id = self.send_stream_message(self.example_user("othello"), "Verona",
                                                  "test")

        # If we call get_messages with use_first_unread_anchor=True, we
        # should get the message we just sent
        messages_response = self.get_messages_response(
            anchor="first_unread", num_before=0, num_after=1)
        self.assertEqual(messages_response['messages'][0]['id'], new_message_id)
        self.assertEqual(messages_response['anchor'], new_message_id)

        # Test with the old way of expressing use_first_unread_anchor=True
        messages_response = self.get_messages_response(
            anchor=0, num_before=0, num_after=1, use_first_unread_anchor=True)
        self.assertEqual(messages_response['messages'][0]['id'], new_message_id)
        self.assertEqual(messages_response['anchor'], new_message_id)

        # We want to get the message_id of an arbitrary old message. We can
        # call get_messages with use_first_unread_anchor=False and simply
        # save the first message we're returned.
        messages = self.get_messages(
            anchor=0, num_before=0, num_after=2, use_first_unread_anchor=False)
        old_message_id = messages[0]['id']
        next_old_message_id = messages[1]['id']

        # Verify the message is marked as read
        user_message = UserMessage.objects.get(
            message_id=old_message_id,
            user_profile=self.example_user('hamlet'))
        self.assertTrue(user_message.flags.read)

        # Let's set this old message to be unread
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([old_message_id]),
                                   "op": "remove",
                                   "flag": "read"})

        # Verify it's now marked as unread
        user_message = UserMessage.objects.get(
            message_id=old_message_id,
            user_profile=self.example_user('hamlet'))
        self.assert_json_success(result)
        self.assertFalse(user_message.flags.read)

        # Now if we call get_messages with use_first_unread_anchor=True,
        # we should get the old message we just set to unread
        messages_response = self.get_messages_response(
            anchor="first_unread", num_before=0, num_after=1)
        self.assertEqual(messages_response['messages'][0]['id'], old_message_id)
        self.assertEqual(messages_response['anchor'], old_message_id)

        # Let's update the pointer to be *after* this old unread message (but
        # still on or before the new unread message we just sent)
        result = self.client_post("/json/users/me/pointer",
                                  {"pointer": next_old_message_id})
        self.assert_json_success(result)
        self.assertEqual(self.example_user('hamlet').pointer,
                         next_old_message_id)

        # Verify that moving the pointer didn't mark our message as read.
        user_message = UserMessage.objects.get(
            message_id=old_message_id,
            user_profile=self.example_user('hamlet'))
        self.assertFalse(user_message.flags.read)

    def test_visible_messages_use_first_unread_anchor(self) -> None:
        self.login('hamlet')
        self.assertEqual(self.example_user('hamlet').pointer, -1)

        result = self.client_post("/json/mark_all_as_read")
        self.assert_json_success(result)

        new_message_id = self.send_stream_message(self.example_user("othello"), "Verona",
                                                  "test")

        messages_response = self.get_messages_response(
            anchor="first_unread", num_before=0, num_after=1)
        self.assertEqual(messages_response['messages'][0]['id'], new_message_id)
        self.assertEqual(messages_response['anchor'], new_message_id)

        with mock.patch('zerver.views.messages.get_first_visible_message_id', return_value=new_message_id):
            messages_response = self.get_messages_response(
                anchor="first_unread", num_before=0, num_after=1)
        self.assertEqual(messages_response['messages'][0]['id'], new_message_id)
        self.assertEqual(messages_response['anchor'], new_message_id)

        with mock.patch('zerver.views.messages.get_first_visible_message_id', return_value=new_message_id + 1):
            messages_reponse = self.get_messages_response(
                anchor="first_unread", num_before=0, num_after=1)
        self.assert_length(messages_reponse['messages'], 0)
        self.assertIn('anchor', messages_reponse)

        with mock.patch('zerver.views.messages.get_first_visible_message_id', return_value=new_message_id - 1):
            messages = self.get_messages(
                anchor="first_unread", num_before=0, num_after=1)
        self.assert_length(messages, 1)

class UnreadCountTests(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        with mock.patch('zerver.lib.push_notifications.push_notifications_enabled',
                        return_value = True) as mock_push_notifications_enabled:
            self.unread_msg_ids = [
                self.send_personal_message(
                    self.example_user("iago"), self.example_user("hamlet"), "hello"),
                self.send_personal_message(
                    self.example_user("iago"), self.example_user("hamlet"), "hello2")]
            mock_push_notifications_enabled.assert_called()

    # Sending a new message results in unread UserMessages being created
    def test_new_message(self) -> None:
        self.login('hamlet')
        content = "Test message for unset read bit"
        last_msg = self.send_stream_message(self.example_user("hamlet"), "Verona", content)
        user_messages = list(UserMessage.objects.filter(message=last_msg))
        self.assertEqual(len(user_messages) > 0, True)
        for um in user_messages:
            self.assertEqual(um.message.content, content)
            if um.user_profile.email != self.example_email("hamlet"):
                self.assertFalse(um.flags.read)

    def test_update_flags(self) -> None:
        self.login('hamlet')

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps(self.unread_msg_ids),
                                   "op": "add",
                                   "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly set the flags
        found = 0
        for msg in self.get_messages():
            if msg['id'] in self.unread_msg_ids:
                self.assertEqual(msg['flags'], ['read'])
                found += 1
        self.assertEqual(found, 2)

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([self.unread_msg_ids[1]]),
                                   "op": "remove", "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly remove just one flag
        for msg in self.get_messages():
            if msg['id'] == self.unread_msg_ids[0]:
                self.assertEqual(msg['flags'], ['read'])
            elif msg['id'] == self.unread_msg_ids[1]:
                self.assertEqual(msg['flags'], [])

    def test_mark_all_in_stream_read(self) -> None:
        self.login('hamlet')
        user_profile = self.example_user('hamlet')
        stream = self.subscribe(user_profile, "test_stream")
        self.subscribe(self.example_user("cordelia"), "test_stream")

        message_id = self.send_stream_message(self.example_user("hamlet"), "test_stream", "hello")
        unrelated_message_id = self.send_stream_message(self.example_user("hamlet"), "Denmark", "hello")

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            result = self.client_post("/json/mark_stream_as_read", {
                "stream_id": stream.id,
            })

        self.assert_json_success(result)
        self.assertTrue(len(events) == 1)

        event = events[0]['event']
        expected = dict(operation='add',
                        messages=[message_id],
                        flag='read',
                        type='update_message_flags',
                        all=False)

        differences = [key for key in expected if expected[key] != event[key]]
        self.assertTrue(len(differences) == 0)

        hamlet = self.example_user('hamlet')
        um = list(UserMessage.objects.filter(message=message_id))
        for msg in um:
            if msg.user_profile.email == hamlet.email:
                self.assertTrue(msg.flags.read)
            else:
                self.assertFalse(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile.email == hamlet.email:
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_stream_read(self) -> None:
        self.login('hamlet')
        invalid_stream_id = "12345678"
        result = self.client_post("/json/mark_stream_as_read", {
            "stream_id": invalid_stream_id,
        })
        self.assert_json_error(result, 'Invalid stream id')

    def test_mark_all_topics_unread_with_invalid_stream_name(self) -> None:
        self.login('hamlet')
        invalid_stream_id = "12345678"
        result = self.client_post("/json/mark_topic_as_read", {
            "stream_id": invalid_stream_id,
            'topic_name': 'whatever',
        })
        self.assert_json_error(result, "Invalid stream id")

    def test_mark_all_in_stream_topic_read(self) -> None:
        self.login('hamlet')
        user_profile = self.example_user('hamlet')
        self.subscribe(user_profile, "test_stream")

        message_id = self.send_stream_message(self.example_user("hamlet"), "test_stream", "hello", "test_topic")
        unrelated_message_id = self.send_stream_message(self.example_user("hamlet"), "Denmark", "hello", "Denmark2")
        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            result = self.client_post("/json/mark_topic_as_read", {
                "stream_id": get_stream("test_stream", user_profile.realm).id,
                "topic_name": "test_topic",
            })

        self.assert_json_success(result)
        self.assertTrue(len(events) == 1)

        event = events[0]['event']
        expected = dict(operation='add',
                        messages=[message_id],
                        flag='read',
                        type='update_message_flags',
                        all=False)

        differences = [key for key in expected if expected[key] != event[key]]
        self.assertTrue(len(differences) == 0)

        um = list(UserMessage.objects.filter(message=message_id))
        for msg in um:
            if msg.user_profile_id == user_profile.id:
                self.assertTrue(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile_id == user_profile.id:
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_topic_read(self) -> None:
        self.login('hamlet')
        invalid_topic_name = "abc"
        result = self.client_post("/json/mark_topic_as_read", {
            "stream_id": get_stream("Denmark", get_realm("zulip")).id,
            "topic_name": invalid_topic_name,
        })
        self.assert_json_error(result, 'No such topic \'abc\'')

class FixUnreadTests(ZulipTestCase):
    def test_fix_unreads(self) -> None:
        user = self.example_user('hamlet')
        realm = get_realm('zulip')

        def send_message(stream_name: str, topic_name: str) -> int:
            msg_id = self.send_stream_message(
                self.example_user("othello"),
                stream_name,
                topic_name=topic_name)
            um = UserMessage.objects.get(
                user_profile=user,
                message_id=msg_id)
            return um.id

        def assert_read(user_message_id: int) -> None:
            um = UserMessage.objects.get(id=user_message_id)
            self.assertTrue(um.flags.read)

        def assert_unread(user_message_id: int) -> None:
            um = UserMessage.objects.get(id=user_message_id)
            self.assertFalse(um.flags.read)

        def mute_stream(stream_name: str) -> None:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient
            subscription = Subscription.objects.get(
                user_profile=user,
                recipient=recipient,
            )
            subscription.is_muted = True
            subscription.save()

        def mute_topic(stream_name: str, topic_name: str) -> None:
            stream = get_stream(stream_name, realm)
            recipient = stream.recipient

            add_topic_mute(
                user_profile=user,
                stream_id=stream.id,
                recipient_id=recipient.id,
                topic_name=topic_name,
            )

        def force_unsubscribe(stream_name: str) -> None:
            '''
            We don't want side effects here, since the eventual
            unsubscribe path may mark messages as read, defeating
            the test setup here.
            '''
            sub = get_subscription(stream_name, user)
            sub.active = False
            sub.save()

        # The data setup here is kind of funny, because some of these
        # conditions should not actually happen in practice going forward,
        # but we may have had bad data from the past.

        mute_stream('Denmark')
        mute_topic('Verona', 'muted_topic')

        um_normal_id = send_message('Verona', 'normal')
        um_muted_topic_id = send_message('Verona', 'muted_topic')
        um_muted_stream_id = send_message('Denmark', 'whatever')

        user.pointer = self.get_last_message().id
        user.save()

        um_post_pointer_id = send_message('Verona', 'muted_topic')

        self.subscribe(user, 'temporary')
        um_unsubscribed_id = send_message('temporary', 'whatever')
        force_unsubscribe('temporary')

        # verify data setup
        assert_unread(um_normal_id)
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_unread(um_post_pointer_id)
        assert_unread(um_unsubscribed_id)

        with connection.cursor() as cursor:
            fix_pre_pointer(cursor, user)

        # The only message that should have been fixed is the "normal"
        # unumuted message before the pointer.
        assert_read(um_normal_id)

        # We don't "fix" any messages that are either muted or after the
        # pointer, because they can be legitimately unread.
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_unread(um_post_pointer_id)
        assert_unread(um_unsubscribed_id)

        # fix unsubscribed
        with connection.cursor() as cursor:
            fix_unsubscribed(cursor, user)

        # Most messages don't change.
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_unread(um_post_pointer_id)

        # The unsubscribed entry should change.
        assert_read(um_unsubscribed_id)

        # test idempotency
        fix(user)

        assert_read(um_normal_id)
        assert_unread(um_muted_topic_id)
        assert_unread(um_muted_stream_id)
        assert_unread(um_post_pointer_id)
        assert_read(um_unsubscribed_id)

class PushNotificationMarkReadFlowsTest(ZulipTestCase):
    def get_mobile_push_notification_ids(self, user_profile: UserProfile) -> List[int]:
        return list(UserMessage.objects.filter(
            user_profile=user_profile,
        ).extra(
            where=[UserMessage.where_active_push_notification()],
        ).order_by("message_id").values_list("message_id", flat=True))

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value=True)
    def test_track_active_mobile_push_notifications(self, mock_push_notifications: mock.MagicMock) -> None:
        mock_push_notifications.return_value = True
        self.login('hamlet')
        user_profile = self.example_user('hamlet')
        stream = self.subscribe(user_profile, "test_stream")
        second_stream = self.subscribe(user_profile, "second_stream")

        property_name = "push_notifications"
        result = self.api_post(user_profile, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": True,
                                                                   "stream_id": stream.id}])})
        result = self.api_post(user_profile, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": True,
                                                                   "stream_id": second_stream.id}])})
        self.assert_json_success(result)
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile), [])

        message_id = self.send_stream_message(self.example_user("cordelia"), "test_stream", "hello", "test_topic")
        second_message_id = self.send_stream_message(self.example_user("cordelia"), "test_stream", "hello", "other_topic")
        third_message_id = self.send_stream_message(self.example_user("cordelia"), "second_stream", "hello", "test_topic")

        self.assertEqual(self.get_mobile_push_notification_ids(user_profile),
                         [message_id, second_message_id, third_message_id])

        result = self.client_post("/json/mark_topic_as_read", {
            "stream_id": str(stream.id),
            "topic_name": "test_topic",
        })

        self.assert_json_success(result)
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile),
                         [second_message_id, third_message_id])

        result = self.client_post("/json/mark_stream_as_read", {
            "stream_id": str(stream.id),
            "topic_name": "test_topic",
        })
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile),
                         [third_message_id])

        fourth_message_id = self.send_stream_message(self.example_user("cordelia"), "test_stream", "hello", "test_topic")
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile),
                         [third_message_id, fourth_message_id])

        result = self.client_post("/json/mark_all_as_read", {})
        self.assertEqual(self.get_mobile_push_notification_ids(user_profile),
                         [])
        mock_push_notifications.assert_called()
