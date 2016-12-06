# -*- coding: utf-8 -*-AA
from __future__ import absolute_import

from typing import Any, Dict, List

from zerver.models import (
    get_user_profile_by_email, Recipient, UserMessage
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
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        msg_id = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)
        result = self.client_put("/json/users/me/pointer", {"pointer": msg_id})
        self.assert_json_success(result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, msg_id)

    def test_api_update_pointer(self):
        # type: () -> None
        """
        Same as above, but for the API view
        """
        email = "hamlet@zulip.com"
        self.assertEqual(get_user_profile_by_email(email).pointer, -1)
        msg_id = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)
        result = self.client_put("/api/v1/users/me/pointer", {"pointer": msg_id},
                                 **self.api_auth(email))
        self.assert_json_success(result)
        self.assertEqual(get_user_profile_by_email(email).pointer, msg_id)

    def test_missing_pointer(self):
        # type: () -> None
        """
        Posting json to /json/users/me/pointer which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        result = self.client_put("/json/users/me/pointer", {"foo": 1})
        self.assert_json_error(result, "Missing 'pointer' argument")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)

    def test_invalid_pointer(self):
        # type: () -> None
        """
        Posting json to /json/users/me/pointer with an invalid pointer returns a 400 and error
        message.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        result = self.client_put("/json/users/me/pointer", {"pointer": "foo"})
        self.assert_json_error(result, "Bad value for 'pointer': foo")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)

    def test_pointer_out_of_range(self):
        # type: () -> None
        """
        Posting json to /json/users/me/pointer with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        result = self.client_put("/json/users/me/pointer", {"pointer": -2})
        self.assert_json_error(result, "Bad value for 'pointer': -2")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)

class UnreadCountTests(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.unread_msg_ids = [self.send_message(
                "iago@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL, "hello"),
                               self.send_message(
                "iago@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL, "hello2")]

    # Sending a new message results in unread UserMessages being created
    def test_new_message(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        content = "Test message for unset read bit"
        last_msg = self.send_message("hamlet@zulip.com", "Verona", Recipient.STREAM, content)
        user_messages = list(UserMessage.objects.filter(message=last_msg))
        self.assertEqual(len(user_messages) > 0, True)
        for um in user_messages:
            self.assertEqual(um.message.content, content)
            if um.user_profile.email != "hamlet@zulip.com":
                self.assertFalse(um.flags.read)

    def test_update_flags(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps(self.unread_msg_ids),
                                   "op": "add",
                                   "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly set the flags
        found = 0
        for msg in self.get_old_messages():
            if msg['id'] in self.unread_msg_ids:
                self.assertEqual(msg['flags'], ['read'])
                found += 1
        self.assertEqual(found, 2)

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([self.unread_msg_ids[1]]),
                                   "op": "remove", "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly remove just one flag
        for msg in self.get_old_messages():
            if msg['id'] == self.unread_msg_ids[0]:
                self.assertEqual(msg['flags'], ['read'])
            elif msg['id'] == self.unread_msg_ids[1]:
                self.assertEqual(msg['flags'], [])

    def test_update_all_flags(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        message_ids = [self.send_message("hamlet@zulip.com", "iago@zulip.com",
                                         Recipient.PERSONAL, "test"),
                       self.send_message("hamlet@zulip.com", "cordelia@zulip.com",
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

        for msg in self.get_old_messages():
            self.assertEqual(msg['flags'], [])

    def test_mark_all_in_stream_read(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "test_stream", user_profile.realm)

        message_id = self.send_message("hamlet@zulip.com", "test_stream", Recipient.STREAM, "hello")
        unrelated_message_id = self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, "hello")

        events = [] # type: List[Dict[str, Any]]
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
            if msg.user_profile.email == "hamlet@zulip.com":
                self.assertTrue(msg.flags.read)
            else:
                self.assertFalse(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile.email == "hamlet@zulip.com":
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_stream_read(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        invalid_stream_name = ""
        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                           "op": "add",
                                                           "flag": "read",
                                                           "stream_name": invalid_stream_name})
        self.assert_json_error(result, 'No such stream \'\'')

    def test_mark_all_in_stream_topic_read(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.subscribe_to_stream(user_profile.email, "test_stream", user_profile.realm)

        message_id = self.send_message("hamlet@zulip.com", "test_stream", Recipient.STREAM, "hello", "test_topic")
        unrelated_message_id = self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM, "hello", "Denmark2")
        events = [] # type: List[Dict[str, Any]]
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
            if msg.user_profile.email == "hamlet@zulip.com":
                self.assertTrue(msg.flags.read)

        unrelated_messages = list(UserMessage.objects.filter(message=unrelated_message_id))
        for msg in unrelated_messages:
            if msg.user_profile.email == "hamlet@zulip.com":
                self.assertFalse(msg.flags.read)

    def test_mark_all_in_invalid_topic_read(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        invalid_topic_name = "abc"
        result = self.client_post("/json/messages/flags", {"messages": ujson.dumps([]),
                                                           "op": "add",
                                                           "flag": "read",
                                                           "topic_name": invalid_topic_name,
                                                           "stream_name": "Denmark"})
        self.assert_json_error(result, 'No such topic \'abc\'')
