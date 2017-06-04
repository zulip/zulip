# -*- coding: utf-8 -*-AA
from __future__ import absolute_import

from typing import Any, Dict, List

from zerver.models import (
    get_user, Recipient, UserMessage
)

from zerver.lib.test_helpers import tornado_redirected_to_list
from zerver.lib.test_classes import (
    ZulipTestCase,
)
import ujson

class PointerTest(ZulipTestCase):

    def test_update_pointer(self):
        # type: () -> None
        """
        Posting a pointer to /update (in the form {"pointer": pointer}) changes
        the pointer we store for your UserProfile.
        """
        self.login(self.example_email("hamlet"))
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        msg_id = self.send_message(self.example_email("othello"), "Verona", Recipient.STREAM)
        result = self.client_post("/json/users/me/pointer", {"pointer": msg_id})
        self.assert_json_success(result)
        self.assertEqual(self.example_user('hamlet').pointer, msg_id)

    def test_api_update_pointer(self):
        # type: () -> None
        """
        Same as above, but for the API view
        """
        user = self.example_user('hamlet')
        email = user.email
        self.assertEqual(user.pointer, -1)
        msg_id = self.send_message(self.example_email("othello"), "Verona", Recipient.STREAM)
        result = self.client_post("/api/v1/users/me/pointer", {"pointer": msg_id},
                                  **self.api_auth(email))
        self.assert_json_success(result)
        self.assertEqual(get_user(email, user.realm).pointer, msg_id)

    def test_missing_pointer(self):
        # type: () -> None
        """
        Posting json to /json/users/me/pointer which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login(self.example_email("hamlet"))
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        result = self.client_post("/json/users/me/pointer", {"foo": 1})
        self.assert_json_error(result, "Missing 'pointer' argument")
        self.assertEqual(self.example_user('hamlet').pointer, -1)

    def test_invalid_pointer(self):
        # type: () -> None
        """
        Posting json to /json/users/me/pointer with an invalid pointer returns a 400 and error
        message.
        """
        self.login(self.example_email("hamlet"))
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        result = self.client_post("/json/users/me/pointer", {"pointer": "foo"})
        self.assert_json_error(result, "Bad value for 'pointer': foo")
        self.assertEqual(self.example_user('hamlet').pointer, -1)

    def test_pointer_out_of_range(self):
        # type: () -> None
        """
        Posting json to /json/users/me/pointer with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login(self.example_email("hamlet"))
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        result = self.client_post("/json/users/me/pointer", {"pointer": -2})
        self.assert_json_error(result, "Bad value for 'pointer': -2")
        self.assertEqual(self.example_user('hamlet').pointer, -1)

    def test_use_first_unread_anchor_interaction_with_pointer(self):
        # type: () -> None
        """
        Getting old messages (a get request to /json/messages) should never
        return an unread message older than the current pointer, when there's
        no narrow set.
        """
        self.login(self.example_email("hamlet"))
        # Ensure the pointer is not set (-1)
        self.assertEqual(self.example_user('hamlet').pointer, -1)
        # Mark all existing messages as read
        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                           "op": "add",
                                                           "flag": "read",
                                                           "all": ujson.dumps(True)})
        self.assert_json_success(result)

        # Send a new message (this will be unread)
        new_message_id = self.send_message(self.example_email("othello"), "Verona",
                                           Recipient.STREAM, "test")

        # If we call get_messages with use_first_unread_anchor=True, we
        # should get the message we just sent
        messages = self.get_messages(
            anchor=0, num_before=0, num_after=1, use_first_unread_anchor=True)
        self.assertEqual(messages[0]['id'], new_message_id)

        # We want to get the message_id of an arbitrar old message. We can
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
        messages = self.get_messages(
            anchor=0, num_before=0, num_after=1, use_first_unread_anchor=True)
        self.assertEqual(messages[0]['id'], old_message_id)

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

        # Now if we call get_messages with use_first_unread_anchor=True,
        # we should not get the old unread message (because it's before the
        # pointer), and instead should get the newly sent unread message
        messages = self.get_messages(
            anchor=0, num_before=0, num_after=1, use_first_unread_anchor=True)
        self.assertEqual(messages[0]['id'], new_message_id)

class UnreadCountTests(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.unread_msg_ids = [
            self.send_message(
                self.example_email("iago"), self.example_email("hamlet"), Recipient.PERSONAL, "hello"),
            self.send_message(
                self.example_email("iago"), self.example_email("hamlet"), Recipient.PERSONAL, "hello2")]

    # Sending a new message results in unread UserMessages being created
    def test_new_message(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        content = "Test message for unset read bit"
        last_msg = self.send_message(self.example_email("hamlet"), "Verona", Recipient.STREAM, content)
        user_messages = list(UserMessage.objects.filter(message=last_msg))
        self.assertEqual(len(user_messages) > 0, True)
        for um in user_messages:
            self.assertEqual(um.message.content, content)
            if um.user_profile.email != self.example_email("hamlet"):
                self.assertFalse(um.flags.read)

    def test_update_flags(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))

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

    def test_update_all_flags(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))

        message_ids = [self.send_message(self.example_email("hamlet"), self.example_email("iago"),
                                         Recipient.PERSONAL, "test"),
                       self.send_message(self.example_email("hamlet"), self.example_email("cordelia"),
                                         Recipient.PERSONAL, "test2")]

        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps(message_ids),
                                                           "op": "add",
                                                           "flag": "read"})
        self.assert_json_success(result)

        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                           "op": "remove",
                                                           "flag": "read",
                                                           "all": ujson.dumps(True)})
        self.assert_json_success(result)

        for msg in self.get_messages():
            self.assertEqual(msg['flags'], [])

    def test_mark_all_in_stream_read(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        self.subscribe_to_stream(user_profile.email, "test_stream", user_profile.realm)
        self.subscribe_to_stream(self.example_email("cordelia"), "test_stream", user_profile.realm)

        message_id = self.send_message(self.example_email("hamlet"), "test_stream", Recipient.STREAM, "hello")
        unrelated_message_id = self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, "hello")

        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                               "op": "add",
                                                               "flag": "read",
                                                               "stream_name": "test_stream"})

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
            if msg.user_profile.email == self.example_email("hamlet"):
                self.assertTrue(msg.flags.read)
            else:
                self.assertFalse(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile.email == self.example_email("hamlet"):
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_stream_read(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        invalid_stream_name = ""
        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                           "op": "add",
                                                           "flag": "read",
                                                           "stream_name": invalid_stream_name})
        self.assert_json_error(result, 'No such stream \'\'')

    def test_mark_all_in_stream_topic_read(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        user_profile = self.example_user('hamlet')
        self.subscribe_to_stream(user_profile.email, "test_stream", user_profile.realm)

        message_id = self.send_message(self.example_email("hamlet"), "test_stream", Recipient.STREAM, "hello", "test_topic")
        unrelated_message_id = self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM, "hello", "Denmark2")
        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                               "op": "add",
                                                               "flag": "read",
                                                               "topic_name": "test_topic",
                                                               "stream_name": "test_stream"})

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
            if msg.user_profile.email == self.example_email("hamlet"):
                self.assertTrue(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile.email == self.example_email("hamlet"):
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_topic_read(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        invalid_topic_name = "abc"
        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                           "op": "add",
                                                           "flag": "read",
                                                           "topic_name": invalid_topic_name,
                                                           "stream_name": "Denmark"})
        self.assert_json_error(result, 'No such topic \'abc\'')
