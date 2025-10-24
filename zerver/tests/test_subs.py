import hashlib
import random
from collections.abc import Sequence
from datetime import timedelta
from io import StringIO
from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.bots import do_change_bot_owner
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.create_realm import do_create_realm
from zerver.actions.default_streams import do_add_default_stream, do_create_default_stream_group
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.realm_settings import (
    do_change_realm_permission_group_setting,
    do_change_realm_plan_type,
    do_set_realm_property,
)
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    deactivated_streams_by_old_name,
    do_change_stream_group_based_setting,
    do_change_stream_permission,
    do_deactivate_stream,
    do_set_stream_property,
    do_unarchive_stream,
)
from zerver.actions.user_groups import bulk_add_members_to_user_groups, check_add_user_group
from zerver.actions.users import do_change_user_role, do_deactivate_user
from zerver.lib.attachments import (
    validate_attachment_request,
    validate_attachment_request_for_spectator_access,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import UnreadStreamInfo, aggregate_unread_data, get_raw_unread_data
from zerver.lib.response import json_success
from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS, pick_colors
from zerver.lib.stream_subscription import (
    get_active_subscriptions_for_stream_id,
    num_subscribers_for_stream_id,
    subscriber_ids_with_stream_history_access,
)
from zerver.lib.stream_traffic import (
    get_average_weekly_stream_traffic,
    round_to_2_significant_digits,
)
from zerver.lib.streams import (
    StreamDict,
    StreamsCategorizedByPermissionsForAddingSubscribers,
    can_access_stream_metadata_user_ids,
    do_get_streams,
    ensure_stream,
    filter_stream_authorization_for_adding_subscribers,
    list_to_streams,
)
from zerver.lib.subscription_info import (
    bulk_get_subscriber_user_ids,
    gather_subscriptions,
    gather_subscriptions_helper,
    validate_user_access_to_subscribers_helper,
)
from zerver.lib.test_classes import ZulipTestCase, get_topic_messages
from zerver.lib.test_helpers import HostRequestMock, cache_tries_captured
from zerver.lib.types import UserGroupMembersData
from zerver.lib.user_groups import UserGroupMembershipDetails, get_group_setting_value_for_api
from zerver.models import (
    Attachment,
    DefaultStream,
    DefaultStreamGroup,
    Message,
    NamedUserGroup,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.streams import StreamTopicsPolicyEnum, get_default_stream_groups, get_stream
from zerver.models.users import active_non_guest_user_ids, get_user, get_user_profile_by_id_in_realm
from zerver.views.streams import compose_views

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def check_subscriptions_exists(user_profile: UserProfile, stream: Stream) -> bool:
    return (
        get_active_subscriptions_for_stream_id(stream.id, include_deactivated_users=True)
        .filter(
            user_profile=user_profile,
        )
        .exists()
    )


class TestMiscStuff(ZulipTestCase):
    def test_test_helper(self) -> None:
        cordelia = self.example_user("cordelia")
        s = self.subscribed_stream_name_list(cordelia)
        self.assertIn("* Verona", s)
        self.assertNotIn("* Denmark", s)

    def test_pick_colors(self) -> None:
        used_colors: set[str] = set()
        color_map: dict[int, str] = {}
        recipient_ids = list(range(30))
        user_color_map = pick_colors(used_colors, color_map, recipient_ids)
        self.assertEqual(
            user_color_map,
            {
                0: "#76ce90",
                1: "#fae589",
                2: "#a6c7e5",
                3: "#e79ab5",
                4: "#bfd56f",
                5: "#f4ae55",
                6: "#b0a5fd",
                7: "#addfe5",
                8: "#f5ce6e",
                9: "#c2726a",
                10: "#94c849",
                11: "#bd86e5",
                12: "#ee7e4a",
                13: "#a6dcbf",
                14: "#95a5fd",
                15: "#53a063",
                16: "#9987e1",
                17: "#e4523d",
                18: "#c2c2c2",
                19: "#4f8de4",
                20: "#c6a8ad",
                21: "#e7cc4d",
                22: "#c8bebf",
                23: "#a47462",
                # start repeating
                24: "#76ce90",
                25: "#fae589",
                26: "#a6c7e5",
                27: "#e79ab5",
                28: "#bfd56f",
                29: "#f4ae55",
            },
        )

        color_map = {98: "color98", 99: "color99"}
        used_colors = set(STREAM_ASSIGNMENT_COLORS) - {"#c6a8ad", "#9987e1"}
        recipient_ids = [99, 98, 1, 2, 3, 4]
        user_color_map = pick_colors(used_colors, color_map, recipient_ids)
        self.assertEqual(
            user_color_map,
            {98: "color98", 99: "color99", 1: "#9987e1", 2: "#c6a8ad", 3: "#e79ab5", 4: "#bfd56f"},
        )

        """
        If we are assigning colors to a user with 24+ streams, we have to start
        reusing old colors.  Our algorithm basically uses recipient_id % 24, so
        the following code reflects the worse case scenario that our new
        streams have recipient ids spaced out by exact multiples of 24.  We
        don't try to work around this edge case, since users who really depend
        on the stream colors can always just assign themselves custom colors
        for the streams that they really want to stand out.

        Even if recipient_ids were completely random, the odds of collisions
        are low, but it's often the case that bulk-adds are done for streams
        that either were or are being created at roughly the same time, so the
        recipient_ids tend to have even fewer collisions.
        """
        used_colors = set(STREAM_ASSIGNMENT_COLORS)
        color_map = {}
        recipient_ids = [2, 26, 50, 74]
        user_color_map = pick_colors(used_colors, color_map, recipient_ids)
        self.assertEqual(
            user_color_map,
            {2: "#a6c7e5", 26: "#a6c7e5", 50: "#a6c7e5", 74: "#a6c7e5"},
        )

    def test_empty_results(self) -> None:
        # These are essentially just tests to ensure line
        # coverage for codepaths that won't ever really be
        # called in practice.

        user_profile = self.example_user("cordelia")

        result = bulk_get_subscriber_user_ids(
            stream_dicts=[],
            user_profile=user_profile,
            subscribed_stream_ids=set(),
            streams_to_partially_fetch=[],
        )
        self.assertEqual(result, {})

        streams = do_get_streams(
            user_profile=user_profile,
            include_public=False,
            include_subscribed=False,
            include_all=False,
            include_default=False,
        )
        self.assertEqual(streams, [])


class RecipientTest(ZulipTestCase):
    def test_recipient(self) -> None:
        realm = get_realm("zulip")
        stream = get_stream("Verona", realm)
        recipient = Recipient.objects.get(
            type_id=stream.id,
            type=Recipient.STREAM,
        )
        self.assertEqual(repr(recipient), f"<Recipient: Verona ({stream.id}, {Recipient.STREAM})>")


class StreamAdminTest(ZulipTestCase):
    def test_make_stream_public(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.make_stream("private_stream_1", invite_only=True)
        self.make_stream("private_stream_2", invite_only=True)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        params = {
            "is_private": orjson.dumps(False).decode(),
        }
        stream_id = get_stream("private_stream_1", user_profile.realm).id
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "Channel content access is required.")

        stream = self.subscribe(user_profile, "private_stream_1")

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        params = {
            "is_private": orjson.dumps(False).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)

        realm = user_profile.realm
        stream = get_stream("private_stream_1", realm)
        self.assertFalse(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**King Hamlet|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Private, protected history** to **Public**."
        )
        self.assertEqual(messages[0].content, expected_notification)

        history_public_to_subscribers_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert history_public_to_subscribers_log is not None

        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: False,
            RealmAuditLog.NEW_VALUE: True,
            "property": "history_public_to_subscribers",
        }
        self.assertEqual(history_public_to_subscribers_log.extra_data, expected_extra_data)

        invite_only_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).order_by("-id")[1]
        assert invite_only_log is not None

        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: True,
            RealmAuditLog.NEW_VALUE: False,
            "property": "invite_only",
        }
        self.assertEqual(invite_only_log.extra_data, expected_extra_data)

        private_stream = self.make_stream("private_stream", realm=realm, invite_only=True)
        realm.moderation_request_channel = private_stream
        realm.save()
        params = {
            "is_private": orjson.dumps(False).decode(),
        }
        result = self.client_patch(f"/json/streams/{private_stream.id}", params)
        self.assert_json_error(result, "Moderation request channel must be private.")
        self.assertTrue(private_stream.invite_only)

        stream = self.subscribe(user_profile, "private_stream_3", invite_only=True)
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_public_channel_group",
            nobody_group,
            acting_user=None,
        )
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_error(result, "Insufficient permission")

        user_profile_group = check_add_user_group(
            realm, "user_profile_group", [user_profile], acting_user=user_profile
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_public_channel_group",
            user_profile_group,
            acting_user=None,
        )
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)
        stream = get_stream("private_stream_3", realm)
        self.assertFalse(stream.invite_only)

    def test_make_stream_private(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream("public_stream_1", realm=realm)
        self.make_stream("public_stream_2")

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        params = {
            "is_private": orjson.dumps(True).decode(),
        }
        stream_id = self.subscribe(user_profile, "public_stream_1").id
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)
        stream = get_stream("public_stream_1", realm)
        self.assertTrue(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**King Hamlet|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Public** to **Private, protected history**."
        )
        self.assertEqual(messages[0].content, expected_notification)

        history_public_to_subscribers_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert history_public_to_subscribers_log is not None

        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: True,
            RealmAuditLog.NEW_VALUE: False,
            "property": "history_public_to_subscribers",
        }
        self.assertEqual(history_public_to_subscribers_log.extra_data, expected_extra_data)

        invite_only_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).order_by("-id")[1]
        assert invite_only_log is not None

        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: False,
            RealmAuditLog.NEW_VALUE: True,
            "property": "invite_only",
        }
        self.assertEqual(invite_only_log.extra_data, expected_extra_data)

        default_stream = self.make_stream("default_stream", realm=realm)
        do_add_default_stream(default_stream)
        params = {
            "is_private": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{default_stream.id}", params)
        self.assert_json_error(result, "A default channel cannot be private.")
        self.assertFalse(default_stream.invite_only)

        stream = self.subscribe(user_profile, "public_stream_3")
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_private_channel_group",
            nobody_group,
            acting_user=None,
        )
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_error(result, "Insufficient permission")

        user_profile_group = check_add_user_group(
            realm, "user_profile_group", [user_profile], acting_user=user_profile
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_private_channel_group",
            user_profile_group,
            acting_user=None,
        )
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)
        stream = get_stream("public_stream_3", realm)
        self.assertTrue(stream.invite_only)

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("stream_without_notification")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

    def test_create_web_public_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        owner = self.example_user("desdemona")

        stream_names = ["new1", "new2", "new3"]
        stream_descriptions = ["des1", "des2", "des3"]
        streams_raw: list[StreamDict] = [
            {"name": stream_name, "description": stream_description, "is_web_public": True}
            for (stream_name, stream_description) in zip(
                stream_names, stream_descriptions, strict=False
            )
        ]

        request_settings_dict = dict.fromkeys(Stream.stream_permission_group_settings)

        self.assertFalse(user_profile.can_create_web_public_streams())
        self.assertTrue(owner.can_create_web_public_streams())
        # As per can_create_web_public_channel_group, only owners
        # can create web-public streams by default.
        with self.assertRaisesRegex(JsonableError, "Insufficient permission"):
            list_to_streams(
                streams_raw,
                user_profile,
                autocreate=True,
                request_settings_dict=request_settings_dict,
            )

        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            self.assertFalse(user_profile.can_create_web_public_streams())
            self.assertFalse(owner.can_create_web_public_streams())
            with self.assertRaisesRegex(JsonableError, "Web-public channels are not enabled."):
                list_to_streams(
                    streams_raw,
                    owner,
                    autocreate=True,
                    request_settings_dict=request_settings_dict,
                )

        existing_streams, new_streams = list_to_streams(
            streams_raw,
            owner,
            autocreate=True,
            request_settings_dict=request_settings_dict,
        )

        self.assert_length(new_streams, 3)
        self.assert_length(existing_streams, 0)

        actual_stream_names = {stream.name for stream in new_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in new_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in new_streams:
            self.assertTrue(stream.is_web_public)

    def test_make_stream_private_with_public_history(self) -> None:
        # Convert a public stream to a private stream with shared history
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream("public_history_stream", realm=realm)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        params = {
            "is_private": orjson.dumps(True).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        stream_id = self.subscribe(user_profile, "public_history_stream").id
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)
        stream = get_stream("public_history_stream", realm)
        self.assertTrue(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**King Hamlet|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Public** to **Private, shared history**."
        )
        self.assertEqual(messages[0].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: False,
            RealmAuditLog.NEW_VALUE: True,
            "property": "invite_only",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Convert a private stream with protected history to a private stream
        # with shared history.
        self.make_stream(
            "private_protected_stream",
            realm=realm,
            invite_only=True,
            history_public_to_subscribers=False,
        )
        params = {
            "is_private": orjson.dumps(True).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        stream_id = self.subscribe(user_profile, "private_protected_stream").id
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)
        stream = get_stream("private_protected_stream", realm)
        self.assertTrue(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**King Hamlet|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Private, protected history** to **Private, shared history**."
        )
        self.assertEqual(messages[0].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: False,
            RealmAuditLog.NEW_VALUE: True,
            "property": "history_public_to_subscribers",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("stream_without_notification")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

    def test_make_stream_web_public(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream("test_stream", realm=realm)
        stream = self.subscribe(user_profile, "test_stream")
        stream_id = stream.id

        user_profile_group = check_add_user_group(
            realm, "user_profile_group", [user_profile], acting_user=user_profile
        )
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            user_profile_group,
            acting_user=user_profile,
        )

        params = {
            "is_web_public": orjson.dumps(True).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_web_public_channel_group",
            owners_group,
            acting_user=None,
        )
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "Insufficient permission")

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_create_web_public_channel_group",
            nobody_group,
            acting_user=None,
        )
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "Insufficient permission")

        do_change_realm_permission_group_setting(
            realm,
            "can_create_web_public_channel_group",
            owners_group,
            acting_user=None,
        )
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_OWNER, acting_user=None)
        with self.settings(WEB_PUBLIC_STREAMS_ENABLED=False):
            result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "Web-public channels are not enabled.")

        bad_params = {
            "is_web_public": orjson.dumps(True).decode(),
            "is_private": orjson.dumps(True).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", bad_params)
        self.assert_json_error(result, "Invalid parameters")

        bad_params = {
            "is_web_public": orjson.dumps(True).decode(),
            "is_private": orjson.dumps(False).decode(),
            "history_public_to_subscribers": orjson.dumps(False).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", bad_params)
        self.assert_json_error(result, "Invalid parameters")

        stream = get_stream("test_stream", realm)
        self.assertFalse(stream.is_web_public)

        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)

        stream = get_stream("test_stream", realm)
        self.assertTrue(stream.is_web_public)
        self.assertFalse(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**King Hamlet|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Public** to **Web-public**."
        )
        self.assertEqual(messages[0].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: False,
            RealmAuditLog.NEW_VALUE: True,
            "property": "is_web_public",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

    def test_change_history_access_for_private_streams(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream("private_stream", realm=realm, invite_only=True)
        stream_id = self.subscribe(user_profile, "private_stream").id

        params = {
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)

        stream = get_stream("private_stream", realm)
        self.assertTrue(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**Iago|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Private, protected history** to **Private, shared history**."
        )
        self.assertEqual(messages[0].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: False,
            RealmAuditLog.NEW_VALUE: True,
            "property": "history_public_to_subscribers",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_success(result)

        stream = get_stream("private_stream", realm)
        self.assertTrue(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)

        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 2)
        expected_notification = (
            f"@_**Iago|{user_profile.id}** changed the [access permissions](/help/channel-permissions) "
            "for this channel from **Private, shared history** to **Private, protected history**."
        )
        self.assertEqual(messages[1].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: True,
            RealmAuditLog.NEW_VALUE: False,
            "property": "history_public_to_subscribers",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

    def test_updating_protected_history_and_can_create_topic_group_for_streams(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        realm = user_profile.realm
        stream = self.make_stream(
            "stream", realm, invite_only=True, history_public_to_subscribers=True
        )
        everyone_system_group = NamedUserGroup.objects.get(
            name="role:everyone", realm=realm, is_system_group=True
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name="role:moderators", realm=realm, is_system_group=True
        )
        hamletcharacters_group = NamedUserGroup.objects.get(name="hamletcharacters", realm=realm)
        anonymous_group = UserGroupMembersData(
            direct_members=[user_profile.id],
            direct_subgroups=[moderators_system_group.id],
        )

        error_msg = "Unsupported parameter combination: history_public_to_subscribers, can_create_topic_group"

        def check_stream_property_update(
            property_name: str,
            setting_value: bool | int | UserGroupMembersData,
            expect_fail: bool = False,
        ) -> None:
            params = {property_name: orjson.dumps(setting_value).decode()}
            if property_name == "can_create_topic_group":
                params = {property_name: orjson.dumps({"new": setting_value}).decode()}

            result = self.client_patch(f"/json/streams/{stream.id}", params)
            stream.refresh_from_db()

            if expect_fail:
                self.assert_json_error(result, error_msg)
                return

            self.assert_json_success(result)
            if property_name == "can_create_topic_group":
                expected_value = setting_value
                current_value = get_group_setting_value_for_api(stream.can_create_topic_group)
                self.assertEqual(expected_value, current_value)
            else:
                self.assertEqual(getattr(stream, property_name), setting_value)

        # Test changing can_create_topic_group setting for a private stream
        # with protected history.
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=False,
            is_web_public=False,
            acting_user=user_profile,
        )

        check_stream_property_update(
            "can_create_topic_group", moderators_system_group.id, expect_fail=True
        )
        check_stream_property_update(
            "can_create_topic_group", hamletcharacters_group.id, expect_fail=True
        )
        check_stream_property_update("can_create_topic_group", anonymous_group, expect_fail=True)
        check_stream_property_update("can_create_topic_group", everyone_system_group.id)

        # Test changing stream to have protected history for different
        # can_create_topic_group setting values.
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=user_profile,
        )
        # Testing for a system group.
        do_change_stream_group_based_setting(
            stream, "can_create_topic_group", moderators_system_group, acting_user=user_profile
        )
        check_stream_property_update("history_public_to_subscribers", False, expect_fail=True)

        # Testing for a user defined group.
        do_change_stream_group_based_setting(
            stream, "can_create_topic_group", hamletcharacters_group, acting_user=user_profile
        )
        check_stream_property_update("history_public_to_subscribers", False, expect_fail=True)

        # Testing for an anonymous group.
        do_change_stream_group_based_setting(
            stream, "can_create_topic_group", anonymous_group, acting_user=user_profile
        )
        check_stream_property_update("history_public_to_subscribers", False, expect_fail=True)

        # Testing for everyone group.
        do_change_stream_group_based_setting(
            stream, "can_create_topic_group", everyone_system_group, acting_user=user_profile
        )
        check_stream_property_update("history_public_to_subscribers", False)

        # Reset stream permissions.
        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=user_profile,
        )

        # Test when both "history_public_to_subscribers" and "can_create_topic_group"
        # are updated in the same request.
        # Testing for a system group.
        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
            "can_create_topic_group": orjson.dumps({"new": moderators_system_group.id}).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_error(result, error_msg)

        # Testing for a user defined group.
        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
            "can_create_topic_group": orjson.dumps({"new": hamletcharacters_group.id}).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_error(result, error_msg)

        # Testing for an anonymous group.
        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
            "can_create_topic_group": orjson.dumps({"new": anonymous_group}).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_error(result, error_msg)

        # Testing for everyone system group.
        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
            "can_create_topic_group": orjson.dumps({"new": everyone_system_group.id}).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)
        stream.refresh_from_db()
        self.assertEqual(stream.history_public_to_subscribers, False)
        self.assertEqual(stream.can_create_topic_group.id, everyone_system_group.id)

        # Stream can be set to an anonymous group if its history
        # is also made public.
        params = {
            "history_public_to_subscribers": orjson.dumps(True).decode(),
            "can_create_topic_group": orjson.dumps({"new": anonymous_group}).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)
        stream.refresh_from_db()
        self.assertEqual(stream.history_public_to_subscribers, True)
        self.assertEqual(list(stream.can_create_topic_group.direct_members.all()), [user_profile])
        self.assertEqual(
            list(stream.can_create_topic_group.direct_subgroups.all()), [moderators_system_group]
        )

        # Test with an anonymous group with no members and only
        # everyone system group as subgroup.
        anonymous_group = UserGroupMembersData(
            direct_members=[],
            direct_subgroups=[everyone_system_group.id],
        )
        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
            "can_create_topic_group": orjson.dumps({"new": anonymous_group}).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)
        stream.refresh_from_db()
        self.assertEqual(stream.history_public_to_subscribers, False)
        self.assertEqual(stream.can_create_topic_group.id, everyone_system_group.id)

    def test_stream_permission_changes_updates_updates_attachments(self) -> None:
        self.login("desdemona")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]

        owner = self.example_user("desdemona")
        realm = owner.realm
        stream = self.make_stream("test_stream", realm=realm)
        self.subscribe(owner, "test_stream")
        body = f"First message ...[zulip.txt](http://{realm.host}" + url + ")"
        msg_id = self.send_stream_message(owner, "test_stream", body, "test")
        attachment = Attachment.objects.get(messages__id=msg_id)

        self.assertFalse(stream.is_web_public)
        self.assertFalse(attachment.is_web_public)
        self.assertFalse(stream.invite_only)
        self.assertTrue(attachment.is_realm_public)

        params = {
            "is_private": orjson.dumps(True).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)

        attachment.refresh_from_db()
        stream.refresh_from_db()
        self.assertFalse(stream.is_web_public)
        self.assertFalse(attachment.is_web_public)
        self.assertTrue(stream.invite_only)
        self.assertIsNone(attachment.is_realm_public)

        cordelia = self.example_user("cordelia")
        self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
        self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
        attachment.refresh_from_db()
        self.assertFalse(attachment.is_realm_public)
        self.assertFalse(validate_attachment_request_for_spectator_access(realm, attachment))

        params = {
            "is_private": orjson.dumps(False).decode(),
            "is_web_public": orjson.dumps(True).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)

        attachment.refresh_from_db()
        stream.refresh_from_db()
        self.assertFalse(stream.invite_only)
        self.assertTrue(stream.is_web_public)
        self.assertIsNone(attachment.is_realm_public)
        self.assertIsNone(attachment.is_web_public)

        self.assertTrue(validate_attachment_request_for_spectator_access(realm, attachment))
        attachment.refresh_from_db()
        self.assertTrue(attachment.is_web_public)
        self.assertIsNone(attachment.is_realm_public)

        self.assertTrue(validate_attachment_request(cordelia, attachment.path_id)[0])
        attachment.refresh_from_db()
        self.assertTrue(attachment.is_realm_public)

        params = {
            "is_private": orjson.dumps(False).decode(),
            "is_web_public": orjson.dumps(False).decode(),
            "history_public_to_subscribers": orjson.dumps(True).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)

        attachment.refresh_from_db()
        stream.refresh_from_db()
        self.assertIsNone(attachment.is_web_public)
        self.assertFalse(stream.invite_only)
        self.assertTrue(attachment.is_realm_public)

        self.assertFalse(validate_attachment_request_for_spectator_access(realm, attachment))
        attachment.refresh_from_db()
        stream.refresh_from_db()
        self.assertFalse(attachment.is_web_public)

        # Verify moving a message to another public stream doesn't reset cache.
        new_stream = self.make_stream("new_stream", realm=realm)
        self.subscribe(owner, "new_stream")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": new_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        attachment.refresh_from_db()
        self.assertFalse(attachment.is_web_public)
        self.assertTrue(attachment.is_realm_public)

        # Verify moving a message to a private stream
        private_stream = self.make_stream(
            "private_stream", realm=realm, invite_only=True, history_public_to_subscribers=True
        )
        self.subscribe(owner, "private_stream")
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": private_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        attachment.refresh_from_db()
        self.assertFalse(attachment.is_web_public)
        self.assertIsNone(attachment.is_realm_public)

        self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
        self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
        attachment.refresh_from_db()
        self.assertFalse(attachment.is_realm_public)

        # Verify moving a message to a web-public stream
        web_public_stream = self.make_stream("web_public_stream", realm=realm, is_web_public=True)
        result = self.client_patch(
            "/json/messages/" + str(msg_id),
            {
                "stream_id": web_public_stream.id,
                "propagate_mode": "change_all",
            },
        )
        self.assert_json_success(result)
        attachment.refresh_from_db()
        self.assertIsNone(attachment.is_web_public)
        self.assertIsNone(attachment.is_realm_public)

        self.assertTrue(validate_attachment_request_for_spectator_access(realm, attachment))
        attachment.refresh_from_db()
        self.assertTrue(attachment.is_web_public)

    def test_stream_group_permission_changes_updates_updates_attachments(self) -> None:
        self.login("desdemona")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]

        owner = self.example_user("desdemona")
        realm = owner.realm
        cordelia = self.example_user("cordelia")
        private_stream_public_history = self.make_stream(
            "private_stream_public_history",
            realm=realm,
            invite_only=True,
            history_public_to_subscribers=True,
        )
        self.subscribe(owner, "private_stream_public_history")
        body = f"First message ...[zulip.txt](http://{realm.host}" + url + ")"
        msg_id = self.send_stream_message(owner, "private_stream_public_history", body, "test")
        attachment = Attachment.objects.get(messages__id=msg_id)

        self.assertFalse(private_stream_public_history.is_web_public)
        self.assertFalse(attachment.is_web_public)
        self.assertTrue(private_stream_public_history.invite_only)
        self.assertFalse(attachment.is_realm_public)

        # User should be able to see the attachment if they have
        # content access to a channel with public history.
        for setting_name in Stream.stream_permission_group_settings_requiring_content_access:
            self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
            do_change_stream_group_based_setting(
                private_stream_public_history,
                setting_name,
                UserGroupMembersData(direct_members=[cordelia.id], direct_subgroups=[]),
                acting_user=cordelia,
            )
            self.assertFalse(check_subscriptions_exists(cordelia, private_stream_public_history))
            self.assertTrue(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
            attachment.refresh_from_db()
            self.assertFalse(attachment.is_realm_public)
            nobody_group = NamedUserGroup.objects.get(
                name="role:nobody", is_system_group=True, realm_for_sharding=realm
            )
            do_change_stream_group_based_setting(
                private_stream_public_history, setting_name, nobody_group, acting_user=cordelia
            )

        fp = StringIO("zulip2!")
        fp.name = "zulip2.txt"

        result = self.client_post("/json/user_uploads", {"file": fp})
        url = self.assert_json_success(result)["url"]

        private_stream_protected_history = self.make_stream(
            "private_stream_protected_history",
            realm=realm,
            invite_only=True,
            history_public_to_subscribers=False,
        )
        self.subscribe(owner, "private_stream_protected_history")
        body = f"First message ...[zulip2.txt](http://{realm.host}" + url + ")"
        msg_id = self.send_stream_message(owner, "private_stream_protected_history", body, "test")
        attachment = Attachment.objects.get(messages__id=msg_id)

        # User should not be able to see the attachment if they have
        # content access to a private channel with protected history
        # but were not subscribed to the channel when the upload was
        # sent.
        for setting_name in Stream.stream_permission_group_settings_requiring_content_access:
            self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
            do_change_stream_group_based_setting(
                private_stream_protected_history,
                setting_name,
                UserGroupMembersData(direct_members=[cordelia.id], direct_subgroups=[]),
                acting_user=cordelia,
            )
            self.assertFalse(check_subscriptions_exists(cordelia, private_stream_protected_history))
            self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])

            # They should not have access to the upload if they are
            # subscribed to the channel but they were not subscribed at
            # the time of upload.
            self.subscribe(cordelia, "private_stream_protected_history")
            self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
            self.unsubscribe(cordelia, "private_stream_protected_history")
            attachment.refresh_from_db()

            nobody_group = NamedUserGroup.objects.get(
                name="role:nobody", is_system_group=True, realm_for_sharding=realm
            )
            do_change_stream_group_based_setting(
                private_stream_protected_history, setting_name, nobody_group, acting_user=cordelia
            )

        # User should be able to see the attachment if they have
        # content access to a private channel with protected history
        # and were subscribed to the channel when the upload was sent.
        self.subscribe(cordelia, "private_stream_protected_history")
        body = f"Second message ...[zulip2.txt](http://{realm.host}" + url + ")"
        msg_id = self.send_stream_message(owner, "private_stream_protected_history", body, "test")
        attachment = Attachment.objects.get(messages__id=msg_id)
        self.unsubscribe(cordelia, "private_stream_protected_history")
        for setting_name in Stream.stream_permission_group_settings_requiring_content_access:
            self.assertFalse(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
            do_change_stream_group_based_setting(
                private_stream_protected_history,
                setting_name,
                UserGroupMembersData(direct_members=[cordelia.id], direct_subgroups=[]),
                acting_user=cordelia,
            )
            self.assertFalse(check_subscriptions_exists(cordelia, private_stream_protected_history))
            self.assertTrue(validate_attachment_request(cordelia, attachment.path_id)[0])
            self.assertTrue(validate_attachment_request(owner, attachment.path_id)[0])
            attachment.refresh_from_db()
            self.assertFalse(attachment.is_realm_public)
            nobody_group = NamedUserGroup.objects.get(
                name="role:nobody", is_system_group=True, realm_for_sharding=realm
            )
            do_change_stream_group_based_setting(
                private_stream_protected_history, setting_name, nobody_group, acting_user=cordelia
            )

    def test_try_make_stream_public_with_private_history(self) -> None:
        # We don't support public streams with private history, so
        # changing the history_public_to_subscribers property of a
        # public stream is not possible in Zulip today
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream("public_stream", realm=realm)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        params = {
            "is_private": orjson.dumps(False).decode(),
            "history_public_to_subscribers": orjson.dumps(False).decode(),
        }
        stream_id = self.subscribe(user_profile, "public_stream").id
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "Invalid parameters")

        params = {
            "history_public_to_subscribers": orjson.dumps(False).decode(),
        }
        result = self.client_patch(f"/json/streams/{stream_id}", params)
        self.assert_json_error(result, "Invalid parameters")

        web_public_stream = self.make_stream("web_public_stream", realm=realm, is_web_public=True)
        result = self.client_patch(f"/json/streams/{web_public_stream.id}", params)
        self.assert_json_error(result, "Invalid parameters")

    def test_subscriber_ids_with_stream_history_access(self) -> None:
        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")

        stream1 = self.make_stream(
            "history_private_stream", invite_only=True, history_public_to_subscribers=False
        )
        self.subscribe(hamlet, stream1.name)
        self.subscribe(polonius, stream1.name)
        self.assertEqual(set(), subscriber_ids_with_stream_history_access(stream1))

        stream2 = self.make_stream(
            "history_public_web_private_stream",
            invite_only=True,
            is_web_public=False,
            history_public_to_subscribers=True,
        )
        self.subscribe(hamlet, stream2.name)
        self.subscribe(polonius, stream2.name)
        self.assertEqual(
            {hamlet.id, polonius.id}, subscriber_ids_with_stream_history_access(stream2)
        )

        stream3 = self.make_stream(
            "history_public_web_public_stream",
            is_web_public=True,
            history_public_to_subscribers=True,
        )
        self.subscribe(hamlet, stream3.name)
        self.subscribe(polonius, stream3.name)
        self.assertEqual(
            {hamlet.id, polonius.id}, subscriber_ids_with_stream_history_access(stream3)
        )

        stream4 = self.make_stream(
            "regular_public_stream",
        )
        self.subscribe(hamlet, stream4.name)
        self.subscribe(polonius, stream4.name)
        self.assertEqual(
            {hamlet.id, polonius.id}, subscriber_ids_with_stream_history_access(stream4)
        )

    def test_deactivate_stream_as_realm_admin(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.make_stream("new_stream_1")
        self.subscribe(user_profile, stream.name)
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        # Subscribe Cordelia to verify that the archive notification is marked as read for all subscribers.
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, stream.name)
        result = self.client_delete(f"/json/streams/{stream.id}")
        self.assert_json_success(result)
        self.assertTrue(check_subscriptions_exists(user_profile, stream))
        # Assert that a notification message was sent for the archive.
        message = self.get_last_message()
        expected_content = f"Channel #**{stream.name}** has been archived."
        self.assertEqual(message.content, expected_content)

        # Assert that the message is read.
        for um in UserMessage.objects.filter(message=message):
            self.assertTrue(um.flags & UserMessage.flags.read)

    def test_deactivate_stream_removes_default_stream(self) -> None:
        stream = self.make_stream("new_stream")
        do_add_default_stream(stream)
        self.assertEqual(1, DefaultStream.objects.filter(stream_id=stream.id).count())
        do_deactivate_stream(stream, acting_user=None)
        self.assertEqual(0, DefaultStream.objects.filter(stream_id=stream.id).count())

    def test_deactivate_stream_removes_stream_from_default_stream_groups(self) -> None:
        realm = get_realm("zulip")
        streams_to_keep = [
            ensure_stream(realm, stream_name, acting_user=None)
            for stream_name in ["stream1", "stream2"]
        ]
        streams_to_remove = [ensure_stream(realm, "stream3", acting_user=None)]
        all_streams = streams_to_keep + streams_to_remove

        def get_streams(group: DefaultStreamGroup) -> list[Stream]:
            return list(group.streams.all().order_by("name"))

        group_name = "group1"
        description = "This is group1"
        do_create_default_stream_group(realm, group_name, description, all_streams)
        default_stream_groups = get_default_stream_groups(realm)
        self.assertEqual(get_streams(default_stream_groups[0]), all_streams)

        do_deactivate_stream(streams_to_remove[0], acting_user=None)
        self.assertEqual(get_streams(default_stream_groups[0]), streams_to_keep)

    def test_deactivated_streams_by_old_name(self) -> None:
        realm = get_realm("zulip")
        stream = self.make_stream("new_stream")
        do_deactivate_stream(stream, acting_user=None)
        self.assertEqual(set(deactivated_streams_by_old_name(realm, "new_stream")), {stream})

        self.make_stream("!DEACTIVATED:old_style")  # This is left active
        old_style = self.make_stream("old_style")
        do_deactivate_stream(old_style, acting_user=None)
        old_style.name = "!!DEACTIVATED:old_style"
        old_style.save()
        self.assertEqual(set(deactivated_streams_by_old_name(realm, "old_style")), {old_style})

    def test_archived_channel_notice(self) -> None:
        desdemona = self.example_user("desdemona")
        channel = get_stream("Denmark", desdemona.realm)
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=channel.realm, is_system_group=True
        )
        self.login_user(desdemona)
        do_deactivate_stream(channel, acting_user=desdemona)
        self.assertTrue(channel.deactivated)

        param_to_notice_list = [
            ({"new_name": "New Denmark"}, f"@_**Desdemona|{desdemona.id}** renamed channel"),
            (
                {"description": "New description"},
                f"@_**Desdemona|{desdemona.id}** changed the description",
            ),
            (
                {"message_retention_days": orjson.dumps(2).decode()},
                f"@_**Desdemona|{desdemona.id}** has changed the [message retention period]",
            ),
            (
                {"can_send_message_group": orjson.dumps({"new": moderators_group.id}).decode()},
                f"@_**Desdemona|{desdemona.id}** changed the [posting permissions]",
            ),
            (
                {"is_private": orjson.dumps(False).decode()},
                f"@_**Desdemona|{desdemona.id}** changed the [access permissions]",
            ),
        ]

        for param, notice in param_to_notice_list:
            result = self.client_patch(f"/json/streams/{channel.id}", param)
            self.assert_json_success(result)
            message = self.get_last_message()
            self.assertIn(notice, message.content)

    def test_unarchive_stream_active_stream(self) -> None:
        stream = self.make_stream("new_stream")
        with self.assertRaisesRegex(JsonableError, "Channel is not currently deactivated"):
            do_unarchive_stream(stream, new_name="new_stream", acting_user=None)

    def test_unarchive_stream_existing_name(self) -> None:
        stream = self.make_stream("new_stream")
        self.make_stream("existing")
        do_deactivate_stream(stream, acting_user=None)
        with self.assertRaisesRegex(JsonableError, "Channel named existing already exists"):
            do_unarchive_stream(stream, new_name="existing", acting_user=None)

    def test_unarchive_stream_private_with_no_subscribers(self) -> None:
        stream = self.make_stream("private", invite_only=True)
        do_deactivate_stream(stream, acting_user=None)
        with self.assertRaisesRegex(JsonableError, "Channel is private and have no subscribers"):
            do_unarchive_stream(stream, new_name="private", acting_user=None)

    def test_unarchive_stream_private_and_web_public(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        aaron = self.example_user("aaron")
        prospero = self.example_user("prospero")
        zoe = self.example_user("ZOE")
        realm = hamlet.realm

        stream = self.make_stream("private", invite_only=True)
        self.subscribe(hamlet, stream.name)
        self.subscribe(cordelia, stream.name)
        do_deactivate_stream(stream, acting_user=None)
        stream = Stream.objects.get(id=stream.id)
        # Previously, archiving a channel set invite_only=True without changing is_web_public.
        # This led to archived channels potentially being in an invalid state.
        stream.is_web_public = True
        stream.save(update_fields=["is_web_public"])

        aaron_group = check_add_user_group(realm, "aaron_group", [aaron], acting_user=aaron)
        do_change_stream_group_based_setting(
            stream,
            "can_administer_channel_group",
            aaron_group,
            acting_user=aaron,
        )
        prospero_group = check_add_user_group(
            realm, "prospero_group", [prospero], acting_user=prospero
        )
        do_change_stream_group_based_setting(
            stream,
            "can_add_subscribers_group",
            prospero_group,
            acting_user=prospero,
        )
        zoe_group = check_add_user_group(realm, "zoe_group", [zoe], acting_user=hamlet)
        do_change_stream_group_based_setting(
            stream,
            "can_subscribe_group",
            zoe_group,
            acting_user=zoe,
        )
        self.subscribe(self.example_user("cordelia"), "stream_private_name1")
        with self.capture_send_event_calls(expected_num_events=3) as events:
            do_unarchive_stream(stream, new_name="private", acting_user=None)

        stream = Stream.objects.get(id=stream.id)
        self.assertFalse(stream.is_web_public)

        # Clients will get this event only if they support
        # archived_channels client capability.
        self.assertEqual(events[0]["event"]["op"], "update")
        self.assertEqual(events[0]["event"]["stream_id"], stream.id)
        self.assertEqual(events[0]["event"]["property"], "is_archived")
        self.assertEqual(events[0]["event"]["value"], False)

        # Tell all users with metadata access that the stream exists.
        # This event will only be sent to clients that do not support
        # archived_channels client capability, as clients supporting
        # archived_channels client capability will already know that
        # the stream exists.
        self.assertEqual(events[1]["event"]["op"], "create")
        self.assertEqual(events[1]["event"]["streams"][0]["name"], "private")
        self.assertEqual(events[1]["event"]["streams"][0]["stream_id"], stream.id)

        for event in [events[0], events[1]]:
            notified_user_ids = set(event["users"])
            self.assertEqual(
                notified_user_ids,
                can_access_stream_metadata_user_ids(stream),
            )
            self.assertIn(self.example_user("cordelia").id, notified_user_ids)
            # An important corner case is that all organization admins are notified.
            self.assertIn(self.example_user("iago").id, notified_user_ids)
            # The current user, Hamlet was made an admin and thus should be notified too.
            self.assertIn(aaron.id, notified_user_ids)
            # Channel admin should be notified.
            self.assertIn(self.example_user("aaron").id, notified_user_ids)
            # User belonging to `can_add_subscribers_group` should be notified.
            self.assertIn(prospero.id, notified_user_ids)
            # User belonging to `can_subscribe_group` should be notified.
            self.assertIn(zoe.id, notified_user_ids)
            # Guest user should not be notified.
            self.assertNotIn(self.example_user("polonius").id, notified_user_ids)

    def test_unarchive_stream(self) -> None:
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")

        stream = self.make_stream("new_stream", is_web_public=True)
        was_invite_only = stream.invite_only
        was_web_public = stream.is_web_public
        was_history_public = stream.history_public_to_subscribers

        self.subscribe(iago, stream.name)
        self.subscribe(cordelia, stream.name)
        do_deactivate_stream(stream, acting_user=None)

        data = {}
        data["is_archived"] = "false"
        with self.capture_send_event_calls(expected_num_events=3) as events:
            result = self.api_patch(iago, f"/api/v1/streams/{stream.id}", info=data)
            self.assert_json_success(result)

        # Clients will get this event only if they support
        # archived_channels client capability.
        self.assertEqual(events[0]["event"]["op"], "update")
        self.assertEqual(events[0]["event"]["stream_id"], stream.id)
        self.assertEqual(events[0]["event"]["property"], "is_archived")
        self.assertEqual(events[0]["event"]["value"], False)

        # Tell all users with metadata access that the stream exists.
        # This event will only be sent to clients that do not support
        # archived_channels client capability, as clients supporting
        # archived_channels client capability will already know that
        # the stream exists.
        self.assertEqual(events[1]["event"]["op"], "create")
        self.assertEqual(events[1]["event"]["streams"][0]["name"], "new_stream")
        self.assertEqual(events[1]["event"]["streams"][0]["stream_id"], stream.id)

        for event in [events[0], events[1]]:
            notified_user_ids = set(event["users"])
            self.assertCountEqual(
                notified_user_ids,
                set(active_non_guest_user_ids(stream.realm_id)),
            )
            # Guest user should not be notified.
            self.assertNotIn(self.example_user("polonius").id, notified_user_ids)

        stream = Stream.objects.get(id=stream.id)
        self.assertFalse(stream.deactivated)
        self.assertEqual(stream.invite_only, was_invite_only)
        self.assertEqual(stream.is_web_public, was_web_public)
        self.assertEqual(stream.history_public_to_subscribers, was_history_public)

        self.assertEqual(
            {iago.id, cordelia.id},
            {
                sub.user_profile_id
                for sub in get_active_subscriptions_for_stream_id(
                    stream.id, include_deactivated_users=True
                )
            },
        )

    def test_is_archived_true_does_not_archive_stream(self) -> None:
        """
        Ensure that passing `is_archived` as True does not archive the stream.
        """
        iago = self.example_user("iago")
        self.login_user(iago)
        stream = self.make_stream("test_stream", invite_only=False)
        self.subscribe(iago, stream.name)

        result = self.client_patch(
            f"/json/streams/{stream.id}", {"is_archived": orjson.dumps(True).decode()}
        )
        self.assert_json_success(result)
        stream.refresh_from_db()
        self.assertFalse(stream.deactivated)

    def test_deactivate_stream_backend_requires_existing_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.make_stream("new_stream")
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        result = self.client_delete("/json/streams/999999999")
        self.assert_json_error(result, "Invalid channel ID")

    def test_private_stream_live_updates(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        self.make_stream("private_stream", invite_only=True)
        self.subscribe(user_profile, "private_stream")
        self.subscribe(self.example_user("cordelia"), "private_stream")

        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = get_stream("private_stream", user_profile.realm).id
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"description": "Test description"},
            )
        self.assert_json_success(result)

        cordelia = self.example_user("cordelia")
        prospero = self.example_user("prospero")

        notified_user_ids = set(events[0]["users"])
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(cordelia.id, notified_user_ids)
        self.assertNotIn(prospero.id, notified_user_ids)

        # Two events should be sent: a name event and a notification event
        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = get_stream("private_stream", user_profile.realm).id
            result = self.client_patch(f"/json/streams/{stream_id}", {"new_name": "whatever"})
        self.assert_json_success(result)

        notified_user_ids = set(events[0]["users"])
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(cordelia.id, notified_user_ids)
        self.assertNotIn(prospero.id, notified_user_ids)

        notified_with_bot_users = events[-1]["users"]
        notified_with_bot_user_ids = []
        notified_with_bot_user_ids.append(notified_with_bot_users[0]["id"])
        notified_with_bot_user_ids.append(notified_with_bot_users[1]["id"])
        self.assertIn(user_profile.id, notified_with_bot_user_ids)
        self.assertIn(cordelia.id, notified_with_bot_user_ids)
        self.assertNotIn(prospero.id, notified_with_bot_user_ids)

    def test_rename_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        realm = user_profile.realm
        stream = self.subscribe(user_profile, "stream_name")

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "stream_name1"})
        self.assert_json_success(result)

        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "stream_name1"})
        self.assert_json_error(result, "Channel already has that name.")
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "Denmark"})
        self.assert_json_error(result, "Channel 'Denmark' already exists", status_code=409)
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "denmark "})
        self.assert_json_error(result, "Channel 'denmark' already exists", status_code=409)

        # Do a rename that is case-only--this should succeed.
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "sTREAm_name1"})
        self.assert_json_success(result)

        def get_notified_user_ids() -> set[int]:
            # Two events should be sent: stream_name update and notification message.
            with self.capture_send_event_calls(expected_num_events=2) as events:
                stream_id = get_stream("stream_name1", user_profile.realm).id
                result = self.client_patch(
                    f"/json/streams/{stream_id}", {"new_name": "stream_name2"}
                )
            self.assert_json_success(result)
            event = events[0]["event"]
            self.assertEqual(
                event,
                dict(
                    op="update",
                    type="stream",
                    property="name",
                    value="stream_name2",
                    stream_id=stream_id,
                    name="sTREAm_name1",
                ),
            )
            self.assertRaises(Stream.DoesNotExist, get_stream, "stream_name1", realm)

            stream_name2_exists = get_stream("stream_name2", realm)
            self.assertTrue(stream_name2_exists)

            self.client_patch(f"/json/streams/{stream_id}", {"new_name": "stream_name1"})
            return set(events[0]["users"])

        stream_name_1 = get_stream("stream_name1", user_profile.realm)
        notified_user_ids = get_notified_user_ids()
        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        self.assertNotIn(self.example_user("polonius").id, notified_user_ids)

        # Guest with metadata access should be notified, but the
        # can_add_subscribers_group setting has
        # allow_everyone_group=False, so should not grant guests
        # metadata access.
        guest_group = check_add_user_group(
            realm, "guest_group", [self.example_user("polonius")], acting_user=user_profile
        )
        do_change_stream_group_based_setting(
            stream_name_1,
            "can_add_subscribers_group",
            guest_group,
            acting_user=self.example_user("polonius"),
        )
        notified_user_ids = get_notified_user_ids()
        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        self.assertNotIn(self.example_user("polonius").id, notified_user_ids)
        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm_for_sharding=realm
        )
        do_change_stream_group_based_setting(
            stream_name_1,
            "can_add_subscribers_group",
            nobody_group,
            acting_user=user_profile,
        )

        # Subscribed guest user should be notified.
        self.subscribe(self.example_user("polonius"), stream_name_1.name)
        notified_user_ids = get_notified_user_ids()
        expected_notified_user_ids = set(active_non_guest_user_ids(realm.id))
        expected_notified_user_ids.add(self.example_user("polonius").id)
        self.assertEqual(notified_user_ids, expected_notified_user_ids)
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        self.assertIn(self.example_user("polonius").id, notified_user_ids)

        # Test case to handle Unicode stream name change
        # *NOTE: Here encoding is needed when Unicode string is passed as an argument*
        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = stream_name_1.id
            result = self.client_patch(f"/json/streams/{stream_id}", {"new_name": "नया नाम"})
        self.assert_json_success(result)
        # While querying, system can handle Unicode strings.
        stream_name_uni_exists = get_stream("नया नाम", realm)
        self.assertTrue(stream_name_uni_exists)

        # Test case to handle changing of Unicode stream name to newer name
        # NOTE: Unicode string being part of URL is handled cleanly
        # by client_patch call, encoding of URL is not needed.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = stream_name_uni_exists.id
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"new_name": "नाम में क्या रक्खा हे"},
            )
        self.assert_json_success(result)
        # While querying, system can handle Unicode strings.
        self.assertRaises(Stream.DoesNotExist, get_stream, "नया नाम", realm)

        stream_name_new_uni_exists = get_stream("नाम में क्या रक्खा हे", realm)
        self.assertTrue(stream_name_new_uni_exists)

        # Test case to change name from one language to other.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = stream_name_new_uni_exists.id
            result = self.client_patch(f"/json/streams/{stream_id}", {"new_name": "français"})
        self.assert_json_success(result)
        stream_name_fr_exists = get_stream("français", realm)
        self.assertTrue(stream_name_fr_exists)

        # Test case to change name to mixed language name.
        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = stream_name_fr_exists.id
            result = self.client_patch(f"/json/streams/{stream_id}", {"new_name": "français name"})
        self.assert_json_success(result)
        stream_name_mixed_exists = get_stream("français name", realm)
        self.assertTrue(stream_name_mixed_exists)

        # Test case for notified users in private streams.
        stream_private = self.make_stream(
            "stream_private_name1", realm=user_profile.realm, invite_only=True
        )
        aaron = self.example_user("aaron")
        aaron_group = check_add_user_group(realm, "aaron_group", [aaron], acting_user=user_profile)
        do_change_stream_group_based_setting(
            stream_private,
            "can_administer_channel_group",
            aaron_group,
            acting_user=aaron,
        )
        prospero = self.example_user("prospero")
        prospero_group = check_add_user_group(
            realm, "prospero_group", [self.example_user("prospero")], acting_user=user_profile
        )
        do_change_stream_group_based_setting(
            stream_private,
            "can_add_subscribers_group",
            prospero_group,
            acting_user=prospero,
        )
        zoe = self.example_user("ZOE")
        zoe_group = check_add_user_group(realm, "zoe_group", [zoe], acting_user=user_profile)
        do_change_stream_group_based_setting(
            stream_private,
            "can_subscribe_group",
            zoe_group,
            acting_user=zoe,
        )
        self.subscribe(self.example_user("cordelia"), "stream_private_name1")
        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = get_stream("stream_private_name1", realm).id
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"new_name": "stream_private_name2"},
            )
        self.assert_json_success(result)
        notified_user_ids = set(events[0]["users"])
        self.assertEqual(notified_user_ids, can_access_stream_metadata_user_ids(stream_private))
        self.assertIn(self.example_user("cordelia").id, notified_user_ids)
        # An important corner case is that all organization admins are notified.
        self.assertIn(self.example_user("iago").id, notified_user_ids)
        # The current user, Hamlet was made an admin and thus should be notified too.
        self.assertIn(user_profile.id, notified_user_ids)
        # Channel admin should be notified.
        self.assertIn(self.example_user("aaron").id, notified_user_ids)
        # User belonging to `can_add_subscribers_group` should be notified.
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        # User belonging to `can_subscribe_group` should be notified.
        self.assertIn(self.example_user("ZOE").id, notified_user_ids)

    def test_notify_on_stream_rename(self) -> None:
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        self.make_stream("stream_name1")

        stream = self.subscribe(user_profile, "stream_name1")
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "stream_name2"})
        self.assert_json_success(result)

        # Inspect the notification message sent
        message = self.get_last_message()
        actual_stream = Stream.objects.get(id=message.recipient.type_id)
        message_content = f"@_**King Hamlet|{user_profile.id}** renamed channel **stream_name1** to **stream_name2**."
        self.assertEqual(actual_stream.name, "stream_name2")
        self.assertEqual(actual_stream.realm_id, user_profile.realm_id)
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.content, message_content)
        self.assertEqual(message.sender.email, "notification-bot@zulip.com")
        self.assertEqual(message.sender.realm, get_realm(settings.SYSTEM_BOT_REALM))

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("stream_without_notification")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"new_name": "stream_without_notification2"},
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

    def test_realm_admin_can_update_unsub_private_stream(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")

        self.login_user(iago)
        result = self.subscribe_via_post(
            iago,
            ["private_stream"],
            dict(principals=orjson.dumps([hamlet.id]).decode()),
            invite_only=True,
        )
        self.assert_json_success(result)

        stream_id = get_stream("private_stream", iago.realm).id
        result = self.client_patch(f"/json/streams/{stream_id}", {"new_name": "new_private_stream"})
        self.assert_json_success(result)

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": "new description"},
        )
        self.assert_json_success(result)

        # But cannot change stream type.
        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {
                "is_private": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_error(result, "Channel content access is required.")

    def test_non_admin_cannot_access_unsub_private_stream(self) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm_for_sharding=hamlet.realm
        )

        self.login_user(hamlet)
        result = self.subscribe_via_post(
            hamlet,
            ["private_stream_1"],
            dict(
                principals=orjson.dumps([iago.id]).decode(),
                can_administer_channel_group=nobody_group.id,
            ),
            invite_only=True,
        )
        self.assert_json_success(result)

        stream_id = get_stream("private_stream_1", hamlet.realm).id

        result = self.client_patch(f"/json/streams/{stream_id}", {"new_name": "private_stream_2"})
        self.assert_json_error(result, "Invalid channel ID")

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": "new description"},
        )
        self.assert_json_error(result, "Invalid channel ID")

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {
                "is_private": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_error(result, "Invalid channel ID")

        result = self.client_delete(f"/json/streams/{stream_id}")
        self.assert_json_error(result, "Invalid channel ID")

    def test_change_stream_description(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.subscribe(user_profile, "stream_name1")

        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = get_stream("stream_name1", realm).id
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"description": "Test description"},
            )
        self.assert_json_success(result)

        event = events[0]["event"]
        self.assertEqual(
            event,
            dict(
                op="update",
                type="stream",
                property="description",
                value="Test description",
                rendered_description="<p>Test description</p>",
                stream_id=stream_id,
                name="stream_name1",
            ),
        )
        notified_user_ids = set(events[0]["users"])

        stream = get_stream("stream_name1", realm)
        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        self.assertNotIn(self.example_user("polonius").id, notified_user_ids)
        self.assertEqual("Test description", stream.description)

        result = self.client_patch(f"/json/streams/{stream_id}", {"description": "a" * 1025})
        self.assert_json_error(
            result,
            f"description is too long (limit: {Stream.MAX_DESCRIPTION_LENGTH} characters)",
        )

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": ""},
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.description, "")

        messages = get_topic_messages(user_profile, stream, "channel events")
        expected_notification = (
            f"@_**{user_profile.full_name}|{user_profile.id}** changed the description for this channel.\n\n"
            "* **Old description:**\n"
            "```` quote\n"
            "Test description\n"
            "````\n"
            "* **New description:**\n"
            "```` quote\n"
            "*No description.*\n"
            "````"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": "Test description"},
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.description, "Test description")

        messages = get_topic_messages(user_profile, stream, "channel events")
        expected_notification = (
            f"@_**{user_profile.full_name}|{user_profile.id}** changed the description for this channel.\n\n"
            "* **Old description:**\n"
            "```` quote\n"
            "*No description.*\n"
            "````\n"
            "* **New description:**\n"
            "```` quote\n"
            "Test description\n"
            "````"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": "a\nmulti\nline\ndescription"},
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.description, "a multi line description")

        messages = get_topic_messages(user_profile, stream, "channel events")
        expected_notification = (
            f"@_**{user_profile.full_name}|{user_profile.id}** changed the description for this channel.\n\n"
            "* **Old description:**\n"
            "```` quote\n"
            "Test description\n"
            "````\n"
            "* **New description:**\n"
            "```` quote\n"
            "a multi line description\n"
            "````"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: "Test description",
            RealmAuditLog.NEW_VALUE: "a multi line description",
            "property": "description",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("stream_without_notification")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"description": "New Description"},
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

        # Verify that we don't render inline URL previews in this code path.
        with self.settings(INLINE_URL_EMBED_PREVIEW=True):
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"description": "See https://zulip.com/team/"},
            )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(
            stream.rendered_description,
            '<p>See <a href="https://zulip.com/team/">https://zulip.com/team/</a></p>',
        )

        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        result = self.client_patch(
            f"/json/streams/{stream_id}", {"description": "Test description"}
        )
        self.assert_json_success(result)

        # Verify that we render topic permalinks in the description depending
        # on whether the acting_user has access to that channel.
        hamlet = self.example_user("hamlet")
        core_stream = self.make_stream("core", realm, True, history_public_to_subscribers=True)

        self.subscribe(hamlet, "core")
        msg_id = self.send_stream_message(hamlet, "core", topic_name="testing")

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": "#**core>testing**"},
        )

        stream = get_stream("stream_name1", realm)

        # permalink is not rendered since acting_user has no access to channel.
        self.assertEqual(
            stream.rendered_description,
            "<p>#<strong>core&gt;testing</strong></p>",
        )

        self.subscribe(user_profile, "core")

        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"description": "#**core>testing**"},
        )

        stream = get_stream("stream_name1", realm)

        # permalink is rendered since acting_user now has access to channel.
        self.assertEqual(
            stream.rendered_description,
            f'<p><a class="stream-topic" data-stream-id="{core_stream.id}" href="/#narrow/channel/{core_stream.id}-core/topic/testing/with/{msg_id}">#{core_stream.name} &gt; testing</a></p>',
        )

    def test_change_stream_message_retention_days_notifications(self) -> None:
        user_profile = self.example_user("desdemona")
        self.login_user(user_profile)
        realm = user_profile.realm
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_SELF_HOSTED, acting_user=None)
        stream = self.subscribe(user_profile, "stream_name1")

        # Go from realm default (forever) to 2 days
        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(2).decode()}
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 1)
        expected_notification = (
            f"@_**Desdemona|{user_profile.id}** has changed the [message retention period](/help/message-retention-policy) for this channel:\n"
            "* **Old retention period**: Forever\n"
            "* **New retention period**: 2 days\n\n"
            "Messages in this channel will now be automatically deleted 2 days after they are sent."
        )
        self.assertEqual(messages[0].content, expected_notification)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_MESSAGE_RETENTION_DAYS_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {RealmAuditLog.OLD_VALUE: None, RealmAuditLog.NEW_VALUE: 2}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Go from 2 days to 8 days
        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(8).decode()}
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 2)
        expected_notification = (
            f"@_**Desdemona|{user_profile.id}** has changed the [message retention period](/help/message-retention-policy) for this channel:\n"
            "* **Old retention period**: 2 days\n"
            "* **New retention period**: 8 days\n\n"
            "Messages in this channel will now be automatically deleted 8 days after they are sent."
        )
        self.assertEqual(messages[1].content, expected_notification)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_MESSAGE_RETENTION_DAYS_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {RealmAuditLog.OLD_VALUE: 2, RealmAuditLog.NEW_VALUE: 8}
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Go from 8 days to realm default (None on stream, forever/-1 on realm)
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"message_retention_days": orjson.dumps("realm_default").decode()},
        )
        self.assert_json_success(result)
        messages = get_topic_messages(user_profile, stream, "channel events")
        self.assert_length(messages, 3)
        expected_notification = (
            f"@_**Desdemona|{user_profile.id}** has changed the [message retention period](/help/message-retention-policy) for this channel:\n"
            "* **Old retention period**: 8 days\n"
            "* **New retention period**: Forever\n\n"
            "Messages in this channel will now be retained forever."
        )
        self.assertEqual(messages[2].content, expected_notification)
        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_MESSAGE_RETENTION_DAYS_CHANGED
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: 8,
            RealmAuditLog.NEW_VALUE: None,
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("stream_without_notification")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"message_retention_days": orjson.dumps(2).decode()},
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

    def test_change_stream_message_retention_days(self) -> None:
        user_profile = self.example_user("desdemona")
        self.login_user(user_profile)
        realm = user_profile.realm
        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=None)
        stream = self.subscribe(user_profile, "stream_name1")

        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(2).decode()}
        )
        self.assert_json_error(result, "Available on Zulip Cloud Standard. Upgrade to access.")

        do_change_realm_plan_type(realm, Realm.PLAN_TYPE_SELF_HOSTED, acting_user=None)
        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.client_patch(
                f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(2).decode()}
            )
        self.assert_json_success(result)

        event = events[0]["event"]
        self.assertEqual(
            event,
            dict(
                op="update",
                type="stream",
                property="message_retention_days",
                value=2,
                stream_id=stream.id,
                name="stream_name1",
            ),
        )
        notified_user_ids = set(events[0]["users"])
        stream = get_stream("stream_name1", realm)

        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        self.assertNotIn(self.example_user("polonius").id, notified_user_ids)
        self.assertEqual(stream.message_retention_days, 2)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.client_patch(
                f"/json/streams/{stream.id}",
                {"message_retention_days": orjson.dumps("unlimited").decode()},
            )
        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(
            event,
            dict(
                op="update",
                type="stream",
                property="message_retention_days",
                value=-1,
                stream_id=stream.id,
                name="stream_name1",
            ),
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.message_retention_days, -1)

        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.client_patch(
                f"/json/streams/{stream.id}",
                {"message_retention_days": orjson.dumps("realm_default").decode()},
            )
        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(
            event,
            dict(
                op="update",
                type="stream",
                property="message_retention_days",
                value=None,
                stream_id=stream.id,
                name="stream_name1",
            ),
        )
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.message_retention_days, None)

        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"message_retention_days": orjson.dumps("invalid").decode()},
        )
        self.assert_json_error(result, "Bad value for 'message_retention_days': invalid")

        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(-1).decode()}
        )
        self.assert_json_error(result, "Bad value for 'message_retention_days': -1")

        result = self.client_patch(
            f"/json/streams/{stream.id}", {"message_retention_days": orjson.dumps(0).decode()}
        )
        self.assert_json_error(result, "Bad value for 'message_retention_days': 0")

    def do_test_change_stream_permission_setting(self, setting_name: str) -> None:
        user_profile = self.example_user("iago")
        realm = user_profile.realm
        stream = self.subscribe(user_profile, "stream_name1")

        permission_config = Stream.stream_permission_group_settings[setting_name]

        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm_for_sharding=realm
        )
        moderators_system_group = NamedUserGroup.objects.get(
            name="role:moderators", realm_for_sharding=realm, is_system_group=True
        )
        params = {}

        self.login("iago")
        params[setting_name] = orjson.dumps({"new": moderators_system_group.id}).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(getattr(stream, setting_name).id, moderators_system_group.id)

        hamletcharacters_group = NamedUserGroup.objects.get(
            name="hamletcharacters", realm_for_sharding=realm
        )
        params[setting_name] = orjson.dumps({"new": hamletcharacters_group.id}).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(getattr(stream, setting_name).id, hamletcharacters_group.id)

        # Test changing it to anonymous group.
        hamlet = self.example_user("hamlet")

        # Test passing incorrect old value.
        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [hamlet.id],
                    "direct_subgroups": [moderators_system_group.id],
                },
                "old": moderators_system_group.id,
            }
        ).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_error(result, "'old' value does not match the expected value.")

        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [hamlet.id],
                    "direct_subgroups": [moderators_system_group.id],
                },
                "old": hamletcharacters_group.id,
            }
        ).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(list(getattr(stream, setting_name).direct_members.all()), [hamlet])
        self.assertEqual(
            list(getattr(stream, setting_name).direct_subgroups.all()),
            [moderators_system_group],
        )

        owners_group = NamedUserGroup.objects.get(
            name="role:owners", is_system_group=True, realm_for_sharding=realm
        )
        params[setting_name] = orjson.dumps({"new": owners_group.id}).decode()
        result = self.client_patch(f"/json/streams/{stream.id}", params)
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(getattr(stream, setting_name).id, owners_group.id)

        params[setting_name] = orjson.dumps({"new": nobody_group.id}).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(getattr(stream, setting_name).id, nobody_group.id)

        everyone_group = NamedUserGroup.objects.get(
            name="role:everyone", is_system_group=True, realm_for_sharding=realm
        )
        params[setting_name] = orjson.dumps({"new": everyone_group.id}).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        if permission_config.allow_everyone_group:
            self.assert_json_success(result)
            stream = get_stream("stream_name1", realm)
            self.assertEqual(getattr(stream, setting_name).id, everyone_group.id)
        else:
            self.assert_json_error(
                result,
                f"'{setting_name}' setting cannot be set to 'role:everyone' group.",
            )

        internet_group = NamedUserGroup.objects.get(
            name="role:internet", is_system_group=True, realm_for_sharding=realm
        )
        params[setting_name] = orjson.dumps({"new": internet_group.id}).decode()
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            params,
        )
        self.assert_json_error(
            result,
            f"'{setting_name}' setting cannot be set to 'role:internet' group.",
        )

    def test_changing_stream_permission_settings(self) -> None:
        self.make_stream("stream_name1")

        for setting_name in Stream.stream_permission_group_settings:
            self.do_test_change_stream_permission_setting(setting_name)

    def test_change_topics_policy(self) -> None:
        user_profile = self.example_user("iago")
        self.login_user(user_profile)
        realm = user_profile.realm
        self.subscribe(user_profile, "stream_name1")

        allow_empty_topic = StreamTopicsPolicyEnum.allow_empty_topic.name

        with self.capture_send_event_calls(expected_num_events=2) as events:
            stream_id = get_stream("stream_name1", realm).id
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"topics_policy": allow_empty_topic},
            )
        self.assert_json_success(result)

        event = events[0]["event"]
        self.assertEqual(
            event,
            dict(
                op="update",
                type="stream",
                property="topics_policy",
                value=allow_empty_topic,
                stream_id=stream_id,
                name="stream_name1",
            ),
        )
        notified_user_ids = set(events[0]["users"])

        stream = get_stream("stream_name1", realm)
        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(self.example_user("prospero").id, notified_user_ids)
        self.assertNotIn(self.example_user("polonius").id, notified_user_ids)
        self.assertEqual(StreamTopicsPolicyEnum.allow_empty_topic.value, stream.topics_policy)

        messages = get_topic_messages(user_profile, stream, "channel events")
        expected_notification = f'@_**{user_profile.full_name}|{user_profile.id}** changed the "Allow posting to the *general chat* topic?" setting from **Automatic** to ***general chat* topic allowed**.'
        self.assertEqual(messages[-1].content, expected_notification)

        realm_audit_log = RealmAuditLog.objects.filter(
            event_type=AuditLogEventType.CHANNEL_PROPERTY_CHANGED,
            modified_stream=stream,
        ).last()
        assert realm_audit_log is not None
        expected_extra_data = {
            RealmAuditLog.OLD_VALUE: StreamTopicsPolicyEnum.inherit.value,
            RealmAuditLog.NEW_VALUE: StreamTopicsPolicyEnum.allow_empty_topic.value,
            "property": "topics_policy",
        }
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Trying to update topics_policy with old value should be noop.
        with self.capture_send_event_calls(expected_num_events=0) as events:
            stream_id = get_stream("stream_name1", realm).id
            result = self.client_patch(
                f"/json/streams/{stream_id}",
                {"topics_policy": allow_empty_topic},
            )
        self.assert_json_success(result)
        self.assertEqual(realm_audit_log.extra_data, expected_extra_data)

        # Test to check if providing invalid topics_policy results in error.
        result = self.client_patch(
            f"/json/streams/{stream_id}",
            {"topics_policy": 2},
        )
        self.assert_json_error(result, "Invalid topics_policy")

        desdemona = self.example_user("desdemona")
        self.login("desdemona")

        new_stream_name = "TestStream"
        new_stream = self.make_stream(new_stream_name, desdemona.realm)
        self.subscribe(desdemona, new_stream_name)
        self.send_stream_message(desdemona, new_stream_name, "test content", "")

        result = self.client_patch(
            f"/json/streams/{new_stream.id}",
            {"topics_policy": StreamTopicsPolicyEnum.allow_empty_topic.name},
        )
        self.assert_json_success(result)

        # Cannot set `topics_policy` to `empty_topic_only` when there are messages
        # in non-empty topics in the current channel.
        result = self.client_patch(
            f"/json/streams/{new_stream.id}",
            {"topics_policy": StreamTopicsPolicyEnum.empty_topic_only.name},
        )
        self.assert_json_error(
            result,
            "To enable this configuration, all messages in this channel must be in the general chat topic. Consider renaming or deleting other topics.",
        )

        topic_messages = Message.objects.filter(
            realm=desdemona.realm,
            recipient=new_stream.recipient,
        )
        do_delete_messages(desdemona.realm, list(topic_messages), acting_user=desdemona)
        self.send_stream_message(desdemona, new_stream_name, "test content", "")

        result = self.client_patch(
            f"/json/streams/{new_stream.id}",
            {"topics_policy": StreamTopicsPolicyEnum.empty_topic_only.name},
        )
        self.assert_json_success(result)

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("TestStream2")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"topics_policy": allow_empty_topic},
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

    def test_can_set_topics_policy_group(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        owners_system_group = NamedUserGroup.objects.get(
            realm_for_sharding=realm, name=SystemGroups.OWNERS, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_set_topics_policy_group",
            owners_system_group,
            acting_user=None,
        )

        subscriptions = [{"name": "new_test_stream"}]
        result = self.subscribe_via_post(
            user,
            subscriptions,
            subdomain="zulip",
            extra_post_data={
                "topics_policy": orjson.dumps(
                    StreamTopicsPolicyEnum.allow_empty_topic.name
                ).decode()
            },
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        admin = self.example_user("iago")
        self.login_user(admin)

        subscriptions = [{"name": "new_test_stream"}]
        result = self.subscribe_via_post(
            admin,
            subscriptions,
            subdomain="zulip",
            extra_post_data={
                "topics_policy": orjson.dumps(
                    StreamTopicsPolicyEnum.allow_empty_topic.name
                ).decode()
            },
            allow_fail=True,
        )
        self.assert_json_success(result)

    def test_notification_on_changing_stream_posting_permission(self) -> None:
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm
        stream = self.subscribe(desdemona, "stream_name1")

        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm_for_sharding=realm, is_system_group=True
        )
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        self.login("desdemona")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"can_send_message_group": orjson.dumps({"new": moderators_group.id}).decode()},
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.can_send_message_group_id, moderators_group.id)

        messages = get_topic_messages(desdemona, stream, "channel events")
        expected_notification = (
            f"@_**{desdemona.full_name}|{desdemona.id}** changed the "
            "[posting permissions](/help/channel-posting-policy) for this channel:\n\n"
            f"* **Old**: @_*{everyone_group.name}*\n"
            f"* **New**: @_*{moderators_group.name}*"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        owners_group = NamedUserGroup.objects.get(
            name=SystemGroups.OWNERS, realm_for_sharding=realm, is_system_group=True
        )
        hamlet = self.example_user("hamlet")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {
                "can_send_message_group": orjson.dumps(
                    {
                        "new": {
                            "direct_members": [hamlet.id],
                            "direct_subgroups": [owners_group.id, moderators_group.id],
                        }
                    }
                ).decode()
            },
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertCountEqual(
            list(stream.can_send_message_group.direct_subgroups.all()),
            [moderators_group, owners_group],
        )
        self.assertCountEqual(list(stream.can_send_message_group.direct_members.all()), [hamlet])

        messages = get_topic_messages(desdemona, stream, "channel events")
        expected_notification = (
            f"@_**{desdemona.full_name}|{desdemona.id}** changed the "
            "[posting permissions](/help/channel-posting-policy) for this channel:\n\n"
            f"* **Old**: @_*{moderators_group.name}*\n"
            f"* **New**: @_*{owners_group.name}*, @_*{moderators_group.name}*, @_**{hamlet.full_name}|{hamlet.id}**"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        hamletcharacters_group = NamedUserGroup.objects.get(
            name="hamletcharacters", realm_for_sharding=realm
        )
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {
                "can_send_message_group": orjson.dumps(
                    {
                        "new": {
                            "direct_members": [desdemona.id],
                            "direct_subgroups": [hamletcharacters_group.id],
                        }
                    }
                ).decode()
            },
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertCountEqual(
            list(stream.can_send_message_group.direct_subgroups.all()), [hamletcharacters_group]
        )
        self.assertCountEqual(list(stream.can_send_message_group.direct_members.all()), [desdemona])

        messages = get_topic_messages(desdemona, stream, "channel events")
        expected_notification = (
            f"@_**{desdemona.full_name}|{desdemona.id}** changed the "
            "[posting permissions](/help/channel-posting-policy) for this channel:\n\n"
            f"* **Old**: @_*{owners_group.name}*, @_*{moderators_group.name}*, @_**{hamlet.full_name}|{hamlet.id}**\n"
            f"* **New**: @_*{hamletcharacters_group.name}*, @_**{desdemona.full_name}|{desdemona.id}**"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"can_send_message_group": orjson.dumps({"new": nobody_group.id}).decode()},
        )
        self.assert_json_success(result)
        stream = get_stream("stream_name1", realm)
        self.assertEqual(stream.can_send_message_group_id, nobody_group.id)

        messages = get_topic_messages(desdemona, stream, "channel events")
        expected_notification = (
            f"@_**{desdemona.full_name}|{desdemona.id}** changed the "
            "[posting permissions](/help/channel-posting-policy) for this channel:\n\n"
            f"* **Old**: @_*{hamletcharacters_group.name}*, @_**{desdemona.full_name}|{desdemona.id}**\n"
            f"* **New**: @_*{nobody_group.name}*"
        )
        self.assertEqual(messages[-1].content, expected_notification)

        # Test notification is not sent in `channel events` if `send_channel_events_messages` is `False`.
        do_set_realm_property(stream.realm, "send_channel_events_messages", False, acting_user=None)
        stream = self.make_stream("stream_without_notification")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"can_send_message_group": orjson.dumps({"new": everyone_group.id}).decode()},
        )
        self.assert_json_success(result)
        with self.assertRaises(Message.DoesNotExist):
            Message.objects.get(recipient__type_id=stream.id)

    def set_up_stream_for_archiving(
        self, stream_name: str, invite_only: bool = False, subscribed: bool = True
    ) -> Stream:
        """
        Create a stream for archiving by an administrator.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.make_stream(stream_name, invite_only=invite_only)

        # For testing archiving streams you aren't on.
        if subscribed:
            self.subscribe(user_profile, stream_name)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)

        return stream

    def archive_stream(self, stream: Stream, *, expect_can_subscribe: bool = True) -> None:
        """
        Archive the stream and assess the result.
        """
        active_name = stream.name
        realm = stream.realm
        stream_id = stream.id

        with self.capture_send_event_calls(expected_num_events=3) as events:
            result = self.client_delete("/json/streams/" + str(stream_id))
        self.assert_json_success(result)

        stream.refresh_from_db()

        # We no longer send subscription events for stream deactivations.
        sub_events = [e for e in events if e["event"]["type"] == "subscription"]
        self.assertEqual(sub_events, [])

        stream_events = [e for e in events if e["event"]["type"] == "stream"]
        self.assert_length(stream_events, 2)

        # Clients will get this event only if they support
        # archived_channels client capability.
        update_event = stream_events[0]["event"]
        self.assertEqual(update_event["op"], "update")
        self.assertEqual(update_event["stream_id"], stream.id)
        self.assertEqual(update_event["property"], "is_archived")
        self.assertEqual(update_event["value"], True)

        # This event will only be sent to clients that do not support
        # archived_channels client capability.
        delete_event = stream_events[1]["event"]
        self.assertEqual(delete_event["op"], "delete")
        self.assertEqual(delete_event["streams"][0]["stream_id"], stream.id)

        hashed_stream_id = hashlib.sha512(str(stream_id).encode()).hexdigest()[0:7]
        old_deactivated_stream_name = hashed_stream_id + "!DEACTIVATED:" + active_name

        with self.assertRaises(Stream.DoesNotExist):
            Stream.objects.get(realm=get_realm("zulip"), name=old_deactivated_stream_name)

        # An archived stream is deactivated, but subscribers and
        # permissions settings are not immediately changed.
        deactivated_stream_name = active_name
        deactivated_stream = get_stream(deactivated_stream_name, realm)
        self.assertTrue(deactivated_stream.deactivated)
        self.assertEqual(deactivated_stream.name, deactivated_stream_name)

        # It doesn't show up in the list of public streams anymore.
        result = self.client_get("/json/streams", {"include_subscribed": "false"})
        public_streams = [s["name"] for s in self.assert_json_success(result)["streams"]]
        self.assertNotIn(deactivated_stream_name, public_streams)

        # It shows up with `exclude_archived` parameter set to false.
        result = self.client_get(
            "/json/streams", {"exclude_archived": "false", "include_all": "true"}
        )
        streams = [s["name"] for s in self.assert_json_success(result)["streams"]]
        self.assertIn(deactivated_stream_name, streams)

        # You can still subscribe to archived stream, if you have content access.
        hamlet = self.example_user("hamlet")
        result = self.subscribe_via_post(
            hamlet,
            [deactivated_stream_name],
            allow_fail=not expect_can_subscribe,
        )
        if expect_can_subscribe:
            self.assert_json_success(result)
        else:
            self.assert_json_error(result, "Unable to access channel (privstream).")

            # now grant content access
            setting_group_member_dict = UserGroupMembersData(
                direct_members=[hamlet.id], direct_subgroups=[]
            )
            do_change_stream_group_based_setting(
                stream, "can_subscribe_group", setting_group_member_dict, acting_user=hamlet
            )

            result = self.subscribe_via_post(hamlet, [deactivated_stream_name])
            self.assert_json_success(result)

        # You can still unsubscribe from an archived stream.
        result = self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps([deactivated_stream_name]).decode(),
                "principals": orjson.dumps([hamlet.id]).decode(),
            },
        )
        self.assert_json_success(result)

        # You cannot re-archive the stream
        with self.capture_send_event_calls(expected_num_events=0) as events:
            result = self.client_delete("/json/streams/" + str(stream_id))
        self.assert_json_error(result, "Channel is already deactivated")

    def test_you_must_be_realm_admin(self) -> None:
        """
        You must be on the realm to create a stream.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)

        other_realm = do_create_realm(string_id="other", name="other")
        stream = self.make_stream("other_realm_stream", realm=other_realm)

        result = self.client_delete("/json/streams/" + str(stream.id))
        self.assert_json_error(result, "Invalid channel ID")

        # Even becoming a realm admin doesn't help us for an out-of-realm
        # stream.
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        result = self.client_delete("/json/streams/" + str(stream.id))
        self.assert_json_error(result, "Invalid channel ID")

    def test_delete_public_stream(self) -> None:
        """
        When an administrator deletes a public stream, that stream is not
        visible to users at all anymore.
        """
        stream = self.set_up_stream_for_archiving("newstream")
        self.archive_stream(stream)

    def test_delete_private_stream(self) -> None:
        """
        Administrators can delete private streams they are on.
        """
        stream = self.set_up_stream_for_archiving("newstream", invite_only=True)
        self.archive_stream(stream)

    def test_archive_stream_youre_not_on(self) -> None:
        """
        Administrators can delete public streams they aren't on
        """
        pub_stream = self.set_up_stream_for_archiving("pubstream", subscribed=False)
        self.archive_stream(pub_stream)

    def test_archive_invite_only_stream_youre_not_on(self) -> None:
        """
        Administrators can delete invite-only streams they aren't on
        """
        priv_stream = self.set_up_stream_for_archiving(
            "privstream", subscribed=False, invite_only=True
        )
        self.archive_stream(priv_stream, expect_can_subscribe=False)

    def test_updating_stream_folder(self) -> None:
        iago = self.example_user("iago")
        channel_folder = check_add_channel_folder(iago.realm, "Frontend", "", acting_user=iago)
        stream = self.make_stream("test_stream")

        self.assertIsNone(stream.folder_id)

        self.login("desdemona")
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"folder_id": orjson.dumps(channel_folder.id).decode()},
        )
        self.assert_json_success(result)
        stream = get_stream("test_stream", iago.realm)
        self.assertEqual(stream.folder_id, channel_folder.id)

        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"folder_id": orjson.dumps(None).decode()},
        )
        self.assert_json_success(result)
        stream = get_stream("test_stream", iago.realm)
        self.assertIsNone(stream.folder_id)

        # Test invalid value.
        result = self.client_patch(
            f"/json/streams/{stream.id}",
            {"folder_id": orjson.dumps(99).decode()},
        )
        self.assert_json_error(result, "Invalid channel folder ID")

    def attempt_unsubscribe_of_principal(
        self,
        target_users: list[UserProfile],
        query_count: int,
        cache_count: int | None = None,
        is_realm_admin: bool = False,
        is_subbed: bool = True,
        invite_only: bool = False,
        target_users_subbed: bool = True,
        using_legacy_emails: bool = False,
        other_sub_users: Sequence[UserProfile] = [],
    ) -> "TestHttpResponse":
        # Set up the main user, who is in most cases an admin.
        if is_realm_admin:
            user_profile = self.example_user("iago")
        else:
            user_profile = self.example_user("hamlet")

        self.login_user(user_profile)

        # Set up the stream.
        stream_name = "hümbüǵ"
        self.make_stream(stream_name, invite_only=invite_only)

        # Set up the principal to be unsubscribed.
        principals = [user.email if using_legacy_emails else user.id for user in target_users]

        # Subscribe the admin and/or principal as specified in the flags.
        if is_subbed:
            self.subscribe(user_profile, stream_name)
        if target_users_subbed:
            for user in target_users:
                self.subscribe(user, stream_name)
        for user in other_sub_users:
            self.subscribe(user, stream_name)

        with (
            self.assert_database_query_count(query_count),
            cache_tries_captured() as cache_tries,
            self.captureOnCommitCallbacks(execute=True),
        ):
            result = self.client_delete(
                "/json/users/me/subscriptions",
                {
                    "subscriptions": orjson.dumps([stream_name]).decode(),
                    "principals": orjson.dumps(principals).decode(),
                },
            )
        if cache_count is not None:
            self.assert_length(cache_tries, cache_count)

        # If the removal succeeded, assert all target users are no longer subscribed.
        if result.status_code not in [400]:
            subbed_users = self.users_subscribed_to_stream(stream_name, user_profile.realm)
            for user in target_users:
                self.assertNotIn(user, subbed_users)

        return result

    def test_cant_remove_other_users_from_stream(self) -> None:
        """
        If you're not an admin, you can't remove other people from streams except your own bots.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=8,
            target_users=[self.example_user("cordelia")],
            is_realm_admin=False,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
        )
        self.assert_json_error(result, "Insufficient permission")

    def test_realm_admin_remove_others_from_public_stream(self) -> None:
        """
        If you're a realm admin, you can remove people from public streams, even
        those you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=15,
            target_users=[self.example_user("cordelia")],
            is_realm_admin=True,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)
        self.assert_length(json["not_removed"], 0)

    def test_realm_admin_remove_multiple_users_from_stream(self) -> None:
        """
        If you're a realm admin, you can remove multiple users from a stream.

        TODO: We have too many queries for this situation--each additional
              user leads to 4 more queries.

              Fortunately, some of the extra work here is in
              do_mark_stream_messages_as_read, which gets deferred
              using a queue.
        """
        target_users = [
            self.example_user(name)
            for name in ["cordelia", "prospero", "iago", "hamlet", "outgoing_webhook_bot"]
        ]
        result = self.attempt_unsubscribe_of_principal(
            query_count=22,
            cache_count=13,
            target_users=target_users,
            is_realm_admin=True,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 5)
        self.assert_length(json["not_removed"], 0)

    def test_realm_admin_remove_others_from_subbed_private_stream(self) -> None:
        """
        If you're a realm admin, you can remove other people from private streams you
        are on.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=18,
            target_users=[self.example_user("cordelia")],
            is_realm_admin=True,
            is_subbed=True,
            invite_only=True,
            target_users_subbed=True,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)
        self.assert_length(json["not_removed"], 0)

    def test_realm_admin_remove_others_from_unsubbed_private_stream(self) -> None:
        """
        If you're a realm admin, you can remove people from private
        streams you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=18,
            target_users=[self.example_user("cordelia")],
            is_realm_admin=True,
            is_subbed=False,
            invite_only=True,
            target_users_subbed=True,
            other_sub_users=[self.example_user("othello")],
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)
        self.assert_length(json["not_removed"], 0)

    def test_cant_remove_others_from_stream_legacy_emails(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=8,
            is_realm_admin=False,
            is_subbed=True,
            invite_only=False,
            target_users=[self.example_user("cordelia")],
            target_users_subbed=True,
            using_legacy_emails=True,
        )
        self.assert_json_error(result, "Insufficient permission")

    def test_admin_remove_others_from_stream_legacy_emails(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=15,
            target_users=[self.example_user("cordelia")],
            is_realm_admin=True,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
            using_legacy_emails=True,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)
        self.assert_length(json["not_removed"], 0)

    def test_admin_remove_multiple_users_from_stream_legacy_emails(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=17,
            target_users=[self.example_user("cordelia"), self.example_user("prospero")],
            is_realm_admin=True,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
            using_legacy_emails=True,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 2)
        self.assert_length(json["not_removed"], 0)

    def test_remove_unsubbed_user_along_with_subbed(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=14,
            target_users=[self.example_user("cordelia"), self.example_user("iago")],
            is_realm_admin=True,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=False,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)
        self.assert_length(json["not_removed"], 1)

    def test_remove_already_not_subbed(self) -> None:
        """
        Trying to unsubscribe someone who already isn't subscribed to a stream
        fails gracefully.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=7,
            target_users=[self.example_user("cordelia")],
            is_realm_admin=True,
            is_subbed=False,
            invite_only=False,
            target_users_subbed=False,
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 0)
        self.assert_length(json["not_removed"], 1)

    def test_bot_owner_can_remove_bot_from_stream(self) -> None:
        user_profile = self.example_user("hamlet")
        webhook_bot = self.example_user("webhook_bot")
        do_change_bot_owner(webhook_bot, bot_owner=user_profile, acting_user=user_profile)
        result = self.attempt_unsubscribe_of_principal(
            query_count=15,
            target_users=[webhook_bot],
            is_realm_admin=False,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
        )
        self.assert_json_success(result)

    def test_non_bot_owner_cannot_remove_bot_from_stream(self) -> None:
        other_user = self.example_user("cordelia")
        webhook_bot = self.example_user("webhook_bot")
        do_change_bot_owner(webhook_bot, bot_owner=other_user, acting_user=other_user)
        result = self.attempt_unsubscribe_of_principal(
            query_count=7,
            target_users=[webhook_bot],
            is_realm_admin=False,
            is_subbed=True,
            invite_only=False,
            target_users_subbed=True,
        )
        self.assert_json_error(result, "Insufficient permission")

    def test_remove_invalid_user(self) -> None:
        """
        Trying to unsubscribe an invalid user from a stream fails gracefully.
        """
        admin = self.example_user("iago")
        self.login_user(admin)
        self.assertTrue(admin.is_realm_admin)

        stream_name = "hümbüǵ"
        self.make_stream(stream_name)

        result = self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps([stream_name]).decode(),
                "principals": orjson.dumps([99]).decode(),
            },
        )
        self.assert_json_error(result, "No such user", status_code=400)

    def test_user_unsubscribe_theirself(self) -> None:
        """
        User trying to unsubscribe theirself from the stream, where
        principals has the id of the acting_user performing the
        unsubscribe action.
        """
        admin = self.example_user("iago")
        self.login_user(admin)
        self.assertTrue(admin.is_realm_admin)

        stream_name = "hümbüǵ"
        self.make_stream(stream_name)
        self.subscribe(admin, stream_name)

        # unsubscribing when subscribed.
        result = self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps([stream_name]).decode(),
                "principals": orjson.dumps([admin.id]).decode(),
            },
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)

        # unsubscribing after already being unsubscribed.
        result = self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps([stream_name]).decode(),
                "principals": orjson.dumps([admin.id]).decode(),
            },
        )

        json = self.assert_json_success(result)
        self.assert_length(json["not_removed"], 1)

    def test_removing_last_user_from_private_stream(self) -> None:
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        hamlet = self.example_user("hamlet")

        self.subscribe(hamlet, stream_name)
        self.login("hamlet")
        result = self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps([stream_name]).decode(),
            },
        )
        json = self.assert_json_success(result)
        self.assert_length(json["removed"], 1)
        self.assert_length(json["not_removed"], 0)

        # Private stream is not deactivated on being vacant.
        stream = get_stream(stream_name, hamlet.realm)
        self.assertFalse(stream.deactivated)
        self.assertFalse(
            Subscription.objects.filter(
                recipient__type_id=stream.id, recipient__type=Recipient.STREAM, active=True
            ).exists()
        )


class SubscriptionRestApiTest(ZulipTestCase):
    def test_basic_add_delete(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # add
        request = {
            "add": orjson.dumps([{"name": "my_test_stream_1"}]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_success(result)
        streams = self.get_streams(user)
        self.assertTrue("my_test_stream_1" in streams)

        # now delete the same stream
        request = {
            "delete": orjson.dumps(["my_test_stream_1"]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_success(result)
        streams = self.get_streams(user)
        self.assertTrue("my_test_stream_1" not in streams)

    def test_add_with_color(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # add with color proposition
        request = {
            "add": orjson.dumps([{"name": "my_test_stream_2", "color": "#afafaf"}]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_success(result)

        # incorrect color format
        subscriptions = [{"name": "my_test_stream_3", "color": "#0g0g0g"}]
        result = self.subscribe_via_post(user, subscriptions, allow_fail=True)
        self.assert_json_error(
            result, "Invalid subscriptions[0]: Value error, add.color is not a valid hex color code"
        )

    def test_api_valid_property(self) -> None:
        """
        Trying to set valid json returns success message.
        """
        user = self.example_user("hamlet")

        self.login_user(user)
        subs = gather_subscriptions(user)[0]
        result = self.api_patch(
            user,
            "/api/v1/users/me/subscriptions/{}".format(subs[0]["stream_id"]),
            {"property": "color", "value": "#c2c2c2"},
        )
        self.assert_json_success(result)

    def test_api_invalid_property(self) -> None:
        """
        Trying to set an invalid property returns a JSON error.
        """

        user = self.example_user("hamlet")

        self.login_user(user)
        subs = gather_subscriptions(user)[0]

        result = self.api_patch(
            user,
            "/api/v1/users/me/subscriptions/{}".format(subs[0]["stream_id"]),
            {"property": "invalid", "value": "somevalue"},
        )
        self.assert_json_error(result, "Unknown subscription property: invalid")

    def test_api_invalid_stream_id(self) -> None:
        """
        Trying to set an invalid stream id returns a JSON error.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.api_patch(
            user,
            "/api/v1/users/me/subscriptions/121",
            {"property": "is_muted", "value": orjson.dumps(True).decode()},
        )
        self.assert_json_error(result, "Invalid channel ID")

    def test_bad_add_parameters(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        def check_for_error(val: Any, expected_message: str) -> None:
            request = {
                "add": orjson.dumps(val).decode(),
            }
            result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
            self.assert_json_error(result, expected_message)

        check_for_error(
            ["foo"],
            "Invalid add[0]: Input should be a valid dictionary or instance of AddSubscriptionData",
        )
        check_for_error([{"bogus": "foo"}], 'add[0]["name"] field is missing: Field required')
        check_for_error([{"name": {}}], 'add[0]["name"] is not a string')

    def test_bad_principals(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        request = {
            "add": orjson.dumps([{"name": "my_new_stream"}]).decode(),
            "principals": orjson.dumps([{}]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, 'principals["list[str]"][0] is not a string')

    def test_bad_delete_parameters(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        request = {
            "delete": orjson.dumps([{"name": "my_test_stream_1"}]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, "delete[0] is not a string")

    def test_add_or_delete_not_specified(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        result = self.api_patch(user, "/api/v1/users/me/subscriptions", {})
        self.assert_json_error(result, 'Nothing to do. Specify at least one of "add" or "delete".')

    def test_patch_enforces_valid_stream_name_check(self) -> None:
        """
        Only way to force an error is with a empty string.
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        invalid_stream_name = ""
        request = {
            "delete": orjson.dumps([invalid_stream_name]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, "Channel name can't be empty.")

    def test_stream_name_too_long(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        long_stream_name = "a" * 61
        request = {
            "delete": orjson.dumps([long_stream_name]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, "Channel name too long (limit: 60 characters).")

    def test_stream_name_contains_null(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream_name = "abc\000"
        request = {
            "delete": orjson.dumps([stream_name]).decode(),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, "Invalid character in channel name, at position 4.")

    def test_compose_views_rollback(self) -> None:
        """
        The compose_views function() is used under the hood by
        update_subscriptions_backend.  It's a pretty simple method in terms of
        control flow, but it uses a Django rollback, which may make it brittle
        code when we upgrade Django.  We test the functions's rollback logic
        here with a simple scenario to avoid false positives related to
        subscription complications.
        """
        user_profile = self.example_user("hamlet")
        user_profile.full_name = "Hamlet"
        user_profile.save()
        request = HostRequestMock(user_profile=user_profile)

        def thunk1() -> HttpResponse:
            user_profile.full_name = "Should not be committed"
            user_profile.save()
            return json_success(request)

        def thunk2() -> HttpResponse:
            raise JsonableError("random failure")

        with transaction.atomic(savepoint=True), self.assertRaises(JsonableError):
            # The atomic() wrapper helps to avoid JsonableError breaking
            # the test's transaction.
            compose_views([thunk1, thunk2])

        user_profile = self.example_user("hamlet")
        self.assertEqual(user_profile.full_name, "Hamlet")


class SubscriptionAPITest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        """
        All tests will be logged in as hamlet. Also save various useful values
        as attributes that tests can access.
        """
        super().setUp()
        self.user_profile = self.example_user("hamlet")
        self.test_email = self.user_profile.email
        self.test_user = self.user_profile
        self.test_id = str(self.user_profile.id)
        self.login_user(self.user_profile)
        self.test_realm = self.user_profile.realm
        self.streams = self.get_streams(self.user_profile)

    def make_random_stream_names(self, existing_stream_names: list[str]) -> list[str]:
        """
        Helper function to make up random stream names. It takes
        existing_stream_names and randomly appends a digit to the end of each,
        but avoids names of streams already in the realm.
        """
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.test_realm)]
        return [
            random_stream
            for stream in existing_stream_names
            if (random_stream := stream + str(random.randint(0, 9))) not in all_stream_names
        ]

    def test_invalid_stream_name(self) -> None:
        """
        Creating a stream with invalid 'Cc' and 'Cn' category of unicode characters in stream name
        """
        user = self.example_user("hamlet")
        self.login_user(user)

        # For Cc category
        subscriptions = [{"name": "new\n\rstream", "description": "this is description"}]
        result = self.subscribe_via_post(user, subscriptions, allow_fail=True, subdomain="zulip")
        self.assert_json_error(result, "Invalid character in channel name, at position 4.")

        # For Cn category
        subscriptions = [{"name": "new\ufffestream", "description": "this is description"}]
        result = self.subscribe_via_post(user, subscriptions, allow_fail=True, subdomain="zulip")
        self.assert_json_error(result, "Invalid character in channel name, at position 4.")

    def test_invalid_stream_rename(self) -> None:
        """
        Renaming a stream with invalid characters.
        """
        user_profile = self.example_user("hamlet")
        self.login_user(user_profile)
        stream = self.subscribe(user_profile, "stream_name1")
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
        # Check for empty name
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": ""})
        self.assert_json_error(result, "Channel name can't be empty.")
        # Check for long name
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "a" * 61})
        self.assert_json_error(result, "Channel name too long (limit: 60 characters).")
        # Check for Cc characters
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "test\n\rname"})
        self.assert_json_error(result, "Invalid character in channel name, at position 5.")
        # Check for Cn characters
        result = self.client_patch(f"/json/streams/{stream.id}", {"new_name": "test\ufffeame"})
        self.assert_json_error(result, "Invalid character in channel name, at position 5.")

    def test_successful_subscriptions_list(self) -> None:
        """
        Calling /api/v1/users/me/subscriptions should successfully return your subscriptions.
        """
        result = self.api_get(self.test_user, "/api/v1/users/me/subscriptions")
        json = self.assert_json_success(result)
        self.assertIn("subscriptions", json)
        for stream in json["subscriptions"]:
            self.assertIsInstance(stream["name"], str)
            self.assertIsInstance(stream["color"], str)
            self.assertIsInstance(stream["invite_only"], bool)
            self.assertNotIn("partial_subscribers", stream)
            self.assertNotIn("subscribers", stream)
            # check that the stream name corresponds to an actual
            # stream; will throw Stream.DoesNotExist if it doesn't
            get_stream(stream["name"], self.test_realm)
        list_streams = [stream["name"] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertEqual(sorted(list_streams), sorted(self.streams))

        # Text explicitly passing `include_subscribers` as "false"
        result = self.api_get(
            self.test_user, "/api/v1/users/me/subscriptions", {"include_subscribers": "false"}
        )
        json = self.assert_json_success(result)
        self.assertIn("subscriptions", json)
        for stream in json["subscriptions"]:
            self.assertIsInstance(stream["name"], str)
            self.assertIsInstance(stream["color"], str)
            self.assertIsInstance(stream["invite_only"], bool)
            self.assertNotIn("partial_subscribers", stream)
            self.assertNotIn("subscribers", stream)
            # check that the stream name corresponds to an actual
            # stream; will throw Stream.DoesNotExist if it doesn't
            get_stream(stream["name"], self.test_realm)
        list_streams = [stream["name"] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertEqual(sorted(list_streams), sorted(self.streams))

    def test_successful_subscriptions_list_subscribers(self) -> None:
        """
        Calling /api/v1/users/me/subscriptions should successfully return your subscriptions.
        """
        result = self.api_get(
            self.test_user,
            "/api/v1/users/me/subscriptions",
            {"include_subscribers": "true"},
        )
        json = self.assert_json_success(result)
        self.assertIn("subscriptions", json)
        for stream in json["subscriptions"]:
            self.assertIsInstance(stream["name"], str)
            self.assertIsInstance(stream["color"], str)
            self.assertIsInstance(stream["invite_only"], bool)
            self.assertIn("subscribers", stream)
            # check that the stream name corresponds to an actual
            # stream; will throw Stream.DoesNotExist if it doesn't
            get_stream(stream["name"], self.test_realm)
        list_streams = [stream["name"] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertEqual(sorted(list_streams), sorted(self.streams))

    def helper_check_subs_before_and_after_add(
        self,
        subscriptions: list[str],
        other_params: dict[str, Any],
        subscribed: list[str],
        already_subscribed: list[str],
        email: str,
        new_subs: list[str],
        realm: Realm,
        id: str,
        invite_only: bool = False,
    ) -> None:
        """
        Check result of adding subscriptions.

        You can add subscriptions for yourself or possibly many
        principals, which is why user ID map to subscriptions in the
        result.

        The result json is of the form

        {"msg": "",
         "result": "success",
         "already_subscribed": {self.example_user("iago").id: ["Venice", "Verona"]},
         "subscribed": {self.example_user("iago").id: ["Venice8"]}}
        """
        result = self.subscribe_via_post(
            self.test_user, subscriptions, other_params, invite_only=invite_only
        )
        json = self.assert_json_success(result)
        self.assertEqual(sorted(subscribed), sorted(json["subscribed"][id]))
        self.assertEqual(sorted(already_subscribed), sorted(json["already_subscribed"][id]))
        user = get_user_profile_by_id_in_realm(int(id), realm)
        new_streams = self.get_streams(user)
        self.assertEqual(sorted(new_streams), sorted(new_subs))

    def test_successful_subscriptions_add(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and should determine which are new subscriptions vs
        which were already subscribed. We add 2 new streams to the
        list of subscriptions and confirm the right number of events
        are generated.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        add_streams = ["Verona2", "Denmark5"]
        self.assertNotEqual(len(add_streams), 0)  # necessary for full test coverage
        # Three events should be sent for each stream for stream creation, subscription add and message notifications.
        with self.capture_send_event_calls(expected_num_events=6):
            self.helper_check_subs_before_and_after_add(
                self.streams + add_streams,
                {},
                add_streams,
                self.streams,
                self.test_email,
                self.streams + add_streams,
                self.test_realm,
                self.test_id,
            )

    def test_successful_subscriptions_add_with_announce(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and should determine which are new subscriptions vs
        which were already subscribed. We add 2 new streams to the
        list of subscriptions and confirm the right number of events
        are generated.
        """
        self.assertNotEqual(len(self.streams), 0)
        add_streams = ["Verona2", "Denmark5"]
        self.assertNotEqual(len(add_streams), 0)
        other_params = {
            "announce": "true",
        }
        new_stream_announcements_stream = get_stream(self.streams[0], self.test_realm)
        self.test_realm.new_stream_announcements_stream_id = new_stream_announcements_stream.id
        self.test_realm.save()

        with self.capture_send_event_calls(expected_num_events=7) as events:
            self.helper_check_subs_before_and_after_add(
                self.streams + add_streams,
                other_params,
                add_streams,
                self.streams,
                self.test_email,
                self.streams + add_streams,
                self.test_realm,
                self.test_id,
            )

        expected_stream_ids = {get_stream(stream, self.test_realm).id for stream in add_streams}

        (peer_add_event,) = (event for event in events if event["event"].get("op") == "peer_add")

        self.assertEqual(set(peer_add_event["event"]["stream_ids"]), expected_stream_ids)
        self.assertEqual(set(peer_add_event["event"]["user_ids"]), {self.test_user.id})

    def test_successful_subscriptions_notifies_pm(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_user("iago")

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]
        self.subscribe_via_post(
            invitee,
            invite_streams,
            extra_post_data={
                "announce": "true",
                "principals": orjson.dumps([self.user_profile.id]).decode(),
            },
        )

    def test_successful_subscriptions_notifies_stream(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_user("iago")
        invitee_full_name = "Iago"

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]

        new_stream_announcements_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.new_stream_announcements_stream_id = new_stream_announcements_stream.id
        self.test_realm.save()

        self.subscribe_via_post(
            invitee,
            invite_streams,
            extra_post_data=dict(
                announce="true",
                principals=orjson.dumps([self.user_profile.id]).decode(),
            ),
        )
        target_stream = get_stream(invite_streams[0], self.test_realm)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.recipient.type_id, new_stream_announcements_stream.id)
        self.assertEqual(msg.sender_id, self.notification_bot(self.test_realm).id)
        self.assertEqual(msg.topic_name(), "new channels")
        expected_msg = f"@_**{invitee_full_name}|{invitee.id}** created a new channel #**{invite_streams[0]}**."
        self.assertEqual(msg.content, expected_msg)

        msg = self.get_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.recipient.type_id, target_stream.id)
        self.assertEqual(msg.sender_id, self.notification_bot(self.test_realm).id)
        expected_msg = (
            f"**Public** channel created by @_**{invitee_full_name}|{invitee.id}**. **Description:**\n"
            "```` quote\n*No description.*\n````"
        )
        self.assertEqual(msg.content, expected_msg)

    def test_successful_subscription_notifies_in_empty_topic_only_stream(self) -> None:
        invitee = self.example_user("iago")
        invitee_full_name = "Iago"

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]

        new_stream_announcements_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.new_stream_announcements_stream_id = new_stream_announcements_stream.id
        self.test_realm.save()

        do_set_stream_property(
            new_stream_announcements_stream,
            "topics_policy",
            StreamTopicsPolicyEnum.empty_topic_only.value,
            invitee,
        )

        self.subscribe_via_post(
            invitee,
            invite_streams,
            extra_post_data=dict(
                announce="true",
                principals=orjson.dumps([self.user_profile.id]).decode(),
            ),
        )

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.recipient.type_id, new_stream_announcements_stream.id)
        self.assertEqual(msg.sender_id, self.notification_bot(self.test_realm).id)
        self.assertEqual(msg.topic_name(), "")
        expected_msg = f"@_**{invitee_full_name}|{invitee.id}** created a new channel #**{invite_streams[0]}**."
        self.assertEqual(msg.content, expected_msg)

    def test_successful_cross_realm_notification(self) -> None:
        """
        Calling POST /json/users/me/subscriptions in a new realm
        should notify with a proper new stream link
        """
        realm = do_create_realm("testrealm", "Test Realm")

        new_stream_announcements_stream = Stream.objects.get(name="general", realm=realm)
        realm.new_stream_announcements_stream = new_stream_announcements_stream
        # `send_channel_events_messages` is `False` for new organizations.
        realm.send_channel_events_messages = True
        realm.save()

        invite_streams = ["cross_stream"]

        user = self.example_user("AARON")
        user.realm = realm
        user.save()

        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        bulk_add_members_to_user_groups([members_group], [user.id], acting_user=None)
        self.subscribe_via_post(
            user,
            invite_streams,
            extra_post_data=dict(
                announce="true",
            ),
            subdomain="testrealm",
        )

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.recipient.type_id, new_stream_announcements_stream.id)
        self.assertEqual(msg.sender_id, self.notification_bot(realm).id)
        stream_id = Stream.objects.latest("id").id
        expected_rendered_msg = f'<p><span class="user-mention silent" data-user-id="{user.id}">{user.full_name}</span> created a new channel <a class="stream" data-stream-id="{stream_id}" href="/#narrow/channel/{stream_id}-{invite_streams[0]}">#{invite_streams[0]}</a>.</p>'
        self.assertEqual(msg.rendered_content, expected_rendered_msg)

    def test_successful_subscriptions_notifies_with_escaping(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee_full_name = "Iago"
        invitee = self.example_user("iago")

        current_stream = self.get_streams(invitee)[0]
        new_stream_announcements_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.new_stream_announcements_stream_id = new_stream_announcements_stream.id
        self.test_realm.save()

        invite_streams = ["strange ) \\ test"]
        self.subscribe_via_post(
            invitee,
            invite_streams,
            extra_post_data={
                "announce": "true",
                "topics_policy": orjson.dumps(
                    StreamTopicsPolicyEnum.allow_empty_topic.name
                ).decode(),
                "principals": orjson.dumps([self.user_profile.id]).decode(),
            },
        )

        msg = self.get_second_to_last_message()
        self.assertEqual(
            msg.sender_id, self.notification_bot(new_stream_announcements_stream.realm).id
        )
        expected_msg = f"@_**{invitee_full_name}|{invitee.id}** created a new channel #**{invite_streams[0]}**."
        self.assertEqual(msg.content, expected_msg)

    def test_non_ascii_stream_subscription(self) -> None:
        """
        Subscribing to a stream name with non-ASCII characters succeeds.
        """
        self.helper_check_subs_before_and_after_add(
            [*self.streams, "hümbüǵ"],
            {},
            ["hümbüǵ"],
            self.streams,
            self.test_email,
            [*self.streams, "hümbüǵ"],
            self.test_realm,
            self.test_id,
        )

    def test_subscriptions_add_too_long(self) -> None:
        """
        Calling POST /json/users/me/subscriptions on a stream whose name is >60
        characters should return a JSON error.
        """
        # character limit is 60 characters
        long_stream_name = "a" * 61
        result = self.subscribe_via_post(self.test_user, [long_stream_name], allow_fail=True)
        self.assert_json_error(result, "Channel name too long (limit: 60 characters).")

    def test_subscriptions_add_stream_with_null(self) -> None:
        """
        Calling POST /json/users/me/subscriptions on a stream whose name contains
        null characters should return a JSON error.
        """
        stream_name = "abc\000"
        result = self.subscribe_via_post(self.test_user, [stream_name], allow_fail=True)
        self.assert_json_error(result, "Invalid character in channel name, at position 4.")

    def _test_group_based_settings_for_creating_streams(
        self,
        stream_policy: str,
        *,
        invite_only: bool,
        is_web_public: bool,
    ) -> None:
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")

        realm = cordelia.realm

        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, stream_policy, admins_group.usergroup_ptr, acting_user=None
        )
        result = self.subscribe_via_post(
            cordelia,
            ["new_stream1"],
            invite_only=invite_only,
            is_web_public=is_web_public,
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        self.subscribe_via_post(iago, ["new_stream1"], invite_only=invite_only)

        full_members_group = NamedUserGroup.objects.get(
            name=SystemGroups.FULL_MEMBERS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, stream_policy, full_members_group, acting_user=None
        )
        do_set_realm_property(realm, "waiting_period_threshold", 100000, acting_user=None)
        result = self.subscribe_via_post(
            cordelia,
            ["new_stream2"],
            invite_only=invite_only,
            is_web_public=is_web_public,
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)
        self.subscribe_via_post(cordelia, ["new_stream2"], invite_only=invite_only)

        leadership_group = check_add_user_group(
            realm, "Leadership", [desdemona], acting_user=desdemona
        )
        do_change_realm_permission_group_setting(
            realm, stream_policy, leadership_group, acting_user=None
        )
        result = self.subscribe_via_post(
            self.example_user("iago"),
            ["new_stream3"],
            invite_only=invite_only,
            is_web_public=is_web_public,
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        self.subscribe_via_post(desdemona, ["new_stream3"], invite_only=invite_only)

        staff_group = check_add_user_group(realm, "Staff", [iago], acting_user=iago)
        setting_group = self.create_or_update_anonymous_group_for_setting([cordelia], [staff_group])
        do_change_realm_permission_group_setting(
            realm, stream_policy, setting_group, acting_user=None
        )

        result = self.subscribe_via_post(
            desdemona,
            ["new_stream4"],
            invite_only=invite_only,
            is_web_public=is_web_public,
            allow_fail=True,
        )
        self.assert_json_error(result, "Insufficient permission")

        self.subscribe_via_post(iago, ["new_stream4"], invite_only=invite_only)
        self.subscribe_via_post(cordelia, ["new_stream5"], invite_only=invite_only)

    def test_user_settings_for_creating_private_streams(self) -> None:
        self._test_group_based_settings_for_creating_streams(
            "can_create_private_channel_group",
            invite_only=True,
            is_web_public=False,
        )

    def test_user_settings_for_creating_public_streams(self) -> None:
        self._test_group_based_settings_for_creating_streams(
            "can_create_public_channel_group",
            invite_only=False,
            is_web_public=False,
        )

    def test_user_settings_for_creating_web_public_streams(self) -> None:
        self._test_group_based_settings_for_creating_streams(
            "can_create_web_public_channel_group",
            invite_only=False,
            is_web_public=True,
        )

    def test_stream_creator_id(self) -> None:
        iago = self.example_user("iago")
        self.login_user(iago)
        user1 = self.example_user("hamlet")
        user2 = self.example_user("desdemona")

        streams_to_sub = ["new_stream"]
        # We create streams by subscribing users to non-existent streams
        # Here we subscribe users other than the stream creator
        with self.capture_send_event_calls(5) as events:
            self.subscribe_via_post(
                iago,
                streams_to_sub,
                dict(principals=orjson.dumps([user1.id, user2.id]).decode()),
            )
        self.assertEqual(events[0]["event"]["streams"][0]["creator_id"], iago.id)
        created_stream_id = events[0]["event"]["streams"][0]["stream_id"]

        all_streams = self.api_get(iago, "/api/v1/streams")
        json = self.assert_json_success(all_streams)
        for stream in json["streams"]:
            if stream["stream_id"] == created_stream_id:
                # Acting user should be the creator for api created streams
                self.assertEqual(stream["creator_id"], iago.id)
                continue

            # We assign creator to some streams in populate_db.
            if stream["name"] == "Venice":
                self.assertEqual(stream["creator_id"], self.example_user("polonius").id)
                continue

            if stream["name"] == "Scotland":
                self.assertEqual(stream["creator_id"], self.example_user("iago").id)
                continue

            if stream["name"] == "core team":
                self.assertEqual(stream["creator_id"], self.example_user("desdemona").id)
                continue

            # Other streams that weren't created using the api should have no creator.
            self.assertIsNone(stream["creator_id"])

    def test_subscriptions_add_invalid_stream(self) -> None:
        """
        Calling POST /json/users/me/subscriptions on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid name is the empty string
        invalid_stream_name = ""
        result = self.subscribe_via_post(self.test_user, [invalid_stream_name], allow_fail=True)
        self.assert_json_error(result, "Channel name can't be empty.")

    def assert_adding_subscriptions_for_principal(
        self,
        invitee_data: str | int,
        invitee_realm: Realm,
        streams: list[str],
        policy_name: str,
        invite_only: bool = False,
    ) -> None:
        """
        Calling POST /json/users/me/subscriptions on behalf of another principal (for
        whom you have permission to add subscriptions) should successfully add
        those subscriptions and send a message to the subscribee notifying
        them.
        """
        if isinstance(invitee_data, str):
            other_profile = get_user(invitee_data, invitee_realm)
        else:
            other_profile = get_user_profile_by_id_in_realm(invitee_data, invitee_realm)
        current_streams = self.get_streams(other_profile)
        self.assertIsInstance(other_profile, UserProfile)
        self.assertNotEqual(len(current_streams), 0)  # necessary for full test coverage
        self.assertNotEqual(len(streams), 0)  # necessary for full test coverage
        streams_to_sub = streams[:1]  # just add one, to make the message easier to check
        streams_to_sub.extend(current_streams)
        self.helper_check_subs_before_and_after_add(
            streams_to_sub,
            {"principals": orjson.dumps([invitee_data]).decode()},
            streams[:1],
            current_streams,
            other_profile.email,
            streams_to_sub,
            invitee_realm,
            str(other_profile.id),
            invite_only=invite_only,
        )

        # verify that a welcome message was sent to the stream
        msg = self.get_last_message()
        self.assertEqual(msg.recipient.type, msg.recipient.STREAM)
        self.assertEqual(msg.topic_name(), "channel events")
        self.assertEqual(msg.sender.email, settings.NOTIFICATION_BOT)
        self.assertIn(
            f"**{policy_name}** channel created by @_**{self.test_user.full_name}|{self.test_user.id}**. **Description:**\n"
            "```` quote",
            msg.content,
        )

    def test_multi_user_subscription(self) -> None:
        user1 = self.example_user("cordelia")
        user2 = self.example_user("iago")
        realm = get_realm("zulip")
        streams_to_sub = ["multi_user_stream"]
        with (
            self.capture_send_event_calls(expected_num_events=5) as events,
            self.assert_database_query_count(44),
        ):
            self.subscribe_via_post(
                self.test_user,
                streams_to_sub,
                dict(principals=orjson.dumps([user1.id, user2.id]).decode()),
            )

        for ev in [x for x in events if x["event"]["type"] not in ("message", "stream")]:
            if ev["event"]["op"] == "add":
                self.assertEqual(
                    set(ev["event"]["subscriptions"][0]["subscribers"]),
                    {user1.id, user2.id},
                )
            else:
                # Check "peer_add" events for streams users were
                # never subscribed to, in order for the neversubscribed
                # structure to stay up-to-date.
                self.assertEqual(ev["event"]["op"], "peer_add")

        stream = get_stream("multi_user_stream", realm)
        self.assertEqual(num_subscribers_for_stream_id(stream.id), 2)

        # Now add ourselves
        with (
            self.capture_send_event_calls(expected_num_events=2) as events,
            self.assert_database_query_count(17),
        ):
            self.subscribe_via_post(
                self.test_user,
                streams_to_sub,
                dict(principals=orjson.dumps([self.test_user.id]).decode()),
            )

        add_event, add_peer_event = events
        self.assertEqual(add_event["event"]["type"], "subscription")
        self.assertEqual(add_event["event"]["op"], "add")
        self.assertEqual(add_event["users"], [get_user(self.test_email, self.test_realm).id])
        self.assertEqual(
            set(add_event["event"]["subscriptions"][0]["subscribers"]),
            {user1.id, user2.id, self.test_user.id},
        )

        self.assertNotIn(self.example_user("polonius").id, add_peer_event["users"])
        self.assert_length(add_peer_event["users"], 11)
        self.assertEqual(add_peer_event["event"]["type"], "subscription")
        self.assertEqual(add_peer_event["event"]["op"], "peer_add")
        self.assertEqual(add_peer_event["event"]["user_ids"], [self.user_profile.id])

        stream = get_stream("multi_user_stream", realm)
        self.assertEqual(num_subscribers_for_stream_id(stream.id), 3)

        # Finally, add othello.
        events = []
        user_profile = self.example_user("othello")
        email3 = user_profile.email
        user3 = user_profile
        realm3 = user_profile.realm
        stream = get_stream("multi_user_stream", realm)
        with self.capture_send_event_calls(expected_num_events=2) as events:
            bulk_add_subscriptions(realm, [stream], [user_profile], acting_user=None)

        add_event, add_peer_event = events

        self.assertEqual(add_event["event"]["type"], "subscription")
        self.assertEqual(add_event["event"]["op"], "add")
        self.assertEqual(add_event["users"], [get_user(email3, realm3).id])
        self.assertEqual(
            set(add_event["event"]["subscriptions"][0]["subscribers"]),
            {user1.id, user2.id, user3.id, self.test_user.id},
        )

        # We don't send a peer_add event to othello
        self.assertNotIn(user_profile.id, add_peer_event["users"])
        self.assertNotIn(self.example_user("polonius").id, add_peer_event["users"])
        self.assert_length(add_peer_event["users"], 11)
        self.assertEqual(add_peer_event["event"]["type"], "subscription")
        self.assertEqual(add_peer_event["event"]["op"], "peer_add")
        self.assertEqual(add_peer_event["event"]["user_ids"], [user_profile.id])

    def test_private_stream_subscription(self) -> None:
        realm = get_realm("zulip")

        # Create a private stream with Hamlet subscribed
        stream_name = "private"
        stream = ensure_stream(realm, stream_name, invite_only=True, acting_user=None)

        existing_user_profile = self.example_user("hamlet")
        bulk_add_subscriptions(realm, [stream], [existing_user_profile], acting_user=None)

        # Now subscribe Cordelia to the stream, capturing events
        user_profile = self.example_user("cordelia")

        with self.capture_send_event_calls(expected_num_events=3) as events:
            bulk_add_subscriptions(realm, [stream], [user_profile], acting_user=None)

        create_event, add_event, add_peer_event = events

        self.assertEqual(create_event["event"]["type"], "stream")
        self.assertEqual(create_event["event"]["op"], "create")
        self.assertEqual(create_event["users"], [user_profile.id])
        self.assertEqual(create_event["event"]["streams"][0]["name"], stream_name)

        self.assertEqual(add_event["event"]["type"], "subscription")
        self.assertEqual(add_event["event"]["op"], "add")
        self.assertEqual(add_event["users"], [user_profile.id])
        self.assertEqual(
            set(add_event["event"]["subscriptions"][0]["subscribers"]),
            {user_profile.id, existing_user_profile.id},
        )

        # We don't send a peer_add event to othello, but we do send peer_add event to
        # all realm admins.
        self.assertNotIn(user_profile.id, add_peer_event["users"])
        self.assert_length(add_peer_event["users"], 3)
        self.assertEqual(add_peer_event["event"]["type"], "subscription")
        self.assertEqual(add_peer_event["event"]["op"], "peer_add")
        self.assertEqual(add_peer_event["event"]["user_ids"], [user_profile.id])

        # Do not send stream creation event to realm admin users
        # even if realm admin is subscribed to stream cause realm admin already get
        # private stream creation event on stream creation.
        new_stream = ensure_stream(realm, "private stream", invite_only=True, acting_user=None)
        with self.capture_send_event_calls(expected_num_events=2) as events:
            bulk_add_subscriptions(
                realm, [new_stream], [self.example_user("iago")], acting_user=None
            )

        # Note that since iago is an admin, he won't get a stream/create
        # event here.
        self.assert_length(events, 2)
        add_event, add_peer_event = events

        self.assertEqual(add_event["event"]["type"], "subscription")
        self.assertEqual(add_event["event"]["op"], "add")
        self.assertEqual(add_event["users"], [self.example_user("iago").id])

        self.assert_length(add_peer_event["users"], 1)
        self.assertEqual(add_peer_event["event"]["type"], "subscription")
        self.assertEqual(add_peer_event["event"]["op"], "peer_add")
        self.assertEqual(add_peer_event["event"]["user_ids"], [self.example_user("iago").id])

    def test_subscribing_to_stream_without_permission_to_post(self) -> None:
        stream = self.make_stream("stream_name1")
        realm = get_realm("zulip")

        iago = self.example_user("iago")
        admins_group = NamedUserGroup.objects.get(
            name=SystemGroups.ADMINISTRATORS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", admins_group, acting_user=iago
        )

        # Members can subscribe even when only admins can post.
        member = self.example_user("hamlet")
        result = self.subscribe_via_post(member, ["stream_name1"])
        json = self.assert_json_success(result)
        self.assertEqual(json["subscribed"], {str(member.id): ["stream_name1"]})
        self.assertEqual(json["already_subscribed"], {})

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        setting_group_member_dict = UserGroupMembersData(
            direct_members=[self.example_user("cordelia").id],
            direct_subgroups=[moderators_group.id],
        )
        do_change_stream_group_based_setting(
            stream, "can_send_message_group", setting_group_member_dict, acting_user=iago
        )

        member = self.example_user("othello")
        result = self.subscribe_via_post(member, ["stream_name1"])
        json = self.assert_json_success(result)
        self.assertEqual(json["subscribed"], {str(member.id): ["stream_name1"]})
        self.assertEqual(json["already_subscribed"], {})

    def test_guest_user_subscribe(self) -> None:
        """Guest users cannot subscribe themselves to anything"""
        guest_user = self.example_user("polonius")
        result = self.subscribe_via_post(guest_user, ["Denmark"], allow_fail=True)
        self.assert_json_error(result, "Not allowed for guest users")

        # Verify the internal checks also block guest users.
        stream = get_stream("Denmark", guest_user.realm)
        streams_categorized_by_permissions = filter_stream_authorization_for_adding_subscribers(
            guest_user, [stream]
        )
        self.assertEqual(
            streams_categorized_by_permissions,
            StreamsCategorizedByPermissionsForAddingSubscribers(
                authorized_streams=[],
                unauthorized_streams=[stream],
                streams_to_which_user_cannot_add_subscribers=[],
            ),
        )

        stream = self.make_stream("private_stream", invite_only=True)
        result = self.subscribe_via_post(guest_user, ["private_stream"], allow_fail=True)
        self.assert_json_error(result, "Not allowed for guest users")
        streams_categorized_by_permissions = filter_stream_authorization_for_adding_subscribers(
            guest_user, [stream]
        )
        self.assertEqual(
            streams_categorized_by_permissions,
            StreamsCategorizedByPermissionsForAddingSubscribers(
                authorized_streams=[],
                unauthorized_streams=[stream],
                streams_to_which_user_cannot_add_subscribers=[],
            ),
        )

        web_public_stream = self.make_stream("web_public_stream", is_web_public=True)
        public_stream = self.make_stream("public_stream", invite_only=False)
        private_stream = self.make_stream("private_stream2", invite_only=True)
        # This test should be added as soon as the subscription endpoint allows
        # guest users to subscribe to web-public streams. Although they are already
        # authorized, the decorator in "add_subscriptions_backend" still needs to be
        # deleted.
        #
        # result = self.subscribe_via_post(guest_user, ['web_public_stream'],
        #                                           is_web_public=True, allow_fail=True)
        # self.assert_json_success(result)
        streams_to_sub = [web_public_stream, public_stream, private_stream]
        streams_categorized_by_permissions = filter_stream_authorization_for_adding_subscribers(
            guest_user, streams_to_sub
        )
        self.assertEqual(
            streams_categorized_by_permissions,
            StreamsCategorizedByPermissionsForAddingSubscribers(
                authorized_streams=[web_public_stream],
                unauthorized_streams=[public_stream, private_stream],
                streams_to_which_user_cannot_add_subscribers=[],
            ),
        )

        # Guest can be subscribed by other users.
        normal_user = self.example_user("aaron")
        with self.capture_send_event_calls(expected_num_events=6) as events:
            self.subscribe_via_post(
                self.example_user("hamlet"),
                ["Denmark"],
                dict(principals=orjson.dumps([guest_user.id, normal_user.id]).decode()),
            )

        # Verify that stream creation event is sent to guest user only.
        stream_create_events = [
            event
            for event in events
            if event["event"]["type"] == "stream" and event["event"]["op"] == "create"
        ]
        self.assert_length(stream_create_events, 1)
        self.assertEqual(stream_create_events[0]["users"], [guest_user.id])

        # Verify that subscription add event is sent to both the users.
        subscription_add_events = [
            event
            for event in events
            if event["event"]["type"] == "subscription" and event["event"]["op"] == "add"
        ]
        self.assert_length(subscription_add_events, 2)
        self.assertEqual(subscription_add_events[0]["users"], [guest_user.id])
        self.assertEqual(subscription_add_events[1]["users"], [normal_user.id])

    def test_users_getting_add_peer_event(self) -> None:
        """
        Check users getting add_peer_event is correct
        """
        streams_to_sub = ["multi_user_stream"]
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        iago = self.example_user("iago")
        orig_user_ids_to_subscribe = [self.test_user.id, othello.id]
        self.subscribe_via_post(
            self.test_user,
            streams_to_sub,
            dict(principals=orjson.dumps(orig_user_ids_to_subscribe).decode()),
        )

        new_user_ids_to_subscribe = [iago.id, cordelia.id]
        with self.capture_send_event_calls(expected_num_events=5) as events:
            self.subscribe_via_post(
                self.test_user,
                streams_to_sub,
                dict(principals=orjson.dumps(new_user_ids_to_subscribe).decode()),
            )

        add_peer_events = [event for event in events if event["event"].get("op") == "peer_add"]
        (add_peer_event,) = add_peer_events

        self.assertEqual(add_peer_event["event"]["type"], "subscription")
        self.assertEqual(add_peer_event["event"]["op"], "peer_add")
        event_sent_to_ids = add_peer_event["users"]
        for user_id in new_user_ids_to_subscribe:
            # Make sure new users subscribed to stream is not in
            # peer_add event recipient list
            self.assertNotIn(user_id, event_sent_to_ids)
        for old_user in orig_user_ids_to_subscribe:
            # Check non-new users are in peer_add event recipient list.
            self.assertIn(old_user, event_sent_to_ids)

    def test_users_getting_remove_peer_event(self) -> None:
        """
        Check users getting add_peer_event is correct
        """
        user1 = self.example_user("othello")
        user2 = self.example_user("cordelia")
        user3 = self.example_user("hamlet")
        user4 = self.example_user("iago")
        user5 = self.example_user("AARON")
        user6 = self.example_user("prospero")
        user7 = self.example_user("shiva")
        user8 = self.example_user("ZOE")
        guest = self.example_user("polonius")

        realm = user1.realm

        stream1 = self.make_stream("stream1")
        stream2 = self.make_stream("stream2")
        stream3 = self.make_stream("stream3")
        stream4 = self.make_stream("stream4")
        stream5 = self.make_stream("stream5", is_web_public=True)
        stream6 = self.make_stream("stream6", is_web_public=True)
        stream7 = self.make_stream("stream7")
        private = self.make_stream("private_stream", invite_only=True)

        self.subscribe(user1, "stream1")
        self.subscribe(user1, "stream7")
        self.subscribe(user2, "stream1")
        self.subscribe(user3, "stream1")

        self.subscribe(user2, "stream2")
        self.subscribe(user2, "stream3")
        self.subscribe(user2, "stream4")
        self.subscribe(user2, "stream5")
        self.subscribe(user2, "stream6")
        self.subscribe(user2, "stream7")

        self.subscribe(guest, "stream4")

        self.subscribe(user1, "private_stream")
        self.subscribe(user2, "private_stream")
        self.subscribe(user3, "private_stream")

        user6_group_member_dict = UserGroupMembersData(
            direct_members=[user6.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            private, "can_administer_channel_group", user6_group_member_dict, acting_user=user6
        )

        user7_and_guests_group_member_dict = UserGroupMembersData(
            direct_members=[user7.id, guest.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            private,
            "can_add_subscribers_group",
            user7_and_guests_group_member_dict,
            acting_user=user7,
        )

        user8_group_member_dict = UserGroupMembersData(
            direct_members=[user8.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            private, "can_subscribe_group", user8_group_member_dict, acting_user=user8
        )

        # Sends 5 peer-remove events, 2 unsubscribe events
        # and 2 stream delete events for private streams.
        with (
            self.assert_database_query_count(27),
            self.assert_memcached_count(5),
            self.capture_send_event_calls(expected_num_events=9) as events,
        ):
            bulk_remove_subscriptions(
                realm,
                [user1, user2],
                [stream1, stream2, stream3, stream4, stream5, stream6, stream7, private],
                acting_user=None,
            )

        peer_events = [e for e in events if e["event"].get("op") == "peer_remove"]
        stream_delete_events = [
            e
            for e in events
            if e["event"].get("type") == "stream" and e["event"].get("op") == "delete"
        ]

        # We only care about a subset of users when we inspect
        # peer_remove events.
        our_user_ids = {
            user1.id,
            user2.id,
            user3.id,
            user4.id,
            user5.id,
            user6.id,
            user7.id,
            user8.id,
            guest.id,
        }

        notifications = []
        for event in peer_events:
            stream_ids = event["event"]["stream_ids"]
            stream_names = sorted(Stream.objects.get(id=stream_id).name for stream_id in stream_ids)
            removed_user_ids = set(event["event"]["user_ids"])
            notified_user_ids = set(event["users"]) & our_user_ids
            notifications.append((",".join(stream_names), removed_user_ids, notified_user_ids))

        notifications.sort(key=lambda tup: tup[0])

        self.assertEqual(
            notifications,
            [
                # user6, user7 and user8 have metadata access to
                # the channel via `can_administer_channel_group`,
                # `can_add_subscribers_group` and `can_subscribe_group`
                # respectively.
                (
                    "private_stream",
                    {user1.id, user2.id},
                    {user3.id, user4.id, user6.id, user7.id, user8.id},
                ),
                # stream1 and stream7 are non-guest public streams,
                # remove peer events for them will be sent together as
                # a separate event since they will have the same peer
                # user ids. This is not sent along with the stream2
                # and stream3 event as user1 is not subscribed to
                # stream2 and stream3 and thus peer_ids will be different.
                (
                    "stream1,stream7",
                    {user1.id, user2.id},
                    {user3.id, user4.id, user5.id, user6.id, user7.id, user8.id},
                ),
                # stream2 and stream3 are non-guest public streams,
                # remove peer events for them will be sent together as
                # a separate event since they will have the same peer
                # user ids. This is not sent along with the stream1
                # and stream7 event as user1 is not subscribed to
                # stream2 and stream3 and thus peer_ids will be different.
                (
                    "stream2,stream3",
                    {user2.id},
                    {user1.id, user3.id, user4.id, user5.id, user6.id, user7.id, user8.id},
                ),
                # stream4 has a guest user and a different set of peer
                # user ids than a non-guest public channel and it thus
                # gets its own event.
                (
                    "stream4",
                    {user2.id},
                    {
                        user1.id,
                        user3.id,
                        user4.id,
                        user5.id,
                        user6.id,
                        user7.id,
                        user8.id,
                        guest.id,
                    },
                ),
                # stream5 and stream6 are web public streams, remove
                # peer events for them will be sent together as a
                # separate event since they will have the same peer
                # user ids.
                (
                    "stream5,stream6",
                    {user2.id},
                    {
                        user1.id,
                        user3.id,
                        user4.id,
                        user5.id,
                        user6.id,
                        user7.id,
                        user8.id,
                        guest.id,
                    },
                ),
            ],
        )

        self.assert_length(stream_delete_events, 2)
        self.assertEqual(stream_delete_events[0]["users"], [user1.id])
        self.assertEqual(stream_delete_events[1]["users"], [user2.id])
        for event in stream_delete_events:
            event_stream_ids = event["event"]["stream_ids"]
            event_stream_objects = event["event"]["streams"]

            self.assert_length(event_stream_ids, 1)
            self.assertEqual(event_stream_ids[0], private.id)

            self.assert_length(event_stream_objects, 1)
            self.assertEqual(event_stream_objects[0]["stream_id"], private.id)

    def test_bulk_subscribe_many(self) -> None:
        # Create a whole bunch of streams
        streams = [f"stream_{i}" for i in range(30)]
        for stream_name in streams:
            self.make_stream(stream_name)

        desdemona = self.example_user("desdemona")

        test_users = [
            desdemona,
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            self.example_user("othello"),
            self.example_user("iago"),
            self.example_user("prospero"),
        ]

        # Subscribe out test users to some streams, including
        # some that we may soon subscribe them to.
        for stream_name in ["Verona", "Denmark", *streams[:10]]:
            for user in test_users:
                self.subscribe(user, stream_name)

        # Now unsubscribe users from the first few streams,
        # so they have to reactivate.
        for stream_name in streams[:5]:
            for user in test_users:
                self.unsubscribe(user, stream_name)

        test_user_ids = [user.id for user in test_users]

        with (
            self.assert_database_query_count(20),
            self.assert_memcached_count(11),
            mock.patch("zerver.views.streams.send_user_subscribed_and_new_channel_notifications"),
        ):
            self.subscribe_via_post(
                desdemona,
                streams,
                dict(principals=orjson.dumps(test_user_ids).decode()),
            )

    def test_subscriptions_add_for_principal(self) -> None:
        """
        You can subscribe other people to streams.
        """
        invitee = self.example_user("iago")
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(
            invitee.id, invitee.realm, invite_streams, policy_name="Public"
        )

    def test_subscriptions_add_for_principal_legacy_emails(self) -> None:
        invitee = self.example_user("iago")
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(
            invitee.email, invitee.realm, invite_streams, policy_name="Public"
        )

    def test_subscriptions_add_for_principal_deactivated(self) -> None:
        """
        You can't subscribe deactivated people to streams.
        """
        target_profile = self.example_user("cordelia")
        post_data = dict(
            principals=orjson.dumps([target_profile.id]).decode(),
        )
        self.subscribe_via_post(self.test_user, ["Verona"], post_data)

        do_deactivate_user(target_profile, acting_user=None)
        result = self.subscribe_via_post(self.test_user, ["Denmark"], post_data, allow_fail=True)
        self.assert_json_error(result, "User is deactivated", status_code=400)

    def test_subscriptions_add_for_principal_invite_only(self) -> None:
        """
        You can subscribe other people to invite only streams.
        """
        invitee = self.example_user("iago")
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(
            invitee.id,
            invitee.realm,
            invite_streams,
            invite_only=True,
            policy_name="Private, protected history",
        )

    def test_non_ascii_subscription_for_principal(self) -> None:
        """
        You can subscribe other people to streams even if they containing
        non-ASCII characters.
        """
        iago = self.example_user("iago")
        self.assert_adding_subscriptions_for_principal(
            iago.id, get_realm("zulip"), ["hümbüǵ"], policy_name="Public"
        )

    def test_subscription_add_invalid_principal_legacy_emails(self) -> None:
        """
        Calling subscribe on behalf of a principal that does not exist
        should return a JSON error.
        """
        invalid_principal = "rosencrantz-and-guildenstern@zulip.com"
        invalid_principal_realm = get_realm("zulip")
        # verify that invalid_principal actually doesn't exist
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user(invalid_principal, invalid_principal_realm)
        result = self.subscribe_via_post(
            self.test_user,
            self.streams,
            {"principals": orjson.dumps([invalid_principal]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "No such user", status_code=400)

    def test_subscription_add_invalid_principal(self) -> None:
        invalid_principal = 999
        invalid_principal_realm = get_realm("zulip")
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_profile_by_id_in_realm(invalid_principal, invalid_principal_realm)
        result = self.subscribe_via_post(
            self.test_user,
            self.streams,
            {"principals": orjson.dumps([invalid_principal]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "No such user", status_code=400)

    def test_subscription_add_principal_other_realm(self) -> None:
        """
        Calling subscribe on behalf of a principal in another realm
        should return a JSON error.
        """
        profile = self.mit_user("starnine")
        principal = profile.id
        # verify that principal exists (thus, the reason for the error is the cross-realming)
        self.assertIsInstance(profile, UserProfile)
        result = self.subscribe_via_post(
            self.test_user,
            self.streams,
            {"principals": orjson.dumps([principal]).decode()},
            allow_fail=True,
        )
        self.assert_json_error(result, "No such user", status_code=400)

    def helper_check_subs_before_and_after_remove(
        self,
        subscriptions: list[str],
        json_dict: dict[str, Any],
        email: str,
        new_subs: list[str],
        realm: Realm,
    ) -> None:
        """
        Check result of removing subscriptions.

        Unlike adding subscriptions, you can only remove subscriptions
        for yourself, so the result format is different.

        {"msg": "",
         "removed": ["Denmark", "Scotland", "Verona"],
         "not_removed": ["Rome"], "result": "success"}
        """
        result = self.client_delete(
            "/json/users/me/subscriptions", {"subscriptions": orjson.dumps(subscriptions).decode()}
        )
        json = self.assert_json_success(result)
        for key, val in json_dict.items():
            # we don't care about the order of the items
            self.assertEqual(sorted(val), sorted(json[key]))
        user = get_user(email, realm)
        new_streams = self.get_streams(user)
        self.assertEqual(sorted(new_streams), sorted(new_subs))

    def test_successful_subscriptions_remove(self) -> None:
        """
        Calling DELETE /json/users/me/subscriptions should successfully remove streams,
        and should determine which were removed vs which weren't subscribed to.
        We cannot randomly generate stream names because the remove code
        verifies whether streams exist.
        """
        self.assertGreaterEqual(len(self.streams), 2)
        streams_to_remove = self.streams[1:]
        not_subbed = [
            stream.name
            for stream in Stream.objects.filter(realm=get_realm("zulip"))
            if stream.name not in self.streams
        ]
        random.shuffle(not_subbed)
        self.assertNotEqual(len(not_subbed), 0)  # necessary for full test coverage
        try_to_remove = not_subbed[:3]  # attempt to remove up to 3 streams not already subbed to
        streams_to_remove.extend(try_to_remove)
        self.helper_check_subs_before_and_after_remove(
            streams_to_remove,
            {"removed": self.streams[1:], "not_removed": try_to_remove},
            self.test_email,
            [self.streams[0]],
            self.test_realm,
        )

    def test_subscriptions_remove_fake_stream(self) -> None:
        """
        Calling DELETE /json/users/me/subscriptions on a stream that doesn't exist
        should return a JSON error.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        # pick only one fake stream, to make checking the error message easy
        streams_to_remove = random_streams[:1]
        result = self.client_delete(
            "/json/users/me/subscriptions",
            {"subscriptions": orjson.dumps(streams_to_remove).decode()},
        )
        self.assert_json_error(result, f"Channel(s) ({random_streams[0]}) do not exist")

    def get_subscription(self, user_profile: UserProfile, stream_name: str) -> Subscription:
        stream = get_stream(stream_name, self.test_realm)
        return Subscription.objects.get(
            user_profile=user_profile,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id,
        )

    def test_subscriptions_add_notification_default_none(self) -> None:
        """
        When creating a subscription, the desktop, push, and audible notification
        settings for that stream are none. A value of None means to use the values
        inherited from the global notification settings.
        """
        user_profile = self.example_user("iago")
        invitee_user_id = user_profile.id
        invitee_realm = user_profile.realm
        user_profile.enable_stream_desktop_notifications = True
        user_profile.enable_stream_push_notifications = True
        user_profile.enable_stream_audible_notifications = True
        user_profile.enable_stream_email_notifications = True
        user_profile.save()
        current_stream = self.get_streams(user_profile)[0]
        invite_streams = self.make_random_stream_names([current_stream])
        self.assert_adding_subscriptions_for_principal(
            invitee_user_id, invitee_realm, invite_streams, policy_name="Public"
        )
        subscription = self.get_subscription(user_profile, invite_streams[0])

        with mock.patch("zerver.models.Recipient.__repr__", return_value="recip"):
            self.assertEqual(
                repr(subscription),
                "<Subscription: "
                f"<UserProfile: {user_profile.email} {user_profile.realm!r}> -> recip>",
            )

        self.assertIsNone(subscription.desktop_notifications)
        self.assertIsNone(subscription.push_notifications)
        self.assertIsNone(subscription.audible_notifications)
        self.assertIsNone(subscription.email_notifications)

    def test_mark_messages_as_unread_on_unsubscribe(self) -> None:
        realm = get_realm("zulip")
        user = self.example_user("iago")
        random_user = self.example_user("hamlet")
        stream1 = ensure_stream(realm, "stream1", invite_only=False, acting_user=None)
        stream2 = ensure_stream(realm, "stream2", invite_only=False, acting_user=None)
        private = ensure_stream(realm, "private_stream", invite_only=True, acting_user=None)

        self.subscribe(user, "stream1")
        self.subscribe(user, "stream2")
        self.subscribe(user, "private_stream")
        self.subscribe(random_user, "stream1")
        self.subscribe(random_user, "stream2")
        self.subscribe(random_user, "private_stream")

        self.send_stream_message(random_user, "stream1", "test", "test")
        self.send_stream_message(random_user, "stream2", "test", "test")
        self.send_stream_message(random_user, "private_stream", "test", "test")

        def get_unread_stream_data() -> list[UnreadStreamInfo]:
            raw_unread_data = get_raw_unread_data(user)
            aggregated_data = aggregate_unread_data(raw_unread_data, allow_empty_topic_name=True)
            return aggregated_data["streams"]

        result = get_unread_stream_data()
        self.assert_length(result, 3)
        self.assertEqual(result[0]["stream_id"], stream1.id)
        self.assertEqual(result[1]["stream_id"], stream2.id)
        self.assertEqual(result[2]["stream_id"], private.id)

        with self.captureOnCommitCallbacks(execute=True):
            # Unsubscribing should mark all the messages in stream2 as read
            self.unsubscribe(user, "stream2")
            self.unsubscribe(user, "private_stream")

        self.subscribe(user, "stream2")
        self.subscribe(user, "private_stream")
        result = get_unread_stream_data()
        self.assert_length(result, 1)
        self.assertEqual(result[0]["stream_id"], stream1.id)

    def test_gather_subscriptions_deactivated_streams(self) -> None:
        """
        Check that gather_subscriptions_helper does/doesn't include deactivated streams in its
        results with `exclude_archived` parameter.
        """
        realm = get_realm("zulip")
        admin_user = self.example_user("iago")
        non_admin_user = self.example_user("cordelia")

        self.login_user(admin_user)

        for stream_name in ["stream1", "stream2", "stream3"]:
            self.make_stream(stream_name, realm=realm, invite_only=False)
            self.subscribe(admin_user, stream_name)
            self.subscribe(non_admin_user, stream_name)
            self.subscribe(self.example_user("othello"), stream_name)

        def archive_stream(stream_name: str) -> None:
            stream_id = get_stream(stream_name, realm).id
            result = self.client_delete(f"/json/streams/{stream_id}")
            self.assert_json_success(result)

        # Deleted/deactivated stream should not be returned in the helper results
        admin_before_delete = gather_subscriptions_helper(admin_user)
        non_admin_before_delete = gather_subscriptions_helper(non_admin_user)

        # Delete our stream
        archive_stream("stream1")

        # Get subs after delete
        admin_after_delete = gather_subscriptions_helper(admin_user)
        non_admin_after_delete = gather_subscriptions_helper(non_admin_user)

        admin_after_delete_include_archived = gather_subscriptions_helper(
            admin_user, include_archived_channels=True
        )

        # Compare results - should be 1 stream less
        self.assertTrue(
            len(admin_before_delete.subscriptions) == len(admin_after_delete.subscriptions) + 1,
            "Expected exactly 1 less stream from gather_subscriptions_helper",
        )
        self.assertTrue(
            len(non_admin_before_delete.subscriptions)
            == len(non_admin_after_delete.subscriptions) + 1,
            "Expected exactly 1 less stream from gather_subscriptions_helper",
        )

        # Compare results - should be the same number of streams
        self.assertTrue(
            len(admin_before_delete.subscriptions) + len(admin_before_delete.unsubscribed)
            == len(admin_after_delete_include_archived.subscriptions)
            + len(admin_after_delete_include_archived.unsubscribed),
            "Expected exact number of streams from gather_subscriptions_helper",
        )

    def test_validate_user_access_to_subscribers_helper(self) -> None:
        """
        Ensure the validate_user_access_to_subscribers_helper is properly raising
        ValidationError on missing user, user not-in-realm.
        """
        user_profile = self.example_user("othello")
        realm_name = "no_othello_allowed"
        realm = do_create_realm(realm_name, "Everyone but Othello is allowed")
        nobody_group = NamedUserGroup.objects.get(
            name="role:nobody", is_system_group=True, realm_for_sharding=realm
        )
        stream_dict = {
            "name": "publicstream",
            "description": "Public stream with public history",
            "realm_id": realm.id,
            "can_administer_channel_group_id": nobody_group.id,
        }

        # For this test to work, othello can't be in the no_othello_here realm
        self.assertNotEqual(
            user_profile.realm.id, realm.id, "Expected othello user to not be in this realm."
        )

        # This should result in missing user
        with self.assertRaises(ValidationError):
            validate_user_access_to_subscribers_helper(
                None,
                stream_dict,
                lambda user_profile: True,
                UserGroupMembershipDetails(user_recursive_group_ids=None),
            )

        # This should result in user not in realm
        with self.assertRaises(ValidationError):
            validate_user_access_to_subscribers_helper(
                user_profile,
                stream_dict,
                lambda user_profile: True,
                UserGroupMembershipDetails(user_recursive_group_ids=None),
            )

    def test_subscriptions_query_count(self) -> None:
        """
        Test database query count when creating stream with api/v1/users/me/subscriptions.
        """
        user1 = self.example_user("cordelia")
        user2 = self.example_user("iago")
        new_streams = [
            "query_count_stream_1",
            "query_count_stream_2",
            "query_count_stream_3",
        ]

        # Test creating a public stream when realm does not have a notification stream.
        with self.assert_database_query_count(44):
            self.subscribe_via_post(
                self.test_user,
                [new_streams[0]],
                dict(principals=orjson.dumps([user1.id, user2.id]).decode()),
            )

        # Test creating private stream.
        with self.assert_database_query_count(52):
            self.subscribe_via_post(
                self.test_user,
                [new_streams[1]],
                dict(principals=orjson.dumps([user1.id, user2.id]).decode()),
                invite_only=True,
            )

        # Test creating a public stream with announce when realm has a new_stream_announcements_stream.
        new_stream_announcements_stream = get_stream(self.streams[0], self.test_realm)
        self.test_realm.new_stream_announcements_stream_id = new_stream_announcements_stream.id
        self.test_realm.save()
        with self.assert_database_query_count(56):
            self.subscribe_via_post(
                self.test_user,
                [new_streams[2]],
                dict(
                    announce="true",
                    principals=orjson.dumps([user1.id, user2.id]).decode(),
                ),
            )

    def test_stream_subscriber_count_upon_bulk_subscription(self) -> None:
        """
        Test subscriber_count increases for the correct streams
        upon bulk subscription.

        We use the api here as we want this to be end-to-end.
        """

        stream_names = [f"stream_{i}" for i in range(10)]
        stream_ids = {self.make_stream(stream_name).id for stream_name in stream_names}

        desdemona = self.example_user("desdemona")
        self.login_user(desdemona)

        user_ids = [
            desdemona.id,
            self.example_user("cordelia").id,
            self.example_user("hamlet").id,
            self.example_user("othello").id,
            self.example_user("iago").id,
            self.example_user("prospero").id,
        ]

        streams_subscriber_counts_before_subscribe = self.fetch_streams_subscriber_count(stream_ids)
        other_streams_subscriber_counts_before_subscribe = (
            self.fetch_other_streams_subscriber_count(stream_ids)
        )

        # Subscribe users to the streams.
        self.subscribe_via_post(
            desdemona,
            stream_names,
            dict(principals=orjson.dumps(user_ids).decode()),
        )

        # DB-refresh streams.
        streams_subscriber_counts_after_subscribe = self.fetch_streams_subscriber_count(stream_ids)
        # DB-refresh other streams.
        other_streams_subscriber_counts_after_subscribe = self.fetch_other_streams_subscriber_count(
            stream_ids
        )

        # Ensure an increase in subscriber_count
        self.assert_stream_subscriber_count(
            streams_subscriber_counts_before_subscribe,
            streams_subscriber_counts_after_subscribe,
            expected_difference=len(user_ids),
        )

        # Make sure other streams are not affected.
        self.assert_stream_subscriber_count(
            other_streams_subscriber_counts_before_subscribe,
            other_streams_subscriber_counts_after_subscribe,
            expected_difference=0,
        )

        # Re-subscribe same users to the same streams.
        self.subscribe_via_post(
            desdemona,
            stream_names,
            dict(principals=orjson.dumps(user_ids).decode()),
        )
        # DB-refresh streams.
        streams_subscriber_counts_after_resubscribe = self.fetch_streams_subscriber_count(
            stream_ids
        )
        # Ensure Idempotency; subscribing "already" subscribed users shouldn't change subscriber_count.
        self.assert_stream_subscriber_count(
            streams_subscriber_counts_after_subscribe,
            streams_subscriber_counts_after_resubscribe,
            expected_difference=0,
        )

    def test_stream_subscriber_count_upon_bulk_unsubscription(self) -> None:
        """
        Test subscriber_count decreases for the correct streams
        upon bulk un-subscription.

        We use the api here as we want this to be end-to-end.
        """

        stream_names = [f"stream_{i}" for i in range(10)]
        stream_ids = {self.make_stream(stream_name).id for stream_name in stream_names}

        desdemona = self.example_user("desdemona")
        self.login_user(desdemona)

        user_ids = [
            desdemona.id,
            self.example_user("cordelia").id,
            self.example_user("hamlet").id,
            self.example_user("othello").id,
            self.example_user("iago").id,
            self.example_user("prospero").id,
        ]

        # Subscribe users to the streams.
        self.subscribe_via_post(
            desdemona,
            stream_names,
            dict(principals=orjson.dumps(user_ids).decode()),
        )

        streams_subscriber_counts_before_unsubscribe = self.fetch_streams_subscriber_count(
            stream_ids
        )
        other_streams_subscriber_counts_before_unsubscribe = (
            self.fetch_other_streams_subscriber_count(stream_ids)
        )

        # Unsubscribe users from the same streams.
        self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps(stream_names).decode(),
                "principals": orjson.dumps(user_ids).decode(),
            },
        )

        # DB-refresh streams.
        streams_subscriber_counts_after_unsubscribe = self.fetch_streams_subscriber_count(
            stream_ids
        )
        # DB-refresh other streams.
        other_streams_subscriber_counts_after_unsubscribe = (
            self.fetch_other_streams_subscriber_count(stream_ids)
        )

        # Ensure a decrease in subscriber_count
        self.assert_stream_subscriber_count(
            streams_subscriber_counts_before_unsubscribe,
            streams_subscriber_counts_after_unsubscribe,
            expected_difference=-len(user_ids),
        )

        # Make sure other streams are not affected.
        self.assert_stream_subscriber_count(
            other_streams_subscriber_counts_before_unsubscribe,
            other_streams_subscriber_counts_after_unsubscribe,
            expected_difference=0,
        )

        # Re-Unsubscribe users from the same streams.
        self.client_delete(
            "/json/users/me/subscriptions",
            {
                "subscriptions": orjson.dumps(stream_names).decode(),
                "principals": orjson.dumps(user_ids).decode(),
            },
        )
        # DB-refresh streams.
        streams_subscriber_counts_after_reunsubscribe = self.fetch_streams_subscriber_count(
            stream_ids
        )
        # Ensure Idempotency; unsubscribing "already" non-subscribed users shouldn't change subscriber_count.
        self.assert_stream_subscriber_count(
            streams_subscriber_counts_after_unsubscribe,
            streams_subscriber_counts_after_reunsubscribe,
            expected_difference=0,
        )

    def test_notification_bot_dm_on_subscription(self) -> None:
        desdemona = self.example_user("desdemona")
        realm = desdemona.realm
        self.login_user(desdemona)
        bot = self.notification_bot(realm)
        test_channel = self.make_stream("test A")
        announce = realm.new_stream_announcements_stream
        assert announce is not None
        user_ids = [
            desdemona.id,
            self.example_user("cordelia").id,
            self.example_user("hamlet").id,
            self.example_user("othello").id,
            self.example_user("iago").id,
            self.example_user("prospero").id,
        ]
        principals_dict = dict(
            principals=orjson.dumps(user_ids).decode(), announce=orjson.dumps(True).decode()
        )
        # When subscribing to an already existing channel with announce=True,
        # the bot should send DMs to all the newly subscribed users, but
        # no announcement message.
        now = timezone_now()
        response = self.subscribe_via_post(
            desdemona,
            [test_channel.name],
            principals_dict,
        )
        data = self.assert_json_success(response)
        self.assertEqual(data["new_subscription_messages_sent"], True)

        notification_bot_dms = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.PERSONAL,
            date_sent__gt=now,
        )
        self.assert_length(notification_bot_dms, 5)
        notif_bot_dm_recipients = [
            dm["recipient__type_id"] for dm in notification_bot_dms.values("recipient__type_id")
        ]
        self.assertSetEqual(
            {id for id in user_ids if id != desdemona.id}, set(notif_bot_dm_recipients)
        )

        announcement_channel_message = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=announce.id,
            date_sent__gt=now,
        )
        self.assertEqual(announcement_channel_message.count(), 0)

        # When subscribing to a newly created channel with announce=True,
        # we expect an announcement message and new channel message,
        # but no DM notifications.
        now = timezone_now()
        response = self.subscribe_via_post(
            desdemona,
            ["test B"],
            principals_dict,
        )
        data = self.assert_json_success(response)
        self.assertEqual(data["new_subscription_messages_sent"], True)

        notification_bot_dms = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.PERSONAL,
            date_sent__gt=now,
        )
        self.assertEqual(notification_bot_dms.count(), 0)

        announcement_channel_message = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=announce.id,
            date_sent__gt=now,
        )
        self.assert_length(announcement_channel_message.values(), 1)
        self.assertEqual(
            announcement_channel_message[0].content,
            f"@_**{desdemona.full_name}|{desdemona.id}** created a new channel #**test B**.",
        )

        new_channel = get_stream("test B", realm)
        new_channel_message = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=new_channel.id,
            date_sent__gt=now,
        )
        self.assert_length(new_channel_message.values(), 1)
        self.assertEqual(
            new_channel_message[0].topic_name(), Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME
        )
        self.assertEqual(
            new_channel_message[0].content,
            f"**Public** channel created by @_**{desdemona.full_name}|{desdemona.id}**. **Description:**\n"
            "```` quote\n*No description.*\n````",
        )

        # When subscribing to an already existing channel, if the number of new
        # subscriptions exceeds the limit, no DMs or announcement message should
        # be sent.
        now = timezone_now()
        test_channel = self.make_stream("test C")
        with self.settings(MAX_BULK_NEW_SUBSCRIPTION_MESSAGES=5):
            response = self.subscribe_via_post(
                desdemona,
                [test_channel.name],
                principals_dict,
            )
        data = self.assert_json_success(response)
        self.assertEqual(data["new_subscription_messages_sent"], False)

        notification_bot_dms = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.PERSONAL,
            date_sent__gt=now,
        )
        self.assertEqual(notification_bot_dms.count(), 0)

        announcement_channel_message = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=announce.id,
            date_sent__gt=now,
        )
        self.assertEqual(announcement_channel_message.count(), 0)

        # The max number of new subscriptions limit only impacts
        # DM notifications, so for a newly created channel, we
        # still expect an announcement message and new channel
        # message (and no DM notifications).
        now = timezone_now()
        with self.settings(MAX_BULK_NEW_SUBSCRIPTION_MESSAGES=5):
            response = self.subscribe_via_post(
                desdemona,
                ["test D"],
                principals_dict,
            )
        data = self.assert_json_success(response)
        self.assertEqual(data["new_subscription_messages_sent"], False)

        notification_bot_dms = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.PERSONAL,
            date_sent__gt=now,
        )
        self.assertEqual(notification_bot_dms.count(), 0)

        announcement_channel_message = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=announce.id,
            date_sent__gt=now,
        )
        self.assertEqual(announcement_channel_message.count(), 1)
        self.assertEqual(
            announcement_channel_message[0].content,
            f"@_**{desdemona.full_name}|{desdemona.id}** created a new channel #**test D**.",
        )

        new_channel = get_stream("test D", realm)
        new_channel_message = Message.objects.filter(
            realm_id=realm.id,
            sender=bot.id,
            recipient__type=Recipient.STREAM,
            recipient__type_id=new_channel.id,
            date_sent__gt=now,
        )
        self.assert_length(new_channel_message.values(), 1)
        self.assertEqual(
            new_channel_message[0].topic_name(), Realm.STREAM_EVENTS_NOTIFICATION_TOPIC_NAME
        )
        self.assertEqual(
            new_channel_message[0].content,
            f"**Public** channel created by @_**{desdemona.full_name}|{desdemona.id}**. **Description:**\n"
            "```` quote\n*No description.*\n````",
        )

        # When send_new_subscription_messages is false, confirm that the
        # response doesn't include new_subscription_messages_sent boolean
        # field.
        response = self.subscribe_via_post(
            desdemona,
            ["test E"],
            dict(
                principals=orjson.dumps(user_ids).decode(),
                send_new_subscription_messages=orjson.dumps(False).decode(),
            ),
        )
        data = self.assert_json_success(response)
        self.assertNotIn("new_subscription_messages_sent", data)


