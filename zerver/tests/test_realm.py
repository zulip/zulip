
import datetime
import ujson

from django.http import HttpResponse
from mock import patch
from typing import Any, Dict, List, Text, Union, Mapping

from zerver.lib.actions import (
    do_change_is_admin,
    do_set_realm_property,
    do_deactivate_realm,
    do_deactivate_stream,
)

from zerver.lib.send_email import send_future_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import tornado_redirected_to_list
from zerver.lib.test_runner import slow
from zerver.models import get_realm, Realm, UserProfile, ScheduledEmail, get_stream

class RealmTest(ZulipTestCase):
    def assert_user_profile_cache_gets_new_name(self, user_profile: UserProfile,
                                                new_realm_name: Text) -> None:
        self.assertEqual(user_profile.realm.name, new_realm_name)

    def test_do_set_realm_name_caching(self) -> None:
        """The main complicated thing about setting realm names is fighting the
        cache, and we start by populating the cache for Hamlet, and we end
        by checking the cache to ensure that the new value is there."""
        self.example_user('hamlet')
        realm = get_realm('zulip')
        new_name = u'Zed You Elle Eye Pea'
        do_set_realm_property(realm, 'name', new_name)
        self.assertEqual(get_realm(realm.string_id).name, new_name)
        self.assert_user_profile_cache_gets_new_name(self.example_user('hamlet'), new_name)

    def test_update_realm_name_events(self) -> None:
        realm = get_realm('zulip')
        new_name = u'Puliz'
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            do_set_realm_property(realm, 'name', new_name)
        event = events[0]['event']
        self.assertEqual(event, dict(
            type='realm',
            op='update',
            property='name',
            value=new_name,
        ))

    def test_update_realm_description_events(self) -> None:
        realm = get_realm('zulip')
        new_description = u'zulip dev group'
        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            do_set_realm_property(realm, 'description', new_description)
        event = events[0]['event']
        self.assertEqual(event, dict(
            type='realm',
            op='update',
            property='description',
            value=new_description,
        ))

    def test_update_realm_description(self) -> None:
        email = self.example_email("iago")
        self.login(email)
        realm = get_realm('zulip')
        new_description = u'zulip dev group'
        data = dict(description=ujson.dumps(new_description))
        events = []  # type: List[Mapping[str, Any]]
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

    def test_realm_description_length(self) -> None:
        new_description = u'A' * 1001
        data = dict(description=ujson.dumps(new_description))

        # create an admin user
        email = self.example_email("iago")
        self.login(email)

        result = self.client_patch('/json/realm', data)
        self.assert_json_error(result, 'Organization description is too long.')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.description, new_description)

    def test_realm_name_length(self) -> None:
        new_name = u'A' * (Realm.MAX_REALM_NAME_LENGTH + 1)
        data = dict(name=ujson.dumps(new_name))

        # create an admin user
        email = self.example_email("iago")
        self.login(email)

        result = self.client_patch('/json/realm', data)
        self.assert_json_error(result, 'Organization name is too long.')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.name, new_name)

    def test_admin_restrictions_for_changing_realm_name(self) -> None:
        new_name = 'Mice will play while the cat is away'

        user_profile = self.example_user('othello')
        email = user_profile.email
        self.login(email)
        do_change_is_admin(user_profile, False)

        req = dict(name=ujson.dumps(new_name))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_unauthorized_name_change(self) -> None:
        data = {'full_name': 'Sir Hamlet'}
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)
        do_set_realm_property(user_profile.realm, 'name_changes_disabled', True)
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assertEqual(result.status_code, 200)
        # Since the setting fails silently, no message is returned
        self.assert_in_response("", result)
        # Realm admins can change their name even setting is disabled.
        data = {'full_name': 'New Iago'}
        self.login(self.example_email("iago"))
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assert_in_success_response(['"full_name":"New Iago"'], result)

    def test_do_deactivate_realm_clears_user_realm_cache(self) -> None:
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

    def test_do_deactivate_realm_clears_scheduled_jobs(self) -> None:
        user = self.example_user('hamlet')
        send_future_email('zerver/emails/followup_day1', user.realm,
                          to_user_id=user.id, delay=datetime.timedelta(hours=1))
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        do_deactivate_realm(user.realm)
        self.assertEqual(ScheduledEmail.objects.count(), 0)

    def test_do_deactivate_realm_on_deactived_realm(self) -> None:
        """Ensure early exit is working in realm deactivation"""
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

        do_deactivate_realm(realm)
        self.assertTrue(realm.deactivated)

        do_deactivate_realm(realm)
        self.assertTrue(realm.deactivated)

    def test_change_notifications_stream(self) -> None:
        # We need an admin user.
        email = 'iago@zulip.com'
        self.login(email)

        disabled_notif_stream_id = -1
        req = dict(notifications_stream_id = ujson.dumps(disabled_notif_stream_id))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.notifications_stream, None)

        new_notif_stream_id = 4
        req = dict(notifications_stream_id = ujson.dumps(new_notif_stream_id))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.notifications_stream.id, new_notif_stream_id)

        invalid_notif_stream_id = 1234
        req = dict(notifications_stream_id = ujson.dumps(invalid_notif_stream_id))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid stream id')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.notifications_stream.id, invalid_notif_stream_id)

    def test_get_default_notifications_stream(self) -> None:
        realm = get_realm("zulip")
        verona = get_stream("verona", realm)
        realm.notifications_stream_id = verona.id
        realm.save()

        notifications_stream = realm.get_notifications_stream()
        self.assertEqual(notifications_stream.id, verona.id)
        do_deactivate_stream(notifications_stream)
        self.assertIsNone(realm.get_notifications_stream())

    def test_change_signup_notifications_stream(self) -> None:
        # We need an admin user.
        email = 'iago@zulip.com'
        self.login(email)

        disabled_signup_notifications_stream_id = -1
        req = dict(signup_notifications_stream_id = ujson.dumps(disabled_signup_notifications_stream_id))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.signup_notifications_stream, None)

        new_signup_notifications_stream_id = 4
        req = dict(signup_notifications_stream_id = ujson.dumps(new_signup_notifications_stream_id))

        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.signup_notifications_stream.id, new_signup_notifications_stream_id)

        invalid_signup_notifications_stream_id = 1234
        req = dict(signup_notifications_stream_id = ujson.dumps(invalid_signup_notifications_stream_id))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid stream id')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.signup_notifications_stream.id, invalid_signup_notifications_stream_id)

    def test_get_default_signup_notifications_stream(self) -> None:
        realm = get_realm("zulip")
        verona = get_stream("verona", realm)
        realm.signup_notifications_stream = verona
        realm.save()

        signup_notifications_stream = realm.get_signup_notifications_stream()
        self.assertEqual(signup_notifications_stream, verona)
        do_deactivate_stream(signup_notifications_stream)
        self.assertIsNone(realm.get_signup_notifications_stream())

    def test_change_realm_default_language(self) -> None:
        new_lang = "de"
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, new_lang)
        # we need an admin user.
        email = self.example_email("iago")
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

    def test_deactivate_realm_by_admin(self) -> None:
        email = self.example_email('iago')
        self.login(email)
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

        result = self.client_post('/json/realm/deactivate')
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertTrue(realm.deactivated)

    def test_deactivate_realm_by_non_admin(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

        result = self.client_post('/json/realm/deactivate')
        self.assert_json_error(result, "Must be an organization administrator")
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

    def test_change_bot_creation_policy(self) -> None:
        # We need an admin user.
        email = 'iago@zulip.com'
        self.login(email)
        req = dict(bot_creation_policy = ujson.dumps(Realm.BOT_CREATION_LIMIT_GENERIC_BOTS))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_add_bot_permission = 4
        req = dict(bot_creation_policy = ujson.dumps(invalid_add_bot_permission))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid bot creation policy')


class RealmAPITest(ZulipTestCase):

    def setUp(self) -> None:
        user_profile = self.example_user('cordelia')
        email = user_profile.email
        self.login(email)
        do_change_is_admin(user_profile, True)

    def set_up_db(self, attr: str, value: Any) -> None:
        realm = get_realm('zulip')
        setattr(realm, attr, value)
        realm.save()

    def update_with_api(self, name: str, value: int) -> Realm:
        result = self.client_patch('/json/realm', {name: ujson.dumps(value)})
        self.assert_json_success(result)
        return get_realm('zulip')  # refresh data

    def do_test_realm_update_api(self, name: str) -> None:
        """Test updating realm properties.

        If new realm properties have been added to the Realm model but the
        test_values dict below has not been updated, this will raise an
        assertion error.
        """

        bool_tests = [False, True]  # type: List[bool]
        test_values = dict(
            default_language=[u'de', u'en'],
            description=[u'Realm description', u'New description'],
            message_retention_days=[10, 20],
            name=[u'Zulip', u'New Name'],
            waiting_period_threshold=[10, 20],
            bot_creation_policy=[1, 2],
        )  # type: Dict[str, Any]
        vals = test_values.get(name)
        if Realm.property_types[name] is bool:
            vals = bool_tests
        if vals is None:
            raise AssertionError('No test created for %s' % (name))

        self.set_up_db(name, vals[0])
        realm = self.update_with_api(name, vals[1])
        self.assertEqual(getattr(realm, name), vals[1])
        realm = self.update_with_api(name, vals[0])
        self.assertEqual(getattr(realm, name), vals[0])

    @slow("Tests a dozen properties in a loop")
    def test_update_realm_properties(self) -> None:
        for prop in Realm.property_types:
            self.do_test_realm_update_api(prop)

    def test_update_realm_allow_message_editing(self) -> None:
        """Tests updating the realm property 'allow_message_editing'."""
        self.set_up_db('allow_message_editing', False)
        self.set_up_db('message_content_edit_limit_seconds', 0)
        self.set_up_db('allow_community_topic_editing', False)
        realm = self.update_with_api('allow_message_editing', True)
        realm = self.update_with_api('message_content_edit_limit_seconds', 100)
        realm = self.update_with_api('allow_community_topic_editing', True)
        self.assertEqual(realm.allow_message_editing, True)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        self.assertEqual(realm.allow_community_topic_editing, True)
        realm = self.update_with_api('allow_message_editing', False)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        self.assertEqual(realm.allow_community_topic_editing, True)
        realm = self.update_with_api('message_content_edit_limit_seconds', 200)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 200)
        self.assertEqual(realm.allow_community_topic_editing, True)
        realm = self.update_with_api('allow_community_topic_editing', False)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 200)
        self.assertEqual(realm.allow_community_topic_editing, False)
