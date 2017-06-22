# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
from typing import Any, Union, Mapping, Callable

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.actions import do_change_is_admin, do_deactivate_user
from zerver.models import (
    get_slash_commands_by_realm,
    get_slash_command_user_by_realm,
    UserProfile,
    get_realm_by_email_domain,
    get_user_profile_by_email,
    Recipient,
)

class SlashCommandTests(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        self.user = self.example_user('hamlet')
        self.login(self.user.email)

        bot_info1 = {
            'full_name': 'Sample user1',
            'short_name': 'user1',
            'bot_type': UserProfile.SLASH_COMMANDS,
        }
        result = self.client_post("/json/bots", bot_info1)
        self.assert_json_success(result)

        bot_info2 = {
            'full_name': 'Sample user2',
            'short_name': 'user2',
            'bot_type': UserProfile.SLASH_COMMANDS,
        }
        result = self.client_post("/json/bots", bot_info2)
        self.assert_json_success(result)
        bot_user = get_user_profile_by_email('user2-command@zulip.testserver')
        do_deactivate_user(bot_user)

    def test_get_slash_commands_by_realm(self):
        # type: () -> None
        realm = get_realm_by_email_domain("zulip.com")

        slash_commands = get_slash_commands_by_realm(realm)
        self.assertIn(u'user1', slash_commands)
        self.assertIn(u'user2', slash_commands)

        slash_commands = get_slash_commands_by_realm(realm, is_active=True)
        self.assertIn(u'user1', slash_commands)
        self.assertNotIn(u'user2', slash_commands)

    def test_get_slash_command_user_by_realm(self):
        # type: () -> None
        bot_user = get_slash_command_user_by_realm(get_realm_by_email_domain("zulip.com"), 'user1')
        self.assertEqual(bot_user.email, 'user1-command@zulip.testserver')
        self.assertEqual(bot_user.full_name, 'Sample user1')
        self.assertEqual(bot_user.is_active, True)
        self.assertEqual(bot_user.bot_type, UserProfile.SLASH_COMMANDS)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_slash_command_event_flow(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        content = "We have an /user1 day today!"
        recipient = 'Denmark'
        trigger = "slash command"
        message_type = Recipient._type_names[Recipient.STREAM]

        def check_values_passed(queue_name, trigger_event, x):
            # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
            self.assertEqual(queue_name, "slash_commands")
            self.assertEqual(trigger_event['command'], "user1")
            self.assertEqual(trigger_event['trigger'], trigger)
            self.assertEqual(trigger_event["message"]["content"], content)
            self.assertEqual(trigger_event["message"]["display_recipient"], recipient)
            self.assertEqual(trigger_event["message"]["sender_email"], self.user.email)
            self.assertEqual(trigger_event["message"]["type"], message_type)

        mock_queue_json_publish.side_effect = check_values_passed

        self.send_message(
            self.user.email,
            'Denmark',
            Recipient.STREAM,
            content)
        self.assertTrue(mock_queue_json_publish.called)
