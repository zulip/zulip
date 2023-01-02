from datetime import timedelta
from typing import Any, Dict, Union

import orjson
from django.contrib.auth.password_validation import validate_password
from django.utils.timezone import now as timezone_now

from analytics.models import StreamCount
from zerver.actions.bots import (
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
)
from zerver.actions.create_user import (
    do_activate_mirror_dummy_user,
    do_create_user,
    do_reactivate_user,
)
from zerver.actions.realm_domains import (
    do_add_realm_domain,
    do_change_realm_domain,
    do_remove_realm_domain,
)
from zerver.actions.realm_emoji import check_add_realm_emoji, do_remove_realm_emoji
from zerver.actions.realm_icon import do_change_icon_source
from zerver.actions.realm_linkifiers import (
    do_add_linkifier,
    do_remove_linkifier,
    do_update_linkifier,
)
from zerver.actions.realm_playgrounds import do_add_realm_playground, do_remove_realm_playground
from zerver.actions.realm_settings import (
    do_deactivate_realm,
    do_reactivate_realm,
    do_set_realm_authentication_methods,
    do_set_realm_notifications_stream,
    do_set_realm_property,
    do_set_realm_signup_notifications_stream,
)
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_subscription_property,
    do_deactivate_stream,
    do_rename_stream,
)
from zerver.actions.user_settings import (
    do_change_avatar_fields,
    do_change_password,
    do_change_tos_version,
    do_change_user_delivery_email,
    do_change_user_setting,
    do_regenerate_api_key,
)
from zerver.actions.users import do_change_user_role, do_deactivate_user
from zerver.lib.emoji import get_emoji_file_name, get_emoji_url
from zerver.lib.message import get_last_message_id
from zerver.lib.stream_traffic import get_streams_traffic
from zerver.lib.streams import create_stream_if_needed
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_test_image_file
from zerver.lib.types import LinkifierDict, RealmPlaygroundDict
from zerver.lib.utils import assert_is_not_none
from zerver.models import (
    EmojiInfo,
    Message,
    Realm,
    RealmAuditLog,
    RealmDomainDict,
    RealmPlayground,
    Recipient,
    Subscription,
    UserProfile,
    get_realm,
    get_realm_domains,
    get_realm_playgrounds,
    get_stream,
    linkifiers_for_realm,
)


