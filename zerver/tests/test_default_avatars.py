"""
Tests for realm default avatar provider settings.

Avatar generation endpoint tests are in test_upload.py.
"""

from django.test import override_settings

from zerver.actions.create_realm import do_create_realm
from zerver.actions.users import change_user_is_active
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm
from zerver.models.users import get_user_profile_by_id


class RealmDefaultAvatarProviderTest(ZulipTestCase):
    """Test realm-wide default avatar provider settings."""

    def test_default_avatar_provider_values(self) -> None:
        """Test that default avatar provider accepts valid values."""
        self.login("iago")
        realm = get_realm("zulip")

        # Test Jdenticon (1)
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 1},
        )
        self.assert_json_success(result)
        realm = get_realm("zulip")
        self.assertEqual(realm.default_avatar_provider, 1)

        # Test Gravatar (2)
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 2},
        )
        self.assert_json_success(result)
        realm = get_realm("zulip")
        self.assertEqual(realm.default_avatar_provider, 2)

        # Test Silhouettes (3)
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)
        realm = get_realm("zulip")
        self.assertEqual(realm.default_avatar_provider, 3)

    def test_invalid_avatar_provider_rejected(self) -> None:
        """Test that invalid default_avatar_provider values are rejected."""
        self.login("iago")

        # Test invalid value
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 999},
        )
        self.assert_json_error(result, "Invalid default_avatar_provider 999")

        # Test 0 (invalid)
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 0},
        )
        self.assert_json_error(result, "Invalid default_avatar_provider 0")

    def test_non_admin_cannot_change_avatar_provider(self) -> None:
        """Test that non-admin users cannot change default avatar provider."""
        self.login("hamlet")

        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 2},
        )
        self.assert_json_error(result, "Must be an organization administrator")

    def test_changing_provider_updates_all_users(self) -> None:
        """Test that changing provider updates all users without custom avatars."""
        self.login("iago")

        # Get users without custom avatars
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        # Make sure hamlet and cordelia don't have custom avatars
        hamlet.avatar_source = "G"
        hamlet.save(update_fields=["avatar_source"])
        cordelia.avatar_source = "J"
        cordelia.save(update_fields=["avatar_source"])

        # Othello has a custom avatar (uploaded)
        othello.avatar_source = "U"
        othello.save(update_fields=["avatar_source"])

        initial_hamlet_version = hamlet.avatar_version
        initial_cordelia_version = cordelia.avatar_version
        initial_othello_version = othello.avatar_version

        # Change to Silhouettes
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)

        # Reload users
        hamlet = get_user_profile_by_id(hamlet.id)
        cordelia = get_user_profile_by_id(cordelia.id)
        othello = get_user_profile_by_id(othello.id)

        # Hamlet and Cordelia should be updated to Silhouettes
        self.assertEqual(hamlet.avatar_source, "S")
        self.assertEqual(cordelia.avatar_source, "S")

        # Their avatar_version should be incremented
        self.assertEqual(hamlet.avatar_version, initial_hamlet_version + 1)
        self.assertEqual(cordelia.avatar_version, initial_cordelia_version + 1)

        # Othello should still have custom avatar
        self.assertEqual(othello.avatar_source, "U")
        self.assertEqual(othello.avatar_version, initial_othello_version)

    def test_switching_between_providers(self) -> None:
        """Test switching between different avatar providers."""
        self.login("iago")
        hamlet = self.example_user("hamlet")
        hamlet.avatar_source = "J"
        hamlet.save(update_fields=["avatar_source"])

        # Switch to Gravatar
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 2},
        )
        self.assert_json_success(result)
        hamlet = get_user_profile_by_id(hamlet.id)
        self.assertEqual(hamlet.avatar_source, "G")

        # Switch to Silhouettes
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)
        hamlet = get_user_profile_by_id(hamlet.id)
        self.assertEqual(hamlet.avatar_source, "S")

        # Switch to Jdenticon
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 1},
        )
        self.assert_json_success(result)
        hamlet = get_user_profile_by_id(hamlet.id)
        self.assertEqual(hamlet.avatar_source, "J")

    def test_avatar_version_increments_on_provider_change(self) -> None:
        """Test that avatar_version increments when provider changes."""
        self.login("iago")
        hamlet = self.example_user("hamlet")
        initial_version = hamlet.avatar_version

        # Change provider
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)

        hamlet = get_user_profile_by_id(hamlet.id)
        # Version should increment for cache busting
        self.assertGreater(hamlet.avatar_version, initial_version)

    def test_realm_creation_default_provider(self) -> None:
        """Test that new realms default to Jdenticon."""
        realm = do_create_realm("test-default", "Test Default Realm")
        # Should default to Jdenticon (1)
        self.assertEqual(realm.default_avatar_provider, 1)

    def test_events_sent_on_provider_change(self) -> None:
        """Test that proper events are sent when provider changes."""
        self.login("iago")
        hamlet = self.example_user("hamlet")
        hamlet.avatar_source = "J"
        hamlet.save(update_fields=["avatar_source"])

        # Change provider - events will be sent
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)

        # Verify realm setting changed
        realm = get_realm("zulip")
        self.assertEqual(realm.default_avatar_provider, 3)

        # Verify user was updated
        hamlet = get_user_profile_by_id(hamlet.id)
        self.assertEqual(hamlet.avatar_source, "S")

    @override_settings(AVATAR_CHANGES_DISABLED=True)
    def test_avatar_changes_disabled_setting(self) -> None:
        """Test behavior when avatar changes are disabled."""
        self.login("iago")

        # Admin should still be able to change default provider
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 2},
        )
        # This should succeed since it's a realm-wide setting, not individual avatar upload
        self.assert_json_success(result)

    def test_deactivated_users_not_updated(self) -> None:
        """Test that deactivated users don't get avatar updates."""
        self.login("iago")
        hamlet = self.example_user("hamlet")
        hamlet.avatar_source = "J"
        hamlet.save(update_fields=["avatar_source"])
        change_user_is_active(hamlet, False)

        initial_version = hamlet.avatar_version

        # Change provider
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)

        hamlet = get_user_profile_by_id(hamlet.id)
        # Deactivated user should not be updated
        self.assertEqual(hamlet.avatar_source, "J")
        self.assertEqual(hamlet.avatar_version, initial_version)

    def test_bot_users_updated_with_provider_change(self) -> None:
        """Test that bot users are also updated when provider changes."""
        self.login("iago")
        bot = self.create_test_bot("test-bot", self.example_user("hamlet"))
        bot.avatar_source = "J"
        bot.save(update_fields=["avatar_source"])

        # Re-login as iago (create_test_bot may have changed the session)
        self.login("iago")

        # Change provider
        result = self.client_patch(
            "/json/realm",
            {"default_avatar_provider": 3},
        )
        self.assert_json_success(result)

        bot = get_user_profile_by_id(bot.id)
        # Bots should be updated too
        self.assertEqual(bot.avatar_source, "S")
