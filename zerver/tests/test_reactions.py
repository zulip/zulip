# -*- coding: utf-8 -*-
from __future__ import absolute_import

import ujson
from typing import Any, Dict, List
from six import string_types

from zerver.lib.test_helpers import tornado_redirected_to_list, get_display_recipient, \
    get_test_image_file
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, Recipient, UserMessage

class ReactionEmojiTest(ZulipTestCase):
    def test_missing_emoji(self):
        # type: () -> None
        """
        Sending reaction without emoji fails
        """
        sender = self.example_email("hamlet")
        result = self.client_put('/api/v1/messages/1/emoji_reactions/',
                                 **self.api_auth(sender))
        self.assertEqual(result.status_code, 400)

    def test_add_invalid_emoji(self):
        # type: () -> None
        """
        Sending invalid emoji fails
        """
        sender = self.example_email("hamlet")
        result = self.client_put('/api/v1/messages/1/emoji_reactions/foo',
                                 **self.api_auth(sender))
        self.assert_json_error(result, "Emoji 'foo' does not exist")

    def test_remove_invalid_emoji(self):
        # type: () -> None
        """
        Removing invalid emoji fails
        """
        sender = self.example_email("hamlet")
        result = self.client_delete('/api/v1/messages/1/emoji_reactions/foo',
                                    **self.api_auth(sender))
        self.assert_json_error(result, "Emoji 'foo' does not exist")

    def test_valid_emoji(self):
        # type: () -> None
        """
        Reacting with valid emoji succeeds
        """
        sender = self.example_email("hamlet")
        result = self.client_put('/api/v1/messages/1/emoji_reactions/smile',
                                 **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

    def test_zulip_emoji(self):
        # type: () -> None
        """
        Reacting with zulip emoji succeeds
        """
        sender = self.example_email("hamlet")
        result = self.client_put('/api/v1/messages/1/emoji_reactions/zulip',
                                 **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

    def test_valid_emoji_react_historical(self):
        # type: () -> None
        """
        Reacting with valid emoji on a historical message succeeds
        """
        realm = get_realm("zulip")
        stream_name = "Saxony"
        self.subscribe_to_stream(self.example_email("cordelia"), stream_name, realm=realm)
        message_id = self.send_message(self.example_email("cordelia"), stream_name, Recipient.STREAM)

        user_profile = self.example_user('hamlet')
        sender = user_profile.email

        # Verify that hamlet did not receive the message.
        self.assertFalse(UserMessage.objects.filter(user_profile=user_profile,
                                                    message_id=message_id).exists())

        # Have hamlet react to the message
        result = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (message_id,),
                                 **self.api_auth(sender))
        self.assert_json_success(result)

        # Fetch the now-created UserMessage object to confirm it exists and is historical
        user_message = UserMessage.objects.get(user_profile=user_profile, message_id=message_id)
        self.assertTrue(user_message.flags.historical)
        self.assertTrue(user_message.flags.read)
        self.assertFalse(user_message.flags.starred)

    def test_valid_realm_emoji(self):
        # type: () -> None
        """
        Reacting with valid realm emoji succeeds
        """
        sender = self.example_email("hamlet")
        emoji_name = 'my_emoji'
        with get_test_image_file('img.png') as fp1:
            emoji_data = {'f1': fp1}
            result = self.client_put_multipart('/json/realm/emoji/my_emoji', info=emoji_data,
                                               **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

        result = self.client_get("/json/realm/emoji", **self.api_auth(sender))
        content = ujson.loads(result.content)
        self.assert_json_success(result)
        self.assertTrue(emoji_name in content["emoji"])

        result = self.client_put('/api/v1/messages/1/emoji_reactions/%s' % (emoji_name,),
                                 **self.api_auth(sender))
        self.assert_json_success(result)

class ReactionMessageIDTest(ZulipTestCase):
    def test_missing_message_id(self):
        # type: () -> None
        """
        Reacting without a message_id fails
        """
        sender = self.example_email("hamlet")
        result = self.client_put('/api/v1/messages//emoji_reactions/smile',
                                 **self.api_auth(sender))
        self.assertEqual(result.status_code, 404)

    def test_invalid_message_id(self):
        # type: () -> None
        """
        Reacting to an invalid message id fails
        """
        sender = self.example_email("hamlet")
        result = self.client_put('/api/v1/messages/-1/emoji_reactions/smile',
                                 **self.api_auth(sender))
        self.assertEqual(result.status_code, 404)

    def test_inaccessible_message_id(self):
        # type: () -> None
        """
        Reacting to a inaccessible (for instance, private) message fails
        """
        pm_sender = self.example_email("hamlet")
        pm_recipient = self.example_email("othello")
        reaction_sender = self.example_email("iago")

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "to": pm_recipient},
                                  **self.api_auth(pm_sender))
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        pm_id = content['id']
        result = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                 **self.api_auth(reaction_sender))
        self.assert_json_error(result, "Invalid message(s)")

