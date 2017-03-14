from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict

from zerver.lib.initial_password import initial_password
from zerver.lib.sessions import get_session_dict_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_user_profile_by_email

class ChangeSettingsTest(ZulipTestCase):

    def check_well_formed_change_settings_response(self, result):
        # type: (Dict[str, Any]) -> None
        self.assertIn("full_name", result)

    # DEPRECATED, to be deleted after all uses of check_for_toggle_param
    # are converted into check_for_toggle_param_patch.
    def check_for_toggle_param(self, pattern, param):
        # type: (str, str) -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        json_result = self.client_post(pattern,
                                       {param: ujson.dumps(True)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_post(pattern,
                                       {param: ujson.dumps(False)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), False)

    # TODO: requires method consolidation, right now, there's no alternative
    # for check_for_toggle_param for PATCH.
    def check_for_toggle_param_patch(self, pattern, param):
        # type: (str, str) -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        json_result = self.client_patch(pattern,
                                        {param: ujson.dumps(True)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_patch(pattern,
                                        {param: ujson.dumps(False)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), False)

    def test_successful_change_settings(self):
        # type: () -> None
        """
        A call to /json/settings/change with valid parameters changes the user's
        settings correctly and returns correct values.
        """
        self.login("hamlet@zulip.com")
        json_result = self.client_post(
            "/json/settings/change",
            dict(
                full_name='Foo Bar',
                old_password=initial_password('hamlet@zulip.com'),
                new_password='foobar1',
                confirm_password='foobar1',
            ))
        self.assert_json_success(json_result)
        result = ujson.loads(json_result.content)
        self.check_well_formed_change_settings_response(result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                         full_name, "Foo Bar")
        self.client_post('/accounts/logout/')
        self.login("hamlet@zulip.com", "foobar1")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_illegal_name_changes(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        user = get_user_profile_by_email(email)
        full_name = user.full_name

        with self.settings(NAME_CHANGES_DISABLED=True):
            json_result = self.client_post("/json/settings/change",
                                           dict(full_name='Foo Bar'))

        # We actually fail silently here, since this only happens if
        # somebody is trying to game our API, and there's no reason to
        # give them the courtesy of an error reason.
        self.assert_json_success(json_result)

        user = get_user_profile_by_email(email)
        self.assertEqual(user.full_name, full_name)

        # Now try a too-long name
        json_result = self.client_post("/json/settings/change",
                                       dict(full_name='x' * 1000))
        self.assert_json_error(json_result, 'Name too long!')

    def test_illegal_characters_in_name_changes(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        # Now try a name with invalid characters
        json_result = self.client_post("/json/settings/change",
                                       dict(full_name='Opheli*'))
        self.assert_json_error(json_result, 'Invalid characters in name!')

    # This is basically a don't-explode test.
    def test_notify_settings(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_desktop_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_stream_desktop_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_stream_sounds")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_sounds")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_offline_email_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_offline_push_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_online_push_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_digest_emails")
        self.check_for_toggle_param_patch("/json/settings/notifications", "pm_content_in_desktop_notifications")

    def test_ui_settings(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/ui", "autoscroll_forever")
        self.check_for_toggle_param_patch("/json/settings/ui", "default_desktop_notifications")

    def test_toggling_left_side_userlist(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/display", "left_side_userlist")

    def test_toggling_emoji_alt_code(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/display", "emoji_alt_code")

    def test_time_setting(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/display", "twenty_four_hour_time")

    def test_enter_sends_setting(self):
        # type: () -> None
        self.check_for_toggle_param('/json/users/me/enter-sends', "enter_sends")

    def test_mismatching_passwords(self):
        # type: () -> None
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.client_post(
            "/json/settings/change",
            dict(
                new_password="mismatched_password",
                confirm_password="not_the_same",
            ))
        self.assert_json_error(result,
                               "New password must match confirmation password!")

    def test_wrong_old_password(self):
        # type: () -> None
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.client_post(
            "/json/settings/change",
            dict(
                old_password='bad_password',
                new_password="ignored",
                confirm_password="ignored",
            ))
        self.assert_json_error(result, "Wrong password!")

    def test_changing_nothing_returns_error(self):
        # type: () -> None
        """
        We need to supply at least one non-empty parameter
        to this API, or it should fail.  (Eventually, we should
        probably use a patch interface for these changes.)
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/settings/change",
                                  dict(old_password='ignored',))
        self.assert_json_error(result, "No new data supplied")

    def test_change_default_language(self):
        # type: () -> None
        """
        Test changing the default language of the user.
        """
        email = "hamlet@zulip.com"
        self.login(email)
        german = "de"
        data = dict(default_language=ujson.dumps(german))
        result = self.client_patch("/json/settings/display", data)
        self.assert_json_success(result)
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.default_language, german)

        # Test to make sure invalid languages are not accepted
        # and saved in the db.
        invalid_lang = "invalid_lang"
        data = dict(default_language=ujson.dumps(invalid_lang))
        result = self.client_patch("/json/settings/display", data)
        self.assert_json_error(result, "Invalid language '%s'" % (invalid_lang,))
        user_profile = get_user_profile_by_email(email)
        self.assertNotEqual(user_profile.default_language, invalid_lang)

class UserChangesTest(ZulipTestCase):
    def test_update_api_key(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        user = get_user_profile_by_email(email)
        old_api_key = user.api_key
        result = self.client_post('/json/users/me/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = ujson.loads(result.content)['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        user = get_user_profile_by_email(email)
        self.assertEqual(new_api_key, user.api_key)
