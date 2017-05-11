from __future__ import absolute_import
from __future__ import print_function

import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict, List, Text, Union

from zerver.lib.actions import (
    do_change_is_admin,
    do_set_realm_property,
    do_deactivate_realm,
)

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
        self.example_user('hamlet')
        realm = get_realm('zulip')
        new_name = u'Zed You Elle Eye Pea'
        do_set_realm_property(realm, 'name', new_name)
        self.assertEqual(get_realm(realm.string_id).name, new_name)
        self.assert_user_profile_cache_gets_new_name('hamlet@zulip.com', new_name)

    def test_update_realm_name_events(self):
        # type: () -> None
        realm = get_realm('zulip')
        new_name = u'Puliz'
        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            do_set_realm_property(realm, 'name', new_name)
        event = events[0]['event']
        self.assertEqual(event, dict(
            type='realm',
            op='update',
            property='name',
            value=new_name,
        ))

    def test_update_realm_description_events(self):
        # type: () -> None
        realm = get_realm('zulip')
        new_description = u'zulip dev group'
        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            do_set_realm_property(realm, 'description', new_description)
        event = events[0]['event']
        self.assertEqual(event, dict(
            type='realm',
            op='update',
            property='description',
            value=new_description,
        ))

    def test_update_realm_description(self):
        # type: () -> None
        email = 'iago@zulip.com'
        self.login(email)
        realm = get_realm('zulip')
        new_description = u'zulip dev group'
        data = dict(description=ujson.dumps(new_description))
        events = []  # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/realm', data)
            self.assert_json_success(result)
            realm = get_realm('zulip')
            self.assertEqual(realm.description, new_description)

        event = events[0]['event']
        self.assertEqual(event, dict(
            type='realm',
            op='update',
            property='description',
            value=new_description,
        ))

    def test_realm_description_length(self):
        # type: () -> None
        new_description = u'A' * 1001
        data = dict(description=ujson.dumps(new_description))

        # create an admin user
        email = 'iago@zulip.com'
        self.login(email)

        result = self.client_patch('/json/realm', data)
        self.assert_json_error(result, 'Realm description is too long.')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.description, new_description)

    def test_admin_restrictions_for_changing_realm_name(self):
        # type: () -> None
        new_name = 'Mice will play while the cat is away'

        user_profile = self.example_user('othello')
        email = user_profile.email
        self.login(email)
        do_change_is_admin(user_profile, False)

        req = dict(name=ujson.dumps(new_name))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_unauthorized_name_change(self):
        # type: () -> None
        data = {'full_name': 'Sir Hamlet'}
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        do_set_realm_property(user_profile.realm, 'name_changes_disabled', True)
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
        self.example_user('hamlet')
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        user = self.example_user('hamlet')
        self.assertTrue(user.realm.deactivated)

    def test_change_realm_default_language(self):
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


class RealmAPITest(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        user_profile = self.example_user('cordelia')
        email = user_profile.email
        self.login(email)
        do_change_is_admin(user_profile, True)

    def set_up_db(self, attr, value):
        # type: (str, Any) -> None
        realm = get_realm('zulip')
        setattr(realm, attr, value)
        realm.save()

    def update_with_api(self, name, value):
        # type: (str, Union[Text, int, bool]) -> Realm
        result = self.client_patch('/json/realm', {name: ujson.dumps(value)})
        self.assert_json_success(result)
        return get_realm('zulip') # refresh data

    def do_test_realm_update_api(self, name):
        # type: (str) -> None
        """Test updating realm properties.

        If new realm properties have been added to the Realm model but the
        test_values dict below has not been updated, this will raise an
        assertion error.
        """

        bool_tests = [False, True] # type: List[bool]
        test_values = dict(
            add_emoji_by_admins_only=bool_tests,
            create_stream_by_admins_only=bool_tests,
            default_language=[u'de', u'en'],
            description=[u'Realm description', u'New description'],
            email_changes_disabled=bool_tests,
            invite_required=bool_tests,
            invite_by_admins_only=bool_tests,
            inline_image_preview=bool_tests,
            inline_url_embed_preview=bool_tests,
            message_retention_days=[10, 20],
            name=[u'Zulip', u'New Name'],
            name_changes_disabled=bool_tests,
            restricted_to_domain=bool_tests,
            waiting_period_threshold=[10, 20],
        ) # type: Dict[str, Any]
        vals = test_values.get(name)
        if vals is None:
            raise AssertionError('No test created for %s' % (name))

        self.set_up_db(name, vals[0])
        realm = self.update_with_api(name, vals[1])
        self.assertEqual(getattr(realm, name), vals[1])
        realm = self.update_with_api(name, vals[0])
        self.assertEqual(getattr(realm, name), vals[0])

    def test_update_realm_properties(self):
        # type: () -> None
        for prop in Realm.property_types:
            self.do_test_realm_update_api(prop)

    def test_update_realm_allow_message_editing(self):
        # type: () -> None
        """Tests updating the realm property 'allow_message_editing'."""
        self.set_up_db('allow_message_editing', False)
        self.set_up_db('message_content_edit_limit_seconds', 0)
        realm = self.update_with_api('allow_message_editing', True)
        realm = self.update_with_api('message_content_edit_limit_seconds', 100)
        self.assertEqual(realm.allow_message_editing, True)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        realm = self.update_with_api('allow_message_editing', False)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        realm = self.update_with_api('message_content_edit_limit_seconds', 200)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 200)
