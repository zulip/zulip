from datetime import timedelta
from typing import Any, Dict, Union

from django.contrib.auth.password_validation import validate_password
from django.utils.timezone import now as timezone_now

from analytics.models import StreamCount
from zerver.actions.bots import (
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
)
from zerver.actions.create_realm import do_create_realm
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
from zerver.actions.realm_playgrounds import check_add_realm_playground, do_remove_realm_playground
from zerver.actions.realm_settings import (
    do_deactivate_realm,
    do_reactivate_realm,
    do_set_realm_authentication_methods,
    do_set_realm_new_stream_announcements_stream,
    do_set_realm_property,
    do_set_realm_signup_announcements_stream,
    do_set_realm_zulip_update_announcements_stream,
)
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_subscription_property,
    do_deactivate_stream,
    do_rename_stream,
)
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    check_add_user_group,
    do_change_user_group_permission_setting,
    do_update_user_group_description,
    do_update_user_group_name,
    remove_subgroups_from_user_group,
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
    Message,
    NamedUserGroup,
    Realm,
    RealmAuditLog,
    RealmPlayground,
    Recipient,
    Subscription,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.linkifiers import linkifiers_for_realm
from zerver.models.realm_emoji import EmojiInfo, get_all_custom_emoji_for_realm
from zerver.models.realm_playgrounds import get_realm_playgrounds
from zerver.models.realms import RealmDomainDict, get_realm, get_realm_domains
from zerver.models.streams import get_stream


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
        self.assertEqual(RealmAuditLog.objects.filter(event_time__gte=now).count(), 8)
        event_types = list(
            RealmAuditLog.objects.filter(
                realm=realm,
                acting_user=user,
                modified_user=user,
                modified_stream=None,
                event_time__gte=now,
                event_time__lte=now + timedelta(minutes=60),
            )
            .order_by("event_time", "event_type")
            .values_list("event_type", flat=True)
        )
        self.assertEqual(
            event_types,
            [
                RealmAuditLog.USER_CREATED,
                RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                RealmAuditLog.USER_DEACTIVATED,
                RealmAuditLog.USER_ACTIVATED,
                RealmAuditLog.USER_DEACTIVATED,
                RealmAuditLog.USER_REACTIVATED,
            ],
        )
        modified_user_group_names = []
        for event in RealmAuditLog.objects.filter(
            realm=realm,
            acting_user=user,
            modified_user=user,
            modified_stream=None,
            event_time__gte=now,
            event_time__lte=now + timedelta(minutes=60),
        ):
            if event.event_type == RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED:
                self.assertDictEqual(event.extra_data, {})
                modified_user_group_names.append(assert_is_not_none(event.modified_user_group).name)
                continue
            extra_data = event.extra_data
            self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])
            self.assertNotIn(RealmAuditLog.OLD_VALUE, extra_data)

        self.assertListEqual(
            modified_user_group_names,
            [
                SystemGroups.MEMBERS,
                SystemGroups.FULL_MEMBERS,
            ],
        )

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
            extra_data = event.extra_data
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

        expected_system_user_group_names = [
            SystemGroups.ADMINISTRATORS,
            SystemGroups.MEMBERS,
            SystemGroups.FULL_MEMBERS,
            SystemGroups.EVERYONE,
            SystemGroups.MEMBERS,
            SystemGroups.FULL_MEMBERS,
            SystemGroups.OWNERS,
            SystemGroups.MEMBERS,
            SystemGroups.FULL_MEMBERS,
            SystemGroups.MODERATORS,
        ]
        user_group_modified_names = (
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                realm=realm,
                modified_user=user_profile,
                acting_user=acting_user,
                event_time__gte=now,
                event_time__lte=now + timedelta(minutes=60),
            )
            .order_by("event_time")
            .values_list("modified_user_group__name", flat=True)
        )
        self.assertListEqual(
            list(user_group_modified_names),
            [
                *expected_system_user_group_names,
                SystemGroups.MEMBERS,
                SystemGroups.FULL_MEMBERS,
            ],
        )
        user_group_modified_names = (
            RealmAuditLog.objects.filter(
                event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED,
                realm=realm,
                modified_user=user_profile,
                acting_user=acting_user,
                event_time__gte=now,
                event_time__lte=now + timedelta(minutes=60),
            )
            .order_by("event_time")
            .values_list("modified_user_group__name", flat=True)
        )
        self.assertListEqual(
            list(user_group_modified_names),
            [
                SystemGroups.MEMBERS,
                SystemGroups.FULL_MEMBERS,
                *expected_system_user_group_names,
            ],
        )

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
            repr(audit_entry).startswith(
                f"<RealmAuditLog: <UserProfile: {user.email} {user.realm!r}> {RealmAuditLog.USER_EMAIL_CHANGED} "
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

        result = get_streams_traffic(stream_ids, realm)
        self.assertEqual(result, {})

        StreamCount.objects.create(
            realm=realm,
            stream=stream,
            property="messages_in_stream:is_bot:day",
            end_time=timezone_now(),
            value=999,
        )

        result = get_streams_traffic(stream_ids, realm)
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
        extra_data = log_entry.extra_data
        self.check_role_count_schema(extra_data[RealmAuditLog.ROLE_COUNT])

        do_reactivate_realm(realm)
        log_entry = RealmAuditLog.objects.get(
            realm=realm, event_type=RealmAuditLog.REALM_REACTIVATED
        )
        extra_data = log_entry.extra_data
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
        extra_data = realm_audit_logs[0].extra_data
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
                extra_data=value_expected,
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
                extra_data=value_expected,
            ).count(),
            1,
        )

    def test_set_realm_new_stream_announcements_stream(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        old_value = realm.new_stream_announcements_stream_id
        stream_name = "test"
        stream = self.make_stream(stream_name, realm)

        do_set_realm_new_stream_announcements_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream.id,
                    "property": "new_stream_announcements_stream",
                },
            ).count(),
            1,
        )

    def test_set_realm_signup_announcements_stream(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        old_value = realm.signup_announcements_stream_id
        stream_name = "test"
        stream = self.make_stream(stream_name, realm)

        do_set_realm_signup_announcements_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream.id,
                    "property": "signup_announcements_stream",
                },
            ).count(),
            1,
        )

    def test_set_realm_zulip_update_announcements_stream(self) -> None:
        now = timezone_now()
        realm = get_realm("zulip")
        user = self.example_user("hamlet")
        old_value = realm.zulip_update_announcements_stream_id
        stream_name = "test"
        stream = self.make_stream(stream_name, realm)

        do_set_realm_zulip_update_announcements_stream(realm, stream, stream.id, acting_user=user)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream.id,
                    "property": "zulip_update_announcements_stream",
                },
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
        self.assertEqual(audit_log.extra_data, {"icon_source": "G", "icon_version": 2})

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
                    extra_data=expected_extra_data,
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
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream.id,
                },
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
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: stream.id,
                },
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
                extra_data={RealmAuditLog.OLD_VALUE: old_value, RealmAuditLog.NEW_VALUE: False},
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
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_name,
                    RealmAuditLog.NEW_VALUE: "updated name",
                },
            ).count(),
            1,
        )
        self.assertEqual(stream.name, "updated name")

    def test_change_user_settings(self) -> None:
        user = self.example_user("hamlet")
        value: Union[bool, int, str]
        test_values = dict(
            default_language="de",
            web_home_view="all_messages",
            emojiset="twitter",
            notification_sound="ding",
        )

        for setting, setting_type in user.property_types.items():
            if setting in test_values:
                value = test_values[setting]
            elif setting_type is int:
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
                    extra_data=expected_extra_data,
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
            "realm_domains": [*initial_domains, added_domain],
            "added_domain": added_domain,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_DOMAIN_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=expected_extra_data,
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
            "realm_domains": [*initial_domains, changed_domain],
            "changed_domain": changed_domain,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_DOMAIN_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=expected_extra_data,
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
                extra_data=expected_extra_data,
            ).count(),
            1,
        )

    def test_realm_playground_entries(self) -> None:
        user = self.example_user("iago")
        initial_playgrounds = get_realm_playgrounds(user.realm)
        now = timezone_now()
        playground_id = check_add_realm_playground(
            user.realm,
            acting_user=user,
            name="Python playground",
            pygments_language="Python",
            url_template="https://python.example.com{code}",
        )
        added_playground = RealmPlaygroundDict(
            id=playground_id,
            name="Python playground",
            pygments_language="Python",
            url_template="https://python.example.com{code}",
        )
        expected_extra_data = {
            "realm_playgrounds": [*initial_playgrounds, added_playground],
            "added_playground": added_playground,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_PLAYGROUND_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=expected_extra_data,
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
            "url_template": "https://python.example.com{code}",
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
                extra_data=expected_extra_data,
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
            url_template="https://realm.com/my_realm_filter/{id}",
            acting_user=user,
        )

        added_linkfier = LinkifierDict(
            pattern="#(?P<id>[123])",
            url_template="https://realm.com/my_realm_filter/{id}",
            id=linkifier_id,
        )
        expected_extra_data = {
            "realm_linkifiers": [*initial_linkifiers, added_linkfier],
            "added_linkifier": added_linkfier,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_LINKIFIER_ADDED,
                event_time__gte=now,
                acting_user=user,
                extra_data=expected_extra_data,
            ).count(),
            1,
        )

        now = timezone_now()
        do_update_linkifier(
            user.realm,
            id=linkifier_id,
            pattern="#(?P<id>[0-9]+)",
            url_template="https://realm.com/my_realm_filter/issues/{id}",
            acting_user=user,
        )
        changed_linkifier = LinkifierDict(
            pattern="#(?P<id>[0-9]+)",
            url_template="https://realm.com/my_realm_filter/issues/{id}",
            id=linkifier_id,
        )
        expected_extra_data = {
            "realm_linkifiers": [*initial_linkifiers, changed_linkifier],
            "changed_linkifier": changed_linkifier,
        }
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=user.realm,
                event_type=RealmAuditLog.REALM_LINKIFIER_CHANGED,
                event_time__gte=now,
                acting_user=user,
                extra_data=expected_extra_data,
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
            "url_template": "https://realm.com/my_realm_filter/issues/{id}",
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
                extra_data=expected_extra_data,
            ).count(),
            1,
        )

    def test_realm_emoji_entries(self) -> None:
        user = self.example_user("iago")
        realm_emoji_dict = get_all_custom_emoji_for_realm(user.realm_id)
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
                extra_data=expected_extra_data,
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
                extra_data=expected_extra_data,
            ).count(),
            1,
        )

    def test_system_user_groups_creation(self) -> None:
        now = timezone_now()
        realm = do_create_realm(string_id="test", name="foo")

        # The expected number of system user group is the total number of roles
        # from NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP in addition to
        # full_members_system_group, everyone_on_internet_system_group and
        # nobody_system_group.
        expected_system_user_group_count = len(NamedUserGroup.SYSTEM_USER_GROUP_ROLE_MAP) + 3

        system_user_group_ids = sorted(
            NamedUserGroup.objects.filter(
                realm=realm,
                is_system_group=True,
            ).values_list("id", flat=True)
        )
        self.assert_length(system_user_group_ids, expected_system_user_group_count)

        logged_system_group_ids = sorted(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.USER_GROUP_CREATED,
                event_time__gte=now,
                acting_user=None,
            ).values_list("modified_user_group_id", flat=True)
        )
        self.assertListEqual(logged_system_group_ids, system_user_group_ids)

        logged_subgroup_entries = sorted(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
                event_time__gte=now,
                acting_user=None,
            ).values_list("modified_user_group_id", "extra_data")
        )
        logged_supergroup_entries = sorted(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=RealmAuditLog.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
                event_time__gte=now,
                acting_user=None,
            ).values_list("modified_user_group_id", "extra_data")
        )
        # Excluding nobody_system_group, the rest of the user groups should have
        # a chain of subgroup memberships in between.
        self.assert_length(logged_subgroup_entries, expected_system_user_group_count - 2)
        self.assert_length(logged_supergroup_entries, expected_system_user_group_count - 2)
        for i in range(len(logged_subgroup_entries)):
            # The offset of 1 is due to nobody_system_group being skipped as
            # the first user group in the list.
            # For supergroup, we add an additional 1 because of the order we
            # put the chain together.
            expected_subgroup_id = system_user_group_ids[i + 1]
            expected_supergroup_id = system_user_group_ids[i + 2]

            supergroup_id, subgroup_extra_data = logged_subgroup_entries[i]
            subgroup_id, supergroup_extra_data = logged_supergroup_entries[i]
            self.assertEqual(subgroup_extra_data["subgroup_ids"][0], expected_subgroup_id)
            self.assertEqual(supergroup_extra_data["supergroup_ids"][0], expected_supergroup_id)
            self.assertEqual(supergroup_id, expected_supergroup_id)
            self.assertEqual(subgroup_id, expected_subgroup_id)

    def test_user_group_creation(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        now = timezone_now()
        public_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE_ON_INTERNET, realm=hamlet.realm
        )
        user_group = check_add_user_group(
            hamlet.realm,
            "empty",
            [hamlet, cordelia],
            acting_user=hamlet,
            description="lorem",
            group_settings_map={"can_mention_group": public_group},
        )

        audit_log_entries = RealmAuditLog.objects.filter(
            acting_user=hamlet,
            realm=hamlet.realm,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_CREATED,
        )
        self.assert_length(audit_log_entries, 1)
        self.assertIsNone(audit_log_entries[0].modified_user)
        self.assertEqual(audit_log_entries[0].modified_user_group, user_group)

        audit_log_entries = RealmAuditLog.objects.filter(
            acting_user=hamlet,
            realm=hamlet.realm,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
        )
        self.assert_length(audit_log_entries, 2)
        self.assertEqual(audit_log_entries[0].modified_user, hamlet)
        self.assertEqual(audit_log_entries[1].modified_user, cordelia)

    def test_change_user_group_memberships(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        now = timezone_now()
        user_group = check_add_user_group(hamlet.realm, "foo", [], acting_user=None)

        bulk_add_members_to_user_groups([user_group], [hamlet.id, cordelia.id], acting_user=hamlet)
        audit_log_entries = RealmAuditLog.objects.filter(
            acting_user=hamlet,
            realm=hamlet.realm,
            modified_user_group=user_group,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
        )
        self.assert_length(audit_log_entries, 2)
        self.assertEqual(audit_log_entries[0].modified_user, hamlet)
        self.assertEqual(audit_log_entries[1].modified_user, cordelia)

        bulk_remove_members_from_user_groups([user_group], [hamlet.id], acting_user=hamlet)
        audit_log_entries = RealmAuditLog.objects.filter(
            acting_user=hamlet,
            realm=hamlet.realm,
            modified_user_group=user_group,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED,
        )
        self.assert_length(audit_log_entries, 1)
        self.assertEqual(audit_log_entries[0].modified_user, hamlet)

    def test_change_user_group_subgroups_memberships(self) -> None:
        hamlet = self.example_user("hamlet")
        user_group = check_add_user_group(hamlet.realm, "main", [], acting_user=None)
        subgroups = [
            check_add_user_group(hamlet.realm, f"subgroup{num}", [], acting_user=hamlet)
            for num in range(3)
        ]

        now = timezone_now()
        add_subgroups_to_user_group(user_group, subgroups, acting_user=hamlet)
        # Only one audit log entry for the subgroup membership is expected.
        audit_log_entry = RealmAuditLog.objects.get(
            realm=hamlet.realm,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_ADDED,
        )
        self.assertEqual(audit_log_entry.modified_user_group, user_group)
        self.assertEqual(audit_log_entry.acting_user, hamlet)
        self.assertDictEqual(
            audit_log_entry.extra_data,
            {"subgroup_ids": [subgroup.id for subgroup in subgroups]},
        )
        audit_log_entries = RealmAuditLog.objects.filter(
            realm=hamlet.realm,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_ADDED,
        ).order_by("id")
        self.assert_length(audit_log_entries, 3)
        for i in range(3):
            self.assertEqual(audit_log_entries[i].modified_user_group, subgroups[i])
            self.assertEqual(audit_log_entries[i].acting_user, hamlet)
            self.assertDictEqual(
                audit_log_entries[i].extra_data,
                {"supergroup_ids": [user_group.id]},
            )

        remove_subgroups_from_user_group(user_group, subgroups[:2], acting_user=hamlet)
        audit_log_entry = RealmAuditLog.objects.get(
            realm=hamlet.realm,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_SUBGROUP_MEMBERSHIP_REMOVED,
        )
        self.assertEqual(audit_log_entry.modified_user_group, user_group)
        self.assertEqual(audit_log_entry.acting_user, hamlet)
        self.assertDictEqual(
            audit_log_entry.extra_data,
            {"subgroup_ids": [subgroup.id for subgroup in subgroups[:2]]},
        )
        audit_log_entries = RealmAuditLog.objects.filter(
            realm=hamlet.realm,
            event_time__gte=now,
            event_type=RealmAuditLog.USER_GROUP_DIRECT_SUPERGROUP_MEMBERSHIP_REMOVED,
        ).order_by("id")
        self.assert_length(audit_log_entries, 2)
        for i in range(2):
            self.assertEqual(audit_log_entries[i].modified_user_group, subgroups[i])
            self.assertEqual(audit_log_entries[i].acting_user, hamlet)
            self.assertDictEqual(
                audit_log_entries[i].extra_data,
                {"supergroup_ids": [user_group.id]},
            )

    def test_user_group_property_change(self) -> None:
        hamlet = self.example_user("hamlet")
        user_group = check_add_user_group(
            hamlet.realm,
            "demo",
            [],
            description="No description",
            acting_user=hamlet,
        )
        now = timezone_now()

        do_update_user_group_name(user_group, "bar", acting_user=hamlet)
        audit_log_entries = RealmAuditLog.objects.filter(
            realm=hamlet.realm,
            event_type=RealmAuditLog.USER_GROUP_NAME_CHANGED,
            event_time__gte=now,
        )
        self.assert_length(audit_log_entries, 1)
        self.assertDictEqual(
            audit_log_entries[0].extra_data,
            {
                RealmAuditLog.OLD_VALUE: "demo",
                RealmAuditLog.NEW_VALUE: "bar",
            },
        )

        do_update_user_group_description(user_group, "Foo", acting_user=hamlet)
        audit_log_entries = RealmAuditLog.objects.filter(
            realm=hamlet.realm,
            event_type=RealmAuditLog.USER_GROUP_DESCRIPTION_CHANGED,
            event_time__gte=now,
        )
        self.assert_length(audit_log_entries, 1)
        self.assertDictEqual(
            audit_log_entries[0].extra_data,
            {
                RealmAuditLog.OLD_VALUE: "No description",
                RealmAuditLog.NEW_VALUE: "Foo",
            },
        )

        old_group = user_group.can_mention_group
        new_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE_ON_INTERNET, realm=user_group.realm
        )
        self.assertNotEqual(old_group.id, new_group.id)
        do_change_user_group_permission_setting(
            user_group, "can_mention_group", new_group, acting_user=None
        )
        audit_log_entries = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.USER_GROUP_GROUP_BASED_SETTING_CHANGED,
            event_time__gte=now,
        )
        self.assert_length(audit_log_entries, 1)
        self.assertIsNone(audit_log_entries[0].acting_user)
        self.assertDictEqual(
            audit_log_entries[0].extra_data,
            {
                RealmAuditLog.OLD_VALUE: old_group.id,
                RealmAuditLog.NEW_VALUE: new_group.id,
                "property": "can_mention_group",
            },
        )
