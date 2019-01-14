
import datetime
import ujson
import re
import mock
from email.utils import parseaddr

from django.conf import settings
from typing import Any, Dict, List, Mapping

from zerver.lib.actions import (
    do_change_is_admin,
    do_change_realm_subdomain,
    do_set_realm_property,
    do_deactivate_realm,
    do_deactivate_stream,
    do_create_realm,
    do_scrub_realm,
    create_stream_if_needed,
    do_change_plan_type,
    do_send_realm_reactivation_email
)

from confirmation.models import create_confirmation_link, Confirmation
from zerver.lib.send_email import send_future_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import tornado_redirected_to_list
from zerver.lib.test_runner import slow
from zerver.models import get_realm, Realm, UserProfile, ScheduledEmail, get_stream, \
    CustomProfileField, Message, UserMessage, Attachment, get_user_profile_by_email, \
    get_user_profile_by_id

class RealmTest(ZulipTestCase):
    def assert_user_profile_cache_gets_new_name(self, user_profile: UserProfile,
                                                new_realm_name: str) -> None:
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

    def test_do_change_realm_subdomain_clears_user_realm_cache(self) -> None:
        """The main complicated thing about changing realm subdomains is
        updating the cache, and we start by populating the cache for
        Hamlet, and we end by checking the cache to ensure that his
        realm appears to be deactivated.  You can make this test fail
        by disabling cache.flush_realm()."""
        user = get_user_profile_by_email('hamlet@zulip.com')
        realm = get_realm('zulip')
        do_change_realm_subdomain(realm, "newzulip")
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(user.realm.string_id, "newzulip")
        # This doesn't use a cache right now, but may later.
        self.assertIsNone(get_realm("zulip"))

    def test_do_deactivate_realm_clears_scheduled_jobs(self) -> None:
        user = self.example_user('hamlet')
        send_future_email('zerver/emails/followup_day1', user.realm,
                          to_user_ids=[user.id], delay=datetime.timedelta(hours=1))
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

    def test_realm_reactivation_link(self) -> None:
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        self.assertTrue(realm.deactivated)
        confirmation_url = create_confirmation_link(realm, realm.host, Confirmation.REALM_REACTIVATION)
        response = self.client_get(confirmation_url)
        self.assert_in_success_response(['Your organization has been successfully reactivated'], response)
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

    def test_do_send_realm_reactivation_email(self) -> None:
        realm = get_realm('zulip')
        do_send_realm_reactivation_email(realm)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)
        from_email = outbox[0].from_email
        tokenized_no_reply_email = parseaddr(from_email)[1]
        self.assertIn("Zulip Account Security", from_email)
        self.assertTrue(re.search(self.TOKENIZED_NOREPLY_REGEX, tokenized_no_reply_email))
        self.assertIn('Reactivate your Zulip organization', outbox[0].subject)
        self.assertIn('Dear former administrators', outbox[0].body)
        admins = realm.get_admin_users()
        confirmation_url = self.get_confirmation_url_from_outbox(admins[0].email)
        response = self.client_get(confirmation_url)
        self.assert_in_success_response(['Your organization has been successfully reactivated'], response)
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

    def test_realm_reactivation_with_random_link(self) -> None:
        random_link = "/reactivate/5e89081eb13984e0f3b130bf7a4121d153f1614b"
        response = self.client_get(random_link)
        self.assert_in_success_response(['The organization reactivation link has expired or is not valid.'], response)

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
        realm.save(update_fields=["notifications_stream"])

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
        realm.save(update_fields=["signup_notifications_stream"])

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

    def test_change_email_address_visibility(self) -> None:
        # We need an admin user.
        user_profile = self.example_user("iago")
        self.login(user_profile.email)
        invalid_value = 4
        req = dict(email_address_visibility = ujson.dumps(invalid_value))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid email address visibility policy')

        realm = get_realm("zulip")
        self.assertEqual(realm.email_address_visibility, Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE)
        req = dict(email_address_visibility = ujson.dumps(Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm("zulip")
        self.assertEqual(realm.email_address_visibility, Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)

        edited_user_profile = get_user_profile_by_id(user_profile.id)
        self.assertEqual(edited_user_profile.email, "user%s@zulip.testserver" % (edited_user_profile.id,))

    def test_change_video_chat_provider(self) -> None:
        self.assertEqual(get_realm('zulip').video_chat_provider, "Jitsi")
        email = self.example_email("iago")
        self.login(email)

        req = {"video_chat_provider": ujson.dumps("Google Hangouts")}
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Invalid domain: Domain can't be empty.")

        req = {
            "video_chat_provider": ujson.dumps("Google Hangouts"),
            "google_hangouts_domain": ujson.dumps("invaliddomain"),
        }
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Invalid domain: Domain must have at least one dot (.)")

        req = {
            "video_chat_provider": ujson.dumps("Google Hangouts"),
            "google_hangouts_domain": ujson.dumps("zulip.com"),
        }
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        self.assertEqual(get_realm('zulip').video_chat_provider, "Google Hangouts")

        req = {"video_chat_provider": ujson.dumps("Jitsi")}
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        self.assertEqual(get_realm('zulip').video_chat_provider, "Jitsi")

        req = {"video_chat_provider": ujson.dumps("Zoom")}
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "User ID cannot be empty")

        req = {
            "video_chat_provider": ujson.dumps("Zoom"),
            "zoom_user_id": ujson.dumps("example@example.com")
        }
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "API key cannot be empty")

        req = {
            "video_chat_provider": ujson.dumps("Zoom"),
            "zoom_user_id": ujson.dumps("example@example.com"),
            "zoom_api_key": ujson.dumps("abc")
        }
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "API secret cannot be empty")

        with mock.patch("zerver.views.realm.request_zoom_video_call_url", return_value=None):
            req = {
                "video_chat_provider": ujson.dumps("Zoom"),
                "zoom_user_id": ujson.dumps("example@example.com"),
                "zoom_api_key": ujson.dumps("abc"),
                "zoom_api_secret": ujson.dumps("abc"),
            }
            result = self.client_patch('/json/realm', req)
            self.assert_json_error(result, "Invalid credentials for the Zoom API.")

        with mock.patch("zerver.views.realm.request_zoom_video_call_url",
                        return_value={'join_url': 'example.com'}) as mock_validation:
            req = {
                "video_chat_provider": ujson.dumps("Zoom"),
                "zoom_user_id": ujson.dumps("example@example.com"),
                "zoom_api_key": ujson.dumps("abc"),
                "zoom_api_secret": ujson.dumps("abc"),
            }
            result = self.client_patch('/json/realm', req)
            self.assert_json_success(result)
            mock_validation.assert_called_once()

        with mock.patch("zerver.views.realm.request_zoom_video_call_url",
                        return_value={'join_url': 'example.com'}) as mock_validation:
            req = {
                "video_chat_provider": ujson.dumps("Zoom"),
                "zoom_user_id": ujson.dumps("example@example.com"),
                "zoom_api_key": ujson.dumps("abc"),
                "zoom_api_secret": ujson.dumps("abc"),
            }
            result = self.client_patch('/json/realm', req)
            self.assert_json_success(result)
            mock_validation.assert_not_called()

        with mock.patch("zerver.views.realm.request_zoom_video_call_url",
                        return_value={'join_url': 'example.com'}) as mock_validation:
            req = {
                "video_chat_provider": ujson.dumps("Zoom"),
                "zoom_user_id": ujson.dumps("example@example.com"),
                "zoom_api_key": ujson.dumps("abc"),
                "zoom_api_secret": ujson.dumps(""),
            }
            result = self.client_patch('/json/realm', req)
            self.assert_json_success(result)
            mock_validation.assert_not_called()

    def test_initial_plan_type(self) -> None:
        with self.settings(BILLING_ENABLED=True):
            self.assertEqual(do_create_realm('hosted', 'hosted').plan_type, Realm.LIMITED)
            self.assertEqual(get_realm("hosted").max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
            self.assertEqual(get_realm("hosted").message_visibility_limit, Realm.MESSAGE_VISIBILITY_LIMITED)
            self.assertEqual(get_realm("hosted").upload_quota_gb, Realm.UPLOAD_QUOTA_LIMITED)

        with self.settings(BILLING_ENABLED=False):
            self.assertEqual(do_create_realm('onpremise', 'onpremise').plan_type, Realm.SELF_HOSTED)
            self.assertEqual(get_realm('onpremise').max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
            self.assertEqual(get_realm('onpremise').message_visibility_limit, None)
            self.assertEqual(get_realm("onpremise").upload_quota_gb, None)

    def test_change_plan_type(self) -> None:
        realm = get_realm('zulip')
        self.assertEqual(realm.plan_type, Realm.SELF_HOSTED)
        self.assertEqual(realm.max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, None)
        self.assertEqual(realm.upload_quota_gb, None)

        do_change_plan_type(realm, Realm.STANDARD)
        realm = get_realm('zulip')
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, None)
        self.assertEqual(realm.upload_quota_gb, Realm.UPLOAD_QUOTA_STANDARD)

        do_change_plan_type(realm, Realm.LIMITED)
        realm = get_realm('zulip')
        self.assertEqual(realm.max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, Realm.MESSAGE_VISIBILITY_LIMITED)
        self.assertEqual(realm.upload_quota_gb, Realm.UPLOAD_QUOTA_LIMITED)

        do_change_plan_type(realm, Realm.STANDARD_FREE)
        realm = get_realm('zulip')
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, None)
        self.assertEqual(realm.upload_quota_gb, Realm.UPLOAD_QUOTA_STANDARD)

