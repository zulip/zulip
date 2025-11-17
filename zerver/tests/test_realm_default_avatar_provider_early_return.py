from zerver.actions.realm_settings import do_change_realm_default_avatar_provider
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm


class RealmDefaultAvatarProviderEarlyReturnTest(ZulipTestCase):
    def test_early_return_no_change(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")

        current = realm.default_avatar_provider

        do_change_realm_default_avatar_provider(
            realm, current, acting_user=self.example_user("iago")
        )

        realm.refresh_from_db()
        self.assertEqual(realm.default_avatar_provider, current)
