import datetime
import re
from typing import Any, Dict, List, Mapping
from unittest import mock

import orjson
from django.conf import settings

from confirmation.models import Confirmation, create_confirmation_link
from zerver.lib.actions import (
    do_change_plan_type,
    do_change_realm_subdomain,
    do_create_realm,
    do_deactivate_realm,
    do_deactivate_stream,
    do_scrub_realm,
    do_send_realm_reactivation_email,
    do_set_realm_property,
)
from zerver.lib.realm_description import get_realm_rendered_description, get_realm_text_description
from zerver.lib.send_email import send_future_email
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import reset_emails_in_zulip_realm, tornado_redirected_to_list
from zerver.models import (
    Attachment,
    CustomProfileField,
    Message,
    Realm,
    ScheduledEmail,
    UserMessage,
    UserProfile,
    get_realm,
    get_stream,
    get_user_profile_by_email,
    get_user_profile_by_id,
)


class RealmTest(ZulipTestCase):
    def assert_user_profile_cache_gets_new_name(self, user_profile: UserProfile,
                                                new_realm_name: str) -> None:
        self.assertEqual(user_profile.realm.name, new_realm_name)

    def test_realm_creation_ensures_internal_realms(self) -> None:
        with mock.patch("zerver.lib.actions.server_initialized", return_value=False):
            with mock.patch("zerver.lib.actions.create_internal_realm") as mock_create_internal, \
                    self.assertLogs(level='INFO') as info_logs:
                do_create_realm("testrealm", "Test Realm")
                mock_create_internal.assert_called_once()
            self.assertEqual(info_logs.output, [
                'INFO:root:Server not yet initialized. Creating the internal realm first.'
            ])

    def test_do_set_realm_name_caching(self) -> None:
        """The main complicated thing about setting realm names is fighting the
        cache, and we start by populating the cache for Hamlet, and we end
        by checking the cache to ensure that the new value is there."""
        self.example_user('hamlet')
        realm = get_realm('zulip')
        new_name = 'Zed You Elle Eye Pea'
        do_set_realm_property(realm, 'name', new_name)
        self.assertEqual(get_realm(realm.string_id).name, new_name)
        self.assert_user_profile_cache_gets_new_name(self.example_user('hamlet'), new_name)

    def test_update_realm_name_events(self) -> None:
        realm = get_realm('zulip')
        new_name = 'Puliz'
        events: List[Mapping[str, Any]] = []
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
        new_description = 'zulip dev group'
        events: List[Mapping[str, Any]] = []
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
        self.login('iago')
        new_description = 'zulip dev group'
        data = dict(description=orjson.dumps(new_description).decode())
        events: List[Mapping[str, Any]] = []
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
        new_description = 'A' * 1001
        data = dict(description=orjson.dumps(new_description).decode())

        # create an admin user
        self.login('iago')

        result = self.client_patch('/json/realm', data)
        self.assert_json_error(result, 'Organization description is too long.')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.description, new_description)

    def test_realm_name_length(self) -> None:
        new_name = 'A' * (Realm.MAX_REALM_NAME_LENGTH + 1)
        data = dict(name=orjson.dumps(new_name).decode())

        # create an admin user
        self.login('iago')

        result = self.client_patch('/json/realm', data)
        self.assert_json_error(result, 'Organization name is too long.')
        realm = get_realm('zulip')
        self.assertNotEqual(realm.name, new_name)

    def test_admin_restrictions_for_changing_realm_name(self) -> None:
        new_name = 'Mice will play while the cat is away'

        self.login('othello')

        req = dict(name=orjson.dumps(new_name).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_unauthorized_name_change(self) -> None:
        data = {'full_name': 'Sir Hamlet'}
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        do_set_realm_property(user_profile.realm, 'name_changes_disabled', True)
        url = '/json/settings'
        result = self.client_patch(url, data)
        self.assertEqual(result.status_code, 200)
        # Since the setting fails silently, no message is returned
        self.assert_in_response("", result)
        # Realm admins can change their name even setting is disabled.
        data = {'full_name': 'New Iago'}
        self.login('iago')
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
        with self.assertRaises(Realm.DoesNotExist):
            get_realm("zulip")

    def test_do_deactivate_realm_clears_scheduled_jobs(self) -> None:
        user = self.example_user('hamlet')
        send_future_email('zerver/emails/followup_day1', user.realm,
                          to_user_ids=[user.id], delay=datetime.timedelta(hours=1))
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        do_deactivate_realm(user.realm)
        self.assertEqual(ScheduledEmail.objects.count(), 0)

    def test_do_change_realm_description_clears_cached_descriptions(self) -> None:
        realm = get_realm('zulip')
        rendered_description = get_realm_rendered_description(realm)
        text_description = get_realm_text_description(realm)

        realm.description = 'New Description'
        realm.save(update_fields=['description'])

        new_rendered_description = get_realm_rendered_description(realm)
        self.assertNotEqual(rendered_description, new_rendered_description)
        self.assertIn(realm.description, new_rendered_description)

        new_text_description = get_realm_text_description(realm)
        self.assertNotEqual(text_description, new_text_description)
        self.assertEqual(realm.description, new_text_description)

    def test_do_deactivate_realm_on_deactivated_realm(self) -> None:
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
        confirmation_url = create_confirmation_link(realm, Confirmation.REALM_REACTIVATION)
        response = self.client_get(confirmation_url)
        self.assert_in_success_response(['Your organization has been successfully reactivated'], response)
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

    def test_realm_reactivation_confirmation_object(self) -> None:
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        self.assertTrue(realm.deactivated)
        create_confirmation_link(realm, Confirmation.REALM_REACTIVATION)
        confirmation = Confirmation.objects.last()
        self.assertEqual(confirmation.content_object, realm)
        self.assertEqual(confirmation.realm, realm)

    def test_do_send_realm_reactivation_email(self) -> None:
        realm = get_realm('zulip')
        do_send_realm_reactivation_email(realm)
        from django.core.mail import outbox
        self.assertEqual(len(outbox), 1)
        self.assertRegex(
            outbox[0].from_email,
            fr"^Zulip Account Security <{self.TOKENIZED_NOREPLY_REGEX}>\Z",
        )
        self.assertIn('Reactivate your Zulip organization', outbox[0].subject)
        self.assertIn('Dear former administrators', outbox[0].body)
        admins = realm.get_human_admin_users()
        confirmation_url = self.get_confirmation_url_from_outbox(admins[0].delivery_email)
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
        self.login('iago')

        disabled_notif_stream_id = -1
        req = dict(notifications_stream_id = orjson.dumps(disabled_notif_stream_id).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.notifications_stream, None)

        new_notif_stream_id = 4
        req = dict(notifications_stream_id = orjson.dumps(new_notif_stream_id).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        assert realm.notifications_stream is not None
        self.assertEqual(realm.notifications_stream.id, new_notif_stream_id)

        invalid_notif_stream_id = 1234
        req = dict(notifications_stream_id = orjson.dumps(invalid_notif_stream_id).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid stream id')
        realm = get_realm('zulip')
        assert realm.notifications_stream is not None
        self.assertNotEqual(realm.notifications_stream.id, invalid_notif_stream_id)

    def test_get_default_notifications_stream(self) -> None:
        realm = get_realm("zulip")
        verona = get_stream("verona", realm)
        realm.notifications_stream_id = verona.id
        realm.save(update_fields=["notifications_stream"])

        notifications_stream = realm.get_notifications_stream()
        assert notifications_stream is not None
        self.assertEqual(notifications_stream.id, verona.id)
        do_deactivate_stream(notifications_stream)
        self.assertIsNone(realm.get_notifications_stream())

    def test_change_signup_notifications_stream(self) -> None:
        # We need an admin user.
        self.login('iago')

        disabled_signup_notifications_stream_id = -1
        req = dict(signup_notifications_stream_id = orjson.dumps(disabled_signup_notifications_stream_id).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.signup_notifications_stream, None)

        new_signup_notifications_stream_id = 4
        req = dict(signup_notifications_stream_id = orjson.dumps(new_signup_notifications_stream_id).decode())

        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        assert realm.signup_notifications_stream is not None
        self.assertEqual(realm.signup_notifications_stream.id, new_signup_notifications_stream_id)

        invalid_signup_notifications_stream_id = 1234
        req = dict(signup_notifications_stream_id = orjson.dumps(invalid_signup_notifications_stream_id).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid stream id')
        realm = get_realm('zulip')
        assert realm.signup_notifications_stream is not None
        self.assertNotEqual(realm.signup_notifications_stream.id, invalid_signup_notifications_stream_id)

    def test_get_default_signup_notifications_stream(self) -> None:
        realm = get_realm("zulip")
        verona = get_stream("verona", realm)
        realm.signup_notifications_stream = verona
        realm.save(update_fields=["signup_notifications_stream"])

        signup_notifications_stream = realm.get_signup_notifications_stream()
        assert signup_notifications_stream is not None
        self.assertEqual(signup_notifications_stream, verona)
        do_deactivate_stream(signup_notifications_stream)
        self.assertIsNone(realm.get_signup_notifications_stream())

    def test_change_realm_default_language(self) -> None:
        new_lang = "de"
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, new_lang)
        # we need an admin user.
        self.login('iago')

        req = dict(default_language=orjson.dumps(new_lang).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.default_language, new_lang)

        # Test to make sure that when invalid languages are passed
        # as the default realm language, correct validation error is
        # raised and the invalid language is not saved in db
        invalid_lang = "invalid_lang"
        req = dict(default_language=orjson.dumps(invalid_lang).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, f"Invalid language '{invalid_lang}'")
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, invalid_lang)

    def test_deactivate_realm_by_owner(self) -> None:
        self.login('desdemona')
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

        result = self.client_post('/json/realm/deactivate')
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertTrue(realm.deactivated)

    def test_deactivate_realm_by_non_owner(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

        result = self.client_post('/json/realm/deactivate')
        self.assert_json_error(result, "Must be an organization owner")
        realm = get_realm('zulip')
        self.assertFalse(realm.deactivated)

    def test_change_bot_creation_policy(self) -> None:
        # We need an admin user.
        self.login('iago')
        req = dict(bot_creation_policy = orjson.dumps(Realm.BOT_CREATION_LIMIT_GENERIC_BOTS).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_add_bot_permission = 4
        req = dict(bot_creation_policy = orjson.dumps(invalid_add_bot_permission).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid bot_creation_policy')

    def test_change_email_address_visibility(self) -> None:
        # We need an admin user.
        user_profile = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        self.login_user(user_profile)
        invalid_value = 12
        req = dict(email_address_visibility = orjson.dumps(invalid_value).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid email_address_visibility')

        reset_emails_in_zulip_realm()
        realm = get_realm("zulip")

        req = dict(email_address_visibility = orjson.dumps(Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm("zulip")
        self.assertEqual(realm.email_address_visibility, Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)

        edited_user_profile = get_user_profile_by_id(user_profile.id)
        self.assertEqual(edited_user_profile.email, f"user{edited_user_profile.id}@zulip.testserver")

        # Check normal user cannot access email
        result = self.api_get(cordelia, f"/api/v1/users/{hamlet.id}")
        self.assert_json_success(result)
        self.assertEqual(result.json()['user']['email'],
                         f'user{hamlet.id}@zulip.testserver')
        self.assertEqual(result.json()['user'].get('delivery_email'), None)

        # Check administrator gets delivery_email with EMAIL_ADDRESS_VISIBILITY_ADMINS
        result = self.api_get(user_profile, f"/api/v1/users/{hamlet.id}")
        self.assert_json_success(result)
        self.assertEqual(result.json()['user']['email'],
                         f'user{hamlet.id}@zulip.testserver')
        self.assertEqual(result.json()['user'].get('delivery_email'),
                         hamlet.delivery_email)

        req = dict(email_address_visibility = orjson.dumps(Realm.EMAIL_ADDRESS_VISIBILITY_NOBODY).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        realm = get_realm("zulip")
        self.assertEqual(realm.email_address_visibility, Realm.EMAIL_ADDRESS_VISIBILITY_NOBODY)
        edited_user_profile = get_user_profile_by_id(user_profile.id)
        self.assertEqual(edited_user_profile.email, f"user{edited_user_profile.id}@zulip.testserver")

        # Check even administrator doesn't get delivery_email with
        # EMAIL_ADDRESS_VISIBILITY_NOBODY
        result = self.api_get(user_profile, f"/api/v1/users/{hamlet.id}")
        self.assert_json_success(result)
        self.assertEqual(result.json()['user']['email'],
                         f'user{hamlet.id}@zulip.testserver')
        self.assertEqual(result.json()['user'].get('delivery_email'), None)

    def test_change_stream_creation_policy(self) -> None:
        # We need an admin user.
        self.login('iago')
        req = dict(create_stream_policy = orjson.dumps(Realm.POLICY_ADMINS_ONLY).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_value = 10
        req = dict(create_stream_policy = orjson.dumps(invalid_value).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid create_stream_policy')

    def test_change_invite_to_stream_policy(self) -> None:
        # We need an admin user.
        self.login('iago')
        req = dict(invite_to_stream_policy = orjson.dumps(Realm.POLICY_ADMINS_ONLY).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_value = 10
        req = dict(invite_to_stream_policy = orjson.dumps(invalid_value).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid invite_to_stream_policy')

    def test_user_group_edit_policy(self) -> None:
        # We need an admin user.
        self.login('iago')
        req = dict(user_group_edit_policy = orjson.dumps(Realm.USER_GROUP_EDIT_POLICY_ADMINS).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_value = 10
        req = dict(user_group_edit_policy = orjson.dumps(invalid_value).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid user_group_edit_policy')

    def test_private_message_policy(self) -> None:
        # We need an admin user.
        self.login('iago')
        req = dict(private_message_policy = orjson.dumps(Realm.PRIVATE_MESSAGE_POLICY_DISABLED).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_value = 10
        req = dict(private_message_policy = orjson.dumps(invalid_value).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid private_message_policy')

    def test_change_wildcard_mention_policy(self) -> None:
        # We need an admin user.
        self.login('iago')
        req = dict(wildcard_mention_policy = orjson.dumps(Realm.WILDCARD_MENTION_POLICY_EVERYONE).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        invalid_value = 10
        req = dict(wildcard_mention_policy = orjson.dumps(invalid_value).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Invalid wildcard_mention_policy')

    def test_invalid_integer_attribute_values(self) -> None:

        integer_values = [key for key, value in Realm.property_types.items() if value is int]

        invalid_values = dict(
            bot_creation_policy=10,
            create_stream_policy=10,
            invite_to_stream_policy=10,
            email_address_visibility=10,
            message_retention_days=10,
            video_chat_provider=10,
            waiting_period_threshold=-10,
            digest_weekday=10,
            user_group_edit_policy=10,
            private_message_policy=10,
            message_content_delete_limit_seconds=-10,
            wildcard_mention_policy=10,
        )

        # We need an admin user.
        self.login('iago')

        for name in integer_values:
            invalid_value = invalid_values.get(name)
            if invalid_value is None:
                raise AssertionError(f'No test created for {name}')

            self.do_test_invalid_integer_attribute_value(name, invalid_value)

    def do_test_invalid_integer_attribute_value(self, val_name: str, invalid_val: int) -> None:

        possible_messages = {
            f"Invalid {val_name}",
            f"Bad value for '{val_name}'",
            f"Bad value for '{val_name}': {invalid_val}",
            f"Invalid {val_name} {invalid_val}",
        }

        req = {val_name: invalid_val}
        result = self.client_patch('/json/realm', req)
        msg = self.get_json_error(result)
        self.assertTrue(msg in possible_messages)

    def test_change_video_chat_provider(self) -> None:
        self.assertEqual(get_realm('zulip').video_chat_provider, Realm.VIDEO_CHAT_PROVIDERS['jitsi_meet']['id'])
        self.login('iago')

        invalid_video_chat_provider_value = 10
        req = {"video_chat_provider": orjson.dumps(invalid_video_chat_provider_value).decode()}
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result,
                               ("Invalid video_chat_provider {}").format(invalid_video_chat_provider_value))

        req = {"video_chat_provider": orjson.dumps(Realm.VIDEO_CHAT_PROVIDERS['disabled']['id']).decode()}
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        self.assertEqual(get_realm('zulip').video_chat_provider,
                         Realm.VIDEO_CHAT_PROVIDERS['disabled']['id'])

        req = {"video_chat_provider": orjson.dumps(Realm.VIDEO_CHAT_PROVIDERS['jitsi_meet']['id']).decode()}
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        self.assertEqual(get_realm('zulip').video_chat_provider, Realm.VIDEO_CHAT_PROVIDERS['jitsi_meet']['id'])

        req = {"video_chat_provider": orjson.dumps(Realm.VIDEO_CHAT_PROVIDERS['big_blue_button']['id']).decode()}
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        self.assertEqual(get_realm('zulip').video_chat_provider,
                         Realm.VIDEO_CHAT_PROVIDERS['big_blue_button']['id'])

        req = {"video_chat_provider": orjson.dumps(Realm.VIDEO_CHAT_PROVIDERS['zoom']['id']).decode()}
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

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
        self.assertEqual(realm.plan_type, Realm.STANDARD)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, None)
        self.assertEqual(realm.upload_quota_gb, Realm.UPLOAD_QUOTA_STANDARD)

        do_change_plan_type(realm, Realm.LIMITED)
        realm = get_realm('zulip')
        self.assertEqual(realm.plan_type, Realm.LIMITED)
        self.assertEqual(realm.max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, Realm.MESSAGE_VISIBILITY_LIMITED)
        self.assertEqual(realm.upload_quota_gb, Realm.UPLOAD_QUOTA_LIMITED)

        do_change_plan_type(realm, Realm.STANDARD_FREE)
        realm = get_realm('zulip')
        self.assertEqual(realm.plan_type, Realm.STANDARD_FREE)
        self.assertEqual(realm.max_invites, Realm.INVITES_STANDARD_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, None)
        self.assertEqual(realm.upload_quota_gb, Realm.UPLOAD_QUOTA_STANDARD)

        do_change_plan_type(realm, Realm.LIMITED)

        do_change_plan_type(realm, Realm.SELF_HOSTED)
        self.assertEqual(realm.plan_type, Realm.SELF_HOSTED)
        self.assertEqual(realm.max_invites, settings.INVITES_DEFAULT_REALM_DAILY_MAX)
        self.assertEqual(realm.message_visibility_limit, None)
        self.assertEqual(realm.upload_quota_gb, None)

    def test_message_retention_days(self) -> None:
        self.login('iago')
        realm = get_realm('zulip')
        self.assertEqual(realm.plan_type, Realm.SELF_HOSTED)

        req = dict(message_retention_days=orjson.dumps(10).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Must be an organization owner")

        self.login('desdemona')

        req = dict(message_retention_days=orjson.dumps(0).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Bad value for 'message_retention_days': 0")

        req = dict(message_retention_days=orjson.dumps(-10).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(
            result, "Bad value for 'message_retention_days': -10")

        req = dict(message_retention_days=orjson.dumps('invalid').decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Bad value for 'message_retention_days': invalid")

        req = dict(message_retention_days=orjson.dumps(-1).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Bad value for 'message_retention_days': -1")

        req = dict(message_retention_days=orjson.dumps('forever').decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        req = dict(message_retention_days=orjson.dumps(10).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

        do_change_plan_type(realm, Realm.LIMITED)
        req = dict(message_retention_days=orjson.dumps(10).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(
            result, "Available on Zulip Standard. Upgrade to access.")

        do_change_plan_type(realm, Realm.STANDARD)
        req = dict(message_retention_days=orjson.dumps(10).decode())
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)

class RealmAPITest(ZulipTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.login('desdemona')

    def set_up_db(self, attr: str, value: Any) -> None:
        realm = get_realm('zulip')
        setattr(realm, attr, value)
        realm.save(update_fields=[attr])

    def update_with_api(self, name: str, value: int) -> Realm:
        result = self.client_patch('/json/realm', {name: orjson.dumps(value).decode()})
        self.assert_json_success(result)
        return get_realm('zulip')  # refresh data

    def update_with_api_multiple_value(self, data_dict: Dict[str, Any]) -> Realm:
        result = self.client_patch('/json/realm', data_dict)
        self.assert_json_success(result)
        return get_realm('zulip')

    def do_test_realm_update_api(self, name: str) -> None:
        """Test updating realm properties.

        If new realm properties have been added to the Realm model but the
        test_values dict below has not been updated, this will raise an
        assertion error.
        """

        bool_tests: List[bool] = [False, True]
        test_values: Dict[str, Any] = dict(
            default_language=['de', 'en'],
            default_code_block_language=['javascript', ''],
            description=['Realm description', 'New description'],
            digest_weekday=[0, 1, 2],
            message_retention_days=[10, 20],
            name=['Zulip', 'New Name'],
            waiting_period_threshold=[10, 20],
            create_stream_policy=[Realm.POLICY_ADMINS_ONLY,
                                  Realm.POLICY_MEMBERS_ONLY,
                                  Realm.POLICY_FULL_MEMBERS_ONLY],
            user_group_edit_policy=[Realm.USER_GROUP_EDIT_POLICY_ADMINS,
                                    Realm.USER_GROUP_EDIT_POLICY_MEMBERS],
            private_message_policy=[Realm.PRIVATE_MESSAGE_POLICY_UNLIMITED,
                                    Realm.PRIVATE_MESSAGE_POLICY_DISABLED],
            invite_to_stream_policy=[Realm.POLICY_ADMINS_ONLY,
                                     Realm.POLICY_MEMBERS_ONLY,
                                     Realm.POLICY_FULL_MEMBERS_ONLY],
            wildcard_mention_policy=[Realm.WILDCARD_MENTION_POLICY_EVERYONE,
                                     Realm.WILDCARD_MENTION_POLICY_FULL_MEMBERS,
                                     Realm.WILDCARD_MENTION_POLICY_ADMINS],
            bot_creation_policy=[1, 2],
            email_address_visibility=[Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
                                      Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS,
                                      Realm.EMAIL_ADDRESS_VISIBILITY_NOBODY],
            video_chat_provider=[
                dict(
                    video_chat_provider=orjson.dumps(Realm.VIDEO_CHAT_PROVIDERS['jitsi_meet']['id']).decode(),
                ),
            ],
            message_content_delete_limit_seconds=[1000, 1100, 1200]
        )

        vals = test_values.get(name)
        if Realm.property_types[name] is bool:
            vals = bool_tests
        if vals is None:
            raise AssertionError(f'No test created for {name}')

        if name == 'video_chat_provider':
            self.set_up_db(name, vals[0][name])
            realm = self.update_with_api_multiple_value(vals[0])
            self.assertEqual(getattr(realm, name), orjson.loads(vals[0][name]))
        else:
            self.set_up_db(name, vals[0])
            realm = self.update_with_api(name, vals[1])
            self.assertEqual(getattr(realm, name), vals[1])
            realm = self.update_with_api(name, vals[0])
            self.assertEqual(getattr(realm, name), vals[0])

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
            self.send_stream_message(iago, "Scotland")
            self.send_stream_message(othello, "Scotland")
            self.send_stream_message(cordelia, "Shakespeare")
            self.send_stream_message(king, "Shakespeare")

        Attachment.objects.filter(realm=zulip).delete()
        Attachment.objects.create(realm=zulip, owner=iago, path_id="a/b/temp1.txt", size=512)
        Attachment.objects.create(realm=zulip, owner=othello, path_id="a/b/temp2.txt", size=512)

        Attachment.objects.filter(realm=lear).delete()
        Attachment.objects.create(realm=lear, owner=cordelia, path_id="c/d/temp1.txt", size=512)
        Attachment.objects.create(realm=lear, owner=king, path_id="c/d/temp2.txt", size=512)

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