class InviteOnlyStreamTest(ZulipTestCase):
    def test_must_be_subbed_to_send(self) -> None:
        """
        If you try to send a message to an invite-only stream to which
        you aren't subscribed, you'll get a 400.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        # Create Saxony as an invite-only stream.
        self.assert_json_success(self.subscribe_via_post(user, ["Saxony"], invite_only=True))

        cordelia = self.example_user("cordelia")
        with self.assertRaises(JsonableError):
            self.send_stream_message(cordelia, "Saxony")

    def test_list_respects_invite_only_bit(self) -> None:
        """
        Make sure that /api/v1/users/me/subscriptions properly returns
        the invite-only bit for streams that are invite-only
        """

        user = self.example_user("hamlet")
        self.login_user(user)

        self.subscribe_via_post(user, ["Saxony"], invite_only=True)
        self.subscribe_via_post(user, ["Normandy"], invite_only=False)
        result = self.api_get(user, "/api/v1/users/me/subscriptions")
        response_dict = self.assert_json_success(result)
        self.assertIn("subscriptions", response_dict)
        for sub in response_dict["subscriptions"]:
            if sub["name"] == "Normandy":
                self.assertEqual(
                    sub["invite_only"], False, "Normandy was mistakenly marked private"
                )
            if sub["name"] == "Saxony":
                self.assertEqual(sub["invite_only"], True, "Saxony was not properly marked private")

    def test_inviteonly(self) -> None:
        # Creating an invite-only stream is allowed
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        stream_name = "Saxony"

        result = self.subscribe_via_post(hamlet, [stream_name], invite_only=True)

        json = self.assert_json_success(result)
        self.assertEqual(json["subscribed"], {str(hamlet.id): [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is not allowed
        self.login_user(othello)
        result = self.subscribe_via_post(othello, [stream_name], allow_fail=True)
        self.assert_json_error(result, "Unable to access channel (Saxony).")

        # authorization_errors_fatal=False works
        self.login_user(othello)
        result = self.subscribe_via_post(
            othello,
            [stream_name],
            extra_post_data={"authorization_errors_fatal": orjson.dumps(False).decode()},
        )
        json = self.assert_json_success(result)
        self.assertEqual(json["unauthorized"], [stream_name])
        self.assertEqual(json["subscribed"], {})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is allowed
        # if user belongs to can_subscribe_group.
        stream = get_stream(stream_name, hamlet.realm)
        setting_group_members_dict = UserGroupMembersData(
            direct_members=[othello.id], direct_subgroups=[]
        )
        do_change_stream_group_based_setting(
            stream,
            "can_subscribe_group",
            setting_group_members_dict,
            acting_user=hamlet,
        )
        result = self.subscribe_via_post(othello, [stream_name])
        json = self.assert_json_success(result)
        self.assertEqual(json["subscribed"], {str(othello.id): [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Inviting another user to an invite-only stream is allowed
        self.login_user(hamlet)
        prospero = self.example_user("prospero")
        result = self.subscribe_via_post(
            hamlet,
            [stream_name],
            extra_post_data={"principals": orjson.dumps([prospero.id]).decode()},
        )
        json = self.assert_json_success(result)
        self.assertEqual(json["subscribed"], {str(prospero.id): [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Make sure all 3 users are subscribed to this stream
        result = self.api_get(hamlet, f"/api/v1/streams/{stream.id}/members")
        json = self.assert_json_success(result)

        self.assertTrue(othello.id in json["subscribers"])
        self.assertTrue(hamlet.id in json["subscribers"])
        self.assertTrue(prospero.id in json["subscribers"])


class StreamTrafficTest(ZulipTestCase):
    def test_average_weekly_stream_traffic_calculation(self) -> None:
        # No traffic data for the stream
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=300), {1: 4003}),
            0,
        )

        # using high numbers here to make it more likely to catch small errors in the denominators
        # of the calculations. That being said we don't want to go over 100, since then the 2
        # significant digits calculation gets applied
        # old stream
        self.assertEqual(
            get_average_weekly_stream_traffic(
                42, timezone_now() - timedelta(days=300), {42: 98 * 4 + 3}
            ),
            98,
        )
        # stream between 7 and 27 days old
        self.assertEqual(
            get_average_weekly_stream_traffic(
                42, timezone_now() - timedelta(days=10), {42: (98 * 10 + 9) // 7}
            ),
            98,
        )
        # stream less than 7 days old
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=5), {42: 100}),
            None,
        )

        # average traffic between 0 and 1
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=300), {42: 1}), 1
        )

    def test_round_to_2_significant_digits(self) -> None:
        self.assertEqual(120, round_to_2_significant_digits(116))


class NoRecipientIDsTest(ZulipTestCase):
    def test_no_recipient_ids(self) -> None:
        user_profile = self.example_user("cordelia")

        Subscription.objects.filter(
            user_profile=user_profile, recipient__type=Recipient.STREAM
        ).delete()
        subs = gather_subscriptions_helper(user_profile).subscriptions

        # Checks that gather_subscriptions_helper will not return anything
        # since there will not be any recipients, without crashing.
        #
        # This covers a rare corner case.
        self.assert_length(subs, 0)
