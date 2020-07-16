from datetime import timedelta
from typing import Any, Dict

import ujson
from django.contrib.auth.password_validation import validate_password
from django.utils.timezone import now as timezone_now

from analytics.models import StreamCount
from zerver.lib.actions import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_activate_user,
    do_change_avatar_fields,
    do_change_bot_owner,
    do_change_password,
    do_change_tos_version,
    do_change_user_delivery_email,
    do_change_user_role,
    do_create_user,
    do_deactivate_realm,
    do_deactivate_stream,
    do_deactivate_user,
    do_reactivate_realm,
    do_reactivate_user,
    do_regenerate_api_key,
    do_set_realm_authentication_methods,
    get_last_message_id,
    get_streams_traffic,
)
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, RealmAuditLog, UserProfile, get_client, get_realm


class TestRealmAuditLog(ZulipTestCase):
    def check_role_count_schema(self, role_counts: Dict[str, Any]) -> None:
        for key in [UserProfile.ROLE_REALM_ADMINISTRATOR,
                    UserProfile.ROLE_MEMBER,
                    UserProfile.ROLE_GUEST,
                    UserProfile.ROLE_REALM_OWNER]:
            # str(key) since json keys are always strings, and ujson.dumps will have converted
            # the UserProfile.role values into strings
            self.assertTrue(isinstance(role_counts[RealmAuditLog.ROLE_COUNT_HUMANS][str(key)], int))
        self.assertTrue(isinstance(role_counts[RealmAuditLog.ROLE_COUNT_BOTS], int))

    def test_user_activation(self) -> None:
        realm = get_realm('zulip')
        now = timezone_now()
        user = do_create_user('email', 'password', realm, 'full_name', acting_user=None)
        do_deactivate_user(user, acting_user=user)
        do_activate_user(user, acting_user=user)
        do_deactivate_user(user, acting_user=user)
        do_reactivate_user(user, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(event_time__gte=now).count(), 5)
        event_types = list(RealmAuditLog.objects.filter(
            realm=realm, acting_user=user, modified_user=user, modified_stream=None,
            event_time__gte=now, event_time__lte=now+timedelta(minutes=60))
            .order_by('event_time').values_list('event_type', flat=True))
        self.assertEqual(event_types, [RealmAuditLog.USER_CREATED, RealmAuditLog.USER_DEACTIVATED,
                                       RealmAuditLog.USER_ACTIVATED, RealmAuditLog.USER_DEACTIVATED,
                                       RealmAuditLog.USER_REACTIVATED])
        for event in RealmAuditLog.objects.filter(
                realm=realm, acting_user=user, modified_user=user, modified_stream=None,
                event_time__gte=now, event_time__lte=now+timedelta(minutes=60)):
            extra_data = ujson.loads(event.extra_data)
            self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])
            self.assertNotIn(RealmAuditLog.OLD_VALUE, extra_data)

    def test_change_role(self) -> None:
        realm = get_realm('zulip')
        now = timezone_now()
        user_profile = self.example_user("hamlet")
        acting_user = self.example_user('iago')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_GUEST, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        old_values_seen = set()
        new_values_seen = set()
        for event in RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_ROLE_CHANGED,
                realm=realm, modified_user=user_profile, acting_user=acting_user,
                event_time__gte=now, event_time__lte=now+timedelta(minutes=60)):
            extra_data = ujson.loads(event.extra_data)
            self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])
            self.assertIn(RealmAuditLog.OLD_VALUE, extra_data)
            self.assertIn(RealmAuditLog.NEW_VALUE, extra_data)
            old_values_seen.add(extra_data[RealmAuditLog.OLD_VALUE])
            new_values_seen.add(extra_data[RealmAuditLog.NEW_VALUE])
        self.assertEqual(old_values_seen, {UserProfile.ROLE_GUEST, UserProfile.ROLE_MEMBER,
                                           UserProfile.ROLE_REALM_ADMINISTRATOR,
                                           UserProfile.ROLE_REALM_OWNER})
        self.assertEqual(old_values_seen, new_values_seen)

    def test_change_password(self) -> None:
        now = timezone_now()
        user = self.example_user('hamlet')
        password = 'test1'
        do_change_password(user, password)
        self.assertEqual(RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_PASSWORD_CHANGED,
                                                      event_time__gte=now).count(), 1)
        self.assertIsNone(validate_password(password, user))

    def test_change_email(self) -> None:
        now = timezone_now()
        user = self.example_user('hamlet')
        new_email = 'test@example.com'
        do_change_user_delivery_email(user, new_email)
        self.assertEqual(RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_EMAIL_CHANGED,
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(new_email, user.delivery_email)

        # Test the RealmAuditLog stringification
        audit_entry = RealmAuditLog.objects.get(event_type=RealmAuditLog.USER_EMAIL_CHANGED, event_time__gte=now)
        self.assertTrue(str(audit_entry).startswith(f"<RealmAuditLog: <UserProfile: {user.email} {user.realm}> {RealmAuditLog.USER_EMAIL_CHANGED} "))

    def test_change_avatar_source(self) -> None:
        now = timezone_now()
        user = self.example_user('hamlet')
        avatar_source = 'G'
        do_change_avatar_fields(user, avatar_source, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_AVATAR_SOURCE_CHANGED,
                                                      modified_user=user, acting_user=user,
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(avatar_source, user.avatar_source)

    def test_change_full_name(self) -> None:
        start = timezone_now()
        new_name = 'George Hamletovich'
        self.login('iago')
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/{}'.format(self.example_user("hamlet").id), req)
        self.assertTrue(result.status_code == 200)
        query = RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_FULL_NAME_CHANGED,
                                             event_time__gte=start)
        self.assertEqual(query.count(), 1)

    def test_change_tos_version(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        tos_version = 'android'
        do_change_tos_version(user, tos_version)
        self.assertEqual(RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_TOS_VERSION_CHANGED,
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(tos_version, user.tos_version)

    def test_change_bot_owner(self) -> None:
        now = timezone_now()
        admin = self.example_user('iago')
        bot = self.notification_bot()
        bot_owner = self.example_user('hamlet')
        do_change_bot_owner(bot, bot_owner, admin)
        self.assertEqual(RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_BOT_OWNER_CHANGED,
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(bot_owner, bot.bot_owner)

    def test_regenerate_api_key(self) -> None:
        now = timezone_now()
        user = self.example_user('hamlet')
        do_regenerate_api_key(user, user)
        self.assertEqual(RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_API_KEY_CHANGED,
                                                      event_time__gte=now).count(), 1)
        self.assertTrue(user.api_key)

    def test_get_streams_traffic(self) -> None:
        realm = get_realm('zulip')
        stream_name = 'whatever'
        stream = self.make_stream(stream_name, realm)
        stream_ids = {stream.id}

        result = get_streams_traffic(stream_ids)
        self.assertEqual(result, {})

        StreamCount.objects.create(
            realm=realm,
            stream=stream,
            property='messages_in_stream:is_bot:day',
            end_time=timezone_now(),
            value=999,
        )

        result = get_streams_traffic(stream_ids)
        self.assertEqual(result, {stream.id: 999})

    def test_subscriptions(self) -> None:
        now = timezone_now()
        user = [self.example_user('hamlet')]
        stream = [self.make_stream('test_stream')]
        acting_user = self.example_user('iago')
        bulk_add_subscriptions(stream, user, acting_user=acting_user)
        subscription_creation_logs = RealmAuditLog.objects.filter(event_type=RealmAuditLog.SUBSCRIPTION_CREATED,
                                                                  event_time__gte=now, acting_user=acting_user, modified_user=user[0],
                                                                  modified_stream=stream[0])
        self.assertEqual(subscription_creation_logs.count(), 1)
        self.assertEqual(subscription_creation_logs[0].modified_stream.id, stream[0].id)
        self.assertEqual(subscription_creation_logs[0].modified_user, user[0])

        bulk_remove_subscriptions(user, stream, get_client("website"), acting_user=acting_user)
        subscription_deactivation_logs = RealmAuditLog.objects.filter(event_type=RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
                                                                      event_time__gte=now, acting_user=acting_user, modified_user=user[0],
                                                                      modified_stream=stream[0])
        self.assertEqual(subscription_deactivation_logs.count(), 1)
        self.assertEqual(subscription_deactivation_logs[0].modified_stream.id, stream[0].id)
        self.assertEqual(subscription_deactivation_logs[0].modified_user, user[0])

    def test_realm_activation(self) -> None:
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        log_entry = RealmAuditLog.objects.get(realm=realm, event_type=RealmAuditLog.REALM_DEACTIVATED)
        extra_data = ujson.loads(log_entry.extra_data)
        self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])

        do_reactivate_realm(realm)
        log_entry = RealmAuditLog.objects.get(realm=realm, event_type=RealmAuditLog.REALM_REACTIVATED)
        extra_data = ujson.loads(log_entry.extra_data)
        self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])

    def test_create_stream_if_needed(self) -> None:
        now = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        stream = create_stream_if_needed(realm, "test", invite_only=False, stream_description="Test Description", acting_user=user)[0]
        self.assertEqual(RealmAuditLog.objects.filter(realm=realm, event_type=RealmAuditLog.STREAM_CREATED,
                                                      event_time__gte=now, acting_user=user,
                                                      modified_stream=stream).count(), 1)

    def test_deactivate_stream(self) -> None:
        now = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        stream_name = 'test'
        stream = self.make_stream(stream_name, realm)
        do_deactivate_stream(stream, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(realm=realm, event_type=RealmAuditLog.STREAM_DEACTIVATED,
                                                      event_time__gte=now, acting_user=user,
                                                      modified_stream=stream).count(), 1)
        self.assertEqual(stream.deactivated, True)

    def test_set_realm_authentication_methods(self) -> None:
        now = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        expected_old_value = {'property': 'authentication_methods', 'value': realm.authentication_methods_dict()}
        auth_method_dict = {'Google': False, 'Email': False, 'GitHub': False, 'Apple': False, 'Dev': True, 'SAML': True, 'GitLab': False}

        do_set_realm_authentication_methods(realm, auth_method_dict, acting_user=user)
        realm_audit_logs = RealmAuditLog.objects.filter(realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                                                        event_time__gte=now, acting_user=user)
        self.assertEqual(realm_audit_logs.count(), 1)
        extra_data = ujson.loads(realm_audit_logs[0].extra_data)
        expected_new_value = {'property': 'authentication_methods', 'value': auth_method_dict}
        self.assertEqual(extra_data[RealmAuditLog.OLD_VALUE], expected_old_value)
        self.assertEqual(extra_data[RealmAuditLog.NEW_VALUE], expected_new_value)

    def test_get_last_message_id(self) -> None:
        # get_last_message_id is a helper mainly used for RealmAuditLog
        self.assertEqual(
            get_last_message_id(),
            Message.objects.latest('id').id,
        )

        Message.objects.all().delete()

        self.assertEqual(get_last_message_id(), -1)
