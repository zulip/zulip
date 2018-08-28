# -*- coding: utf-8 -*-

from zerver.models import Realm, UserProfile
from zerver.lib.onboarding import create_if_missing_realm_internal_bots
from zerver.lib.test_classes import (
    ZulipTestCase,
)

class TestRealmInternalBotCreation(ZulipTestCase):
    def test_create_if_missing_realm_internal_bots(self) -> None:
        realm_internal_bots_dict = [{'var_name': 'TEST_BOT',
                                     'email_template': 'test-bot@%s',
                                     'name': 'Test Bot'}]

        def check_test_bot_exists() -> bool:
            all_realms_count = Realm.objects.count()
            all_test_bot_count = UserProfile.objects.filter(
                email='test-bot@zulip.com'
            ).count()
            return all_realms_count == all_test_bot_count

        self.assertFalse(check_test_bot_exists())
        with self.settings(REALM_INTERNAL_BOTS=realm_internal_bots_dict):
            create_if_missing_realm_internal_bots()
        self.assertTrue(check_test_bot_exists())
