import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict
from unittest import mock

import orjson
from django.http import HttpRequest
from django.test import override_settings

from zerver.lib.initial_password import initial_password
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file, ratelimit_rule
from zerver.lib.users import get_all_api_keys
from zerver.models import (
    Draft,
    NotificationTriggers,
    ScheduledMessageNotificationEmail,
    UserProfile,
    get_user_profile_by_api_key,
)

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class ChangeSettingsTest(ZulipTestCase):
    # TODO: requires method consolidation, right now, there's no alternative
    # for check_for_toggle_param for PATCH.
    def check_for_toggle_param_patch(self, pattern: str, param: str) -> None:
        self.login("hamlet")
        user_profile = self.example_user("hamlet")
        json_result = self.client_patch(pattern, {param: orjson.dumps(True).decode()})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = self.example_user("hamlet")
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_patch(pattern, {param: orjson.dumps(False).decode()})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = self.example_user("hamlet")
        self.assertEqual(getattr(user_profile, param), False)

    def test_successful_change_settings(self) -> None:
        """
        A call to /json/settings with valid parameters changes the user's
        settings correctly and returns correct values.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        json_result = self.client_patch(
            "/json/settings",
            dict(
                full_name="Foo Bar",
                old_password=initial_password(user.delivery_email),
                new_password="foobar1",
            ),
        )
        self.assert_json_success(json_result)

        user.refresh_from_db()
        self.assertEqual(user.full_name, "Foo Bar")
        self.logout()

        # This is one of the few places we log in directly
        # with Django's client (to test the password change
        # with as few moving parts as possible).
        request = HttpRequest()
        request.session = self.client.session
        self.assertTrue(
            self.client.login(
                request=request,
                username=user.delivery_email,
                password="foobar1",
                realm=user.realm,
            ),
        )
        self.assert_logged_in_user_id(user.id)

    def test_password_change_check_strength(self) -> None:
        self.login("hamlet")
        with self.settings(PASSWORD_MIN_LENGTH=3, PASSWORD_MIN_GUESSES=1000):
            json_result = self.client_patch(
                "/json/settings",
                dict(
                    full_name="Foo Bar",
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="easy",
                ),
            )
            self.assert_json_error(json_result, "New password is too weak!")

            json_result = self.client_patch(
                "/json/settings",
                dict(
                    full_name="Foo Bar",
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="f657gdGGk9",
                ),
            )
            self.assert_json_success(json_result)

    def test_illegal_name_changes(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        full_name = user.full_name

        with self.settings(NAME_CHANGES_DISABLED=True):
            json_result = self.client_patch("/json/settings", dict(full_name="Foo Bar"))

        # We actually fail silently here, since this only happens if
        # somebody is trying to game our API, and there's no reason to
        # give them the courtesy of an error reason.
        self.assert_json_success(json_result)

        user = self.example_user("hamlet")
        self.assertEqual(user.full_name, full_name)

        # Now try a too-long name
        json_result = self.client_patch("/json/settings", dict(full_name="x" * 1000))
        self.assert_json_error(json_result, "Name too long!")

        # Now try too-short names
        short_names = ["", "x"]
        for name in short_names:
            json_result = self.client_patch("/json/settings", dict(full_name=name))
            self.assert_json_error(json_result, "Name too short!")

    def test_illegal_characters_in_name_changes(self) -> None:
        self.login("hamlet")

        # Now try a name with invalid characters
        json_result = self.client_patch("/json/settings", dict(full_name="Opheli*"))
        self.assert_json_error(json_result, "Invalid characters in name!")

    def test_change_email_to_disposable_email(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        realm = hamlet.realm
        realm.disallow_disposable_email_addresses = True
        realm.emails_restricted_to_domains = False
        realm.save()

        json_result = self.client_patch("/json/settings", dict(email="hamlet@mailnator.com"))
        self.assert_json_error(json_result, "Please use your real email address.")

    def test_change_email_batching_period(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.login_user(hamlet)

        # Default is two minutes
        self.assertEqual(hamlet.email_notifications_batching_period_seconds, 120)

        result = self.client_patch(
            "/json/settings", {"email_notifications_batching_period_seconds": -1}
        )
        self.assert_json_error(result, "Invalid email batching period: -1 seconds")

        result = self.client_patch(
            "/json/settings", {"email_notifications_batching_period_seconds": 7 * 24 * 60 * 60 + 10}
        )
        self.assert_json_error(result, "Invalid email batching period: 604810 seconds")

        result = self.client_patch(
            "/json/settings", {"email_notifications_batching_period_seconds": 5 * 60}
        )
        self.assert_json_success(result)
        hamlet = self.example_user("hamlet")
        self.assertEqual(hamlet.email_notifications_batching_period_seconds, 300)

        # Test that timestamps get updated for existing ScheduledMessageNotificationEmail rows
        hamlet_msg_id1 = self.send_stream_message(sender=cordelia, stream_name="Verona")
        hamlet_msg_id2 = self.send_stream_message(sender=cordelia, stream_name="Verona")
        othello_msg_id1 = self.send_stream_message(sender=cordelia, stream_name="Verona")

        def create_entry(user_profile_id: int, message_id: int, timestamp: datetime) -> int:
            # The above messages don't actually mention anyone. We just fill up the trigger
            # because we need to.
            entry = ScheduledMessageNotificationEmail.objects.create(
                user_profile_id=user_profile_id,
                message_id=message_id,
                trigger=NotificationTriggers.MENTION,
                scheduled_timestamp=timestamp,
            )
            return entry.id

        def get_datetime_object(minutes: int) -> datetime:
            return datetime(
                year=2021, month=8, day=10, hour=10, minute=minutes, second=15, tzinfo=timezone.utc
            )

        hamlet_timestamp = get_datetime_object(10)
        othello_timestamp = get_datetime_object(20)

        hamlet_entry1_id = create_entry(hamlet.id, hamlet_msg_id1, hamlet_timestamp)
        hamlet_entry2_id = create_entry(hamlet.id, hamlet_msg_id2, hamlet_timestamp)
        othello_entry1_id = create_entry(othello.id, othello_msg_id1, othello_timestamp)

        # Update Hamlet's setting from 300 seconds (5 minutes) to 600 seconds (10 minutes)
        self.assertEqual(hamlet.email_notifications_batching_period_seconds, 300)
        result = self.client_patch(
            "/json/settings", {"email_notifications_batching_period_seconds": 10 * 60}
        )
        self.assert_json_success(result)
        hamlet = self.example_user("hamlet")
        self.assertEqual(hamlet.email_notifications_batching_period_seconds, 10 * 60)

        def check_scheduled_timestamp(entry_id: int, expected_timestamp: datetime) -> None:
            entry = ScheduledMessageNotificationEmail.objects.get(id=entry_id)
            self.assertEqual(entry.scheduled_timestamp, expected_timestamp)

        # For Hamlet, the new scheduled timestamp should have been updated
        expected_hamlet_timestamp = get_datetime_object(15)
        check_scheduled_timestamp(hamlet_entry1_id, expected_hamlet_timestamp)
        check_scheduled_timestamp(hamlet_entry2_id, expected_hamlet_timestamp)

        # Nothing should have changed for Othello
        check_scheduled_timestamp(othello_entry1_id, othello_timestamp)

    def test_toggling_boolean_user_settings(self) -> None:
        """Test updating each boolean setting in UserProfile property_types"""
        boolean_settings = (
            s for s in UserProfile.property_types if UserProfile.property_types[s] is bool
        )
        for user_setting in boolean_settings:
            self.check_for_toggle_param_patch("/json/settings", user_setting)

    def test_wrong_old_password(self) -> None:
        self.login("hamlet")
        result = self.client_patch(
            "/json/settings",
            dict(
                old_password="bad_password",
                new_password="ignored",
            ),
        )
        self.assert_json_error(result, "Wrong password!")

    @override_settings(RATE_LIMITING_AUTHENTICATE=True)
    @ratelimit_rule(10, 2, domain="authenticate_by_username")
    def test_wrong_old_password_rate_limiter(self) -> None:
        self.login("hamlet")
        start_time = time.time()
        with mock.patch("time.time", return_value=start_time):
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password="bad_password",
                    new_password="ignored",
                ),
            )
            self.assert_json_error(result, "Wrong password!")
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password="bad_password",
                    new_password="ignored",
                ),
            )
            self.assert_json_error(result, "Wrong password!")

            # We're over the limit, so we'll get blocked even with the correct password.
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ),
            )
            self.assert_json_error(
                result, "You're making too many attempts! Try again in 10 seconds."
            )

        # After time passes, we should be able to succeed if we give the correct password.
        with mock.patch("time.time", return_value=start_time + 11):
            json_result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="foobar1",
                ),
            )
            self.assert_json_success(json_result)

    @override_settings(
        AUTHENTICATION_BACKENDS=(
            "zproject.backends.ZulipLDAPAuthBackend",
            "zproject.backends.EmailAuthBackend",
            "zproject.backends.ZulipDummyBackend",
        )
    )
    def test_change_password_ldap_backend(self) -> None:
        self.init_default_ldap_database()
        ldap_user_attr_map = {"full_name": "cn", "short_name": "sn"}

        self.login("hamlet")

        with self.settings(
            LDAP_APPEND_DOMAIN="zulip.com", AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map
        ):
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ),
            )
            self.assert_json_error(result, "Your Zulip password is managed in LDAP")

            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=self.ldap_password("hamlet"),  # hamlet's password in LDAP
                    new_password="ignored",
                ),
            )
            self.assert_json_error(result, "Your Zulip password is managed in LDAP")

        with self.settings(
            LDAP_APPEND_DOMAIN="example.com", AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map
        ), self.assertLogs("zulip.ldap", "DEBUG") as debug_log:
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ),
            )
            self.assert_json_success(result)
            self.assertEqual(
                debug_log.output,
                [
                    "DEBUG:zulip.ldap:ZulipLDAPAuthBackend: Email hamlet@zulip.com does not match LDAP domain example.com."
                ],
            )

        with self.settings(LDAP_APPEND_DOMAIN=None, AUTH_LDAP_USER_ATTR_MAP=ldap_user_attr_map):
            result = self.client_patch(
                "/json/settings",
                dict(
                    old_password=initial_password(self.example_email("hamlet")),
                    new_password="ignored",
                ),
            )
            self.assert_json_error(result, "Your Zulip password is managed in LDAP")

    def do_test_change_user_setting(self, setting_name: str) -> None:
        test_changes: Dict[str, Any] = dict(
            default_language="de",
            default_view="all_messages",
            emojiset="google",
            timezone="America/Denver",
            demote_inactive_streams=2,
            web_mark_read_on_scroll_policy=2,
            user_list_style=2,
            web_stream_unreads_count_display_policy=2,
            color_scheme=2,
            email_notifications_batching_period_seconds=100,
            notification_sound="ding",
            desktop_icon_count_display=2,
            email_address_visibility=3,
            realm_name_in_email_notifications_policy=2,
        )

        self.login("hamlet")
        test_value = test_changes.get(setting_name)
        # Error if a setting in UserProfile.property_types does not have test values
        if test_value is None:
            raise AssertionError(f"No test created for {setting_name}")

        if setting_name not in [
            "demote_inactive_streams",
            "user_list_style",
            "color_scheme",
            "web_mark_read_on_scroll_policy",
            "web_stream_unreads_count_display_policy",
        ]:
            data = {setting_name: test_value}
        else:
            data = {setting_name: orjson.dumps(test_value).decode()}

        result = self.client_patch("/json/settings", data)
        self.assert_json_success(result)
        user_profile = self.example_user("hamlet")
        self.assertEqual(getattr(user_profile, setting_name), test_value)

    def test_change_user_setting(self) -> None:
        """Test updating each non-boolean setting in UserProfile property_types"""
        user_settings = (
            s for s in UserProfile.property_types if UserProfile.property_types[s] is not bool
        )
        for setting in user_settings:
            self.do_test_change_user_setting(setting)
        self.do_test_change_user_setting("timezone")

    def test_invalid_setting_value(self) -> None:
        invalid_values_dict = dict(
            default_language="invalid_de",
            default_view="invalid_view",
            emojiset="apple",
            timezone="invalid_US/Mountain",
            demote_inactive_streams=10,
            web_mark_read_on_scroll_policy=10,
            user_list_style=10,
            web_stream_unreads_count_display_policy=10,
            color_scheme=10,
            notification_sound="invalid_sound",
            desktop_icon_count_display=10,
        )

        self.login("hamlet")
        for setting_name in invalid_values_dict:
            invalid_value = invalid_values_dict.get(setting_name)
            if isinstance(invalid_value, str):
                invalid_value = orjson.dumps(invalid_value).decode()

            req = {setting_name: invalid_value}
            result = self.client_patch("/json/settings", req)

            expected_error_msg = f"Invalid {setting_name}"
            if setting_name == "notification_sound":
                expected_error_msg = f"Invalid notification sound '{invalid_value}'"
            elif setting_name == "timezone":
                expected_error_msg = "timezone is not a recognized time zone"
            self.assert_json_error(result, expected_error_msg)
            hamlet = self.example_user("hamlet")
            self.assertNotEqual(getattr(hamlet, setting_name), invalid_value)

    def do_change_emojiset(self, emojiset: str) -> "TestHttpResponse":
        self.login("hamlet")
        data = {"emojiset": emojiset}
        result = self.client_patch("/json/settings", data)
        return result

    def test_emojiset(self) -> None:
        """Test banned emoji sets are not accepted."""
        banned_emojisets = ["apple", "emojione"]
        valid_emojisets = ["google", "google-blob", "text", "twitter"]

        for emojiset in banned_emojisets:
            result = self.do_change_emojiset(emojiset)
            self.assert_json_error(result, "Invalid emojiset")

        for emojiset in valid_emojisets:
            result = self.do_change_emojiset(emojiset)
            self.assert_json_success(result)

    def test_avatar_changes_disabled(self) -> None:
        self.login("hamlet")

        with self.settings(AVATAR_CHANGES_DISABLED=True):
            result = self.client_delete("/json/users/me/avatar")
            self.assert_json_error(result, "Avatar changes are disabled in this organization.", 400)

        with self.settings(AVATAR_CHANGES_DISABLED=True):
            with get_test_image_file("img.png") as fp1:
                result = self.client_post("/json/users/me/avatar", {"f1": fp1})
            self.assert_json_error(result, "Avatar changes are disabled in this organization.", 400)

    def test_invalid_setting_name(self) -> None:
        self.login("hamlet")

        # Now try an invalid setting name
        result = self.client_patch("/json/settings", dict(invalid_setting="value"))
        self.assert_json_success(result, ignored_parameters=["invalid_setting"])

    def test_changing_setting_using_display_setting_endpoint(self) -> None:
        """
        This test is just for adding coverage for `/settings/display` endpoint which is
        now deprecated.
        """
        self.login("hamlet")

        result = self.client_patch(
            "/json/settings/display", dict(color_scheme=UserProfile.COLOR_SCHEME_NIGHT)
        )
        self.assert_json_success(result)
        hamlet = self.example_user("hamlet")
        self.assertEqual(hamlet.color_scheme, UserProfile.COLOR_SCHEME_NIGHT)

    def test_changing_setting_using_notification_setting_endpoint(self) -> None:
        """
        This test is just for adding coverage for `/settings/notifications` endpoint which is
        now deprecated.
        """
        self.login("hamlet")

        result = self.client_patch(
            "/json/settings/notifications",
            dict(enable_stream_desktop_notifications=orjson.dumps(True).decode()),
        )
        self.assert_json_success(result)
        hamlet = self.example_user("hamlet")
        self.assertEqual(hamlet.enable_stream_desktop_notifications, True)


class UserChangesTest(ZulipTestCase):
    def test_update_api_key(self) -> None:
        user = self.example_user("hamlet")
        email = user.email

        self.login_user(user)
        old_api_keys = get_all_api_keys(user)
        # Ensure the old API keys are in the authentication cache, so
        # that the below logic can test whether we have a cache-flushing bug.
        for api_key in old_api_keys:
            self.assertEqual(get_user_profile_by_api_key(api_key).email, email)

        # First verify this endpoint is not registered in the /json/... path
        # to prevent access with only a session.
        result = self.client_post("/json/users/me/api_key/regenerate")
        self.assertEqual(result.status_code, 404)

        # A logged-in session doesn't allow access to an /api/v1/ endpoint
        # of course.
        result = self.client_post("/api/v1/users/me/api_key/regenerate")
        self.assertEqual(result.status_code, 401)

        result = self.api_post(user, "/api/v1/users/me/api_key/regenerate")
        new_api_key = self.assert_json_success(result)["api_key"]
        self.assertNotIn(new_api_key, old_api_keys)
        user = self.example_user("hamlet")
        current_api_keys = get_all_api_keys(user)
        self.assertIn(new_api_key, current_api_keys)

        for api_key in old_api_keys:
            with self.assertRaises(UserProfile.DoesNotExist):
                get_user_profile_by_api_key(api_key)

        for api_key in current_api_keys:
            self.assertEqual(get_user_profile_by_api_key(api_key).email, email)


class UserDraftSettingsTests(ZulipTestCase):
    def test_enable_drafts_syncing(self) -> None:
        hamlet = self.example_user("hamlet")
        hamlet.enable_drafts_synchronization = False
        hamlet.save()
        payload = {"enable_drafts_synchronization": orjson.dumps(True).decode()}
        resp = self.api_patch(hamlet, "/api/v1/settings", payload)
        self.assert_json_success(resp)
        hamlet = self.example_user("hamlet")
        self.assertTrue(hamlet.enable_drafts_synchronization)

    def test_disable_drafts_syncing(self) -> None:
        aaron = self.example_user("aaron")
        self.assertTrue(aaron.enable_drafts_synchronization)

        initial_count = Draft.objects.count()

        # Create some drafts. These should be deleted once aaron disables
        # syncing drafts.
        visible_stream_id = self.get_stream_id(self.get_streams(aaron)[0])
        draft_dicts = [
            {
                "type": "stream",
                "to": [visible_stream_id],
                "topic": "thinking out loud",
                "content": "What if pigs really could fly?",
                "timestamp": 15954790199,
            },
            {
                "type": "private",
                "to": [],
                "topic": "",
                "content": "What if made it possible to sync drafts in Zulip?",
                "timestamp": 1595479020,
            },
        ]
        payload = {"drafts": orjson.dumps(draft_dicts).decode()}
        resp = self.api_post(aaron, "/api/v1/drafts", payload)
        self.assert_json_success(resp)
        self.assertEqual(Draft.objects.count() - initial_count, 2)

        payload = {"enable_drafts_synchronization": orjson.dumps(False).decode()}
        resp = self.api_patch(aaron, "/api/v1/settings", payload)
        self.assert_json_success(resp)
        aaron = self.example_user("aaron")
        self.assertFalse(aaron.enable_drafts_synchronization)
        self.assertEqual(Draft.objects.count() - initial_count, 0)
