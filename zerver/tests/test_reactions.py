# -*- coding: utf-8 -*-
from __future__ import absolute_import

import ujson
from typing import Any, Dict, List
from six import string_types

from zerver.lib.test_helpers import tornado_redirected_to_list, get_display_recipient
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user_profile_by_email

class ReactionEmojiTest(ZulipTestCase):
    def test_missing_emoji(self):
        # type: () -> None
        """
        Sending reaction without emoji fails
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/reactions', {'message_id': 1},
                                  **self.api_auth(sender))
        self.assert_json_error(result, "Missing 'emoji' argument")

    def test_empty_emoji(self):
        # type: () -> None
        """
        Sending empty emoji fails
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/reactions', {'message_id': 1, 'emoji': ''},
                                  **self.api_auth(sender))
        self.assert_json_error(result, "Emoji name can't be empty")

    def test_invalid_emoji(self):
        # type: () -> None
        """
        Sending invalid emoji fails
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/reactions', {'message_id': 1, 'emoji': 'foo'},
                                  **self.api_auth(sender))
        self.assert_json_error(result, 'Emoji does not exist')

    def test_invalid_realm_emoji(self):
        # type: () -> None
        """
        Sending invalid realm emoji fails
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/reactions', {'message_id': 1, 'emoji': 'foo'},
                                  **self.api_auth(sender))
        self.assert_json_error(result, 'Emoji does not exist')

    def test_valid_emoji(self):
        # type: () -> None
        """
        Reacting with valid emoji succeeds
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/reactions', {'message_id': 1, 'emoji': 'smile'},
                                  **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

    def test_valid_realm_emoji(self):
        # type: () -> None
        """
        Reacting with valid realm emoji succeeds
        """
        sender = 'hamlet@zulip.com'
        emoji_name = 'my_emoji'
        emoji_data = {'name': emoji_name, 'url': 'https://example.com/my_emoji'}
        result = self.client_put('/json/realm/emoji', info=emoji_data,
                                 **self.api_auth(sender))
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)

        result = self.client_get("/json/realm/emoji", **self.api_auth(sender))
        content = ujson.loads(result.content)
        self.assert_json_success(result)
        self.assertTrue(emoji_name in content["emoji"])

        result = self.client_post('/api/v1/reactions', {'message_id': 1, 'emoji': emoji_name},
                                  **self.api_auth(sender))
        self.assert_json_success(result)

class ReactionMessageIDTest(ZulipTestCase):
    def test_missing_message_id(self):
        # type: () -> None
        """
        Reacting without a message_id fails
        """
        sender = 'hamlet@zulip.com'
        result = self.client_post('/api/v1/reactions', {'emoji': 'smile'},
                                  **self.api_auth(sender))
        self.assert_json_error(result, "Missing 'message_id' argument")

    def test_invalid_message_id(self):
        # type: () -> None
        """
        Reacting to an invalid message id fails
        """
        sender = 'hamlet@zulip.com'
        message_id = -1
        result = self.client_post('/api/v1/reactions', {'message_id': message_id, 'emoji': 'smile'},
                                  **self.api_auth(sender))
        self.assert_json_error(result, "Bad value for 'message_id': " + str(message_id))

    def test_inaccessible_message_id(self):
        # type: () -> None
        """
        Reacting to a inaccessible (for instance, private) message fails
        """
        pm_sender = 'hamlet@zulip.com'
        pm_recipient = 'othello@zulip.com'
        reaction_sender = 'iago@zulip.com'

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "to": pm_recipient},
                                  **self.api_auth(pm_sender))
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        pm_id = content['id']
        result = self.client_post('/api/v1/reactions', {'message_id': pm_id, 'emoji': 'smile'},
                                  **self.api_auth(reaction_sender))
        self.assert_json_error(result, "Invalid message(s)")

class ReactionEventTest(ZulipTestCase):
    def test_event(self):
        # type: () -> None
        """
        Recipients of the message receive the reaction event
        and event contains relevant data
        """
        pm_sender = 'hamlet@zulip.com'
        pm_recipient = 'othello@zulip.com'
        reaction_sender = pm_recipient

        result = self.client_post("/api/v1/messages", {"type": "private",
                                                       "content": "Test message",
                                                       "to": pm_recipient},
                                  **self.api_auth(pm_sender))
        self.assert_json_success(result)
        content = ujson.loads(result.content)
        pm_id = content['id']

        expected_recipient_emails = set([pm_sender, pm_recipient])
        expected_recipient_ids = set([get_user_profile_by_email(email).id for email in expected_recipient_emails])

        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_post('/api/v1/reactions', {'message_id': pm_id,
                                                            'emoji': 'smile'},
                                      **self.api_auth(reaction_sender))
        self.assert_json_success(result)
        self.assertEqual(len(events), 1)

        event = events[0]['event']
        event_user_ids = set(events[0]['users'])

        self.assertEqual(expected_recipient_ids, event_user_ids)
        self.assertEqual(event['user']['email'], reaction_sender)
        self.assertEqual(event['type'], 'reaction')
        self.assertEqual(event['emoji_name'], 'smile')
        self.assertEqual(event['message_id'], pm_id)