class ReactionTest(ZulipTestCase):
    def test_add_existing_reaction(self):
        # type: () -> None
        """
        Creating the same reaction twice fails
        """
        pm_sender = self.example_email("hamlet")
        pm_recipient = self.example_email("othello")
        reaction_sender = pm_recipient

        pm = self.client_post("/api/v1/messages", {"type": "private",
                                                   "content": "Test message",
                                                   "to": pm_recipient},
                              **self.api_auth(pm_sender))
        self.assert_json_success(pm)
        content = ujson.loads(pm.content)

        pm_id = content['id']
        first = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                **self.api_auth(reaction_sender))
        self.assert_json_success(first)
        second = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                 **self.api_auth(reaction_sender))
        self.assert_json_error(second, "Reaction already exists")

    def test_remove_nonexisting_reaction(self):
        # type: () -> None
        """
        Removing a reaction twice fails
        """
        pm_sender = self.example_email("hamlet")
        pm_recipient = self.example_email("othello")
        reaction_sender = pm_recipient

        pm = self.client_post("/api/v1/messages", {"type": "private",
                                                   "content": "Test message",
                                                   "to": pm_recipient},
                              **self.api_auth(pm_sender))
        self.assert_json_success(pm)
        content = ujson.loads(pm.content)
        pm_id = content['id']
        add = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                              **self.api_auth(reaction_sender))
        self.assert_json_success(add)

        first = self.client_delete('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                   **self.api_auth(reaction_sender))
        self.assert_json_success(first)

        second = self.client_delete('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                    **self.api_auth(reaction_sender))
        self.assert_json_error(second, "Reaction does not exist")


class ReactionEventTest(ZulipTestCase):
    def test_add_event(self):
        # type: () -> None
        """
        Recipients of the message receive the reaction event
        and event contains relevant data
        """
        pm_sender = self.example_user('hamlet')
        pm_recipient = self.example_user('othello')
        reaction_sender = pm_recipient

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "to": pm_recipient.email},
                                  **self.api_auth(pm_sender.email))
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        pm_id = content['id']

        expected_recipient_ids = set([pm_sender.id, pm_recipient.id])

        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                     **self.api_auth(reaction_sender.email))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_user_ids = set(events[0]['users'])

        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['user']['email'], reaction_sender.email)
        self.assertEqual(event['type'], 'reaction')
        self.assertEqual(event['op'], 'add')
        self.assertEqual(event['emoji_name'], 'smile')
        self.assertEqual(event['message_id'], pm_id)

    def test_remove_event(self):
        # type: () -> None
        """
        Recipients of the message receive the reaction event
        and event contains relevant data
        """
        pm_sender = self.example_user('hamlet')
        pm_recipient = self.example_user('othello')
        reaction_sender = pm_recipient

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "to": pm_recipient.email},
                                  **self.api_auth(pm_sender.email))
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        pm_id = content['id']

        expected_recipient_ids = set([pm_sender.id, pm_recipient.id])

        add = self.client_put('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                              **self.api_auth(reaction_sender.email))
        self.assert_json_success(add)

        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_delete('/api/v1/messages/%s/emoji_reactions/smile' % (pm_id,),
                                        **self.api_auth(reaction_sender.email))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_user_ids = set(events[0]['users'])

        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['user']['email'], reaction_sender.email)
        self.assertEqual(event['type'], 'reaction')
        self.assertEqual(event['op'], 'remove')
        self.assertEqual(event['emoji_name'], 'smile')
        self.assertEqual(event['message_id'], pm_id)
