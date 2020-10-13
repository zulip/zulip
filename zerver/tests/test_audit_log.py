from datetime import timedelta
from typing import Any, Dict, Union

import orjson
from django.contrib.auth.password_validation import validate_password
from django.utils.timezone import now as timezone_now

from analytics.models import StreamCount
from zerver.lib.actions import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_activate_user,
    do_change_avatar_fields,
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
    do_change_icon_source,
    do_change_notification_settings,
    do_change_password,
    do_change_subscription_property,
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
    do_rename_stream,
    do_set_realm_authentication_methods,
    do_set_realm_message_editing,
    do_set_realm_notifications_stream,
    do_set_realm_signup_notifications_stream,
    get_last_message_id,
    get_streams_traffic,
)
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Message,
    RealmAuditLog,
    Recipient,
    Subscription,
    UserProfile,
    get_client,
    get_realm,
    get_stream,
)


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
            extra_data = orjson.loads(event.extra_data)
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
            extra_data = orjson.loads(event.extra_data)
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
        req = dict(full_name=orjson.dumps(new_name).decode())
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

        user = self.example_user('hamlet')
        stream = self.make_stream('test_stream')
        acting_user = self.example_user('iago')
        bulk_add_subscriptions(user.realm, [stream], [user], acting_user=acting_user)
        subscription_creation_logs = RealmAuditLog.objects.filter(event_type=RealmAuditLog.SUBSCRIPTION_CREATED,
                                                                  event_time__gte=now, acting_user=acting_user, modified_user=user,
                                                                  modified_stream=stream)
        self.assertEqual(subscription_creation_logs.count(), 1)
        self.assertEqual(subscription_creation_logs[0].modified_stream.id, stream.id)
        self.assertEqual(subscription_creation_logs[0].modified_user, user)

        bulk_remove_subscriptions([user], [stream], get_client("website"), acting_user=acting_user)
        subscription_deactivation_logs = RealmAuditLog.objects.filter(event_type=RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
                                                                      event_time__gte=now, acting_user=acting_user, modified_user=user,
                                                                      modified_stream=stream)
        self.assertEqual(subscription_deactivation_logs.count(), 1)
        self.assertEqual(subscription_deactivation_logs[0].modified_stream.id, stream.id)
        self.assertEqual(subscription_deactivation_logs[0].modified_user, user)

    def test_realm_activation(self) -> None:
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        log_entry = RealmAuditLog.objects.get(realm=realm, event_type=RealmAuditLog.REALM_DEACTIVATED)
        extra_data = orjson.loads(log_entry.extra_data)
        self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])

        do_reactivate_realm(realm)
        log_entry = RealmAuditLog.objects.get(realm=realm, event_type=RealmAuditLog.REALM_REACTIVATED)
        extra_data = orjson.loads(log_entry.extra_data)
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
        expected_old_value = realm.authentication_methods_dict()
        auth_method_dict = {'Google': False, 'Email': False, 'GitHub': False, 'Apple': False, 'Dev': True, 'SAML': True, 'GitLab': False}

        do_set_realm_authentication_methods(realm, auth_method_dict, acting_user=user)
        realm_audit_logs = RealmAuditLog.objects.filter(realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                                                        event_time__gte=now, acting_user=user)
        self.assertEqual(realm_audit_logs.count(), 1)
        extra_data = orjson.loads(realm_audit_logs[0].extra_data)
        expected_new_value = auth_method_dict
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

    def test_set_realm_message_editing(self) -> None:
        now = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        values_expected = [
            {
                'property': 'message_content_edit_limit_seconds',
                RealmAuditLog.OLD_VALUE: realm.message_content_edit_limit_seconds,
                RealmAuditLog.NEW_VALUE: 1000,
            },
            {
                'property': 'allow_community_topic_editing',
                RealmAuditLog.OLD_VALUE: True,
                RealmAuditLog.NEW_VALUE: False,
            },
        ]

        do_set_realm_message_editing(realm, True, 1000, False, acting_user=user)
        realm_audit_logs = RealmAuditLog.objects.filter(realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                                                        event_time__gte=now, acting_user=user).order_by("id")
        self.assertEqual(realm_audit_logs.count(), 2)
        self.assertEqual([orjson.loads(entry.extra_data) for entry in realm_audit_logs],
                         values_expected)

    def test_set_realm_notifications_stream(self) -> None:
        now = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        old_value = realm.notifications_stream_id
        stream_name = 'test'
        stream = self.make_stream(stream_name, realm)

        do_set_realm_notifications_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(
            realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time__gte=now, acting_user=user,
            extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: stream.id,
                'property': 'notifications_stream',
            }).decode()).count(), 1)

    def test_set_realm_signup_notifications_stream(self) -> None:
        now = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        old_value = realm.signup_notifications_stream_id
        stream_name = 'test'
        stream = self.make_stream(stream_name, realm)

        do_set_realm_signup_notifications_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(
            realm=realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time__gte=now, acting_user=user,
            extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: stream.id,
                'property': 'signup_notifications_stream',
            }).decode()).count(), 1)

    def test_change_icon_source(self) -> None:
        test_start = timezone_now()
        realm = get_realm('zulip')
        user = self.example_user('hamlet')
        icon_source = 'G'
        do_change_icon_source(realm, icon_source, acting_user=user)
        audit_entries = RealmAuditLog.objects.filter(
            realm=realm,
            event_type=RealmAuditLog.REALM_ICON_SOURCE_CHANGED,
            acting_user=user,
            event_time__gte=test_start)
        self.assertEqual(len(audit_entries), 1)
        self.assertEqual(icon_source, realm.icon_source)
        self.assertEqual(audit_entries.first().extra_data,
                         "{'icon_source': 'G', 'icon_version': 2}")

    def test_change_subscription_property(self) -> None:
        user = self.example_user('hamlet')
        # Fetch the Denmark stream for testing
        stream = get_stream("Denmark", user.realm)
        sub = Subscription.objects.get(user_profile=user, recipient__type=Recipient.STREAM,
                                       recipient__type_id=stream.id)
        properties = {"color": True,
                      "is_muted": True,
                      "desktop_notifications": False,
                      "audible_notifications": False,
                      "push_notifications": True,
                      "email_notifications": True,
                      "pin_to_top": True,
                      "wildcard_mentions_notify": False}

        for property, value in properties.items():
            now = timezone_now()

            old_value = getattr(sub, property)
            self.assertNotEqual(old_value, value)
            do_change_subscription_property(user, sub, stream, property, value, acting_user=user)
            expected_extra_data = {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                'property': property,
            }
            self.assertEqual(RealmAuditLog.objects.filter(
                realm=user.realm, event_type=RealmAuditLog.SUBSCRIPTION_PROPERTY_CHANGED,
                event_time__gte=now, acting_user=user, modified_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode()).count(), 1)
            self.assertEqual(getattr(sub, property), value)

    def test_change_default_streams(self) -> None:
        now = timezone_now()
        user = self.example_user('hamlet')
        stream = get_stream("Denmark", user.realm)

        old_value = user.default_sending_stream_id
        do_change_default_sending_stream(user, stream, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(
            realm=user.realm, event_type=RealmAuditLog.USER_DEFAULT_SENDING_STREAM_CHANGED,
            event_time__gte=now, acting_user=user,
            extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: stream.id,
            }).decode()).count(), 1)
        self.assertEqual(user.default_sending_stream, stream)

        old_value = user.default_events_register_stream_id
        do_change_default_events_register_stream(user, stream, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(
            realm=user.realm, event_type=RealmAuditLog.USER_DEFAULT_REGISTER_STREAM_CHANGED,
            event_time__gte=now, acting_user=user,
            extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: stream.id,
            }).decode()).count(), 1)
        self.assertEqual(user.default_events_register_stream, stream)

        old_value = user.default_all_public_streams
        do_change_default_all_public_streams(user, False, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(
            realm=user.realm, event_type=RealmAuditLog.USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED,
            event_time__gte=now, acting_user=user,
            extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: False
            }).decode()).count(), 1)
        self.assertEqual(user.default_all_public_streams, False)

    def test_rename_stream(self) -> None:
        now = timezone_now()
        user = self.example_user('hamlet')
        stream = self.make_stream('test', user.realm)
        old_name = stream.name
        do_rename_stream(stream, 'updated name', user)
        self.assertEqual(RealmAuditLog.objects.filter(
            realm=user.realm, event_type=RealmAuditLog.STREAM_NAME_CHANGED,
            event_time__gte=now, acting_user=user, modified_stream=stream,
            extra_data=orjson.dumps({
                RealmAuditLog.OLD_VALUE: old_name,
                RealmAuditLog.NEW_VALUE: 'updated name'
            }).decode()).count(), 1)
        self.assertEqual(stream.name, 'updated name')

    def test_change_notification_settings(self) -> None:
        user = self.example_user('hamlet')
        value: Union[bool, int, str]
        for setting, v in user.notification_setting_types.items():
            if setting == "notification_sound":
                value = 'ding'
            elif setting == "desktop_icon_count_display":
                value = 3
            else:
                value = False
            now = timezone_now()

            old_value = getattr(user, setting)
            do_change_notification_settings(user, setting, value, acting_user=user)
            expected_extra_data = {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                'property': setting,
            }
            self.assertEqual(RealmAuditLog.objects.filter(
                realm=user.realm, event_type=RealmAuditLog.USER_NOTIFICATION_SETTINGS_CHANGED,
                event_time__gte=now, acting_user=user, modified_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode()).count(), 1)
            self.assertEqual(getattr(user, setting), value)