class RealmAPITest(ZulipTestCase):

    def setUp(self) -> None:
        user_profile = self.example_user('cordelia')
        email = user_profile.email
        self.login(email)
        do_change_is_admin(user_profile, True)

    def set_up_db(self, attr: str, value: Any) -> None:
        realm = get_realm('zulip')
        setattr(realm, attr, value)
        realm.save(update_fields=[attr])

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
            email_address_visibility=[Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
                                      Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS],
            video_chat_provider=[u'Jitsi', u'Hangouts'],
            google_hangouts_domain=[u'zulip.com', u'zulip.org'],
            zoom_api_secret=[u"abc", u"xyz"],
            zoom_api_key=[u"abc", u"xyz"],
            zoom_user_id=[u"example@example.com", u"example@example.org"]
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
            with self.subTest(property=prop):
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

    def test_update_realm_allow_message_deleting(self) -> None:
        """Tests updating the realm property 'allow_message_deleting'."""
        self.set_up_db('allow_message_deleting', True)
        self.set_up_db('message_content_delete_limit_seconds', 0)
        realm = self.update_with_api('allow_message_deleting', False)
        self.assertEqual(realm.allow_message_deleting, False)
        self.assertEqual(realm.message_content_delete_limit_seconds, 0)
        realm = self.update_with_api('allow_message_deleting', True)
        realm = self.update_with_api('message_content_delete_limit_seconds', 100)
        self.assertEqual(realm.allow_message_deleting, True)
        self.assertEqual(realm.message_content_delete_limit_seconds, 100)
        realm = self.update_with_api('message_content_delete_limit_seconds', 600)
        self.assertEqual(realm.allow_message_deleting, True)
        self.assertEqual(realm.message_content_delete_limit_seconds, 600)