class TestRealmAuditLog(ZulipTestCase):
    def check_role_count_schema(self, role_counts: Dict[str, Any]) -> None:
        for key in [
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_GUEST,
            UserProfile.ROLE_REALM_OWNER,
        ]:
            # str(key) since json keys are always strings, and ujson.dumps will have converted
            # the UserProfile.role values into strings
            self.assertTrue(isinstance(role_counts[RealmAuditLog.ROLE_COUNT_HUMANS][str(key)], int))
        self.assertTrue(isinstance(role_counts[RealmAuditLog.ROLE_COUNT_BOTS], int))

    def test_user_activation(self) -> None:
        realm = get_realm("zulip")
        now = timezone_now()
        user = do_create_user("email", "password", realm, "full_name", acting_user=None)
        do_deactivate_user(user, acting_user=user)
        do_activate_mirror_dummy_user(user, acting_user=user)
        do_deactivate_user(user, acting_user=user)
        do_reactivate_user(user, acting_user=user)
        self.assertEqual(RealmAuditLog.objects.filter(event_time__gte=now).count(), 6)
        event_types = list(
            RealmAuditLog.objects.filter(
                realm=realm,
                acting_user=user,
                modified_user=user,
                modified_stream=None,
                event_time__gte=now,
                event_time__lte=now + timedelta(minutes=60),
            )
            .order_by("event_time")
            .values_list("event_type", flat=True)
        )
        self.assertEqual(
            event_types,
            [
                RealmAuditLog.USER_CREATED,
                RealmAuditLog.USER_DEACTIVATED,
                RealmAuditLog.USER_ACTIVATED,
                RealmAuditLog.USER_DEACTIVATED,
                RealmAuditLog.USER_REACTIVATED,
            ],
        )
        for event in RealmAuditLog.objects.filter(
            realm=realm,
            acting_user=user,
            modified_user=user,
            modified_stream=None,
            event_time__gte=now,
            event_time__lte=now + timedelta(minutes=60),
        ):
            extra_data = orjson.loads(assert_is_not_none(event.extra_data))
            self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])
            self.assertNotIn(RealmAuditLog.OLD_VALUE, extra_data)

    def test_change_role(self) -> None:
        realm = get_realm("zulip")
        now = timezone_now()
        user_profile = self.example_user("hamlet")
        acting_user = self.example_user("iago")
        do_change_user_role(
            user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=acting_user
        )
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_GUEST, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MODERATOR, acting_user=acting_user)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=acting_user)
        old_values_seen = set()
        new_values_seen = set()
        for event in RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.USER_ROLE_CHANGED,
            realm=realm,
            modified_user=user_profile,
            acting_user=acting_user,
            event_time__gte=now,
            event_time__lte=now + timedelta(minutes=60),
        ):
            extra_data = orjson.loads(assert_is_not_none(event.extra_data))
            self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])
            self.assertIn(RealmAuditLog.OLD_VALUE, extra_data)
            self.assertIn(RealmAuditLog.NEW_VALUE, extra_data)
            old_values_seen.add(extra_data[RealmAuditLog.OLD_VALUE])
            new_values_seen.add(extra_data[RealmAuditLog.NEW_VALUE])
        self.assertEqual(
            old_values_seen,
            {
                UserProfile.ROLE_GUEST,
                UserProfile.ROLE_MEMBER,
                UserProfile.ROLE_REALM_ADMINISTRATOR,
                UserProfile.ROLE_REALM_OWNER,
                UserProfile.ROLE_MODERATOR,
            },
        )
        self.assertEqual(old_values_seen, new_values_seen)

    def test_change_password(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        password = "test1"
        do_change_password(user, password)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_PASSWORD_CHANGED, event_time__gte=now
            ).count(),
            1,
        )
        # No error should be raised here
        validate_password(password, user)

    def test_change_email(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        new_email = "test@example.com"
        do_change_user_delivery_email(user, new_email)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_EMAIL_CHANGED, event_time__gte=now
            ).count(),
            1,
        )
        self.assertEqual(new_email, user.delivery_email)

        # Test the RealmAuditLog stringification
        audit_entry = RealmAuditLog.objects.get(
            event_type=RealmAuditLog.USER_EMAIL_CHANGED, event_time__gte=now
        )
        self.assertTrue(
            str(audit_entry).startswith(
                f"<RealmAuditLog: <UserProfile: {user.email} {user.realm}> {RealmAuditLog.USER_EMAIL_CHANGED} "
            )
        )

    def test_change_avatar_source(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        avatar_source = "G"
        do_change_avatar_fields(user, avatar_source, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_AVATAR_SOURCE_CHANGED,
                modified_user=user,
                acting_user=user,
                event_time__gte=now,
            ).count(),
            1,
        )
        self.assertEqual(avatar_source, user.avatar_source)

    def test_change_full_name(self) -> None:
        start = timezone_now()
        new_name = "George Hamletovich"
        self.login("iago")
        req = dict(full_name=new_name)
        result = self.client_patch("/json/users/{}".format(self.example_user("hamlet").id), req)
        self.assertTrue(result.status_code == 200)
        query = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.USER_FULL_NAME_CHANGED, event_time__gte=start
        )
        self.assertEqual(query.count(), 1)

    def test_change_tos_version(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        tos_version = "android"
        do_change_tos_version(user, tos_version)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_TERMS_OF_SERVICE_VERSION_CHANGED, event_time__gte=now
            ).count(),
            1,
        )
        self.assertEqual(tos_version, user.tos_version)

    def test_change_bot_owner(self) -> None:
        now = timezone_now()
        admin = self.example_user("iago")
        bot = self.notification_bot(admin.realm)
        bot_owner = self.example_user("hamlet")
        do_change_bot_owner(bot, bot_owner, admin)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_BOT_OWNER_CHANGED, event_time__gte=now
            ).count(),
            1,
        )
        self.assertEqual(bot_owner, bot.bot_owner)

    def test_regenerate_api_key(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        do_regenerate_api_key(user, user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_API_KEY_CHANGED, event_time__gte=now
            ).count(),
            1,
        )
        self.assertTrue(user.api_key)

    def test_get_streams_traffic(self) -> None:
        realm = get_realm("zulip")
        stream_name = "whatever"
        stream = self.make_stream(stream_name, realm)
        stream_ids = {stream.id}

        result = get_streams_traffic(stream_ids)
        self.assertEqual(result, {})

        StreamCount.objects.create(
            realm=realm,
            stream=stream,
            property="messages_in_stream:is_bot:day",
            end_time=timezone_now(),
            value=999,
        )

        result = get_streams_traffic(stream_ids)
        self.assertEqual(result, {stream.id: 999})

    def test_subscriptions(self) -> None:
        now = timezone_now()

        user = self.example_user("hamlet")
        realm = user.realm
        stream = self.make_stream("test_stream")
        acting_user = self.example_user("iago")
        bulk_add_subscriptions(user.realm, [stream], [user], acting_user=acting_user)
        subscription_creation_logs = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.SUBSCRIPTION_CREATED,
            event_time__gte=now,
            acting_user=acting_user,
            modified_user=user,
            modified_stream=stream,
        )
        modified_stream = subscription_creation_logs[0].modified_stream
        assert modified_stream is not None
        self.assertEqual(subscription_creation_logs.count(), 1)
        self.assertEqual(modified_stream.id, stream.id)
        self.assertEqual(subscription_creation_logs[0].modified_user, user)

        bulk_remove_subscriptions(realm, [user], [stream], acting_user=acting_user)
        subscription_deactivation_logs = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.SUBSCRIPTION_DEACTIVATED,
            event_time__gte=now,
            acting_user=acting_user,
            modified_user=user,
            modified_stream=stream,
        )
        modified_stream = subscription_deactivation_logs[0].modified_stream
        assert modified_stream is not None
        self.assertEqual(subscription_deactivation_logs.count(), 1)
        self.assertEqual(modified_stream.id, stream.id)
        self.assertEqual(subscription_deactivation_logs[0].modified_user, user)

    def test_realm_activation(self) -> None:
        realm = get_realm("zulip")
        user = self.example_user("desdemona")
        do_deactivate_realm(realm, acting_user=user)
        log_entry = RealmAuditLog.objects.get(
            realm=realm, event_type=RealmAuditLog.REALM_DEACTIVATED, acting_user=user
        )
        extra_data = orjson.loads(assert_is_not_none(log_entry.extra_data))
        self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])

        do_reactivate_realm(realm)
        log_entry = RealmAuditLog.objects.get(
            realm=realm, event_type=RealmAuditLog.REALM_REACTIVATED
        )
        extra_data = orjson.loads(assert_is_not_none(log_entry.extra_data))
        self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])

    def test_create_stream_if_needed(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        stream = create_stream_if_needed(
            realm,
            "test",
            invite_only=False,
            stream_description="Test description",
            acting_user=user,
        )[0]
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.STREAM_CREATED,
                event_time__gte=now,
                acting_user=user,
                modified_stream=stream,
            ).count(),
            1,
        )

    def test_deactivate_stream(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        stream_name = "test"
        stream = self.make_stream(stream_name, realm)
        do_deactivate_stream(stream, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.STREAM_DEACTIVATED,
                event_time__gte=now,
                acting_user=user,
                modified_stream=stream,
            ).count(),
            1,
        )
        self.assertEqual(stream.deactivated, True)

    def test_set_realm_authentication_methods(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        expected_old_value = realm.authentication_methods_dict()
        auth_method_dict = {
            "Google": False,
            "Email": False,
            "GitHub": False,
            "Apple": False,
            "Dev": True,
            "SAML": True,
            "GitLab": False,
            "OpenID Connect": False,
        }

        do_set_realm_authentication_methods(realm, auth_method_dict, acting_user=user)
        realm_audit_logs = RealmAuditLog.objects.filter(
            realm=realm,
            event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
            event_time__gte=now,
            acting_user=user,
        )
        self.assertEqual(realm_audit_logs.count(), 1)
        extra_data = orjson.loads(assert_is_not_none(realm_audit_logs[0].extra_data))
        expected_new_value = auth_method_dict
        self.assertEqual(extra_data[RealmAuditLog.OLD_VALUE], expected_old_value)
        self.assertEqual(extra_data[RealmAuditLog.NEW_VALUE], expected_new_value)

    def test_get_last_message_id(self) -> None:
        # get_last_message_id is a helper mainly used for RealmAuditLog
        self.assertEqual(
            get_last_message_id(),
            Message.objects.latest("id").id,
        )

        Message.objects.all().delete()

        self.assertEqual(get_last_message_id(), -1)

    def test_set_realm_message_editing(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        value_expected = {
            RealmAuditLog.OLD_VALUE: realm.message_content_edit_limit_seconds,
            RealmAuditLog.NEW_VALUE: 1000,
            "property": "message_content_edit_limit_seconds",
        }

        do_set_realm_property(realm, "message_content_edit_limit_seconds", 1000, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(value_expected).decode(),
            ).count(),
            1,
        )

        value_expected = {
            RealmAuditLog.OLD_VALUE: Realm.POLICY_EVERYONE,
            RealmAuditLog.NEW_VALUE: Realm.POLICY_ADMINS_ONLY,
            "property": "edit_topic_policy",
        }

        do_set_realm_property(
            realm, "edit_topic_policy", Realm.POLICY_ADMINS_ONLY, acting_user=user
        )
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(value_expected).decode(),
            ).count(),
            1,
        )

    def test_set_realm_notifications_stream(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        old_value = realm.notifications_stream_id
        stream_name = "test"
        stream = self.make_stream(stream_name, realm)

        do_set_realm_notifications_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: stream.id,
                        "property": "notifications_stream",
                    }
                ).decode(),
            ).count(),
            1,
        )

    def test_set_realm_signup_notifications_stream(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        old_value = realm.signup_notifications_stream_id
        stream_name = "test"
        stream = self.make_stream(stream_name, realm)

        do_set_realm_signup_notifications_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: stream.id,
                        "property": "signup_notifications_stream",
                    }
                ).decode(),
            ).count(),
            1,
        )

    def test_change_icon_source(self) -> None:
        test_start = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        icon_source = "G"
        do_change_icon_source(realm, icon_source, acting_user=user)
        audit_entries = RealmAuditLog.objects.filter(
            realm=realm,
            event_type=RealmAuditLog.REALM_ICON_SOURCE_CHANGED,
            acting_user=user,
            event_time__gte=test_start,
        )
        audit_log = audit_entries.first()
        assert audit_log is not None
        self.assert_length(audit_entries, 1)
        self.assertEqual(icon_source, realm.icon_source)
        self.assertEqual(audit_log.extra_data, "{'icon_source': 'G', 'icon_version': 2}")

    def test_change_subscription_property(self) -> None:
        user = self.example_user("hamlet")
        # Fetch the Denmark stream for testing
        stream = get_stream("Denmark", user.realm)
        sub = Subscription.objects.get(
            user_profile=user, recipient__type=Recipient.STREAM, recipient__type_id=stream.id
        )
        properties = {
            "color": True,
            "is_muted": True,
            "desktop_notifications": False,
            "audible_notifications": False,
            "push_notifications": True,
            "email_notifications": True,
            "pin_to_top": True,
            "wildcard_mentions_notify": False,
        }

        for property, value in properties.items():
            now = timezone_now()

            old_value = getattr(sub, property)
            self.assertNotEqual(old_value, value)
            do_change_subscription_property(user, sub, stream, property, value, acting_user=user)
            expected_extra_data = {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                "property": property,
            }
            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=user.realm,
                    event_type=RealmAuditLog.SUBSCRIPTION_PROPERTY_CHANGED,
                    event_time__gte=now,
                    acting_user=user,
                    modified_user=user,
                    extra_data=orjson.dumps(expected_extra_data).decode(),
                ).count(),
                1,
            )
            self.assertEqual(getattr(sub, property), value)

    def test_change_default_streams(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        stream = get_stream("Denmark", user.realm)

        old_value = user.default_sending_stream_id
        do_change_default_sending_stream(user, stream, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.USER_DEFAULT_SENDING_STREAM_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: stream.id,
                    }
                ).decode(),
            ).count(),
            1,
        )
        self.assertEqual(user.default_sending_stream, stream)

        old_value = user.default_events_register_stream_id
        do_change_default_events_register_stream(user, stream, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.USER_DEFAULT_REGISTER_STREAM_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: stream.id,
                    }
                ).decode(),
            ).count(),
            1,
        )
        self.assertEqual(user.default_events_register_stream, stream)

        old_value = user.default_all_public_streams
        do_change_default_all_public_streams(user, False, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.USER_DEFAULT_ALL_PUBLIC_STREAMS_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(
                    {RealmAuditLog.OLD_VALUE: old_value, RealmAuditLog.NEW_VALUE: False}
                ).decode(),
            ).count(),
            1,
        )
        self.assertEqual(user.default_all_public_streams, False)

    def test_rename_stream(self) -> None:
        now = timezone_now()
        user = self.example_user("hamlet")
        stream = self.make_stream("test", user.realm)
        old_name = stream.name
        do_rename_stream(stream, "updated name", user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.STREAM_NAME_CHANGED,
                event_time__gte=now,
                acting_user=user,
                modified_stream=stream,
                extra_data=orjson.dumps(
                    {RealmAuditLog.OLD_VALUE: old_name, RealmAuditLog.NEW_VALUE: "updated name"}
                ).decode(),
            ).count(),
            1,
        )
        self.assertEqual(stream.name, "updated name")

    def test_change_notification_settings(self) -> None:
        user = self.example_user("hamlet")
        value: Union[bool, int, str]
        for setting, v in user.notification_setting_types.items():
            if setting == "notification_sound":
                value = "ding"
            elif setting == "desktop_icon_count_display":
                value = 3
            else:
                value = False
            now = timezone_now()

            old_value = getattr(user, setting)
            do_change_user_setting(user, setting, value, acting_user=user)
            expected_extra_data = {
                RealmAuditLog.OLD_VALUE: old_value,
                RealmAuditLog.NEW_VALUE: value,
                "property": setting,
            }
            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=user.realm,
                    event_type=RealmAuditLog.USER_SETTING_CHANGED,
                    event_time__gte=now,
                    acting_user=user,
                    modified_user=user,
                    extra_data=orjson.dumps(expected_extra_data).decode(),
                ).count(),
                1,
            )
            self.assertEqual(getattr(user, setting), value)

    def test_realm_domain_entries(self) -> None:
        user = self.example_user("iago")
        initial_domains = get_realm_domains(user.realm)

        now = timezone_now()
        realm_domain = do_add_realm_domain(user.realm, "zulip.org", False, acting_user=user)
        added_domain = RealmDomainDict(
            domain="zulip.org",
            allow_subdomains=False,
        )
        expected_extra_data = {
            "realm_domains": initial_domains + [added_domain],
            "added_domain": added_domain,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_DOMAIN_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

        now = timezone_now()
        do_change_realm_domain(realm_domain, True, acting_user=user)
        changed_domain = RealmDomainDict(
            domain="zulip.org",
            allow_subdomains=True,
        )
        expected_extra_data = {
            "realm_domains": initial_domains + [changed_domain],
            "changed_domain": changed_domain,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_DOMAIN_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

        now = timezone_now()
        do_remove_realm_domain(realm_domain, acting_user=user)
        removed_domain = RealmDomainDict(
            domain="zulip.org",
            allow_subdomains=True,
        )
        expected_extra_data = {
            "realm_domains": initial_domains,
            "removed_domain": removed_domain,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_DOMAIN_REMOVED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

    def test_realm_playground_entries(self) -> None:
        user = self.example_user("iago")
        initial_playgrounds = get_realm_playgrounds(user.realm)
        now = timezone_now()
        playground_id = do_add_realm_playground(
            user.realm,
            acting_user=user,
            name="Python playground",
            pygments_language="Python",
            url_prefix="https://python.example.com",
        )
        added_playground = RealmPlaygroundDict(
            id=playground_id,
            name="Python playground",
            pygments_language="Python",
            url_prefix="https://python.example.com",
        )
        expected_extra_data = {
            "realm_playgrounds": initial_playgrounds + [added_playground],
            "added_playground": added_playground,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_PLAYGROUND_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

        now = timezone_now()
        realm_playground = RealmPlayground.objects.get(id=playground_id)
        do_remove_realm_playground(
            user.realm,
            realm_playground,
            acting_user=user,
        )
        removed_playground = {
            "name": "Python playground",
            "pygments_language": "Python",
            "url_prefix": "https://python.example.com",
        }
        expected_extra_data = {
            "realm_playgrounds": initial_playgrounds,
            "removed_playground": removed_playground,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_PLAYGROUND_REMOVED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

    def test_realm_linkifier_entries(self) -> None:
        user = self.example_user("iago")
        initial_linkifiers = linkifiers_for_realm(user.realm.id)
        now = timezone_now()
        linkifier_id = do_add_linkifier(
            user.realm,
            pattern="#(?P<id>[123])",
            url_format_string="https://realm.com/my_realm_filter/%(id)s",
            acting_user=user,
        )

        added_linkfier = LinkifierDict(
            pattern="#(?P<id>[123])",
            url_format="https://realm.com/my_realm_filter/%(id)s",
            id=linkifier_id,
        )
        expected_extra_data = {
            "realm_linkifiers": initial_linkifiers + [added_linkfier],
            "added_linkifier": added_linkfier,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_LINKIFIER_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

        now = timezone_now()
        do_update_linkifier(
            user.realm,
            id=linkifier_id,
            pattern="#(?P<id>[0-9]+)",
            url_format_string="https://realm.com/my_realm_filter/issues/%(id)s",
            acting_user=user,
        )
        changed_linkifier = LinkifierDict(
            pattern="#(?P<id>[0-9]+)",
            url_format="https://realm.com/my_realm_filter/issues/%(id)s",
            id=linkifier_id,
        )
        expected_extra_data = {
            "realm_linkifiers": initial_linkifiers + [changed_linkifier],
            "changed_linkifier": changed_linkifier,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_LINKIFIER_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

        now = timezone_now()
        do_remove_linkifier(
            user.realm,
            id=linkifier_id,
            acting_user=user,
        )
        removed_linkifier = {
            "pattern": "#(?P<id>[0-9]+)",
            "url_format": "https://realm.com/my_realm_filter/issues/%(id)s",
        }
        expected_extra_data = {
            "realm_linkifiers": initial_linkifiers,
            "removed_linkifier": removed_linkifier,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_LINKIFIER_REMOVED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

    def test_realm_emoji_entries(self) -> None:
        user = self.example_user("iago")
        realm_emoji_dict = user.realm.get_emoji()
        now = timezone_now()
        with get_test_image_file("img.png") as img_file:
            # Because we want to verify the IntegrityError handling
            # logic in check_add_realm_emoji rather than the primary
            # check in upload_emoji, we need to make this request via
            # that helper rather than via the API.
            realm_emoji = check_add_realm_emoji(
                realm=user.realm, name="test_emoji", author=user, image_file=img_file
            )

        added_emoji = EmojiInfo(
            id=str(realm_emoji.id),
            name="test_emoji",
            source_url=get_emoji_url(get_emoji_file_name("img.png", realm_emoji.id), user.realm_id),
            deactivated=False,
            author_id=user.id,
            still_url=None,
        )
        realm_emoji_dict[str(realm_emoji.id)] = added_emoji
        expected_extra_data = {
            "realm_emoji": dict(sorted(realm_emoji_dict.items())),
            "added_emoji": added_emoji,
        }

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_EMOJI_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )

        now = timezone_now()
        do_remove_realm_emoji(user.realm, "test_emoji", acting_user=user)

        deactivated_emoji = EmojiInfo(
            id=str(realm_emoji.id),
            name="test_emoji",
            source_url=get_emoji_url(get_emoji_file_name("img.png", realm_emoji.id), user.realm_id),
            deactivated=True,
            author_id=user.id,
            still_url=None,
        )
        realm_emoji_dict[str(realm_emoji.id)] = deactivated_emoji

        expected_extra_data = {
            "realm_emoji": dict(sorted(realm_emoji_dict.items())),
            "deactivated_emoji": deactivated_emoji,
        }

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_EMOJI_REMOVED,
                event_time__gte=now,
                acting_user=user,
                extra_data=orjson.dumps(expected_extra_data).decode(),
            ).count(),
            1,
        )
