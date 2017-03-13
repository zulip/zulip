from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict, List, Text

from zerver.lib.actions import \
    do_change_is_admin, do_set_realm_name, do_deactivate_realm, do_set_name_changes_disabled

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import tornado_redirected_to_list
from zerver.models import get_realm, get_user_profile_by_email, Realm


class RealmTest(ZulipTestCase):
    def assert_user_profile_cache_gets_new_name(self, email, new_realm_name):
        # type: (Text, Text) -> None
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.realm.name, new_realm_name)

    def test_do_set_realm_name_caching(self):
        # type: () -> None
        """The main complicated thing about setting realm names is fighting the
        cache, and we start by populating the cache for Hamlet, and we end
        by checking the cache to ensure that the new value is there."""
        get_user_profile_by_email('hamlet@zulip.com')
        realm = get_realm('zulip')
        new_name = 'Zed You Elle Eye Pea'
        do_set_realm_name(realm, new_name)
        self.assertEqual(get_realm(realm.string_id).name, new_name)
        self.assert_user_profile_cache_gets_new_name('hamlet@zulip.com', new_name)

    def test_do_set_realm_name_events(self):
        # type: () -> None
        realm = get_realm('zulip')
        new_name = 'Puliz'
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            do_set_realm_name(realm, new_name)
        event = events[0]['event']
        self.assertEqual(event, dict(
            type = 'realm',
            op = 'update',
            property = 'name',
            value = new_name,
        ))

    def test_update_realm_api(self):
        # type: () -> None
        new_name = 'Zulip: Worldwide Exporter of APIs'

        email = 'cordelia@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, True)

        def set_up_db(attr, value):
            # type: (str, Any) -> None
            realm = get_realm('zulip')
            setattr(realm, attr, value)
            realm.save()

        def update_with_api(**kwarg):
            # type: (**Any) -> Realm
            params = {k: ujson.dumps(v) for k, v in kwarg.items()}
            result = self.client_patch('/json/realm', params)
            self.assert_json_success(result)
            return get_realm('zulip') # refresh data

        # name
        realm = update_with_api(name=new_name)
        self.assertEqual(realm.name, new_name)

        # restricted
        set_up_db('restricted_to_domain', False)
        realm = update_with_api(restricted_to_domain=True)
        self.assertEqual(realm.restricted_to_domain, True)
        realm = update_with_api(restricted_to_domain=False)
        self.assertEqual(realm.restricted_to_domain, False)

        # invite_required
        set_up_db('invite_required', False)
        realm = update_with_api(invite_required=True)
        self.assertEqual(realm.invite_required, True)
        realm = update_with_api(invite_required=False)
        self.assertEqual(realm.invite_required, False)

        # invite_by_admins_only
        set_up_db('invite_by_admins_only', False)
        realm = update_with_api(invite_by_admins_only=True)
        self.assertEqual(realm.invite_by_admins_only, True)
        realm = update_with_api(invite_by_admins_only=False)
        self.assertEqual(realm.invite_by_admins_only, False)

        # create_stream_by_admins_only
        set_up_db('create_stream_by_admins_only', False)
        realm = update_with_api(create_stream_by_admins_only=True)
        self.assertEqual(realm.create_stream_by_admins_only, True)
        realm = update_with_api(create_stream_by_admins_only=False)
        self.assertEqual(realm.create_stream_by_admins_only, False)

        # email address change disabled
        set_up_db('name_changes_disabled', False)
        realm = update_with_api(name_changes_disabled=True)
        self.assertEqual(realm.name_changes_disabled, True)
        realm = update_with_api(name_changes_disabled=False)
        self.assertEqual(realm.name_changes_disabled, False)

        # email address change disabled
        set_up_db('email_changes_disabled', False)
        realm = update_with_api(email_changes_disabled=True)
        self.assertEqual(realm.email_changes_disabled, True)
        realm = update_with_api(email_changes_disabled=False)
        self.assertEqual(realm.email_changes_disabled, False)

        # add_emoji_by_admins_only
        set_up_db('add_emoji_by_admins_only', False)
        realm = update_with_api(add_emoji_by_admins_only=True)
        self.assertEqual(realm.add_emoji_by_admins_only, True)
        realm = update_with_api(add_emoji_by_admins_only=False)
        self.assertEqual(realm.add_emoji_by_admins_only, False)

        # allow_message_editing
        set_up_db('allow_message_editing', False)
        set_up_db('message_content_edit_limit_seconds', 0)
        realm = update_with_api(allow_message_editing=True,
                                message_content_edit_limit_seconds=100)
        self.assertEqual(realm.allow_message_editing, True)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        realm = update_with_api(allow_message_editing=False)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        realm = update_with_api(message_content_edit_limit_seconds=200)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 200)

        # waiting_period_threshold
        set_up_db('waiting_period_threshold', 10)
        realm = update_with_api(waiting_period_threshold=20)
        self.assertEqual(realm.waiting_period_threshold, 20)
        realm = update_with_api(waiting_period_threshold=10)
        self.assertEqual(realm.waiting_period_threshold, 10)

    def test_admin_restrictions_for_changing_realm_name(self):
        # type: () -> None
        new_name = 'Mice will play while the cat is away'

        email = 'othello@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, False)

        req = dict(name=ujson.dumps(new_name))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_unauthorized_name_change(self):
        # type: () -> None
        data = {'full_name': 'Sir Hamlet'}
        email = 'hamlet@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_set_name_changes_disabled(user_profile.realm, name_changes_disabled=True)
        url = '/json/settings/change'
        result = self.client_post(url, data)
        self.assertEqual(result.status_code, 200)
        # Since the setting fails silently, no message is returned
        self.assert_in_response("", result)

    def test_do_deactivate_realm(self):
        # type: () -> None
        """The main complicated thing about deactivating realm names is
        updating the cache, and we start by populating the cache for
        Hamlet, and we end by checking the cache to ensure that his
        realm appears to be deactivated.  You can make this test fail
        by disabling cache.flush_realm()."""
        get_user_profile_by_email('hamlet@zulip.com')
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.realm.deactivated)

    def test_do_set_realm_default_language(self):
        # type: () -> None
        new_lang = "de"
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, new_lang)
        # we need an admin user.
        email = 'iago@zulip.com'
        self.login(email)

        req = dict(default_language=ujson.dumps(new_lang))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.default_language, new_lang)

        # Test to make sure that when invalid languages are passed
        # as the default realm language, correct validation error is
        # raised and the invalid language is not saved in db
        invalid_lang = "invalid_lang"
        req = dict(default_language=ujson.dumps(invalid_lang))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Invalid language '%s'" % (invalid_lang,))
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, invalid_lang)