class ScrubRealmTest(ZulipTestCase):
    def test_scrub_realm(self) -> None:
        zulip = get_realm("zulip")
        lear = get_realm("lear")

        iago = self.example_user("iago")
        othello = self.example_user("othello")

        cordelia = self.lear_user("cordelia")
        king = self.lear_user("king")

        create_stream_if_needed(lear, "Shakespeare")

        self.subscribe(cordelia, "Shakespeare")
        self.subscribe(king, "Shakespeare")

        Message.objects.all().delete()
        UserMessage.objects.all().delete()

        for i in range(5):
            self.send_stream_message(iago.email, "Scotland")
            self.send_stream_message(othello.email, "Scotland")
            self.send_stream_message(cordelia.email, "Shakespeare", sender_realm="lear")
            self.send_stream_message(king.email, "Shakespeare", sender_realm="lear")

        Attachment.objects.filter(realm=zulip).delete()
        Attachment.objects.create(realm=zulip, owner=iago, path_id="a/b/temp1.txt")
        Attachment.objects.create(realm=zulip, owner=othello, path_id="a/b/temp2.txt")

        Attachment.objects.filter(realm=lear).delete()
        Attachment.objects.create(realm=lear, owner=cordelia, path_id="c/d/temp1.txt")
        Attachment.objects.create(realm=lear, owner=king, path_id="c/d/temp2.txt")

        CustomProfileField.objects.create(realm=lear)

        self.assertEqual(Message.objects.filter(sender__in=[iago, othello]).count(), 10)
        self.assertEqual(Message.objects.filter(sender__in=[cordelia, king]).count(), 10)
        self.assertEqual(UserMessage.objects.filter(user_profile__in=[iago, othello]).count(), 20)
        self.assertEqual(UserMessage.objects.filter(user_profile__in=[cordelia, king]).count(), 20)

        self.assertNotEqual(CustomProfileField.objects.filter(realm=zulip).count(), 0)

        with mock.patch('logging.warning'):
            do_scrub_realm(zulip)

        self.assertEqual(Message.objects.filter(sender__in=[iago, othello]).count(), 0)
        self.assertEqual(Message.objects.filter(sender__in=[cordelia, king]).count(), 10)
        self.assertEqual(UserMessage.objects.filter(user_profile__in=[iago, othello]).count(), 0)
        self.assertEqual(UserMessage.objects.filter(user_profile__in=[cordelia, king]).count(), 20)

        self.assertEqual(Attachment.objects.filter(realm=zulip).count(), 0)
        self.assertEqual(Attachment.objects.filter(realm=lear).count(), 2)

        self.assertEqual(CustomProfileField.objects.filter(realm=zulip).count(), 0)
        self.assertNotEqual(CustomProfileField.objects.filter(realm=lear).count(), 0)

        zulip_users = UserProfile.objects.filter(realm=zulip)
        for user in zulip_users:
            self.assertTrue(re.search("Scrubbed [a-z0-9]{15}", user.full_name))
            self.assertTrue(re.search("scrubbed-[a-z0-9]{15}@" + zulip.host, user.email))
            self.assertTrue(re.search("scrubbed-[a-z0-9]{15}@" + zulip.host, user.delivery_email))

        lear_users = UserProfile.objects.filter(realm=lear)
        for user in lear_users:
            self.assertIsNone(re.search("Scrubbed [a-z0-9]{15}", user.full_name))
            self.assertIsNone(re.search("scrubbed-[a-z0-9]{15}@" + zulip.host, user.email))
            self.assertIsNone(re.search("scrubbed-[a-z0-9]{15}@" + zulip.host, user.delivery_email))
