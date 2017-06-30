# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.actions import do_change_is_admin, do_deactivate_user
from zerver.models import (
    get_slash_commands_by_realm,
    get_slash_command_user_by_realm,
    UserProfile,
    get_realm_by_email_domain,
    get_user_profile_by_email
)

class SlashCommandTests(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        user = self.example_user('hamlet')
        self.login(user.email)

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
