# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
#
# This module is closely integrated with zerver/lib/event_schema.py
# and zerver/lib/data_types.py systems for validating the schemas of
# events; it also uses the OpenAPI tools to validate our documentation.
import base64
import copy
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from enum import Enum
from io import StringIO
from typing import Any
from unittest import mock

import orjson
import time_machine
from dateutil.parser import parse as dateparser
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.alert_words import do_add_alert_words, do_remove_alert_words
from zerver.actions.bots import (
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
)
from zerver.actions.channel_folders import (
    check_add_channel_folder,
    do_archive_channel_folder,
    do_change_channel_folder_description,
    do_change_channel_folder_name,
    do_unarchive_channel_folder,
    try_reorder_realm_channel_folders,
)
from zerver.actions.create_user import do_create_user, do_reactivate_user
from zerver.actions.custom_profile_fields import (
    check_remove_custom_profile_field_value,
    do_remove_realm_custom_profile_field,
    do_update_user_custom_profile_data_if_changed,
    try_add_realm_custom_profile_field,
    try_update_realm_custom_profile_field,
)
from zerver.actions.default_streams import (
    do_add_default_stream,
    do_add_streams_to_default_stream_group,
    do_change_default_stream_group_description,
    do_change_default_stream_group_name,
    do_create_default_stream_group,
    do_remove_default_stream,
    do_remove_default_stream_group,
    do_remove_streams_from_default_stream_group,
    lookup_default_stream_groups,
)
from zerver.actions.invites import (
    do_create_multiuse_invite_link,
    do_invite_users,
    do_revoke_multi_use_invite,
    do_revoke_user_invite,
)
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import (
    build_message_edit_request,
    do_update_embedded_data,
    do_update_message,
)
from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.muted_users import do_mute_user, do_unmute_user
from zerver.actions.navigation_views import (
    do_add_navigation_view,
    do_remove_navigation_view,
    do_update_navigation_view,
)
from zerver.actions.onboarding_steps import do_mark_onboarding_step_as_read
from zerver.actions.presence import do_update_user_presence
from zerver.actions.reactions import do_add_reaction, do_remove_reaction
from zerver.actions.realm_domains import (
    do_add_realm_domain,
    do_change_realm_domain,
    do_remove_realm_domain,
)
from zerver.actions.realm_emoji import check_add_realm_emoji, do_remove_realm_emoji
from zerver.actions.realm_icon import do_change_icon_source
from zerver.actions.realm_linkifiers import (
    check_reorder_linkifiers,
    do_add_linkifier,
    do_remove_linkifier,
    do_update_linkifier,
)
from zerver.actions.realm_logo import do_change_logo_source
from zerver.actions.realm_playgrounds import check_add_realm_playground, do_remove_realm_playground
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_change_realm_permission_group_setting,
    do_change_realm_plan_type,
    do_deactivate_realm,
    do_set_push_notifications_enabled_end_timestamp,
    do_set_realm_authentication_methods,
    do_set_realm_moderation_request_channel,
    do_set_realm_new_stream_announcements_stream,
    do_set_realm_property,
    do_set_realm_signup_announcements_stream,
    do_set_realm_user_default_setting,
    do_set_realm_zulip_update_announcements_stream,
)
from zerver.actions.saved_snippets import (
    do_create_saved_snippet,
    do_delete_saved_snippet,
    do_edit_saved_snippet,
)
from zerver.actions.scheduled_messages import (
    check_schedule_message,
    delete_scheduled_message,
    edit_scheduled_message,
)
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_description,
    do_change_stream_folder,
    do_change_stream_group_based_setting,
    do_change_stream_message_retention_days,
    do_change_stream_permission,
    do_change_subscription_property,
    do_deactivate_stream,
    do_rename_stream,
    do_set_stream_property,
    do_unarchive_stream,
)
from zerver.actions.submessage import do_add_submessage
from zerver.actions.typing import (
    check_send_typing_notification,
    do_send_direct_message_edit_typing_notification,
    do_send_stream_message_edit_typing_notification,
    do_send_stream_typing_notification,
)
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    check_add_user_group,
    do_change_user_group_permission_setting,
    do_deactivate_user_group,
    do_reactivate_user_group,
    do_update_user_group_description,
    do_update_user_group_name,
    remove_subgroups_from_user_group,
)
from zerver.actions.user_settings import (
    do_change_avatar_fields,
    do_change_full_name,
    do_change_user_delivery_email,
    do_change_user_setting,
    do_regenerate_api_key,
)
from zerver.actions.user_status import do_update_user_status
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.actions.users import (
    do_change_is_imported_stub,
    do_change_user_role,
    do_deactivate_user,
    do_update_outgoing_webhook_service,
)
from zerver.actions.video_calls import do_set_zoom_token
from zerver.lib.drafts import DraftData, do_create_drafts, do_delete_draft, do_edit_draft
from zerver.lib.event_schema import (
    check_alert_words,
    check_attachment_add,
    check_attachment_remove,
    check_attachment_update,
    check_channel_folder_add,
    check_channel_folder_reorder,
    check_channel_folder_update,
    check_custom_profile_fields,
    check_default_stream_groups,
    check_default_streams,
    check_delete_message,
    check_direct_message,
    check_draft_add,
    check_draft_remove,
    check_draft_update,
    check_has_zoom_token,
    check_heartbeat,
    check_invites_changed,
    check_legacy_presence,
    check_message,
    check_modern_presence,
    check_muted_topics,
    check_muted_users,
    check_navigation_view_add,
    check_navigation_view_remove,
    check_navigation_view_update,
    check_onboarding_steps,
    check_push_device,
    check_reaction_add,
    check_reaction_remove,
    check_realm_bot_add,
    check_realm_bot_delete,
    check_realm_bot_update,
    check_realm_deactivated,
    check_realm_default_update,
    check_realm_domains_add,
    check_realm_domains_change,
    check_realm_domains_remove,
    check_realm_emoji_update,
    check_realm_export,
    check_realm_export_consent,
    check_realm_linkifiers,
    check_realm_playgrounds,
    check_realm_update,
    check_realm_update_dict,
    check_realm_user_add,
    check_realm_user_remove,
    check_realm_user_update,
    check_saved_snippets_add,
    check_saved_snippets_remove,
    check_saved_snippets_update,
    check_scheduled_message_add,
    check_scheduled_message_remove,
    check_scheduled_message_update,
    check_stream_create,
    check_stream_delete,
    check_stream_update,
    check_submessage,
    check_subscription_add,
    check_subscription_peer_add,
    check_subscription_peer_remove,
    check_subscription_remove,
    check_subscription_update,
    check_typing_edit_message_start,
    check_typing_edit_message_stop,
    check_typing_start,
    check_typing_stop,
    check_update_message,
    check_update_message_flags_add,
    check_update_message_flags_remove,
    check_user_group_add,
    check_user_group_add_members,
    check_user_group_add_subgroups,
    check_user_group_remove,
    check_user_group_remove_members,
    check_user_group_remove_subgroups,
    check_user_group_update,
    check_user_settings_update,
    check_user_status,
    check_user_topic,
)
from zerver.lib.events import apply_events, fetch_initial_state_data, post_process_state
from zerver.lib.exceptions import InvalidBouncerPublicKeyError
from zerver.lib.markdown import render_message_markdown
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.muted_users import get_mute_object
from zerver.lib.push_registration import (
    RegisterPushDeviceToBouncerQueueItem,
    handle_register_push_device_to_bouncer,
)
from zerver.lib.streams import check_update_all_streams_active_status, user_has_metadata_access
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_dummy_file,
    get_subscription,
    get_test_image_file,
    read_test_image_file,
    reset_email_visibility_to_everyone_in_zulip_realm,
    stdout_suppressed,
)
from zerver.lib.timestamp import convert_to_UTC, datetime_to_timestamp
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.types import (
    ProfileDataElementUpdateDict,
    UserGroupMembersData,
    UserGroupMembersDict,
)
from zerver.lib.upload import upload_message_attachment
from zerver.lib.user_groups import (
    UserGroupMembershipDetails,
    get_group_setting_value_for_api,
    get_role_based_system_groups_dict,
)
from zerver.models import (
    Attachment,
    CustomProfileField,
    ImageAttachment,
    Message,
    MultiuseInvite,
    NamedUserGroup,
    PreregistrationUser,
    PushDevice,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmExport,
    RealmFilter,
    RealmPlayground,
    RealmUserDefault,
    SavedSnippet,
    Service,
    Stream,
    UserMessage,
    UserPresence,
    UserProfile,
    UserStatus,
    UserTopic,
)
from zerver.models.bots import get_bot_services
from zerver.models.clients import get_client
from zerver.models.groups import SystemGroups
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.streams import StreamTopicsPolicyEnum, get_stream
from zerver.models.users import get_user_by_delivery_email
from zerver.openapi.openapi import validate_against_openapi_schema
from zerver.tornado.django_api import send_event_rollback_unsafe
from zerver.tornado.event_queue import (
    allocate_client_descriptor,
    clear_client_event_queues_for_testing,
    create_heartbeat_event,
    mark_clients_to_reload,
    send_restart_events,
    send_web_reload_client_events,
)
from zerver.views.realm_playgrounds import access_playground_by_id
from zerver.worker.thumbnail import ensure_thumbnails


class BaseAction(ZulipTestCase):
    """Core class for verifying the apply_event race handling logic as
    well as the event formatting logic of any function using send_event_rollback_unsafe.

    See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html#testing
    for extensive design details for this testing system.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")

    @contextmanager
    def verify_action(
        self,
        *,
        event_types: list[str] | None = None,
        include_subscribers: bool = True,
        state_change_expected: bool = True,
        notification_settings_null: bool = False,
        client_gravatar: bool = True,
        user_avatar_url_field_optional: bool = False,
        slim_presence: bool = False,
        include_streams: bool = True,
        num_events: int = 1,
        bulk_message_deletion: bool = True,
        stream_typing_notifications: bool = True,
        user_settings_object: bool = False,
        pronouns_field_type_supported: bool = True,
        linkifier_url_template: bool = True,
        user_list_incomplete: bool = False,
        client_is_old: bool = False,
        include_deactivated_groups: bool = False,
        archived_channels: bool = False,
        allow_empty_topic_name: bool = True,
        simplified_presence_events: bool = False,
    ) -> Iterator[list[dict[str, Any]]]:
        """
        Make sure we have a clean slate of client descriptors for these tests.
        If we don't do this, then certain failures will only manifest when you
        run multiple tests within a single test function.

        See also https://zulip.readthedocs.io/en/latest/subsystems/events-system.html#testing
        for details on the design of this test system.
        """
        clear_client_event_queues_for_testing()

        client = allocate_client_descriptor(
            dict(
                user_profile_id=self.user_profile.id,
                realm_id=self.user_profile.realm_id,
                event_types=event_types,
                client_type_name="website",
                apply_markdown=True,
                client_gravatar=client_gravatar,
                slim_presence=slim_presence,
                all_public_streams=False,
                queue_timeout=600,
                last_connection_time=time.time(),
                narrow=[],
                bulk_message_deletion=bulk_message_deletion,
                stream_typing_notifications=stream_typing_notifications,
                user_settings_object=user_settings_object,
                pronouns_field_type_supported=pronouns_field_type_supported,
                linkifier_url_template=linkifier_url_template,
                user_list_incomplete=user_list_incomplete,
                include_deactivated_groups=include_deactivated_groups,
                archived_channels=archived_channels,
                simplified_presence_events=simplified_presence_events,
            )
        )

        # hybrid_state = initial fetch state + re-applying events triggered by our action
        # normal_state = do action then fetch at the end (the "normal" code path)
        hybrid_state = fetch_initial_state_data(
            self.user_profile,
            realm=self.user_profile.realm,
            event_types=event_types,
            client_gravatar=client_gravatar,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
            include_streams=include_streams,
            pronouns_field_type_supported=pronouns_field_type_supported,
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
            include_deactivated_groups=include_deactivated_groups,
            archived_channels=archived_channels,
        )

        if client_is_old:
            mark_clients_to_reload([client.event_queue.id])

        events: list[dict[str, Any]] = []

        # We want even those `send_event_rollback_unsafe` calls which have
        # been hooked to `transaction.on_commit` to execute in tests.
        # See the comment in `ZulipTestCase.capture_send_event_calls`.
        with self.captureOnCommitCallbacks(execute=True):
            yield events

        self.user_profile.refresh_from_db()

        # Append to an empty list so the result is accessible through the
        # reference we just yielded.
        events += client.event_queue.contents()

        content = {
            "queue_id": "123.12",
            # The JSON wrapper helps in converting tuples to lists
            # as tuples aren't valid JSON structure.
            "events": orjson.loads(orjson.dumps(events)),
            "msg": "",
            "result": "success",
        }
        validate_against_openapi_schema(content, "/events", "get", "200")
        self.assert_length(events, num_events)
        initial_state = copy.deepcopy(hybrid_state)
        post_process_state(
            self.user_profile, initial_state, notification_settings_null, allow_empty_topic_name
        )
        before = orjson.dumps(initial_state)
        apply_events(
            self.user_profile,
            state=hybrid_state,
            events=events,
            fetch_event_types=None,
            client_gravatar=client_gravatar,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
            include_deactivated_groups=include_deactivated_groups,
            archived_channels=archived_channels,
            simplified_presence_events=simplified_presence_events,
        )
        post_process_state(
            self.user_profile, hybrid_state, notification_settings_null, allow_empty_topic_name
        )
        after = orjson.dumps(hybrid_state)

        if state_change_expected:
            if before == after:  # nocoverage
                print(orjson.dumps(initial_state, option=orjson.OPT_INDENT_2).decode())
                print(events)
                raise AssertionError(
                    "Test does not exercise enough code -- events do not change state."
                )
        else:
            try:
                self.match_states(initial_state, copy.deepcopy(hybrid_state), events)
            except AssertionError:  # nocoverage
                raise AssertionError("Test is invalid--state actually does change here.")

        normal_state = fetch_initial_state_data(
            self.user_profile,
            realm=self.user_profile.realm,
            event_types=event_types,
            client_gravatar=client_gravatar,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
            include_streams=include_streams,
            pronouns_field_type_supported=pronouns_field_type_supported,
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
            include_deactivated_groups=include_deactivated_groups,
            archived_channels=archived_channels,
            simplified_presence_events=simplified_presence_events,
        )
        post_process_state(
            self.user_profile, normal_state, notification_settings_null, allow_empty_topic_name
        )
        self.match_states(hybrid_state, normal_state, events)

    def match_states(
        self, state1: dict[str, Any], state2: dict[str, Any], events: list[dict[str, Any]]
    ) -> None:
        def normalize(state: dict[str, Any]) -> None:
            if "never_subscribed" in state:
                for u in state["never_subscribed"]:
                    if "subscribers" in u:
                        u["subscribers"].sort()
                    # this isn't guaranteed to match
                    del u["subscriber_count"]
            if "subscriptions" in state:
                for u in state["subscriptions"]:
                    if "subscribers" in u:
                        u["subscribers"].sort()
                    # this isn't guaranteed to match
                    del u["subscriber_count"]
                state["subscriptions"] = {u["name"]: u for u in state["subscriptions"]}
            if "unsubscribed" in state:
                for u in state["unsubscribed"]:
                    # this isn't guaranteed to match
                    del u["subscriber_count"]
                state["unsubscribed"] = {u["name"]: u for u in state["unsubscribed"]}
            if "streams" in state:
                for stream in state["streams"]:
                    if "subscriber_count" in stream:
                        # this isn't guaranteed to match
                        del stream["subscriber_count"]
            if "realm_bots" in state:
                state["realm_bots"] = {u["email"]: u for u in state["realm_bots"]}
            # Since time is different for every call, just fix the value
            state["server_timestamp"] = 0
            if "presence_last_update_id" in state:
                # We don't adjust presence_last_update_id via apply_events,
                # since events don't carry the relevant information.
                # Fix the value just like server_timestamp.
                state["presence_last_update_id"] = 0

        normalize(state1)
        normalize(state2)

        # If this assertions fails, we have unusual problems.
        self.assertEqual(state1.keys(), state2.keys())

        # The far more likely scenario is that some section of
        # our enormous payload does not get updated properly.  We
        # want the diff here to be developer-friendly, hence
        # the somewhat tedious code to provide useful output.
        if state1 != state2:  # nocoverage
            print("\n---States DO NOT MATCH---")
            print("\nEVENTS:\n")

            # Printing out the events is a big help to
            # developers.
            import json

            for event in events:
                print(json.dumps(event, indent=4))

            print("\nMISMATCHES:\n")
            for k, v1 in state1.items():
                if v1 != state2[k]:
                    print("\nkey = " + k)
                    try:
                        self.assertEqual({k: v1}, {k: state2[k]})
                    except AssertionError as e:
                        print(e)
            print(
                """
                NOTE:

                    This is an advanced test that verifies how
                    we apply events after fetching data.  If you
                    do not know how to debug it, you can ask for
                    help on chat.
                """,
                flush=True,
            )

            raise AssertionError("Mismatching states")


class NormalActionsTest(BaseAction):
    def create_bot(self, email: str, **extras: Any) -> UserProfile:
        return self.create_test_bot(email, self.user_profile, **extras)

    def test_mentioned_send_message_events(self) -> None:
        user = self.example_user("hamlet")

        for i in range(3):
            content = "mentioning... @**" + user.full_name + "** hello " + str(i)
            with self.verify_action():
                self.send_stream_message(
                    self.example_user("cordelia"),
                    "Verona",
                    content,
                    skip_capture_on_commit_callbacks=True,
                )

    def test_automatically_follow_topic_where_mentioned(self) -> None:
        user = self.user_profile

        do_change_user_setting(
            user_profile=user,
            setting_name="automatically_follow_topics_where_mentioned",
            setting_value=True,
            acting_user=None,
        )

        def get_num_events() -> int:  # nocoverage
            try:
                user_topic = UserTopic.objects.get(
                    user_profile=user,
                    stream_id=get_stream("Verona", user.realm).id,
                    topic_name__iexact="test",
                )
                if user_topic.visibility_policy != UserTopic.VisibilityPolicy.FOLLOWED:
                    return 3
            except UserTopic.DoesNotExist:
                return 3
            return 1

        for i in range(3):
            content = "mentioning... @**" + user.full_name + "** hello " + str(i)
            with self.verify_action(num_events=get_num_events()):
                self.send_stream_message(
                    self.example_user("cordelia"),
                    "Verona",
                    content,
                    skip_capture_on_commit_callbacks=True,
                )

    def test_topic_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = "mentioning... @**topic** hello " + str(i)
            with self.verify_action():
                self.send_stream_message(
                    self.example_user("cordelia"),
                    "Verona",
                    content,
                    skip_capture_on_commit_callbacks=True,
                )

    def test_stream_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = "mentioning... @**all** hello " + str(i)
            with self.verify_action():
                self.send_stream_message(
                    self.example_user("cordelia"),
                    "Verona",
                    content,
                    skip_capture_on_commit_callbacks=True,
                )

    def test_pm_send_message_events(self) -> None:
        with self.verify_action() as events:
            self.send_personal_message(
                self.example_user("cordelia"),
                self.example_user("hamlet"),
                "hola",
                skip_capture_on_commit_callbacks=True,
            )
        self.assertEqual(events[0]["message"][TOPIC_NAME], "")

        # Verify direct message editing - content only edit
        pm = Message.objects.order_by("-id")[0]
        content = "new content"
        rendering_result = render_message_markdown(pm, content)
        prior_mention_user_ids: set[int] = set()
        mention_backend = MentionBackend(self.user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
            message_sender=self.example_user("cordelia"),
        )

        message_edit_request = build_message_edit_request(
            message=pm,
            user_profile=self.user_profile,
            propagate_mode="change_one",
            stream_id=None,
            topic_name=None,
            content=content,
        )
        with self.verify_action(state_change_expected=False) as events:
            do_update_message(
                self.user_profile,
                pm,
                message_edit_request,
                False,
                False,
                rendering_result,
                prior_mention_user_ids,
                mention_data,
            )
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=False,
            has_content=True,
            has_topic=False,
            has_new_stream_id=False,
            is_embedded_update_only=False,
        )

    def test_pm_send_message_events_via_direct_message_group(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Create a direct message group with hamlet and cordelia
        get_or_create_direct_message_group(id_list=[hamlet.id, cordelia.id])

        with self.verify_action():
            self.send_group_direct_message(
                from_user=hamlet,
                to_users=[hamlet, cordelia],
                content="hola",
                skip_capture_on_commit_callbacks=True,
            )

    def test_direct_message_group_send_message_events(self) -> None:
        direct_message_group = [
            self.example_user("hamlet"),
            self.example_user("othello"),
        ]
        with self.verify_action() as events:
            self.send_group_direct_message(
                self.example_user("cordelia"),
                direct_message_group,
                "hola",
                skip_capture_on_commit_callbacks=True,
            )
        self.assertEqual(events[0]["message"][TOPIC_NAME], "")

    def test_user_creation_events_on_sending_messages(self) -> None:
        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")
        cordelia = self.example_user("cordelia")

        self.user_profile = polonius

        # Test that guest will not receive creation event
        # for bots as they can access all the bots.
        bot = self.create_test_bot("test2", cordelia, full_name="Test bot")
        with self.verify_action(num_events=1) as events:
            self.send_personal_message(bot, polonius, "hola", skip_capture_on_commit_callbacks=True)
        check_direct_message("events[0]", events[0])

        with self.verify_action(num_events=2) as events:
            self.send_personal_message(
                cordelia, polonius, "hola", skip_capture_on_commit_callbacks=True
            )
        check_realm_user_add("events[0]", events[0])
        check_direct_message("events[1]", events[1])
        self.assertEqual(events[0]["person"]["user_id"], cordelia.id)

        othello = self.example_user("othello")
        desdemona = self.example_user("desdemona")

        with self.verify_action(num_events=3) as events:
            self.send_group_direct_message(
                othello, [polonius, desdemona, bot], "hola", skip_capture_on_commit_callbacks=True
            )
        check_realm_user_add("events[0]", events[0])
        check_realm_user_add("events[1]", events[1])
        check_direct_message("events[2]", events[2])
        user_creation_user_ids = {events[0]["person"]["user_id"], events[1]["person"]["user_id"]}
        self.assertEqual(user_creation_user_ids, {othello.id, desdemona.id})

    def test_stream_send_message_events(self) -> None:
        hamlet = self.user_profile
        for stream_name in ["Verona", "Denmark", "core team"]:
            stream = get_stream(stream_name, hamlet.realm)
            sub = get_subscription(stream.name, hamlet)
            do_change_subscription_property(hamlet, sub, stream, "is_muted", True, acting_user=None)

        def verify_events_generated_and_reset_visibility_policy(
            events: list[dict[str, Any]], stream_name: str, topic_name: str
        ) -> None:
            # event-type: muted_topics
            check_muted_topics("events[0]", events[0])
            # event-type: user_topic
            check_user_topic("events[1]", events[1])

            if events[2]["type"] == "message":
                check_message("events[2]", events[2])
            else:
                # event-type: reaction
                check_reaction_add("events[2]", events[2])

            # Reset visibility policy
            do_set_user_topic_visibility_policy(
                hamlet,
                get_stream(stream_name, hamlet.realm),
                topic_name,
                visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
            )

        # Events generated during send message action depends on the 'automatically_follow_topics_policy'
        # and 'automatically_unmute_topics_in_muted_streams_policy' settings. Here we test all the
        # possible combinations.

        # action: participation
        # 'automatically_follow_topics_policy' | 'automatically_unmute_topics_in_muted_streams_policy' | visibility_policy
        #         ON_PARTICIPATION             |                    ON_INITIATION                      |     FOLLOWED
        #         ON_PARTICIPATION             |                   ON_PARTICIPATION                    |     FOLLOWED
        #         ON_PARTICIPATION             |                       ON_SEND                         |     FOLLOWED
        #         ON_PARTICIPATION             |                        NEVER                          |     FOLLOWED
        message_id = self.send_stream_message(hamlet, "Verona", "hello", "topic")
        message = Message.objects.get(id=message_id)
        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION,
            acting_user=None,
        )
        for setting_value in UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES:
            do_change_user_setting(
                user_profile=hamlet,
                setting_name="automatically_unmute_topics_in_muted_streams_policy",
                setting_value=setting_value,
                acting_user=None,
            )
            # Three events are generated:
            # 2 for following the topic and 1 for adding reaction.
            with self.verify_action(client_gravatar=False, num_events=3) as events:
                do_add_reaction(hamlet, message, "tada", "1f389", "unicode_emoji")
            verify_events_generated_and_reset_visibility_policy(events, "Verona", "topic")
            do_remove_reaction(hamlet, message, "1f389", "unicode_emoji")

        # action: send
        # 'automatically_follow_topics_policy' | 'automatically_unmute_topics_in_muted_streams_policy' | visibility_policy
        #                ON_SEND               |                    ON_INITIATION                      |     FOLLOWED
        #                ON_SEND               |                   ON_PARTICIPATION                    |     FOLLOWED
        #                ON_SEND               |                       ON_SEND                         |     FOLLOWED
        #                ON_SEND               |                        NEVER                          |     FOLLOWED
        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
            acting_user=None,
        )
        for setting_value in UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES:
            do_change_user_setting(
                user_profile=hamlet,
                setting_name="automatically_unmute_topics_in_muted_streams_policy",
                setting_value=setting_value,
                acting_user=None,
            )
            # Three events are generated:
            # 2 for following the topic and 1 for the message sent.
            with self.verify_action(client_gravatar=False, num_events=3) as events:
                self.send_stream_message(
                    hamlet, "Verona", "hello", "topic", skip_capture_on_commit_callbacks=True
                )
            verify_events_generated_and_reset_visibility_policy(events, "Verona", "topic")

        # action: initiation
        # 'automatically_follow_topics_policy' | 'automatically_unmute_topics_in_muted_streams_policy' | visibility_policy
        #          ON_INITIATION               |                    ON_INITIATION                      |     FOLLOWED
        #          ON_INITIATION               |                   ON_PARTICIPATION                    |     FOLLOWED
        #          ON_INITIATION               |                       ON_SEND                         |     FOLLOWED
        #          ON_INITIATION               |                        NEVER                          |     FOLLOWED
        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION,
            acting_user=None,
        )
        for index, setting_value in enumerate(
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES
        ):
            do_change_user_setting(
                user_profile=hamlet,
                setting_name="automatically_unmute_topics_in_muted_streams_policy",
                setting_value=setting_value,
                acting_user=None,
            )
            # Three events are generated:
            # 2 for following the topic and 1 for the message sent.
            with self.verify_action(client_gravatar=False, num_events=3) as events:
                self.send_stream_message(
                    hamlet,
                    "Denmark",
                    "hello",
                    f"new topic {index}",
                    skip_capture_on_commit_callbacks=True,
                )
            verify_events_generated_and_reset_visibility_policy(
                events, "Denmark", f"new topic {index}"
            )

        # 'automatically_follow_topics_policy' | 'automatically_unmute_topics_in_muted_streams_policy' | visibility_policy
        #             NEVER                    |                    ON_INITIATION                      |      UNMUTED
        #             NEVER                    |                  ON_PARTICIPATION                     |      UNMUTED
        #             NEVER                    |                      ON_SEND                          |      UNMUTED
        #             NEVER                    |                       NEVER                           |        NA
        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_follow_topics_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
            acting_user=None,
        )
        for setting_value in [
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION,
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION,
            UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_SEND,
        ]:
            do_change_user_setting(
                user_profile=hamlet,
                setting_name="automatically_unmute_topics_in_muted_streams_policy",
                setting_value=setting_value,
                acting_user=None,
            )
            # Three events are generated:
            # 2 for unmuting the topic and 1 for the message sent.
            with self.verify_action(client_gravatar=False, num_events=3) as events:
                self.send_stream_message(
                    hamlet, "core team", "hello", "topic", skip_capture_on_commit_callbacks=True
                )
            verify_events_generated_and_reset_visibility_policy(events, "core team", "topic")

        # If current_visibility_policy is already set to the value the policies would set.
        do_set_user_topic_visibility_policy(
            hamlet,
            get_stream("core team", hamlet.realm),
            "new Topic",
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )
        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_unmute_topics_in_muted_streams_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_PARTICIPATION,
            acting_user=None,
        )
        # 1 event for the message sent
        with self.verify_action(client_gravatar=False, num_events=1) as events:
            self.send_stream_message(
                hamlet, "core team", "hello", "new Topic", skip_capture_on_commit_callbacks=True
            )

        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_unmute_topics_in_muted_streams_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
            acting_user=None,
        )
        # Only one message event is generated
        with self.verify_action(client_gravatar=True) as events:
            self.send_stream_message(
                hamlet, "core team", "hello", skip_capture_on_commit_callbacks=True
            )
        # event-type: message
        check_message("events[0]", events[0])
        assert isinstance(events[0]["message"]["avatar_url"], str)

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )

        with self.verify_action(client_gravatar=True) as events:
            self.send_stream_message(
                hamlet, "core team", "hello", skip_capture_on_commit_callbacks=True
            )
        check_message("events[0]", events[0])
        assert events[0]["message"]["avatar_url"] is None

        # Here we add coverage for the case where 'apply_unread_message_event'
        # should be called and unread messages in unmuted or followed topic in
        # muted stream is treated as unmuted stream message, thus added to 'unmuted_stream_msgs'.
        stream = get_stream("Verona", hamlet.realm)
        do_set_user_topic_visibility_policy(
            hamlet,
            stream,
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )
        with self.verify_action(state_change_expected=True):
            self.send_stream_message(
                self.example_user("aaron"), "Verona", "hello", skip_capture_on_commit_callbacks=True
            )

    def test_stream_update_message_events(self) -> None:
        iago = self.example_user("iago")
        self.send_stream_message(iago, "Verona", "hello")

        # Verify stream message editing - content only
        message = Message.objects.order_by("-id")[0]
        content = "new content"
        rendering_result = render_message_markdown(message, content)
        prior_mention_user_ids: set[int] = set()
        mention_backend = MentionBackend(self.user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
            message_sender=iago,
        )

        message_edit_request = build_message_edit_request(
            message=message,
            user_profile=self.user_profile,
            propagate_mode="change_one",
            stream_id=None,
            topic_name=None,
            content=content,
        )
        with self.verify_action(state_change_expected=False) as events:
            do_update_message(
                self.user_profile,
                message,
                message_edit_request,
                False,
                False,
                rendering_result,
                prior_mention_user_ids,
                mention_data,
            )
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=True,
            has_content=True,
            has_topic=False,
            has_new_stream_id=False,
            is_embedded_update_only=False,
        )

        # Verify stream message editing - topic only
        topic_name = "new_topic"
        propagate_mode = "change_all"

        message_edit_request = build_message_edit_request(
            message=message,
            user_profile=self.user_profile,
            propagate_mode=propagate_mode,
            stream_id=None,
            topic_name=topic_name,
            content=None,
        )

        with self.verify_action(state_change_expected=True) as events:
            do_update_message(
                self.user_profile,
                message,
                message_edit_request,
                False,
                False,
                None,
                prior_mention_user_ids,
                mention_data,
            )
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=True,
            has_content=False,
            has_topic=True,
            has_new_stream_id=False,
            is_embedded_update_only=False,
        )

        # Verify special case of embedded content update
        content = "embed_content"
        mention_data = MentionData(
            mention_backend=MentionBackend(message.realm_id),
            content=content,
            message_sender=message.sender,
        )
        rendering_result = render_message_markdown(message, content, mention_data=mention_data)
        with self.verify_action(state_change_expected=False) as events:
            do_update_embedded_data(self.user_profile, message, rendering_result, mention_data)
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=False,
            has_content=False,
            has_topic=False,
            has_new_stream_id=False,
            is_embedded_update_only=True,
        )

        # Verify move topic to different stream.
        self.subscribe(self.user_profile, "Verona")
        self.subscribe(self.user_profile, "Denmark")
        # Message passed to the message edit request is usually last in
        # event["message_ids"]. Since we want to test sorting of these
        # message_ids later on, we need send the message_id to be used
        # in the message_edit_request first; Otherwise
        # event["message_ids"] would be sorted even without any sorting
        # function.
        message_id = self.send_stream_message(self.user_profile, "Verona")
        message = Message.objects.get(id=message_id)
        self.send_stream_message(iago, "Verona")
        stream = get_stream("Denmark", self.user_profile.realm)
        propagate_mode = "change_all"
        prior_mention_user_ids = set()

        message_edit_request = build_message_edit_request(
            message=message,
            user_profile=self.user_profile,
            propagate_mode=propagate_mode,
            stream_id=stream.id,
            topic_name=None,
            content=None,
        )
        with self.verify_action(
            state_change_expected=True,
            # There are 3 events generated for this action
            # * update_message: For updating existing messages
            # * 2 new message events: Breadcrumb messages in the new and old topics.
            num_events=3,
        ) as events:
            do_update_message(
                self.user_profile,
                message,
                message_edit_request,
                True,
                True,
                None,
                set(),
                None,
            )
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=True,
            has_content=False,
            has_topic=False,
            has_new_stream_id=True,
            is_embedded_update_only=False,
        )
        # Make sure the message_ids returned are sorted.
        self.assertEqual(events[0]["message_ids"], sorted(events[0]["message_ids"]))

        # Move both stream and topic, with update_message_flags
        # excluded from event types.
        self.send_stream_message(self.user_profile, "Verona")
        message_id = self.send_stream_message(self.user_profile, "Verona")
        message = Message.objects.get(id=message_id)
        stream = get_stream("Denmark", self.user_profile.realm)
        propagate_mode = "change_all"
        prior_mention_user_ids = set()

        message_edit_request = build_message_edit_request(
            message=message,
            user_profile=self.user_profile,
            propagate_mode="change_one",
            stream_id=stream.id,
            topic_name="final_topic",
            content=None,
        )
        with self.verify_action(
            state_change_expected=True,
            # Skip "update_message_flags" to exercise the code path
            # where raw_unread_msgs does not exist in the state.
            event_types=["message", "update_message"],
            # There are 3 events generated for this action
            # * update_message: For updating existing messages
            # * 2 new message events: Breadcrumb messages in the new and old topics.
            num_events=3,
        ) as events:
            do_update_message(
                self.user_profile,
                message,
                message_edit_request,
                True,
                True,
                None,
                set(),
                None,
            )
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=True,
            has_content=False,
            has_topic=True,
            has_new_stream_id=True,
            is_embedded_update_only=False,
        )

    def test_thumbnail_event(self) -> None:
        iago = self.example_user("iago")
        url = upload_message_attachment(
            "img.png", "image/png", read_test_image_file("img.png"), self.example_user("iago")
        )[0]
        path_id = url[len("/user_upload/") + 1 :]
        self.send_stream_message(
            iago, "Verona", f"[img.png]({url})", skip_capture_on_commit_callbacks=True
        )

        # Generating a thumbnail for an image sends a message update event
        with self.verify_action(state_change_expected=False) as events:
            ensure_thumbnails(ImageAttachment.objects.get(path_id=path_id))
        check_update_message(
            "events[0]",
            events[0],
            is_stream_message=False,
            has_content=False,
            has_topic=False,
            has_new_stream_id=False,
            is_embedded_update_only=True,
        )

    def test_update_message_flags(self) -> None:
        # Test message flag update events
        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )
        user_profile = self.example_user("hamlet")
        with self.verify_action(state_change_expected=True) as events:
            do_update_message_flags(user_profile, "add", "starred", [message])
        check_update_message_flags_add("events[0]", events[0])

        with self.verify_action(state_change_expected=True) as events:
            do_update_message_flags(user_profile, "remove", "starred", [message])
        check_update_message_flags_remove("events[0]", events[0])

    def test_update_read_flag_removes_unread_msg_ids(self) -> None:
        user_profile = self.example_user("hamlet")
        mention = "@**" + user_profile.full_name + "**"

        for content in ["hello", mention]:
            message = self.send_stream_message(
                self.example_user("cordelia"),
                "Verona",
                content,
            )

            with self.verify_action(state_change_expected=True):
                do_update_message_flags(user_profile, "add", "read", [message])

            with self.verify_action(state_change_expected=True) as events:
                do_update_message_flags(user_profile, "remove", "read", [message])
            check_update_message_flags_remove("events[0]", events[0])

            personal_message = self.send_personal_message(
                from_user=self.example_user("cordelia"), to_user=user_profile, content=content
            )
            with self.verify_action(state_change_expected=True):
                do_update_message_flags(user_profile, "add", "read", [personal_message])

            with self.verify_action(state_change_expected=True) as events:
                do_update_message_flags(user_profile, "remove", "read", [personal_message])
            check_update_message_flags_remove("events[0]", events[0])

            group_direct_message = self.send_group_direct_message(
                from_user=self.example_user("cordelia"),
                to_users=[user_profile, self.example_user("othello")],
                content=content,
            )

            with self.verify_action(state_change_expected=True):
                do_update_message_flags(user_profile, "add", "read", [group_direct_message])

            with self.verify_action(state_change_expected=True) as events:
                do_update_message_flags(user_profile, "remove", "read", [group_direct_message])
            check_update_message_flags_remove("events[0]", events[0])

    def test_send_message_to_existing_recipient(self) -> None:
        sender = self.example_user("cordelia")
        self.send_stream_message(
            sender,
            "Verona",
            "hello 1",
        )
        with self.verify_action(state_change_expected=True):
            self.send_stream_message(
                sender, "Verona", "hello 2", skip_capture_on_commit_callbacks=True
            )

    def test_events_for_message_from_inaccessible_sender(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()
        self.set_up_db_for_testing_user_access()
        othello = self.example_user("othello")
        self.user_profile = self.example_user("polonius")

        with self.verify_action() as events:
            self.send_stream_message(
                othello,
                "test_stream1",
                "hello 2",
                allow_unsubscribed_sender=True,
                skip_capture_on_commit_callbacks=True,
            )
        check_message("events[0]", events[0])
        message_obj = events[0]["message"]
        self.assertEqual(message_obj["sender_full_name"], "Unknown user")
        self.assertEqual(message_obj["sender_email"], f"user{othello.id}@zulip.testserver")
        self.assertTrue(message_obj["avatar_url"].endswith("images/unknown-user-avatar.png"))

        iago = self.example_user("iago")
        with self.verify_action() as events:
            self.send_stream_message(
                iago,
                "test_stream1",
                "hello 2",
                allow_unsubscribed_sender=True,
                skip_capture_on_commit_callbacks=True,
            )
        check_message("events[0]", events[0])
        message_obj = events[0]["message"]
        self.assertEqual(message_obj["sender_full_name"], iago.full_name)
        self.assertEqual(message_obj["sender_email"], iago.delivery_email)
        self.assertIsNone(message_obj["avatar_url"])

    def test_add_reaction(self) -> None:
        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        with self.verify_action(state_change_expected=False) as events:
            do_add_reaction(self.user_profile, message, "tada", "1f389", "unicode_emoji")
        check_reaction_add("events[0]", events[0])

    def test_heartbeat_event(self) -> None:
        with self.verify_action(state_change_expected=False) as events:
            send_event_rollback_unsafe(
                self.user_profile.realm,
                create_heartbeat_event(),
                [self.user_profile.id],
            )
        check_heartbeat("events[0]", events[0])

    def test_add_submessage(self) -> None:
        cordelia = self.example_user("cordelia")
        stream_name = "Verona"
        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )
        with self.verify_action(state_change_expected=False) as events:
            do_add_submessage(
                realm=cordelia.realm,
                sender_id=cordelia.id,
                message_id=message_id,
                msg_type="whatever",
                content='"stuff"',
            )
        check_submessage("events[0]", events[0])

    def test_remove_reaction(self) -> None:
        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        do_add_reaction(self.user_profile, message, "tada", "1f389", "unicode_emoji")
        with self.verify_action(state_change_expected=False) as events:
            do_remove_reaction(self.user_profile, message, "1f389", "unicode_emoji")
        check_reaction_remove("events[0]", events[0])

    def do_test_events_on_changing_private_stream_permission_settings_granting_metadata_access(
        self, setting_name: str
    ) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        private_stream = get_stream("private_stream", iago.realm)
        self.login_user(iago)
        params = {}

        self.assertFalse(
            user_has_metadata_access(
                hamlet,
                private_stream,
                UserGroupMembershipDetails(user_recursive_group_ids=None),
                is_subscribed=False,
            )
        )
        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [hamlet.id],
                    "direct_subgroups": [],
                },
            }
        ).decode()
        with self.verify_action(num_events=2) as events:
            result = self.client_patch(
                f"/json/streams/{private_stream.id}",
                params,
            )
        self.assert_json_success(result)
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=iago.realm, is_system_group=True
        )
        private_stream = get_stream("private_stream", iago.realm)
        self.assertTrue(
            user_has_metadata_access(
                hamlet,
                private_stream,
                UserGroupMembershipDetails(user_recursive_group_ids=None),
                is_subscribed=False,
            )
        )
        params[setting_name] = orjson.dumps(
            {
                "new": nobody_group.id,
            }
        ).decode()
        with self.verify_action(num_events=1) as events:
            result = self.client_patch(
                f"/json/streams/{private_stream.id}",
                params,
            )
        self.assert_json_success(result)
        check_stream_delete("events[0]", events[0])

    def do_test_events_on_changing_private_stream_permission_settings_not_granting_metadata_access(
        self, setting_name: str
    ) -> None:
        iago = self.example_user("iago")
        hamlet = self.example_user("hamlet")
        private_stream = get_stream("private_stream", iago.realm)
        params = {}
        self.login_user(iago)
        expected_num_events = 1
        if setting_name == "can_send_message_group":
            expected_num_events = 2

        self.assertFalse(
            user_has_metadata_access(
                hamlet,
                private_stream,
                UserGroupMembershipDetails(user_recursive_group_ids=None),
                is_subscribed=False,
            )
        )
        params[setting_name] = orjson.dumps(
            {
                "new": {
                    "direct_members": [hamlet.id],
                    "direct_subgroups": [],
                },
            }
        ).decode()
        with self.capture_send_event_calls(expected_num_events=expected_num_events) as events:
            result = self.client_patch(
                f"/json/streams/{private_stream.id}",
                params,
            )
        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["type"], "stream")
        self.assertEqual(event["op"], "update")
        self.assertEqual(event["stream_id"], private_stream.id)

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=iago.realm, is_system_group=True
        )
        private_stream = get_stream("private_stream", iago.realm)
        self.assertFalse(
            user_has_metadata_access(
                hamlet,
                private_stream,
                UserGroupMembershipDetails(user_recursive_group_ids=None),
                is_subscribed=False,
            )
        )
        params[setting_name] = orjson.dumps(
            {
                "new": nobody_group.id,
            }
        ).decode()
        with self.capture_send_event_calls(expected_num_events=expected_num_events) as events:
            result = self.client_patch(
                f"/json/streams/{private_stream.id}",
                params,
            )
        self.assert_json_success(result)
        event = events[0]["event"]
        self.assertEqual(event["type"], "stream")
        self.assertEqual(event["op"], "update")
        self.assertEqual(event["stream_id"], private_stream.id)

    def test_events_on_changing_private_stream_permission_settings(self) -> None:
        self.make_stream("private_stream", invite_only=True, history_public_to_subscribers=True)
        self.subscribe(self.example_user("iago"), "private_stream")
        for setting_name in Stream.stream_permission_group_settings:
            if setting_name in Stream.stream_permission_group_settings_granting_metadata_access:
                self.do_test_events_on_changing_private_stream_permission_settings_granting_metadata_access(
                    setting_name
                )
            else:
                self.do_test_events_on_changing_private_stream_permission_settings_not_granting_metadata_access(
                    setting_name
                )

    def test_invite_user_event(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Denmark", "Scotland"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.verify_action(state_change_expected=False) as events:
            do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                include_realm_default_subscriptions=False,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        check_invites_changed("events[0]", events[0])

    def test_create_multiuse_invite_event(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Denmark", "Verona"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.verify_action(state_change_expected=False) as events:
            do_create_multiuse_invite_link(
                self.user_profile,
                PreregistrationUser.INVITE_AS["MEMBER"],
                invite_expires_in_minutes,
                False,
                streams,
            )
        check_invites_changed("events[0]", events[0])

    def test_deactivate_user_invites_changed_event(self) -> None:
        self.user_profile = self.example_user("iago")
        user_profile = self.example_user("cordelia")
        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                user_profile,
                ["foo@zulip.com"],
                [],
                include_realm_default_subscriptions=False,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )

        with self.verify_action(num_events=3) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_invites_changed("events[0]", events[0])

    def test_revoke_user_invite_event(self) -> None:
        # We need set self.user_profile to be an admin, so that
        # we receive the invites_changed event.
        self.user_profile = self.example_user("iago")
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Denmark", "Verona"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                include_realm_default_subscriptions=False,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        prereg_users = PreregistrationUser.objects.filter(
            referred_by__realm=self.user_profile.realm
        )
        with self.verify_action(state_change_expected=False) as events:
            do_revoke_user_invite(prereg_users[0])
        check_invites_changed("events[0]", events[0])

    def test_revoke_multiuse_invite_event(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Denmark", "Verona"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        do_create_multiuse_invite_link(
            self.user_profile,
            PreregistrationUser.INVITE_AS["MEMBER"],
            invite_expires_in_minutes,
            False,
            streams,
        )

        multiuse_object = MultiuseInvite.objects.get()
        with self.verify_action(state_change_expected=False) as events:
            do_revoke_multi_use_invite(multiuse_object)
        check_invites_changed("events[0]", events[0])

    def test_invitation_accept_invite_event(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        self.user_profile = self.example_user("iago")
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Denmark", "Scotland"]
        ]

        invite_expires_in_minutes = 2 * 24 * 60
        with self.captureOnCommitCallbacks(execute=True):
            do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                include_realm_default_subscriptions=False,
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")

        with self.verify_action(state_change_expected=True, num_events=6) as events:
            do_create_user(
                "foo@zulip.com",
                "password",
                self.user_profile.realm,
                "full name",
                prereg_user=prereg_user,
                acting_user=None,
            )

        check_invites_changed("events[6]", events[5])

    def test_typing_events(self) -> None:
        with self.verify_action(state_change_expected=False) as events:
            check_send_typing_notification(
                self.user_profile, [self.example_user("cordelia").id], "start"
            )
        check_typing_start("events[0]", events[0])
        with self.verify_action(state_change_expected=False) as events:
            check_send_typing_notification(
                self.user_profile, [self.example_user("cordelia").id], "stop"
            )
        check_typing_stop("events[0]", events[0])

    def test_stream_typing_events(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        topic_name = "streams typing"

        with self.verify_action(state_change_expected=False) as events:
            do_send_stream_typing_notification(
                self.user_profile,
                "start",
                stream,
                topic_name,
            )
        check_typing_start("events[0]", events[0])

        with self.verify_action(state_change_expected=False) as events:
            do_send_stream_typing_notification(
                self.user_profile,
                "stop",
                stream,
                topic_name,
            )
        check_typing_stop("events[0]", events[0])

        # Having client_capability `stream_typing_notification=False`
        # shouldn't produce any events.
        with self.verify_action(
            state_change_expected=False, stream_typing_notifications=False, num_events=0
        ) as events:
            do_send_stream_typing_notification(
                self.user_profile,
                "start",
                stream,
                topic_name,
            )
        self.assertEqual(events, [])

        with self.verify_action(
            state_change_expected=False, stream_typing_notifications=False, num_events=0
        ) as events:
            do_send_stream_typing_notification(
                self.user_profile,
                "stop",
                stream,
                topic_name,
            )
        self.assertEqual(events, [])

    def test_edit_direct_message_typing_events(self) -> None:
        msg_id = self.send_personal_message(self.user_profile, self.example_user("cordelia"))
        with self.verify_action(state_change_expected=False) as events:
            do_send_direct_message_edit_typing_notification(
                self.user_profile,
                [self.example_user("cordelia").id, self.user_profile.id],
                msg_id,
                "start",
            )
        check_typing_edit_message_start("events[0]", events[0])

        with self.verify_action(state_change_expected=False) as events:
            do_send_direct_message_edit_typing_notification(
                self.user_profile,
                [self.example_user("cordelia").id, self.user_profile.id],
                msg_id,
                "stop",
            )
        check_typing_edit_message_stop("events[0]", events[0])

    def test_stream_edit_message_typing_events(self) -> None:
        channel = get_stream("Denmark", self.user_profile.realm)
        msg_id = self.send_stream_message(
            self.user_profile, channel.name, topic_name="editing", content="before edit"
        )
        topic_name = "editing"
        with self.verify_action(state_change_expected=False) as events:
            do_send_stream_message_edit_typing_notification(
                self.user_profile, channel.id, msg_id, "start", topic_name
            )
        check_typing_edit_message_start("events[0]", events[0])

        with self.verify_action(state_change_expected=False) as events:
            do_send_stream_message_edit_typing_notification(
                self.user_profile, channel.id, msg_id, "stop", topic_name
            )
        check_typing_edit_message_stop("events[0]", events[0])

    def test_custom_profile_fields_events(self) -> None:
        realm = self.user_profile.realm

        with self.verify_action() as events:
            try_add_realm_custom_profile_field(
                realm=realm, name="Expertise", field_type=CustomProfileField.LONG_TEXT
            )
        check_custom_profile_fields("events[0]", events[0])

        field = realm.customprofilefield_set.get(realm=realm, name="Biography")
        name = field.name
        hint = "Biography of the user"
        display_in_profile_summary = False

        with self.verify_action() as events:
            try_update_realm_custom_profile_field(
                realm=realm,
                field=field,
                name=name,
                hint=hint,
                display_in_profile_summary=display_in_profile_summary,
            )
        check_custom_profile_fields("events[0]", events[0])

        with self.verify_action() as events:
            do_remove_realm_custom_profile_field(realm, field)
        check_custom_profile_fields("events[0]", events[0])

    def test_pronouns_type_support_in_custom_profile_fields_events(self) -> None:
        realm = self.user_profile.realm
        field = CustomProfileField.objects.get(realm=realm, name="Pronouns")
        name = field.name
        hint = "What pronouns should people use for you?"

        with self.verify_action(pronouns_field_type_supported=True) as events:
            try_update_realm_custom_profile_field(realm, field, name, hint=hint)
        check_custom_profile_fields("events[0]", events[0])
        [pronouns_field] = (
            field_obj for field_obj in events[0]["fields"] if field_obj["id"] == field.id
        )
        self.assertEqual(pronouns_field["type"], CustomProfileField.PRONOUNS)

        hint = "What pronouns should people use to refer you?"
        with self.verify_action(pronouns_field_type_supported=False) as events:
            try_update_realm_custom_profile_field(realm=realm, field=field, name=name, hint=hint)
        check_custom_profile_fields("events[0]", events[0])
        [pronouns_field] = (
            field_obj for field_obj in events[0]["fields"] if field_obj["id"] == field.id
        )
        self.assertEqual(pronouns_field["type"], CustomProfileField.SHORT_TEXT)

    def test_custom_profile_field_data_events(self) -> None:
        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name="Biography"
        ).id
        field: ProfileDataElementUpdateDict = {
            "id": field_id,
            "value": "New value",
        }
        with self.verify_action() as events:
            do_update_user_custom_profile_data_if_changed(self.user_profile, [field])
        check_realm_user_update("events[0]", events[0], "custom_profile_field")
        self.assertEqual(
            events[0]["person"]["custom_profile_field"].keys(), {"id", "value", "rendered_value"}
        )

        # Test we pass correct stringify value in custom-user-field data event
        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name="Mentor"
        ).id
        field = {
            "id": field_id,
            "value": [self.example_user("ZOE").id],
        }
        with self.verify_action() as events:
            do_update_user_custom_profile_data_if_changed(self.user_profile, [field])
        check_realm_user_update("events[0]", events[0], "custom_profile_field")
        self.assertEqual(events[0]["person"]["custom_profile_field"].keys(), {"id", "value"})

        # Test event for removing custom profile data
        with self.verify_action() as events:
            check_remove_custom_profile_field_value(
                self.user_profile, field_id, acting_user=self.user_profile
            )
        check_realm_user_update("events[0]", events[0], "custom_profile_field")
        self.assertEqual(events[0]["person"]["custom_profile_field"].keys(), {"id", "value"})

        # Test event for updating custom profile data for guests.
        self.set_up_db_for_testing_user_access()
        self.user_profile = self.example_user("polonius")
        field = {
            "id": field_id,
            "value": "New value",
        }
        cordelia = self.example_user("cordelia")
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_update_user_custom_profile_data_if_changed(cordelia, [field])

        hamlet = self.example_user("hamlet")
        with self.verify_action() as events:
            do_update_user_custom_profile_data_if_changed(hamlet, [field])
        check_realm_user_update("events[0]", events[0], "custom_profile_field")
        self.assertEqual(events[0]["person"]["custom_profile_field"].keys(), {"id", "value"})

    def test_navigation_views_events(self) -> None:
        with self.verify_action() as events:
            navigation_view = do_add_navigation_view(
                self.user_profile, fragment="inbox", is_pinned=True, name=None
            )
        check_navigation_view_add("events[0]", events[0])
        self.assertEqual(events[0]["navigation_view"]["fragment"], "inbox")
        self.assertEqual(events[0]["navigation_view"]["is_pinned"], True)
        self.assertIsNone(events[0]["navigation_view"]["name"])

        with self.verify_action() as events:
            do_update_navigation_view(
                self.user_profile, navigation_view, is_pinned=False, name=None
            )
        check_navigation_view_update("events[0]", events[0])
        self.assertEqual(events[0]["fragment"], "inbox")
        self.assertEqual(events[0]["data"]["is_pinned"], False)

        with self.verify_action() as events:
            do_remove_navigation_view(self.user_profile, navigation_view)
        check_navigation_view_remove("events[0]", events[0])
        self.assertEqual(events[0]["fragment"], "inbox")

    def test_legacy_presence_events(self) -> None:
        with self.verify_action(slim_presence=False) as events:
            do_update_user_presence(
                self.user_profile,
                get_client("website"),
                timezone_now(),
                UserPresence.LEGACY_STATUS_ACTIVE_INT,
            )

        check_legacy_presence(
            "events[0]",
            events[0],
            has_email=True,
            presence_key="website",
            status="active",
        )

        with self.verify_action(slim_presence=True) as events:
            do_update_user_presence(
                self.example_user("cordelia"),
                get_client("website"),
                timezone_now(),
                UserPresence.LEGACY_STATUS_ACTIVE_INT,
            )

        check_legacy_presence(
            "events[0]",
            events[0],
            has_email=False,
            presence_key="website",
            status="active",
        )

    def test_modern_presence_events(self) -> None:
        with self.verify_action(simplified_presence_events=True) as events:
            do_update_user_presence(
                self.user_profile,
                get_client("ZulipAndroid/1.0"),
                timezone_now(),
                UserPresence.LEGACY_STATUS_ACTIVE_INT,
            )
        check_modern_presence("events[0]", events[0], self.user_profile.id)

    def test_presence_events_multiple_clients(self) -> None:
        now = timezone_now()
        initial_presence = now - timedelta(days=365)
        UserPresence.objects.create(
            user_profile=self.user_profile,
            realm=self.user_profile.realm,
            last_active_time=initial_presence,
            last_connected_time=initial_presence,
        )

        self.api_post(
            self.user_profile,
            "/api/v1/users/me/presence",
            {"status": "idle"},
            HTTP_USER_AGENT="ZulipAndroid/1.0",
        )
        with self.verify_action():
            do_update_user_presence(
                self.user_profile,
                get_client("website"),
                timezone_now(),
                UserPresence.LEGACY_STATUS_ACTIVE_INT,
            )
        with self.verify_action(state_change_expected=False, num_events=0):
            do_update_user_presence(
                self.user_profile,
                get_client("ZulipAndroid/1.0"),
                timezone_now(),
                UserPresence.LEGACY_STATUS_IDLE_INT,
            )
        with self.verify_action() as events:
            do_update_user_presence(
                self.user_profile,
                get_client("ZulipAndroid/1.0"),
                timezone_now() + timedelta(seconds=301),
                UserPresence.LEGACY_STATUS_ACTIVE_INT,
            )

        check_legacy_presence(
            "events[0]",
            events[0],
            has_email=True,
            # We no longer store information about the client and we simply
            # set the field to 'website' for backwards compatibility.
            presence_key="website",
            status="active",
        )

    def test_register_events(self) -> None:
        realm = self.user_profile.realm
        realm.signup_announcements_stream = get_stream("core team", realm)
        realm.save(update_fields=["signup_announcements_stream"])

        with self.verify_action(num_events=6) as events:
            self.register("test1@zulip.com", "test1")
        self.assert_length(events, 6)

        check_realm_user_add("events[0]", events[0])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.delivery_email, "test1@zulip.com")

        check_subscription_peer_add("events[3]", events[3])
        check_subscription_peer_add("events[4]", events[4])

        check_message("events[5]", events[5])
        self.assertIn(
            f'data-user-id="{new_user_profile.id}">test1_zulip.com</span> joined this organization.',
            events[5]["message"]["content"],
        )

        check_user_group_add_members("events[1]", events[1])
        check_user_group_add_members("events[2]", events[2])

    def test_register_events_email_address_visibility(self) -> None:
        realm_user_default = RealmUserDefault.objects.get(realm=self.user_profile.realm)
        do_set_realm_user_default_setting(
            realm_user_default,
            "email_address_visibility",
            RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )
        realm = self.user_profile.realm
        realm.signup_announcements_stream = get_stream("core team", realm)
        realm.save(update_fields=["signup_announcements_stream"])

        with self.verify_action(num_events=6) as events:
            self.register("test1@zulip.com", "test1")
        self.assert_length(events, 6)
        check_realm_user_add("events[0]", events[0])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.email, f"user{new_user_profile.id}@zulip.testserver")

        check_subscription_peer_add("events[3]", events[3])
        check_subscription_peer_add("events[4]", events[4])

        check_message("events[5]", events[5])
        self.assertIn(
            f'data-user-id="{new_user_profile.id}">test1_zulip.com</span> joined this organization',
            events[5]["message"]["content"],
        )

        check_user_group_add_members("events[1]", events[1])
        check_user_group_add_members("events[2]", events[2])

    def test_register_events_for_restricted_users(self) -> None:
        self.set_up_db_for_testing_user_access()
        self.user_profile = self.example_user("polonius")

        with self.verify_action(num_events=3) as events:
            self.register("test1@zulip.com", "test1")

        check_realm_user_add("events[0]", events[0])
        self.assertEqual(events[0]["person"]["full_name"], "Unknown user")

        check_user_group_add_members("events[1]", events[1])
        check_user_group_add_members("events[2]", events[2])

        with self.verify_action(num_events=2, user_list_incomplete=True) as events:
            self.register("alice@zulip.com", "alice")

        check_user_group_add_members("events[0]", events[0])
        check_user_group_add_members("events[1]", events[1])

    def test_alert_words_events(self) -> None:
        with self.verify_action() as events:
            do_add_alert_words(self.user_profile, ["alert_word"])
        check_alert_words("events[0]", events[0])

        with self.verify_action() as events:
            do_remove_alert_words(self.user_profile, ["alert_word"])
        check_alert_words("events[0]", events[0])

    def test_saved_replies_events(self) -> None:
        with self.verify_action() as events:
            do_create_saved_snippet("Welcome message", "Welcome", self.user_profile)
        check_saved_snippets_add("events[0]", events[0])

        saved_snippet_id = (
            SavedSnippet.objects.filter(user_profile=self.user_profile).order_by("id")[0].id
        )
        with self.verify_action() as events:
            do_edit_saved_snippet(saved_snippet_id, "Example", None, self.user_profile)
        check_saved_snippets_update("events[0]", events[0])

        with self.verify_action() as events:
            do_delete_saved_snippet(saved_snippet_id, self.user_profile)
        check_saved_snippets_remove("events[0]", events[0])

    def test_away_events(self) -> None:
        client = get_client("website")
        now = timezone_now()

        # Updating user status to away activates the codepath of disabling
        # the presence_enabled user setting.
        # See test_change_presence_enabled for more details, since it tests that codepath directly.
        #
        # Set up an initial presence state for the user:
        UserPresence.objects.filter(user_profile=self.user_profile).delete()
        with time_machine.travel(now, tick=False):
            result = self.api_post(
                self.user_profile,
                "/api/v1/users/me/presence",
                dict(status="active"),
                HTTP_USER_AGENT="ZulipAndroid/1.0",
            )
            self.assert_json_success(result)

        # Set all
        away_val = True
        with self.verify_action(num_events=3) as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
            )

        check_user_settings_update("events[0]", events[0])
        check_user_status(
            "events[1]",
            events[1],
            {"away", "status_text", "emoji_name", "emoji_code", "reaction_type"},
        )
        check_legacy_presence(
            "events[2]",
            events[2],
            has_email=True,
            presence_key="website",
            status="active",
        )

        # Remove all
        away_val = False
        with self.verify_action(num_events=3) as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text="",
                emoji_name="",
                emoji_code="",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
            )

        check_user_settings_update("events[0]", events[0])
        check_user_status(
            "events[1]",
            events[1],
            {"away", "status_text", "emoji_name", "emoji_code", "reaction_type"},
        )
        check_legacy_presence(
            "events[2]",
            events[2],
            has_email=True,
            presence_key="website",
            status="active",
        )

        # Only set away
        away_val = True
        with self.verify_action(num_events=3) as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text=None,
                emoji_name=None,
                emoji_code=None,
                reaction_type=None,
                client_id=client.id,
            )

        check_user_settings_update("events[0]", events[0])
        check_user_status("events[1]", events[1], {"away"})
        check_legacy_presence(
            "events[2]",
            events[2],
            has_email=True,
            presence_key="website",
            status="active",
        )

        # Only set status_text
        with self.verify_action() as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=None,
                status_text="at the beach",
                emoji_name=None,
                emoji_code=None,
                reaction_type=None,
                client_id=client.id,
            )

        check_user_status("events[0]", events[0], {"status_text"})

        self.set_up_db_for_testing_user_access()
        cordelia = self.example_user("cordelia")
        self.user_profile = self.example_user("polonius")

        # Set the date_joined for cordelia here like we did at
        # the start of this test.
        cordelia.date_joined = timezone_now() - timedelta(days=15)
        cordelia.save()

        away_val = False
        with (
            self.settings(CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE=True),
            self.verify_action(num_events=0, state_change_expected=False) as events,
        ):
            do_update_user_status(
                user_profile=cordelia,
                away=away_val,
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
            )

        away_val = True
        with self.verify_action(num_events=1, state_change_expected=True) as events:
            do_update_user_status(
                user_profile=cordelia,
                away=away_val,
                status_text="at the beach",
                emoji_name=None,
                emoji_code=None,
                reaction_type=None,
                client_id=client.id,
            )
        check_legacy_presence(
            "events[0]",
            events[0],
            has_email=True,
            # We no longer store information about the client and we simply
            # set the field to 'website' for backwards compatibility.
            presence_key="website",
            status="active",
        )

    def test_user_group_events(self) -> None:
        othello = self.example_user("othello")
        with self.verify_action() as events:
            check_add_user_group(
                self.user_profile.realm, "backend", [othello], "Backend team", acting_user=othello
            )
        check_user_group_add("events[0]", events[0])
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY,
            realm_for_sharding=self.user_profile.realm,
            is_system_group=True,
        )
        self.assertEqual(events[0]["group"]["can_join_group"], nobody_group.id)
        self.assertEqual(
            events[0]["group"]["can_manage_group"],
            UserGroupMembersDict(direct_members=[12], direct_subgroups=[]),
        )
        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE,
            realm_for_sharding=self.user_profile.realm,
            is_system_group=True,
        )
        self.assertEqual(events[0]["group"]["can_mention_group"], everyone_group.id)
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS,
            realm_for_sharding=self.user_profile.realm,
            is_system_group=True,
        )
        user_group = self.create_or_update_anonymous_group_for_setting(
            [othello], [moderators_group]
        )

        with self.verify_action() as events:
            check_add_user_group(
                self.user_profile.realm,
                "frontend",
                [othello],
                "",
                {
                    "can_join_group": user_group,
                    "can_manage_group": user_group,
                    "can_mention_group": user_group,
                },
                acting_user=othello,
            )
        check_user_group_add("events[0]", events[0])
        self.assertEqual(
            events[0]["group"]["can_join_group"],
            UserGroupMembersDict(
                direct_members=[othello.id], direct_subgroups=[moderators_group.id]
            ),
        )
        self.assertEqual(
            events[0]["group"]["can_manage_group"],
            UserGroupMembersDict(
                direct_members=[othello.id], direct_subgroups=[moderators_group.id]
            ),
        )
        self.assertEqual(
            events[0]["group"]["can_mention_group"],
            UserGroupMembersDict(
                direct_members=[othello.id], direct_subgroups=[moderators_group.id]
            ),
        )
        self.assertEqual(
            events[0]["group"]["can_remove_members_group"],
            nobody_group.id,
        )

        # Test name update
        backend = NamedUserGroup.objects.get(name="backend")
        with self.verify_action() as events:
            do_update_user_group_name(backend, "backendteam", acting_user=None)
        check_user_group_update("events[0]", events[0], {"name"})

        # Test description update
        description = "Backend team to deal with backend code."
        with self.verify_action() as events:
            do_update_user_group_description(backend, description, acting_user=None)
        check_user_group_update("events[0]", events[0], {"description"})

        # Test can_mention_group setting update
        with self.verify_action() as events:
            do_change_user_group_permission_setting(
                backend,
                "can_mention_group",
                moderators_group,
                old_setting_api_value=everyone_group.id,
                acting_user=None,
            )
        check_user_group_update("events[0]", events[0], {"can_mention_group"})
        self.assertEqual(events[0]["data"]["can_mention_group"], moderators_group.id)

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [othello], [moderators_group]
        )
        with self.verify_action() as events:
            do_change_user_group_permission_setting(
                backend,
                "can_mention_group",
                setting_group,
                old_setting_api_value=moderators_group.id,
                acting_user=None,
            )
        check_user_group_update("events[0]", events[0], {"can_mention_group"})
        self.assertEqual(
            events[0]["data"]["can_mention_group"],
            UserGroupMembersDict(
                direct_members=[othello.id], direct_subgroups=[moderators_group.id]
            ),
        )

        # Test add members
        hamlet = self.example_user("hamlet")
        with self.verify_action() as events:
            bulk_add_members_to_user_groups([backend], [hamlet.id], acting_user=None)
        check_user_group_add_members("events[0]", events[0])

        # Test remove members
        hamlet = self.example_user("hamlet")
        with self.verify_action() as events:
            bulk_remove_members_from_user_groups([backend], [hamlet.id], acting_user=None)

        check_user_group_remove_members("events[0]", events[0])

        api_design = check_add_user_group(
            hamlet.realm, "api-design", [hamlet], description="API design team", acting_user=othello
        )

        # Test add subgroups
        with self.verify_action() as events:
            add_subgroups_to_user_group(backend, [api_design], acting_user=None)
        check_user_group_add_subgroups("events[0]", events[0])

        # Test remove subgroups
        with self.verify_action() as events:
            remove_subgroups_from_user_group(backend, [api_design], acting_user=None)
        check_user_group_remove_subgroups("events[0]", events[0])

        # Test deactivate and reactivate events
        with self.verify_action() as events:
            do_deactivate_user_group(backend, acting_user=None)
        check_user_group_remove("events[0]", events[0])

        with self.verify_action() as events:
            do_reactivate_user_group(backend, acting_user=None)
        check_user_group_add("events[0]", events[0])

        with self.verify_action(include_deactivated_groups=True) as events:
            do_deactivate_user_group(api_design, acting_user=None)
        check_user_group_update("events[0]", events[0], {"deactivated"})
        self.assertTrue(events[0]["data"]["deactivated"])

        with self.verify_action(include_deactivated_groups=True) as events:
            do_reactivate_user_group(api_design, acting_user=None)
        check_user_group_update("events[0]", events[0], {"deactivated"})
        self.assertFalse(events[0]["data"]["deactivated"])

        do_deactivate_user_group(api_design, acting_user=None)

        with self.verify_action(num_events=0, state_change_expected=False):
            do_update_user_group_name(api_design, "api-design-team", acting_user=None)

        with self.verify_action(include_deactivated_groups=True) as events:
            do_update_user_group_name(api_design, "api-design", acting_user=None)
        check_user_group_update("events[0]", events[0], {"name"})

    def do_test_user_group_events_on_stream_metadata_access_change(
        self,
        setting_name: str,
        stream: Stream,
        user_group: NamedUserGroup,
        hamlet_group: NamedUserGroup,
    ) -> None:
        othello = self.example_user("othello")
        hamlet = self.example_user("hamlet")
        do_change_stream_group_based_setting(stream, setting_name, user_group, acting_user=othello)

        if setting_name in Stream.stream_permission_group_settings_granting_metadata_access:
            with self.verify_action(num_events=3) as events:
                bulk_add_members_to_user_groups([user_group], [hamlet.id], acting_user=None)
            check_user_group_add_members("events[0]", events[0])
            check_stream_create("events[1]", events[1])
            check_subscription_peer_add("events[2]", events[2])

            with self.verify_action(num_events=2) as events:
                bulk_remove_members_from_user_groups([user_group], [hamlet.id], acting_user=None)
            check_user_group_remove_members("events[0]", events[0])
            check_stream_delete("events[1]", events[1])

            with self.verify_action(num_events=3) as events:
                add_subgroups_to_user_group(user_group, [hamlet_group], acting_user=None)
            check_user_group_add_subgroups("events[0]", events[0])
            check_stream_create("events[1]", events[1])
            check_subscription_peer_add("events[2]", events[2])

            with self.verify_action(num_events=2) as events:
                remove_subgroups_from_user_group(user_group, [hamlet_group], acting_user=None)
            check_user_group_remove_subgroups("events[0]", events[0])
            check_stream_delete("events[1]", events[1])
        else:
            with self.verify_action() as events:
                bulk_add_members_to_user_groups([user_group], [hamlet.id], acting_user=None)
            check_user_group_add_members("events[0]", events[0])

            with self.verify_action() as events:
                bulk_remove_members_from_user_groups([user_group], [hamlet.id], acting_user=None)
            check_user_group_remove_members("events[0]", events[0])

            with self.verify_action() as events:
                add_subgroups_to_user_group(user_group, [hamlet_group], acting_user=None)
            check_user_group_add_subgroups("events[0]", events[0])

            with self.verify_action() as events:
                remove_subgroups_from_user_group(user_group, [hamlet_group], acting_user=None)
            check_user_group_remove_subgroups("events[0]", events[0])

        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=othello.realm, is_system_group=True
        )
        do_change_stream_group_based_setting(
            stream, setting_name, nobody_group, acting_user=othello
        )

    def test_user_group_events_on_stream_metadata_access_change(self) -> None:
        test_group = check_add_user_group(
            self.user_profile.realm,
            "test_group",
            [self.example_user("othello")],
            "Test group",
            acting_user=self.example_user("othello"),
        )
        hamlet_group = check_add_user_group(
            self.user_profile.realm,
            "hamlet_group",
            [self.example_user("hamlet")],
            "Hamlet group",
            acting_user=self.example_user("othello"),
        )
        private_stream = self.make_stream("private_stream", invite_only=True)
        for setting_name in Stream.stream_permission_group_settings:
            self.do_test_user_group_events_on_stream_metadata_access_change(
                setting_name, private_stream, test_group, hamlet_group
            )

    def test_default_stream_groups_events(self) -> None:
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Scotland", "Rome", "Denmark"]
        ]

        with self.verify_action() as events:
            do_create_default_stream_group(
                self.user_profile.realm, "group1", "This is group1", streams
            )
        check_default_stream_groups("events[0]", events[0])

        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]
        venice_stream = get_stream("Venice", self.user_profile.realm)
        with self.verify_action() as events:
            do_add_streams_to_default_stream_group(self.user_profile.realm, group, [venice_stream])
        check_default_stream_groups("events[0]", events[0])

        with self.verify_action() as events:
            do_remove_streams_from_default_stream_group(
                self.user_profile.realm, group, [venice_stream]
            )
        check_default_stream_groups("events[0]", events[0])

        with self.verify_action() as events:
            do_change_default_stream_group_description(
                self.user_profile.realm, group, "New description"
            )
        check_default_stream_groups("events[0]", events[0])

        with self.verify_action() as events:
            do_change_default_stream_group_name(self.user_profile.realm, group, "New group name")
        check_default_stream_groups("events[0]", events[0])

        with self.verify_action() as events:
            do_remove_default_stream_group(self.user_profile.realm, group)
        check_default_stream_groups("events[0]", events[0])

    def test_default_stream_group_events_guest(self) -> None:
        streams = [
            get_stream(stream_name, self.user_profile.realm)
            for stream_name in ["Scotland", "Rome", "Denmark"]
        ]

        do_create_default_stream_group(self.user_profile.realm, "group1", "This is group1", streams)
        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]

        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST, acting_user=None)
        venice_stream = get_stream("Venice", self.user_profile.realm)
        with self.verify_action(state_change_expected=False, num_events=0):
            do_add_streams_to_default_stream_group(self.user_profile.realm, group, [venice_stream])

    def test_default_streams_events(self) -> None:
        stream = get_stream("Scotland", self.user_profile.realm)
        with self.verify_action() as events:
            do_add_default_stream(stream)
        check_default_streams("events[0]", events[0])
        with self.verify_action() as events:
            do_remove_default_stream(stream)
        check_default_streams("events[0]", events[0])

    def test_default_streams_events_guest(self) -> None:
        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST, acting_user=None)
        stream = get_stream("Scotland", self.user_profile.realm)
        with self.verify_action(state_change_expected=False, num_events=0):
            do_add_default_stream(stream)
        with self.verify_action(state_change_expected=False, num_events=0):
            do_remove_default_stream(stream)

    def test_muted_topics_events(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        with self.verify_action(num_events=2) as events:
            do_set_user_topic_visibility_policy(
                self.user_profile,
                stream,
                "topic",
                visibility_policy=UserTopic.VisibilityPolicy.MUTED,
            )
        check_muted_topics("events[0]", events[0])
        check_user_topic("events[1]", events[1])

        with self.verify_action(num_events=2) as events:
            do_set_user_topic_visibility_policy(
                self.user_profile,
                stream,
                "topic",
                visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
            )
        check_muted_topics("events[0]", events[0])
        check_user_topic("events[1]", events[1])

        with self.verify_action(event_types=["muted_topics", "user_topic"]) as events:
            do_set_user_topic_visibility_policy(
                self.user_profile,
                stream,
                "topic",
                visibility_policy=UserTopic.VisibilityPolicy.MUTED,
            )
        check_user_topic("events[0]", events[0])

    def test_unmuted_topics_events(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        with self.verify_action(num_events=2) as events:
            do_set_user_topic_visibility_policy(
                self.user_profile,
                stream,
                "topic",
                visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
            )
        check_muted_topics("events[0]", events[0])
        check_user_topic("events[1]", events[1])

    def test_muted_users_events(self) -> None:
        muted_user = self.example_user("othello")
        with self.verify_action(num_events=1) as events:
            do_mute_user(self.user_profile, muted_user)
        check_muted_users("events[0]", events[0])

        mute_object = get_mute_object(self.user_profile, muted_user)
        assert mute_object is not None

        with self.verify_action() as events:
            do_unmute_user(mute_object)
        check_muted_users("events[0]", events[0])

    def test_change_avatar_fields(self) -> None:
        with self.verify_action() as events:
            do_change_avatar_fields(
                self.user_profile, UserProfile.AVATAR_FROM_USER, acting_user=self.user_profile
            )
        check_realm_user_update("events[0]", events[0], "avatar_fields")
        assert isinstance(events[0]["person"]["avatar_url"], str)
        assert isinstance(events[0]["person"]["avatar_url_medium"], str)

        do_change_user_setting(
            self.user_profile,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=self.user_profile,
        )
        with self.verify_action() as events:
            do_change_avatar_fields(
                self.user_profile, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=self.user_profile
            )
        check_realm_user_update("events[0]", events[0], "avatar_fields")
        self.assertEqual(events[0]["person"]["avatar_url"], None)
        self.assertEqual(events[0]["person"]["avatar_url_medium"], None)

        self.set_up_db_for_testing_user_access()
        self.user_profile = self.example_user("polonius")
        cordelia = self.example_user("cordelia")
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_change_avatar_fields(
                cordelia, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=cordelia
            )

    def test_change_full_name(self) -> None:
        now = timezone_now()
        with self.verify_action() as events:
            do_change_full_name(self.user_profile, "Sir Hamlet", self.user_profile)
        check_realm_user_update("events[0]", events[0], "full_name")
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=self.user_profile.realm,
                event_type=AuditLogEventType.USER_FULL_NAME_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )

        # Verify no operation if the value isn't changing.
        with self.verify_action(num_events=0, state_change_expected=False):
            do_change_full_name(self.user_profile, "Sir Hamlet", self.user_profile)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=self.user_profile.realm,
                event_type=AuditLogEventType.USER_FULL_NAME_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )

        self.set_up_db_for_testing_user_access()
        cordelia = self.example_user("cordelia")
        self.user_profile = self.example_user("polonius")
        with self.verify_action(num_events=0, state_change_expected=False):
            do_change_full_name(cordelia, "Cordelia", self.user_profile)

    def test_change_user_delivery_email_email_address_visibility_admins(self) -> None:
        do_change_user_setting(
            self.user_profile,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )
        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()
        with self.verify_action(num_events=2, client_gravatar=False) as events:
            do_change_user_delivery_email(
                self.user_profile, "newhamlet@zulip.com", acting_user=self.user_profile
            )

        check_realm_user_update("events[0]", events[0], "delivery_email")
        check_realm_user_update("events[1]", events[1], "avatar_fields")
        assert isinstance(events[1]["person"]["avatar_url"], str)
        assert isinstance(events[1]["person"]["avatar_url_medium"], str)

    def test_change_user_delivery_email_email_address_visibility_everyone(self) -> None:
        do_change_user_setting(
            self.user_profile,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )
        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()
        with self.verify_action(num_events=3, client_gravatar=False) as events:
            do_change_user_delivery_email(
                self.user_profile, "newhamlet@zulip.com", acting_user=self.user_profile
            )

        check_realm_user_update("events[0]", events[0], "delivery_email")
        check_realm_user_update("events[1]", events[1], "avatar_fields")
        check_realm_user_update("events[2]", events[2], "email")
        assert isinstance(events[1]["person"]["avatar_url"], str)
        assert isinstance(events[1]["person"]["avatar_url_medium"], str)

        # Reset hamlet's email to original email.
        do_change_user_delivery_email(
            self.user_profile, "hamlet@zulip.com", acting_user=self.user_profile
        )

        self.set_up_db_for_testing_user_access()
        cordelia = self.example_user("cordelia")
        do_change_user_setting(
            cordelia,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )
        self.user_profile = self.example_user("polonius")
        with self.verify_action(num_events=0, state_change_expected=False):
            do_change_user_delivery_email(cordelia, "newcordelia@zulip.com", acting_user=None)

    def test_change_realm_authentication_methods(self) -> None:
        def fake_backends() -> Any:
            backends = (
                "zproject.backends.DevAuthBackend",
                "zproject.backends.EmailAuthBackend",
                "zproject.backends.GitHubAuthBackend",
                "zproject.backends.GoogleAuthBackend",
                "zproject.backends.ZulipLDAPAuthBackend",
            )
            return self.settings(AUTHENTICATION_BACKENDS=backends)

        # Test transitions; any new backends should be tested with T/T/T/F/T
        for auth_method_dict in (
            {"Google": True, "Email": True, "GitHub": True, "LDAP": False, "Dev": False},
            {"Google": True, "Email": True, "GitHub": False, "LDAP": False, "Dev": False},
            {"Google": True, "Email": False, "GitHub": False, "LDAP": False, "Dev": False},
            {"Google": True, "Email": False, "GitHub": True, "LDAP": False, "Dev": False},
            {"Google": False, "Email": False, "GitHub": False, "LDAP": False, "Dev": True},
            {"Google": False, "Email": False, "GitHub": True, "LDAP": False, "Dev": True},
            {"Google": False, "Email": True, "GitHub": True, "LDAP": True, "Dev": False},
        ):
            with fake_backends(), self.verify_action() as events:
                do_set_realm_authentication_methods(
                    self.user_profile.realm,
                    auth_method_dict,
                    acting_user=None,
                )

            check_realm_update_dict("events[0]", events[0])

    def test_change_pin_stream(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        sub = get_subscription(stream.name, self.user_profile)
        do_change_subscription_property(
            self.user_profile, sub, stream, "pin_to_top", False, acting_user=None
        )
        for pinned in (True, False):
            with self.verify_action() as events:
                do_change_subscription_property(
                    self.user_profile,
                    sub,
                    stream,
                    "pin_to_top",
                    pinned,
                    acting_user=None,
                )
            check_subscription_update(
                "events[0]",
                events[0],
                property="pin_to_top",
                value=pinned,
            )

    def test_mute_and_unmute_stream(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        sub = get_subscription(stream.name, self.user_profile)

        # While migrating events API from in_home_view to is_muted:
        # First, test in_home_view sends 2 events: in_home_view and is_muted.
        do_change_subscription_property(
            self.user_profile, sub, stream, "in_home_view", False, acting_user=None
        )

        with self.verify_action(num_events=2) as events:
            do_change_subscription_property(
                self.user_profile, sub, stream, "in_home_view", True, acting_user=None
            )
        check_subscription_update(
            "events[0]",
            events[0],
            property="in_home_view",
            value=True,
        )
        check_subscription_update(
            "events[1]",
            events[1],
            property="is_muted",
            value=False,
        )

        # Then, test is_muted also sends both events, in the same order.
        with self.verify_action(num_events=2) as events:
            do_change_subscription_property(
                self.user_profile, sub, stream, "is_muted", True, acting_user=None
            )
        check_subscription_update(
            "events[0]",
            events[0],
            property="in_home_view",
            value=False,
        )
        check_subscription_update(
            "events[1]",
            events[1],
            property="is_muted",
            value=True,
        )

    def test_change_stream_notification_settings(self) -> None:
        for setting_name in ["email_notifications"]:
            stream = get_stream("Denmark", self.user_profile.realm)
            sub = get_subscription(stream.name, self.user_profile)

            # First test with notification_settings_null enabled
            for value in (True, False):
                with self.verify_action(notification_settings_null=True) as events:
                    do_change_subscription_property(
                        self.user_profile,
                        sub,
                        stream,
                        setting_name,
                        value,
                        acting_user=None,
                    )
                check_subscription_update(
                    "events[0]",
                    events[0],
                    property=setting_name,
                    value=value,
                )

            for value in (True, False):
                with self.verify_action() as events:
                    do_change_subscription_property(
                        self.user_profile,
                        sub,
                        stream,
                        setting_name,
                        value,
                        acting_user=None,
                    )
                check_subscription_update(
                    "events[0]",
                    events[0],
                    property=setting_name,
                    value=value,
                )

    def test_change_realm_new_stream_announcements_stream(self) -> None:
        stream = get_stream("Rome", self.user_profile.realm)

        for new_stream_announcements_stream, new_stream_announcements_stream_id in (
            (stream, stream.id),
            (None, -1),
        ):
            with self.verify_action() as events:
                do_set_realm_new_stream_announcements_stream(
                    self.user_profile.realm,
                    new_stream_announcements_stream,
                    new_stream_announcements_stream_id,
                    acting_user=None,
                )
            check_realm_update("events[0]", events[0], "new_stream_announcements_stream_id")

    def test_change_realm_signup_announcements_stream(self) -> None:
        stream = get_stream("Rome", self.user_profile.realm)

        for signup_announcements_stream, signup_announcements_stream_id in (
            (stream, stream.id),
            (None, -1),
        ):
            with self.verify_action() as events:
                do_set_realm_signup_announcements_stream(
                    self.user_profile.realm,
                    signup_announcements_stream,
                    signup_announcements_stream_id,
                    acting_user=None,
                )
            check_realm_update("events[0]", events[0], "signup_announcements_stream_id")

    def test_change_realm_zulip_update_announcements_stream(self) -> None:
        stream = get_stream("Rome", self.user_profile.realm)

        for zulip_update_announcements_stream, zulip_update_announcements_stream_id in (
            (stream, stream.id),
            (None, -1),
        ):
            with self.verify_action() as events:
                do_set_realm_zulip_update_announcements_stream(
                    self.user_profile.realm,
                    zulip_update_announcements_stream,
                    zulip_update_announcements_stream_id,
                    acting_user=None,
                )
            check_realm_update("events[0]", events[0], "zulip_update_announcements_stream_id")

    def test_change_realm_moderation_request_channel(self) -> None:
        channel = self.make_stream("private_stream", invite_only=True)

        for moderation_request_channel, moderation_request_channel_id in (
            (channel, channel.id),
            (None, -1),
        ):
            with self.verify_action() as events:
                do_set_realm_moderation_request_channel(
                    self.user_profile.realm,
                    moderation_request_channel,
                    moderation_request_channel_id,
                    acting_user=None,
                )
            check_realm_update("events[0]", events[0], "moderation_request_channel_id")

    def do_test_change_role(
        self,
        current_role: int,
        new_role: int,
        validators: list[Callable[[str, dict[str, object]], None]],
    ) -> None:
        # We accept one less validator since `check_realm_user_update`
        # has a different shape of arguments and that check will always
        # be required.
        num_events = len(validators) + 1
        do_change_user_role(self.user_profile, current_role, acting_user=None)

        with self.verify_action(num_events=num_events) as events:
            do_change_user_role(self.user_profile, new_role, acting_user=None)
        check_realm_user_update("events[0]", events[0], "role")
        self.assertEqual(events[0]["person"]["role"], new_role)

        for i, validator in enumerate(validators):
            # We accept one less validator since `check_realm_user_update`
            # has a different shape of arguments and that check will always
            # be required.
            validator(f"events[{i + 1}]", events[i + 1])

        # Revert the role back to it's original state.
        do_change_user_role(self.user_profile, current_role, acting_user=None)

    def test_change_is_admin(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        self.make_stream("private_stream_1", invite_only=True)
        self.subscribe(self.example_user("othello"), "private_stream_1")

        private_stream_2 = self.make_stream("private_stream_2", invite_only=True)
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_administer_channel_group",
            UserGroupMembersData(direct_members=[self.user_profile.id], direct_subgroups=[]),
            acting_user=self.user_profile,
        )

        # There should only be one stream create event here for
        # `private_stream_1` since user already had access to
        # `private_stream_2` via `can_administer_channel_group.`
        self.do_test_change_role(
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_remove_members,
                check_stream_create,
                check_subscription_peer_add,
            ],
        )
        # There should only be one stream delete event here for
        # `private_stream_1` since user already had access to
        # `private_stream_2` via `can_administer_channel_group.`
        self.do_test_change_role(
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_MEMBER,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_add_members,
                check_stream_delete,
            ],
        )

    def test_change_is_owner(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)

        self.make_stream("private_stream_1", invite_only=True)
        self.subscribe(self.example_user("othello"), "private_stream_1")

        private_stream_2 = self.make_stream("private_stream_2", invite_only=True)
        do_change_stream_group_based_setting(
            private_stream_2,
            "can_administer_channel_group",
            UserGroupMembersData(direct_members=[self.user_profile.id], direct_subgroups=[]),
            acting_user=self.user_profile,
        )

        # There should only be one stream create event here for
        # `private_stream_1` since user already had access to
        # `private_stream_2` via `can_administer_channel_group.`
        self.do_test_change_role(
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_REALM_OWNER,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_remove_members,
                check_stream_create,
                check_subscription_peer_add,
            ],
        )
        # There should only be one stream delete event here for
        # `private_stream_1` since user already had access to
        # `private_stream_2` via `can_administer_channel_group.`
        self.do_test_change_role(
            UserProfile.ROLE_REALM_OWNER,
            UserProfile.ROLE_MEMBER,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_add_members,
                check_stream_delete,
            ],
        )

    def test_change_is_moderator(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        self.do_test_change_role(
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_MODERATOR,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_remove_members,
            ],
        )
        self.do_test_change_role(
            UserProfile.ROLE_MODERATOR,
            UserProfile.ROLE_MEMBER,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_add_members,
            ],
        )

    def test_change_is_guest(self) -> None:
        stream = Stream.objects.get(name="Denmark")
        do_add_default_stream(stream)

        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        self.do_test_change_role(
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_GUEST,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_remove_members,
                check_stream_delete,
            ],
        )
        self.do_test_change_role(
            UserProfile.ROLE_GUEST,
            UserProfile.ROLE_MEMBER,
            [
                check_user_group_remove_members,
                check_user_group_add_members,
                check_user_group_add_members,
                check_stream_create,
                check_subscription_peer_add,
                check_subscription_peer_add,
            ],
        )

    def test_change_user_role_for_restricted_users(self) -> None:
        self.set_up_db_for_testing_user_access()
        self.user_profile = self.example_user("polonius")

        # Technically, we can use `do_test_change_role` here also, but
        # this implementation will be more succinct and easier to
        # read than using `do_test_change_role` here.
        for role in [
            UserProfile.ROLE_REALM_OWNER,
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_MODERATOR,
            UserProfile.ROLE_MEMBER,
            UserProfile.ROLE_GUEST,
        ]:
            cordelia = self.example_user("cordelia")
            old_role = cordelia.role

            num_events = 2
            if UserProfile.ROLE_MEMBER in [old_role, role]:
                num_events = 3

            with self.verify_action(num_events=num_events) as events:
                do_change_user_role(cordelia, role, acting_user=None)

            check_user_group_remove_members("events[0]", events[0])
            check_user_group_add_members("events[1]", events[1])

            if old_role == UserProfile.ROLE_MEMBER:
                check_user_group_remove_members("events[2]", events[2])
            elif role == UserProfile.ROLE_MEMBER:
                check_user_group_add_members("events[2]", events[2])

    def test_gain_access_through_metadata_groups(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        private_stream_1 = self.make_stream("private_stream_1", invite_only=True)
        # We add this subscriber to make sure that event
        # applies correctly to the `subscribers` key of
        # stream data of "streams".
        self.subscribe(self.example_user("cordelia"), "private_stream_1")
        with self.verify_action(num_events=2, include_subscribers=True) as events:
            do_change_stream_group_based_setting(
                private_stream_1,
                "can_administer_channel_group",
                UserGroupMembersData(direct_members=[self.user_profile.id], direct_subgroups=[]),
                acting_user=self.user_profile,
            )
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])

        private_stream_2 = self.make_stream("private_stream_2", invite_only=True)
        # We add this subscriber to make sure that event
        # applies correctly to the `unsubscribed` key of
        # stream data of "streams".
        self.subscribe(self.example_user("cordelia"), "private_stream_2")
        self.subscribe(self.user_profile, "private_stream_2")
        self.unsubscribe(self.user_profile, "private_stream_2")
        with self.verify_action(num_events=2, include_subscribers=True) as events:
            do_change_stream_group_based_setting(
                private_stream_2,
                "can_administer_channel_group",
                UserGroupMembersData(direct_members=[self.user_profile.id], direct_subgroups=[]),
                acting_user=self.user_profile,
            )
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])

    def test_change_notification_settings(self) -> None:
        for notification_setting in self.user_profile.notification_setting_types:
            if notification_setting in [
                "notification_sound",
                "desktop_icon_count_display",
                "presence_enabled",
                "realm_name_in_email_notifications_policy",
                "automatically_follow_topics_policy",
                "automatically_unmute_topics_in_muted_streams_policy",
            ]:
                # These settings are tested in their own tests.
                continue

            do_change_user_setting(
                self.user_profile, notification_setting, False, acting_user=self.user_profile
            )

            # Since legacy events have been removed, only user_settings events are sent
            num_events = 1

            for setting_value in [True, False]:
                with self.verify_action(num_events=num_events) as events:
                    do_change_user_setting(
                        self.user_profile,
                        notification_setting,
                        setting_value,
                        acting_user=self.user_profile,
                    )
                check_user_settings_update("events[0]", events[0])

                # Also test with notification_settings_null=True
                with self.verify_action(
                    notification_settings_null=True,
                    state_change_expected=False,
                    num_events=num_events,
                ) as events:
                    do_change_user_setting(
                        self.user_profile,
                        notification_setting,
                        setting_value,
                        acting_user=self.user_profile,
                    )
                check_user_settings_update("events[0]", events[0])

    def test_change_presence_enabled(self) -> None:
        presence_enabled_setting = "presence_enabled"
        UserPresence.objects.filter(user_profile=self.user_profile).delete()

        # Disabling presence will lead to the creation of a UserPresence object for the user
        # with a last_connected_time and last_active_time slightly preceding the moment of flipping the
        # setting.
        for val in [True, False]:
            with self.verify_action(num_events=2) as events:
                do_change_user_setting(
                    self.user_profile,
                    presence_enabled_setting,
                    val,
                    acting_user=self.user_profile,
                )
            check_user_settings_update("events[0]", events[0])
            check_legacy_presence(
                "events[1]", events[1], has_email=True, presence_key="website", status="active"
            )

    def test_change_notification_sound(self) -> None:
        notification_setting = "notification_sound"

        with self.verify_action(num_events=1) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, "ding", acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])

    def test_change_desktop_icon_count_display(self) -> None:
        notification_setting = "desktop_icon_count_display"

        with self.verify_action(num_events=1) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 2, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])

        with self.verify_action(num_events=1) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 1, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])

    def test_change_realm_name_in_email_notifications_policy(self) -> None:
        notification_setting = "realm_name_in_email_notifications_policy"

        with self.verify_action(num_events=1) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 3, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])

        with self.verify_action(num_events=1) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 2, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])

    def test_change_automatically_follow_topics_policy(self) -> None:
        notification_setting = "automatically_follow_topics_policy"

        for setting_value in UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES:
            with self.verify_action(num_events=1) as events:
                do_change_user_setting(
                    self.user_profile,
                    notification_setting,
                    setting_value,
                    acting_user=self.user_profile,
                )
            check_user_settings_update("events[0]", events[0])

    def test_change_automatically_unmute_topics_in_muted_streams_policy(self) -> None:
        notification_setting = "automatically_unmute_topics_in_muted_streams_policy"

        for setting_value in UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES:
            with self.verify_action(num_events=1) as events:
                do_change_user_setting(
                    self.user_profile,
                    notification_setting,
                    setting_value,
                    acting_user=self.user_profile,
                )
            check_user_settings_update("events[0]", events[0])

    def test_realm_update_org_type(self) -> None:
        realm = self.user_profile.realm

        state_data = fetch_initial_state_data(self.user_profile, realm=realm)
        self.assertEqual(state_data["realm_org_type"], Realm.ORG_TYPES["business"]["id"])

        with self.verify_action() as events:
            do_change_realm_org_type(
                realm, Realm.ORG_TYPES["government"]["id"], acting_user=self.user_profile
            )
        check_realm_update("events[0]", events[0], "org_type")

        state_data = fetch_initial_state_data(self.user_profile, realm=realm)
        self.assertEqual(state_data["realm_org_type"], Realm.ORG_TYPES["government"]["id"])

    def test_realm_update_plan_type(self) -> None:
        realm = self.user_profile.realm
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=realm
        )
        do_change_realm_permission_group_setting(
            realm, "can_access_all_users_group", members_group, acting_user=None
        )

        state_data = fetch_initial_state_data(self.user_profile, realm=realm)
        self.assertEqual(state_data["realm_plan_type"], Realm.PLAN_TYPE_SELF_HOSTED)
        self.assertEqual(state_data["zulip_plan_is_not_limited"], True)

        with self.verify_action(num_events=3) as events:
            do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=self.user_profile)
        check_realm_update("events[0]", events[0], "enable_spectator_access")
        check_realm_update_dict("events[1]", events[1])
        check_realm_update_dict("events[2]", events[2])

        state_data = fetch_initial_state_data(self.user_profile, realm=realm)
        self.assertEqual(state_data["realm_plan_type"], Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(state_data["zulip_plan_is_not_limited"], False)

    def test_realm_emoji_events(self) -> None:
        author = self.example_user("iago")
        with get_test_image_file("img.png") as img_file, self.verify_action() as events:
            check_add_realm_emoji(
                self.user_profile.realm, "my_emoji", author, img_file, "image/png"
            )

        check_realm_emoji_update("events[0]", events[0])

        with self.verify_action() as events:
            do_remove_realm_emoji(
                self.user_profile.realm, "my_emoji", acting_user=self.user_profile
            )
        check_realm_emoji_update("events[0]", events[0])

    def test_realm_filter_events(self) -> None:
        regex = "#(?P<id>[123])"
        url = "https://realm.com/my_realm_filter/{id}"

        with self.verify_action(num_events=1) as events:
            do_add_linkifier(self.user_profile.realm, regex, url, acting_user=None)
        check_realm_linkifiers("events[0]", events[0])

        linkifier_id = events[0]["realm_linkifiers"][-1]["id"]
        self.assertEqual(RealmFilter.objects.get(id=linkifier_id).pattern, regex)

        regex = "#(?P<id>[0-9]+)"
        with self.verify_action(num_events=1) as events:
            do_update_linkifier(self.user_profile.realm, linkifier_id, regex, url, acting_user=None)
        check_realm_linkifiers("events[0]", events[0])

        linkifier_ids = list(
            RealmFilter.objects.all().values_list("id", flat=True).order_by("order")
        )
        with self.verify_action(num_events=1) as events:
            check_reorder_linkifiers(
                self.user_profile.realm, [linkifier_ids[-1], *linkifier_ids[:-1]], acting_user=None
            )
        check_realm_linkifiers("events[0]", events[0])

        with self.verify_action(num_events=1) as events:
            do_remove_linkifier(self.user_profile.realm, regex, acting_user=None)
        check_realm_linkifiers("events[0]", events[0])

        # Redo the checks, but assume that the client does not support URL template.
        # apply_event should drop the event, and no state change should occur.
        regex = "#(?P<id>[123])"

        with self.verify_action(
            num_events=1, linkifier_url_template=False, state_change_expected=False
        ) as events:
            do_add_linkifier(self.user_profile.realm, regex, url, acting_user=None)

        regex = "#(?P<id>[0-9]+)"
        linkifier_id = events[0]["realm_linkifiers"][0]["id"]
        with self.verify_action(
            num_events=1, linkifier_url_template=False, state_change_expected=False
        ) as events:
            do_update_linkifier(self.user_profile.realm, linkifier_id, regex, url, acting_user=None)

        with self.verify_action(
            num_events=1, linkifier_url_template=False, state_change_expected=False
        ) as events:
            do_remove_linkifier(self.user_profile.realm, regex, acting_user=None)

    def test_realm_domain_events(self) -> None:
        with self.verify_action() as events:
            do_add_realm_domain(self.user_profile.realm, "zulip.org", False, acting_user=None)

        check_realm_domains_add("events[0]", events[0])
        self.assertEqual(events[0]["realm_domain"]["domain"], "zulip.org")
        self.assertEqual(events[0]["realm_domain"]["allow_subdomains"], False)

        test_domain = RealmDomain.objects.get(realm=self.user_profile.realm, domain="zulip.org")
        with self.verify_action() as events:
            do_change_realm_domain(test_domain, True, acting_user=None)

        check_realm_domains_change("events[0]", events[0])
        self.assertEqual(events[0]["realm_domain"]["domain"], "zulip.org")
        self.assertEqual(events[0]["realm_domain"]["allow_subdomains"], True)

        with self.verify_action() as events:
            do_remove_realm_domain(test_domain, acting_user=None)

        check_realm_domains_remove("events[0]", events[0])
        self.assertEqual(events[0]["domain"], "zulip.org")

    def test_realm_playground_events(self) -> None:
        with self.verify_action() as events:
            check_add_realm_playground(
                self.user_profile.realm,
                acting_user=None,
                name="Python playground",
                pygments_language="Python",
                url_template="https://python.example.com{code}",
            )
        check_realm_playgrounds("events[0]", events[0])

        last_realm_playground = RealmPlayground.objects.last()
        assert last_realm_playground is not None
        last_id = last_realm_playground.id
        realm_playground = access_playground_by_id(self.user_profile.realm, last_id)
        with self.verify_action() as events:
            do_remove_realm_playground(self.user_profile.realm, realm_playground, acting_user=None)
        check_realm_playgrounds("events[0]", events[0])

    def test_create_bot(self) -> None:
        with self.verify_action(num_events=4) as events:
            self.create_bot("test")
        check_realm_bot_add("events[3]", events[3])

        with self.verify_action(num_events=4) as events:
            self.create_bot(
                "test_outgoing_webhook",
                full_name="Outgoing Webhook Bot",
                payload_url=orjson.dumps("https://foo.bar.com").decode(),
                interface_type=Service.GENERIC,
                bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            )
        # The third event is the second call of notify_created_bot, which contains additional
        # data for services (in contrast to the first call).
        check_realm_bot_add("events[3]", events[3])

        with self.verify_action(num_events=4) as events:
            self.create_bot(
                "test_embedded",
                full_name="Embedded Bot",
                service_name="helloworld",
                config_data=orjson.dumps({"foo": "bar"}).decode(),
                bot_type=UserProfile.EMBEDDED_BOT,
            )
        check_realm_bot_add("events[3]", events[3])

    def test_change_bot_full_name(self) -> None:
        bot = self.create_bot("test")
        with self.verify_action(num_events=2) as events:
            do_change_full_name(bot, "New Bot Name", self.user_profile)
        check_realm_bot_update("events[1]", events[1], "full_name")

    def test_regenerate_bot_api_key(self) -> None:
        bot = self.create_bot("test")
        with self.verify_action() as events:
            do_regenerate_api_key(bot, self.user_profile)
        check_realm_bot_update("events[0]", events[0], "api_key")

    def test_change_bot_avatar_source(self) -> None:
        bot = self.create_bot("test")
        with self.verify_action(num_events=2) as events:
            do_change_avatar_fields(bot, bot.AVATAR_FROM_USER, acting_user=self.user_profile)
        check_realm_bot_update("events[0]", events[0], "avatar_url")
        self.assertEqual(events[1]["type"], "realm_user")

    def test_change_realm_icon_source(self) -> None:
        with self.verify_action(state_change_expected=True) as events:
            do_change_icon_source(self.user_profile.realm, Realm.ICON_UPLOADED, acting_user=None)
        check_realm_update_dict("events[0]", events[0])

    def test_change_realm_light_theme_logo_source(self) -> None:
        with self.verify_action(state_change_expected=True) as events:
            do_change_logo_source(
                self.user_profile.realm, Realm.LOGO_UPLOADED, False, acting_user=self.user_profile
            )
        check_realm_update_dict("events[0]", events[0])

    def test_change_realm_dark_theme_logo_source(self) -> None:
        with self.verify_action(state_change_expected=True) as events:
            do_change_logo_source(
                self.user_profile.realm, Realm.LOGO_UPLOADED, True, acting_user=self.user_profile
            )
        check_realm_update_dict("events[0]", events[0])

    def test_change_bot_default_all_public_streams(self) -> None:
        bot = self.create_bot("test")
        with self.verify_action() as events:
            do_change_default_all_public_streams(bot, True, acting_user=None)
        check_realm_bot_update("events[0]", events[0], "default_all_public_streams")

    def test_change_bot_default_sending_stream(self) -> None:
        bot = self.create_bot("test")
        stream = get_stream("Rome", bot.realm)

        with self.verify_action() as events:
            do_change_default_sending_stream(bot, stream, acting_user=None)
        check_realm_bot_update("events[0]", events[0], "default_sending_stream")

        with self.verify_action() as events:
            do_change_default_sending_stream(bot, None, acting_user=None)
        check_realm_bot_update("events[0]", events[0], "default_sending_stream")

    def test_change_bot_default_events_register_stream(self) -> None:
        bot = self.create_bot("test")
        stream = get_stream("Rome", bot.realm)

        with self.verify_action() as events:
            do_change_default_events_register_stream(bot, stream, acting_user=None)
        check_realm_bot_update("events[0]", events[0], "default_events_register_stream")

        with self.verify_action() as events:
            do_change_default_events_register_stream(bot, None, acting_user=None)
        check_realm_bot_update("events[0]", events[0], "default_events_register_stream")

    def test_change_bot_owner(self) -> None:
        self.user_profile = self.example_user("iago")
        owner = self.example_user("hamlet")
        bot = self.create_bot("test")
        with self.verify_action(num_events=2) as events:
            do_change_bot_owner(bot, owner, self.user_profile)
        check_realm_bot_update("events[0]", events[0], "owner_id")
        check_realm_user_update("events[1]", events[1], "bot_owner_id")

        self.user_profile = self.example_user("aaron")
        owner = self.example_user("hamlet")
        bot = self.create_bot("test1", full_name="Test1 Testerson")
        with self.verify_action(num_events=2) as events:
            do_change_bot_owner(bot, owner, self.user_profile)
        check_realm_bot_delete("events[0]", events[0])
        check_realm_user_update("events[1]", events[1], "bot_owner_id")

        previous_owner = self.example_user("aaron")
        self.user_profile = self.example_user("hamlet")
        bot = self.create_test_bot("test2", previous_owner, full_name="Test2 Testerson")
        with self.verify_action(num_events=2) as events:
            do_change_bot_owner(bot, self.user_profile, previous_owner)
        check_realm_bot_add("events[0]", events[0])
        check_realm_user_update("events[1]", events[1], "bot_owner_id")

    def test_do_update_outgoing_webhook_service(self) -> None:
        self.user_profile = self.example_user("iago")
        bot = self.create_test_bot(
            "test",
            self.user_profile,
            full_name="Test Bot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            payload_url=orjson.dumps("http://hostname.domain2.com").decode(),
            interface_type=Service.GENERIC,
        )
        with self.verify_action() as events:
            do_update_outgoing_webhook_service(
                bot,
                interface=2,
                base_url="http://hostname.domain2.com",
                acting_user=self.user_profile,
            )

        check_realm_bot_update("events[0]", events[0], "services")

        # Check the updated Service data we send as event on commit.
        bot_service = get_bot_services(bot.id)[0]
        event_data_service = events[0]["bot"]["services"][0]
        self.assertEqual(
            {
                "base_url": bot_service.base_url,
                "interface": bot_service.interface,
                "token": bot_service.token,
            },
            event_data_service,
        )

        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_update_outgoing_webhook_service(bot, acting_user=self.user_profile)

        # Trying to update with the same value as existing value results in no op.
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_update_outgoing_webhook_service(
                bot,
                interface=2,
                base_url="http://hostname.domain2.com",
                acting_user=self.user_profile,
            )

    def test_do_deactivate_bot(self) -> None:
        bot = self.create_bot("test")
        with self.verify_action(num_events=2) as events:
            do_deactivate_user(bot, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")
        check_realm_bot_update("events[1]", events[1], "is_active")

    def test_do_deactivate_user(self) -> None:
        user_profile = self.example_user("cordelia")
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=user_profile.realm, is_system_group=True
        )
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [user_profile], [members_group]
        )
        do_change_realm_permission_group_setting(
            self.user_profile.realm,
            "can_create_public_channel_group",
            setting_group,
            acting_user=None,
        )
        hamletcharacters_group = NamedUserGroup.objects.get(
            name="hamletcharacters", realm_for_sharding=self.user_profile.realm
        )
        hamlet = self.example_user("hamlet")
        self.user_profile = hamlet
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [user_profile, hamlet], [members_group]
        )
        do_change_user_group_permission_setting(
            hamletcharacters_group, "can_mention_group", setting_group, acting_user=None
        )

        with self.verify_action(num_events=2) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])
        check_realm_user_update("events[1]", events[1], "is_active")

        do_reactivate_user(user_profile, acting_user=None)
        self.set_up_db_for_testing_user_access()
        self.user_profile.refresh_from_db()

        # Test that users who can access the deactivated user
        # do not receive the 'user_group/remove_members' event.
        user_profile = self.example_user("cordelia")
        with self.verify_action(num_events=2) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])
        check_realm_user_update("events[1]", events[1], "is_active")

        # Send peer_remove events for archived streams.
        do_reactivate_user(user_profile, acting_user=None)
        stream = self.make_stream("Stream to be archived")
        self.subscribe(user_profile, "Stream to be archived")
        do_deactivate_stream(stream, acting_user=None)
        with self.verify_action(num_events=2) as events:
            do_deactivate_user(user_profile, acting_user=None)
        self.assertIn(stream.id, events[0]["stream_ids"])
        check_subscription_peer_remove("events[0]", events[0])
        check_realm_user_update("events[1]", events[1], "is_active")

        do_reactivate_user(user_profile, acting_user=None)

        # Test that guest users receive 'user_group/remove_members'
        # event if they cannot access the deactivated user.
        user_profile = self.example_user("cordelia")
        self.user_profile = self.example_user("polonius")
        with self.verify_action(num_events=7) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_user_group_remove_members("events[0]", events[0])
        check_user_group_remove_members("events[1]", events[1])
        check_user_group_remove_members("events[2]", events[2])
        check_user_group_update("events[3]", events[3], {"can_add_members_group"})
        check_user_group_update("events[4]", events[4], {"can_manage_group"})
        check_realm_update_dict("events[5]", events[5])
        check_user_group_update("events[6]", events[6], {"can_mention_group"})
        self.assertEqual(
            events[3]["data"]["can_add_members_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[]),
        )
        self.assertEqual(
            events[4]["data"]["can_manage_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[]),
        )
        self.assertEqual(
            events[5]["data"]["can_create_public_channel_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[members_group.id]),
        )
        self.assertEqual(
            events[6]["data"]["can_mention_group"],
            UserGroupMembersDict(direct_members=[hamlet.id], direct_subgroups=[members_group.id]),
        )

        user_profile = self.example_user("cordelia")
        do_reactivate_user(user_profile, acting_user=None)
        with self.verify_action(num_events=7, user_list_incomplete=True) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_user_group_remove_members("events[0]", events[0])
        check_user_group_remove_members("events[1]", events[1])
        check_user_group_remove_members("events[2]", events[2])
        check_user_group_update("events[3]", events[3], {"can_add_members_group"})
        check_user_group_update("events[4]", events[4], {"can_manage_group"})
        check_realm_update_dict("events[5]", events[5])
        check_user_group_update("events[6]", events[6], {"can_mention_group"})
        self.assertEqual(
            events[3]["data"]["can_add_members_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[]),
        )
        self.assertEqual(
            events[4]["data"]["can_manage_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[]),
        )
        self.assertEqual(
            events[5]["data"]["can_create_public_channel_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[members_group.id]),
        )
        self.assertEqual(
            events[6]["data"]["can_mention_group"],
            UserGroupMembersDict(direct_members=[hamlet.id], direct_subgroups=[members_group.id]),
        )

        user_profile = self.example_user("shiva")
        with self.verify_action(num_events=1) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")

        # Guest loses access to deactivated user if the user
        # was not involved in DMs.
        user_profile = self.example_user("hamlet")
        # User is in the same channel as guest, but not in DMs.
        self.make_stream("Test new stream")
        self.subscribe(user_profile, "Test new stream")
        self.subscribe(self.user_profile, "Test new stream")
        with self.verify_action(num_events=7) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])
        check_subscription_peer_remove("events[1]", events[1])
        check_user_group_remove_members("events[2]", events[2])
        check_user_group_remove_members("events[3]", events[3])
        check_user_group_remove_members("events[4]", events[4])
        check_user_group_update("events[5]", events[5], {"can_mention_group"})
        check_realm_user_remove("events[6]]", events[6])
        self.assertEqual(
            events[5]["data"]["can_mention_group"],
            UserGroupMembersDict(direct_members=[], direct_subgroups=[members_group.id]),
        )

        user_profile = self.example_user("aaron")
        # One update event is for a deactivating a bot owned by aaron.
        with self.verify_action(num_events=2) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")
        check_realm_user_update("events[1]", events[1], "is_active")

    def test_do_reactivate_user(self) -> None:
        bot = self.create_bot("test")
        self.subscribe(bot, "Denmark")
        self.make_stream("Test private stream", invite_only=True)
        self.subscribe(bot, "Test private stream")
        do_deactivate_user(bot, acting_user=None)
        with self.verify_action(num_events=5) as events:
            do_reactivate_user(bot, acting_user=None)
        check_realm_bot_update("events[1]", events[1], "is_active")
        check_subscription_peer_add("events[2]", events[2])
        check_user_group_add_members("events[3]", events[3])
        check_user_group_add_members("events[4]", events[4])

        # Test 'peer_add' event for private stream is received only if user is subscribed to it.
        do_deactivate_user(bot, acting_user=None)
        self.subscribe(self.example_user("hamlet"), "Test private stream")
        with self.verify_action(num_events=6) as events:
            do_reactivate_user(bot, acting_user=None)
        check_realm_bot_update("events[1]", events[1], "is_active")
        check_subscription_peer_add("events[2]", events[2])
        check_subscription_peer_add("events[3]", events[3])

        do_deactivate_user(bot, acting_user=None)
        do_deactivate_user(self.example_user("hamlet"), acting_user=None)

        reset_email_visibility_to_everyone_in_zulip_realm()
        bot.refresh_from_db()

        self.user_profile = self.example_user("iago")
        with self.verify_action(num_events=8) as events:
            do_reactivate_user(bot, acting_user=self.example_user("iago"))
        check_realm_bot_update("events[1]", events[1], "is_active")
        check_realm_bot_update("events[2]", events[2], "owner_id")
        check_realm_user_update("events[3]", events[3], "bot_owner_id")
        check_subscription_peer_add("events[4]", events[4])
        check_subscription_peer_add("events[5]", events[5])

        user_profile = self.example_user("cordelia")
        members_group = NamedUserGroup.objects.get(
            name=SystemGroups.MEMBERS, realm_for_sharding=user_profile.realm, is_system_group=True
        )
        hamletcharacters_group = NamedUserGroup.objects.get(
            name="hamletcharacters", realm_for_sharding=self.user_profile.realm
        )

        setting_group = self.create_or_update_anonymous_group_for_setting(
            [user_profile], [hamletcharacters_group]
        )
        do_change_realm_permission_group_setting(
            user_profile.realm,
            "can_create_public_channel_group",
            setting_group,
            acting_user=None,
        )
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [user_profile], [members_group]
        )
        do_change_user_group_permission_setting(
            hamletcharacters_group, "can_mention_group", setting_group, acting_user=None
        )

        self.set_up_db_for_testing_user_access()
        # Test that guest users receive realm_user/update event
        # only if they can access the reactivated user.
        user_profile = self.example_user("cordelia")
        do_deactivate_user(user_profile, acting_user=None)

        self.user_profile = self.example_user("polonius")
        # Guest users receives group members update event for three groups -
        # members group, full members group and hamletcharacters group.
        with self.verify_action(num_events=7) as events:
            do_reactivate_user(user_profile, acting_user=None)
        check_user_group_add_members("events[0]", events[0])
        check_user_group_add_members("events[1]", events[1])
        check_user_group_add_members("events[2]", events[2])
        check_user_group_update("events[3]", events[3], {"can_add_members_group"})
        check_user_group_update("events[4]", events[4], {"can_manage_group"})
        check_realm_update_dict("events[5]", events[5])
        check_user_group_update("events[6]", events[6], {"can_mention_group"})
        self.assertEqual(
            events[3]["data"]["can_add_members_group"],
            UserGroupMembersDict(direct_members=[user_profile.id], direct_subgroups=[]),
        )
        self.assertEqual(
            events[4]["data"]["can_manage_group"],
            UserGroupMembersDict(direct_members=[user_profile.id], direct_subgroups=[]),
        )
        self.assertEqual(
            events[5]["data"]["can_create_public_channel_group"],
            UserGroupMembersDict(
                direct_members=[user_profile.id], direct_subgroups=[hamletcharacters_group.id]
            ),
        )
        self.assertEqual(
            events[6]["data"]["can_mention_group"],
            UserGroupMembersDict(
                direct_members=[user_profile.id], direct_subgroups=[members_group.id]
            ),
        )

        user_profile = self.example_user("shiva")
        do_deactivate_user(user_profile, acting_user=None)
        with self.verify_action(num_events=2) as events:
            do_reactivate_user(user_profile, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")
        check_user_group_add_members("events[1]", events[1])

        # Verify that admins receive 'realm_export_consent' event
        # when a user is reactivated.
        do_deactivate_user(user_profile, acting_user=None)
        self.user_profile = self.example_user("iago")
        with self.verify_action(num_events=4) as events:
            do_reactivate_user(user_profile, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")
        check_realm_export_consent("events[1]", events[1])
        check_subscription_peer_add("events[2]", events[2])
        check_user_group_add_members("events[3]", events[3])

    def test_do_activate_imported_stub_user(self) -> None:
        self.user_profile.is_imported_stub = True
        self.user_profile.save()

        with self.verify_action() as events:
            do_change_is_imported_stub(self.user_profile)

        check_realm_user_update("events[0]", events[0], "is_imported_stub")
        self.assertEqual(events[0]["person"]["user_id"], self.user_profile.id)
        self.assertFalse(events[0]["person"]["is_imported_stub"])

    def test_do_deactivate_realm(self) -> None:
        realm = self.user_profile.realm

        # We delete sessions of all active users when a realm is
        # deactivated, and redirect them to a deactivated page in
        # order to inform that realm/organization has been
        # deactivated.  state_change_expected is False is kinda
        # correct because were one to somehow compute page_params (as
        # this test does), but that's not actually possible.
        with self.verify_action(state_change_expected=False) as events:
            do_deactivate_realm(
                realm, acting_user=None, deactivation_reason="owner_request", email_owners=False
            )
        check_realm_deactivated("events[0]", events[0])

    def test_do_mark_onboarding_step_as_read(self) -> None:
        self.user_profile = do_create_user(
            "user@zulip.com", "password", self.user_profile.realm, "user", acting_user=None
        )
        with self.verify_action() as events:
            do_mark_onboarding_step_as_read(self.user_profile, "intro_inbox_view_modal")
        check_onboarding_steps("events[0]", events[0])

    def test_rename_stream(self) -> None:
        for i, include_streams in enumerate([True, False]):
            old_name = f"old name{i}"
            new_name = f"new name{i}"

            stream = self.make_stream(old_name)
            self.subscribe(self.user_profile, stream.name)
            with self.verify_action(num_events=2, include_streams=include_streams) as events:
                do_rename_stream(stream, new_name, self.user_profile)

            check_stream_update("events[0]", events[0])
            self.assertEqual(events[0]["name"], old_name)

            check_message("events[1]", events[1])

            fields = dict(
                sender_email="notification-bot@zulip.com",
                display_recipient=new_name,
                sender_full_name="Notification Bot",
                is_me_message=False,
                type="stream",
                client="Internal",
            )

            fields[TOPIC_NAME] = "channel events"

            msg = events[1]["message"]
            for k, v in fields.items():
                self.assertEqual(msg[k], v)

    def test_deactivate_stream_neversubscribed(self) -> None:
        for i, include_streams in enumerate([True, False]):
            stream = self.make_stream(f"stream{i}")
            with self.verify_action(
                include_streams=include_streams, archived_channels=True
            ) as events:
                do_deactivate_stream(stream, acting_user=None)
            check_stream_update("events[0]", events[0])
            self.assertEqual(events[0]["stream_id"], stream.id)
            self.assertEqual(events[0]["property"], "is_archived")
            self.assertEqual(events[0]["value"], True)

            do_unarchive_stream(stream, stream.name, acting_user=None)

            with self.verify_action(
                include_streams=include_streams, archived_channels=False
            ) as events:
                do_deactivate_stream(stream, acting_user=None)
            check_stream_delete("events[0]", events[0])
            self.assertEqual(events[0]["stream_ids"], [stream.id])

    def test_admin_deactivate_unsubscribed_stream(self) -> None:
        self.set_up_db_for_testing_user_access()
        stream = self.make_stream("test_stream")
        iago = self.example_user("iago")
        realm = iago.realm
        self.user_profile = self.example_user("iago")

        self.subscribe(iago, stream.name)
        self.assertCountEqual(self.users_subscribed_to_stream(stream.name, realm), [iago])

        self.unsubscribe(iago, stream.name)
        self.assertCountEqual(self.users_subscribed_to_stream(stream.name, realm), [])

        with self.verify_action(num_events=1, archived_channels=True) as events:
            do_deactivate_stream(stream, acting_user=iago)
        check_stream_update("events[0]", events[0])
        self.assertEqual(events[0]["stream_id"], stream.id)
        self.assertEqual(events[0]["property"], "is_archived")
        self.assertEqual(events[0]["value"], True)

        do_unarchive_stream(stream, stream.name, acting_user=iago)

        with self.verify_action(num_events=1, archived_channels=False) as events:
            do_deactivate_stream(stream, acting_user=iago)
        check_stream_delete("events[0]", events[0])
        self.assertEqual(events[0]["stream_ids"], [stream.id])

    def test_unarchiving_stream(self) -> None:
        iago = self.example_user("iago")
        stream = self.make_stream("test_stream")
        do_deactivate_stream(stream, acting_user=iago)

        with self.verify_action(num_events=1, archived_channels=False) as events:
            do_unarchive_stream(stream, stream.name, acting_user=iago)
        check_stream_create("events[0]", events[0])
        self.assert_length(events[0]["streams"], 1)
        self.assertEqual(events[0]["streams"][0]["stream_id"], stream.id)

        do_deactivate_stream(stream, acting_user=iago)

        with self.verify_action(num_events=1, archived_channels=True) as events:
            do_unarchive_stream(stream, stream.name, acting_user=iago)
        check_stream_update("events[0]", events[0])
        self.assertEqual(events[0]["stream_id"], stream.id)
        self.assertEqual(events[0]["property"], "is_archived")
        self.assertEqual(events[0]["value"], False)

    def test_user_losing_access_on_deactivating_stream(self) -> None:
        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm
        self.user_profile = self.example_user("polonius")

        stream = get_stream("test_stream1", realm)
        self.assertCountEqual(
            self.users_subscribed_to_stream(stream.name, realm), [hamlet, polonius]
        )

        with self.verify_action(num_events=2, archived_channels=True) as events:
            do_deactivate_stream(stream, acting_user=None)
        check_stream_update("events[0]", events[0])

        # Test that if the subscribers of deactivated stream are involved in
        # DMs with guest, then the guest does not get "remove" event for them.
        stream = get_stream("test_stream2", self.user_profile.realm)
        shiva = self.example_user("shiva")
        iago = self.example_user("iago")
        self.subscribe(shiva, stream.name)
        self.assertCountEqual(
            self.users_subscribed_to_stream(stream.name, realm), [iago, polonius, shiva]
        )

        with self.verify_action(num_events=2, archived_channels=True) as events:
            do_deactivate_stream(stream, acting_user=None)
        check_stream_update("events[0]", events[0])

    def test_subscribe_other_user_never_subscribed(self) -> None:
        for i, include_streams in enumerate([True, False]):
            with self.verify_action(num_events=2, include_streams=True) as events:
                self.subscribe(self.example_user("othello"), f"test_stream{i}")
            check_subscription_peer_add("events[1]", events[1])

    def test_remove_other_user_never_subscribed(self) -> None:
        othello = self.example_user("othello")
        realm = othello.realm
        self.subscribe(othello, "test_stream")
        stream = get_stream("test_stream", self.user_profile.realm)

        with self.verify_action() as events:
            bulk_remove_subscriptions(realm, [othello], [stream], acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])

    def test_do_delete_message_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Verona")
        msg_id_2 = self.send_stream_message(hamlet, "Verona")
        # Pass messages in reverse sorted order, so we can test that
        # the backend is sorting the messages_ids sent in the delete
        # event.
        messages = [Message.objects.get(id=msg_id_2), Message.objects.get(id=msg_id)]
        with self.verify_action(state_change_expected=True) as events:
            do_delete_messages(self.user_profile.realm, messages, acting_user=None)
        check_delete_message(
            "events[0]",
            events[0],
            message_type="stream",
            num_message_ids=2,
            is_legacy=False,
        )
        self.assertEqual(events[0]["message_ids"], sorted(events[0]["message_ids"]))

    def test_do_delete_message_stream_legacy(self) -> None:
        """
        Test for legacy method of deleting messages which
        sends an event per message to delete to the client.
        """
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Verona")
        msg_id_2 = self.send_stream_message(hamlet, "Verona")
        messages = [Message.objects.get(id=msg_id), Message.objects.get(id=msg_id_2)]
        with self.verify_action(
            state_change_expected=True, bulk_message_deletion=False, num_events=2
        ) as events:
            do_delete_messages(self.user_profile.realm, messages, acting_user=None)
        check_delete_message(
            "events[0]",
            events[0],
            message_type="stream",
            num_message_ids=1,
            is_legacy=True,
        )

    def test_do_delete_first_message_in_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "test_stream1")
        msg_id = self.send_stream_message(hamlet, "test_stream1")
        msg_id_2 = self.send_stream_message(hamlet, "test_stream1")
        message = Message.objects.get(id=msg_id)
        with self.verify_action(state_change_expected=True, num_events=2) as events:
            do_delete_messages(self.user_profile.realm, [message], acting_user=None)

        check_stream_update("events[0]", events[0])
        self.assertEqual(events[0]["property"], "first_message_id")
        self.assertEqual(events[0]["value"], msg_id_2)

        check_delete_message(
            "events[1]",
            events[1],
            message_type="stream",
            num_message_ids=1,
            is_legacy=False,
        )

    def test_check_update_all_streams_active_status(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "test_stream1")
        stream = get_stream("test_stream1", self.user_profile.realm)

        # Delete all messages in the stream so that it becomes inactive.
        Message.objects.filter(recipient__type_id=stream.id, realm=stream.realm).delete()

        with self.verify_action() as events:
            check_update_all_streams_active_status()

        check_stream_update("events[0]", events[0])

    def test_do_delete_message_personal(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("cordelia"),
            self.user_profile,
            "hello",
        )
        message = Message.objects.get(id=msg_id)
        with self.verify_action(state_change_expected=True) as events:
            do_delete_messages(self.user_profile.realm, [message], acting_user=None)
        check_delete_message(
            "events[0]",
            events[0],
            message_type="private",
            num_message_ids=1,
            is_legacy=False,
        )

    def test_do_delete_message_personal_legacy(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("cordelia"),
            self.user_profile,
            "hello",
        )
        message = Message.objects.get(id=msg_id)
        with self.verify_action(state_change_expected=True, bulk_message_deletion=False) as events:
            do_delete_messages(self.user_profile.realm, [message], acting_user=None)
        check_delete_message(
            "events[0]",
            events[0],
            message_type="private",
            num_message_ids=1,
            is_legacy=True,
        )

    def test_do_delete_message_no_max_id(self) -> None:
        user_profile = self.example_user("aaron")
        # Delete all historical messages for this user
        user_profile = self.example_user("hamlet")
        UserMessage.objects.filter(user_profile=user_profile).delete()
        msg_id = self.send_stream_message(user_profile, "Verona")
        message = Message.objects.get(id=msg_id)
        with self.verify_action(state_change_expected=True):
            do_delete_messages(self.user_profile.realm, [message], acting_user=None)
        result = fetch_initial_state_data(user_profile, realm=user_profile.realm)
        self.assertEqual(result["max_message_id"], -1)

    def test_do_delete_message_with_no_messages(self) -> None:
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_delete_messages(self.user_profile.realm, [], acting_user=None)
        self.assertEqual(events, [])

    def test_add_attachment(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        url = None

        def do_upload() -> None:
            nonlocal url
            result = self.client_post("/json/user_uploads", {"file": fp})

            response_dict = self.assert_json_success(result)
            self.assertIn("uri", response_dict)
            self.assertIn("url", response_dict)
            url = response_dict["url"]
            self.assertEqual(response_dict["uri"], url)
            base = "/user_uploads/"
            self.assertEqual(base, url[: len(base)])

        with self.verify_action(num_events=1, state_change_expected=False) as events:
            do_upload()

        check_attachment_add("events[0]", events[0])
        self.assertEqual(events[0]["upload_space_used"], 6)

        # Verify that the DB has the attachment marked as unclaimed
        entry = Attachment.objects.get(file_name="zulip.txt")
        self.assertEqual(entry.is_claimed(), False)

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        assert url is not None
        body = f"First message ...[zulip.txt](http://{hamlet.realm.host}" + url + ")"
        with self.verify_action(num_events=2) as events:
            self.send_stream_message(
                self.example_user("hamlet"),
                "Denmark",
                body,
                "test",
                skip_capture_on_commit_callbacks=True,
            )

        check_attachment_update("events[0]", events[0])
        self.assertEqual(events[0]["upload_space_used"], 6)

        # Now remove the attachment
        with self.verify_action(num_events=1, state_change_expected=False) as events:
            self.client_delete(f"/json/attachments/{entry.id}")

        check_attachment_remove("events[0]", events[0])
        self.assertEqual(events[0]["upload_space_used"], 0)

    def test_notify_realm_export(self) -> None:
        do_change_user_role(
            self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None
        )
        self.login_user(self.user_profile)

        with mock.patch(
            "zerver.lib.export.do_export_realm",
            return_value=(create_dummy_file("test-export.tar.gz"), dict()),
        ):
            with (
                stdout_suppressed(),
                self.assertLogs(level="INFO") as info_logs,
                self.verify_action(state_change_expected=True, num_events=3) as events,
            ):
                self.client_post("/json/export/realm")
            self.assertTrue("INFO:root:Completed data export for zulip in" in info_logs.output[0])

        # We get two realm_export events for this action, where the first
        # is missing the export_url (because it's pending).
        check_realm_export(
            "events[0]",
            events[0],
            has_export_url=False,
            has_deleted_timestamp=False,
            has_failed_timestamp=False,
        )

        check_realm_export(
            "events[2]",
            events[2],
            has_export_url=True,
            has_deleted_timestamp=False,
            has_failed_timestamp=False,
        )

        # Now we check the deletion of the export.
        export_row = RealmExport.objects.first()
        assert export_row is not None
        export_row_id = export_row.id
        with self.verify_action(state_change_expected=False, num_events=1) as events:
            self.client_delete(f"/json/export/realm/{export_row_id}")

        check_realm_export(
            "events[0]",
            events[0],
            has_export_url=False,
            has_deleted_timestamp=True,
            has_failed_timestamp=False,
        )

        audit_log = RealmAuditLog.objects.last()
        assert audit_log is not None
        self.assertEqual(audit_log.event_type, AuditLogEventType.REALM_EXPORT_DELETED)
        self.assertEqual(audit_log.acting_user, self.user_profile)
        self.assertEqual(audit_log.extra_data["realm_export_id"], export_row_id)

    def test_push_device_registration_failure(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        push_device = PushDevice.objects.create(
            user=hamlet,
            token_kind=PushDevice.TokenKind.FCM,
            push_account_id=2408,
            push_key=base64.b64decode("MbZ1JWx6YMHw1cZEgCPRQAgolV3lBRefP5qp/GNisiP+"),
        )

        queue_item: RegisterPushDeviceToBouncerQueueItem = {
            "user_profile_id": push_device.user.id,
            "push_account_id": push_device.push_account_id,
            "bouncer_public_key": "bouncer-public-key",
            "encrypted_push_registration": "encrypted-push-registration",
        }
        with (
            mock.patch(
                "zerver.lib.push_registration.do_register_remote_push_device",
                side_effect=InvalidBouncerPublicKeyError,
            ),
            self.verify_action(state_change_expected=True, num_events=1) as events,
        ):
            handle_register_push_device_to_bouncer(queue_item)
        check_push_device("events[0]", events[0])
        self.assertEqual(events[0]["status"], "failed")
        self.assertEqual(events[0]["error_code"], "INVALID_BOUNCER_PUBLIC_KEY")

    def test_notify_realm_export_on_failure(self) -> None:
        do_change_user_role(
            self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None
        )
        self.login_user(self.user_profile)

        with (
            mock.patch("zerver.lib.export.do_export_realm", side_effect=Exception("Some failure")),
            self.assertLogs(level="ERROR") as error_log,
        ):
            with (
                stdout_suppressed(),
                self.verify_action(state_change_expected=False, num_events=2) as events,
            ):
                self.client_post("/json/export/realm")

            # Log is of following format: "ERROR:root:Data export for zulip failed after 0.004499673843383789"
            # Where last floating number is time and will vary in each test hence the following assertion is
            # independent of time bit by not matching exact log but only part of it.
            self.assertTrue("ERROR:root:Data export for zulip failed after" in error_log.output[0])
            self.assertTrue("Some failure" in error_log.output[0])

        # We get two events for the export.
        check_realm_export(
            "events[0]",
            events[0],
            has_export_url=False,
            has_deleted_timestamp=False,
            has_failed_timestamp=False,
        )
        check_realm_export(
            "events[1]",
            events[1],
            has_export_url=False,
            has_deleted_timestamp=False,
            has_failed_timestamp=True,
        )

    def test_has_zoom_token(self) -> None:
        with self.verify_action() as events:
            do_set_zoom_token(self.user_profile, {"access_token": "token"})
        check_has_zoom_token("events[0]", events[0], value=True)

        with self.verify_action() as events:
            do_set_zoom_token(self.user_profile, None)
        check_has_zoom_token("events[0]", events[0], value=False)

    def test_restart_event(self) -> None:
        with self.verify_action(num_events=1, state_change_expected=False):
            send_restart_events()

    def test_web_reload_client_event(self) -> None:
        with self.verify_action(client_is_old=False, num_events=0, state_change_expected=False):
            send_web_reload_client_events()
        with self.assertLogs(level="WARNING") as logs:
            with self.verify_action(client_is_old=True, num_events=1, state_change_expected=False):
                send_web_reload_client_events()
            self.assertEqual(
                logs.output, ["WARNING:root:Got a web_reload_client event during apply_events"]
            )

    def test_display_setting_event_not_sent(self) -> None:
        with self.verify_action(state_change_expected=True, user_settings_object=True) as events:
            do_change_user_setting(
                self.user_profile,
                "web_home_view",
                "all_messages",
                acting_user=self.user_profile,
            )
        check_user_settings_update("events[0]", events[0])

    def test_notification_setting_event_not_sent(self) -> None:
        with self.verify_action(state_change_expected=True, user_settings_object=True) as events:
            do_change_user_setting(
                self.user_profile,
                "enable_sounds",
                False,
                acting_user=self.user_profile,
            )
        check_user_settings_update("events[0]", events[0])


class RealmPropertyActionTest(BaseAction):
    def do_set_realm_property_test(self, name: str) -> None:
        bool_tests: list[bool] = [True, False, True]
        test_values: dict[str, Any] = dict(
            default_language=["es", "de", "en"],
            welcome_message_custom_text=[
                "Welcome Bot Custom Message",
                "New Welcome Bot Custom Message",
            ],
            description=["Realm description", "New description"],
            digest_weekday=[0, 1, 2],
            message_edit_history_visibility_policy=Realm.MESSAGE_EDIT_HISTORY_VISIBILITY_POLICY_TYPES,
            message_retention_days=[10, 20],
            name=["Zulip", "New Name"],
            waiting_period_threshold=[1000, 2000],
            video_chat_provider=[
                Realm.VIDEO_CHAT_PROVIDERS["jitsi_meet"]["id"],
            ],
            jitsi_server_url=["https://jitsi1.example.com", "https://jitsi2.example.com", None],
            giphy_rating=[
                Realm.GIPHY_RATING_OPTIONS["disabled"]["id"],
            ],
            default_code_block_language=["python", "javascript"],
            message_content_delete_limit_seconds=[1000, 1100, 1200, None],
            message_content_edit_limit_seconds=[1000, 1100, 1200, None],
            move_messages_within_stream_limit_seconds=[1000, 1100, 1200, None],
            move_messages_between_streams_limit_seconds=[1000, 1100, 1200, None],
            topics_policy=Realm.REALM_TOPICS_POLICY_TYPES,
        )

        vals = test_values.get(name)
        property_type = Realm.property_types[name]
        if property_type is bool:
            vals = bool_tests

        if vals is None:
            raise AssertionError(f"No test created for {name}")
        now = timezone_now()
        original_val = getattr(self.user_profile.realm, name)

        do_set_realm_property(self.user_profile.realm, name, vals[0], acting_user=self.user_profile)

        if vals[0] != original_val and not (
            isinstance(vals[0], Enum) and vals[0].value == original_val
        ):
            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                ).count(),
                1,
            )
        for count, raw_value in enumerate(vals[1:]):
            now = timezone_now()
            state_change_expected = True
            num_events = 1
            raw_old_value = vals[count]

            if isinstance(raw_value, Enum):
                value = raw_value.value
                old_value = raw_old_value.value
            else:
                value = raw_value
                old_value = raw_old_value

            with self.verify_action(
                state_change_expected=state_change_expected, num_events=num_events
            ) as events:
                do_set_realm_property(
                    self.user_profile.realm,
                    name,
                    raw_value,
                    acting_user=self.user_profile,
                )

            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data={
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: value,
                        "property": name,
                    },
                ).count(),
                1,
            )

            if name in [
                "allow_message_editing",
                "message_content_edit_limit_seconds",
                "topics_policy",
            ]:
                check_realm_update_dict("events[0]", events[0])
            else:
                check_realm_update("events[0]", events[0], name)

    def do_test_allow_system_group(self, setting_name: str) -> None:
        all_system_user_groups = NamedUserGroup.objects.filter(
            realm_for_sharding=self.user_profile.realm,
            is_system_group=True,
        )

        setting_permission_configuration = Realm.REALM_PERMISSION_GROUP_SETTINGS[setting_name]

        default_group_name = setting_permission_configuration.default_group_name
        default_group = all_system_user_groups.get(name=default_group_name)
        old_group_id = default_group.id

        now = timezone_now()

        for user_group in all_system_user_groups:
            if user_group.name == default_group_name:
                continue

            if (
                not setting_permission_configuration.allow_internet_group
                and user_group.name == SystemGroups.EVERYONE_ON_INTERNET
            ):
                continue

            if (
                not setting_permission_configuration.allow_everyone_group
                and user_group.name == SystemGroups.EVERYONE
            ):
                continue

            if (
                not setting_permission_configuration.allow_nobody_group
                and user_group.name == SystemGroups.NOBODY
            ):
                continue

            now = timezone_now()
            state_change_expected = True
            num_events = 1
            new_group_id = user_group.id

            with self.verify_action(
                state_change_expected=state_change_expected, num_events=num_events
            ) as events:
                do_change_realm_permission_group_setting(
                    self.user_profile.realm,
                    setting_name,
                    user_group,
                    acting_user=self.user_profile,
                )

            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data={
                        RealmAuditLog.OLD_VALUE: old_group_id,
                        RealmAuditLog.NEW_VALUE: new_group_id,
                        "property": setting_name,
                    },
                ).count(),
                1,
            )
            check_realm_update_dict("events[0]", events[0])

            old_group_id = new_group_id

    def do_set_realm_permission_group_setting_to_anonymous_groups_test(
        self, setting_name: str
    ) -> None:
        realm = self.user_profile.realm
        system_user_groups_dict = get_role_based_system_groups_dict(
            realm,
        )

        setting_permission_configuration = Realm.REALM_PERMISSION_GROUP_SETTINGS[setting_name]

        default_group_name = setting_permission_configuration.default_group_name
        default_group = system_user_groups_dict[default_group_name]

        now = timezone_now()

        do_change_realm_permission_group_setting(
            realm,
            setting_name,
            default_group,
            acting_user=self.user_profile,
        )

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )

        othello = self.example_user("othello")
        admins_group = system_user_groups_dict[SystemGroups.ADMINISTRATORS]

        setting_group = self.create_or_update_anonymous_group_for_setting([othello], [admins_group])
        now = timezone_now()

        with self.verify_action(state_change_expected=True, num_events=1) as events:
            do_change_realm_permission_group_setting(
                realm,
                setting_name,
                setting_group,
                acting_user=self.user_profile,
            )

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
                extra_data={
                    RealmAuditLog.OLD_VALUE: default_group.id,
                    RealmAuditLog.NEW_VALUE: {
                        "direct_members": [othello.id],
                        "direct_subgroups": [admins_group.id],
                    },
                    "property": setting_name,
                },
            ).count(),
            1,
        )
        check_realm_update_dict("events[0]", events[0])
        self.assertEqual(
            events[0]["data"][setting_name],
            UserGroupMembersDict(direct_members=[othello.id], direct_subgroups=[admins_group.id]),
        )

        old_setting_api_value = get_group_setting_value_for_api(setting_group)
        moderators_group = system_user_groups_dict[SystemGroups.MODERATORS]
        setting_group = self.create_or_update_anonymous_group_for_setting(
            [self.user_profile], [moderators_group], existing_setting_group=setting_group
        )

        # state_change_expected is False here because the initial state will
        # also have the new setting value due to the setting group already
        # being modified with the new members.
        with self.verify_action(state_change_expected=False, num_events=1) as events:
            do_change_realm_permission_group_setting(
                realm,
                setting_name,
                setting_group,
                old_setting_api_value=old_setting_api_value,
                acting_user=self.user_profile,
            )

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
                extra_data={
                    RealmAuditLog.OLD_VALUE: {
                        "direct_members": [othello.id],
                        "direct_subgroups": [admins_group.id],
                    },
                    RealmAuditLog.NEW_VALUE: {
                        "direct_members": [self.user_profile.id],
                        "direct_subgroups": [moderators_group.id],
                    },
                    "property": setting_name,
                },
            ).count(),
            1,
        )
        check_realm_update_dict("events[0]", events[0])
        self.assertEqual(
            events[0]["data"][setting_name],
            UserGroupMembersDict(
                direct_members=[self.user_profile.id], direct_subgroups=[moderators_group.id]
            ),
        )

        with self.verify_action(state_change_expected=True, num_events=1) as events:
            do_change_realm_permission_group_setting(
                realm,
                setting_name,
                default_group,
                acting_user=self.user_profile,
            )

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
                extra_data={
                    RealmAuditLog.OLD_VALUE: {
                        "direct_members": [self.user_profile.id],
                        "direct_subgroups": [moderators_group.id],
                    },
                    RealmAuditLog.NEW_VALUE: default_group.id,
                    "property": setting_name,
                },
            ).count(),
            1,
        )
        check_realm_update_dict("events[0]", events[0])
        self.assertEqual(events[0]["data"][setting_name], default_group.id)

    def test_change_realm_property(self) -> None:
        for prop in Realm.property_types:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_property_test(prop)

        for prop in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_test_allow_system_group(prop)
            if Realm.REALM_PERMISSION_GROUP_SETTINGS[prop].require_system_group:
                # Anonymous system groups aren't relevant when
                # restricted to system groups.
                continue
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_permission_group_setting_to_anonymous_groups_test(prop)

    def do_set_realm_user_default_setting_test(self, name: str) -> None:
        bool_tests: list[bool] = [True, False, True]
        test_values: dict[str, Any] = dict(
            web_font_size_px=[UserProfile.WEB_FONT_SIZE_PX_COMPACT],
            web_line_height_percent=[UserProfile.WEB_LINE_HEIGHT_PERCENT_COMPACT],
            color_scheme=UserProfile.COLOR_SCHEME_CHOICES,
            web_home_view=["recent_topics", "inbox", "all_messages"],
            emojiset=[emojiset["key"] for emojiset in RealmUserDefault.emojiset_choices()],
            demote_inactive_streams=UserProfile.DEMOTE_STREAMS_CHOICES,
            web_mark_read_on_scroll_policy=UserProfile.WEB_MARK_READ_ON_SCROLL_POLICY_CHOICES,
            web_channel_default_view=UserProfile.WEB_CHANNEL_DEFAULT_VIEW_CHOICES,
            user_list_style=UserProfile.USER_LIST_STYLE_CHOICES,
            web_animate_image_previews=["always", "on_hover", "never"],
            web_stream_unreads_count_display_policy=UserProfile.WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_CHOICES,
            desktop_icon_count_display=UserProfile.DESKTOP_ICON_COUNT_DISPLAY_CHOICES,
            notification_sound=["zulip", "ding"],
            email_notifications_batching_period_seconds=[120, 300],
            email_address_visibility=UserProfile.EMAIL_ADDRESS_VISIBILITY_TYPES,
            realm_name_in_email_notifications_policy=UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_CHOICES,
            automatically_follow_topics_policy=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES,
            automatically_unmute_topics_in_muted_streams_policy=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES,
            resolved_topic_notice_auto_read_policy=UserProfile.RESOLVED_TOPIC_NOTICE_AUTO_READ_POLICY_TYPES,
        )

        vals = test_values.get(name)
        property_type = RealmUserDefault.property_types[name]

        if property_type is bool:
            vals = bool_tests

        if vals is None:
            raise AssertionError(f"No test created for {name}")

        realm_user_default = RealmUserDefault.objects.get(realm=self.user_profile.realm)
        now = timezone_now()
        do_set_realm_user_default_setting(
            realm_user_default, name, vals[0], acting_user=self.user_profile
        )
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=self.user_profile.realm,
                event_type=AuditLogEventType.REALM_DEFAULT_USER_SETTINGS_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )
        for count, val in enumerate(vals[1:]):
            now = timezone_now()
            state_change_expected = True
            with self.verify_action(state_change_expected=state_change_expected) as events:
                do_set_realm_user_default_setting(
                    realm_user_default,
                    name,
                    val,
                    acting_user=self.user_profile,
                )

            if isinstance(val, Enum):
                old_value = vals[count].value
                new_value = val.value
            else:
                old_value = vals[count]
                new_value = val
            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=AuditLogEventType.REALM_DEFAULT_USER_SETTINGS_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data={
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: new_value,
                        "property": name,
                    },
                ).count(),
                1,
            )
            check_realm_default_update("events[0]", events[0], name)

    def test_change_realm_user_default_setting(self) -> None:
        for prop in RealmUserDefault.property_types:
            if prop == "default_language":
                continue
            self.do_set_realm_user_default_setting_test(prop)

    def test_do_set_push_notifications_enabled_end_timestamp(self) -> None:
        realm = self.user_profile.realm

        # Default value of 'push_notifications_enabled_end_timestamp' is None.
        # Verify that no event is sent when the new value is the same as existing value.
        new_timestamp = None
        with self.verify_action(state_change_expected=False, num_events=0):
            do_set_push_notifications_enabled_end_timestamp(
                realm=realm,
                value=new_timestamp,
                acting_user=None,
            )

        old_datetime = timezone_now() - timedelta(days=3)
        old_timestamp = datetime_to_timestamp(old_datetime)
        now = timezone_now()
        timestamp_now = datetime_to_timestamp(now)

        realm.push_notifications_enabled_end_timestamp = old_datetime
        realm.save(update_fields=["push_notifications_enabled_end_timestamp"])

        with self.verify_action(
            state_change_expected=True,
            num_events=1,
        ) as events:
            do_set_push_notifications_enabled_end_timestamp(
                realm=realm,
                value=timestamp_now,
                acting_user=None,
            )
        self.assertEqual(events[0]["type"], "realm")
        self.assertEqual(events[0]["op"], "update")
        self.assertEqual(events[0]["property"], "push_notifications_enabled_end_timestamp")
        self.assertEqual(events[0]["value"], timestamp_now)

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=realm,
                event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
                acting_user=None,
                extra_data={
                    RealmAuditLog.OLD_VALUE: old_timestamp,
                    RealmAuditLog.NEW_VALUE: timestamp_now,
                    "property": "push_notifications_enabled_end_timestamp",
                },
            ).count(),
            1,
        )


class UserDisplayActionTest(BaseAction):
    def do_change_user_settings_test(self, setting_name: str) -> None:
        """Test updating each setting in UserProfile.property_types dict."""

        test_changes: dict[str, Any] = dict(
            emojiset=["twitter"],
            default_language=["es", "de", "en"],
            web_home_view=["all_messages", "inbox", "recent_topics"],
            demote_inactive_streams=[2, 3, 1],
            web_mark_read_on_scroll_policy=[2, 3, 1],
            web_channel_default_view=[2, 1, 3, 4],
            user_list_style=[1, 2, 3],
            web_animate_image_previews=["always", "on_hover", "never"],
            web_stream_unreads_count_display_policy=[1, 2, 3],
            web_font_size_px=[12, 16, 18],
            web_line_height_percent=[105, 120, 160],
            color_scheme=[2, 3, 1],
            email_address_visibility=[5, 4, 1, 2, 3],
            resolved_topic_notice_auto_read_policy=UserProfile.RESOLVED_TOPIC_NOTICE_AUTO_READ_POLICY_TYPES,
        )

        user_settings_object = True
        num_events = 1

        # Legacy display settings events have been removed, so all settings
        # now only send user_settings events

        values = test_changes.get(setting_name)

        property_type = UserProfile.property_types[setting_name]
        if property_type is bool:
            if getattr(self.user_profile, setting_name) is False:
                values = [True, False, True]
            else:
                values = [False, True, False]

        if values is None:
            raise AssertionError(f"No test created for {setting_name}")

        for value in values:
            if setting_name == "email_address_visibility":
                # When "email_address_visibility" setting is changed, there is at least
                # one event with type "user_settings" sent to the modified user itself.
                num_events = 1

                old_value = getattr(self.user_profile, setting_name)
                if UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE in [old_value, value]:
                    # In case when either the old value or new value of setting is
                    # UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE, "email" field of
                    # UserProfile object is updated and thus two additional events, for
                    # changing email and avatar_url field, are sent.
                    num_events = 3

            with self.verify_action(
                num_events=num_events, user_settings_object=user_settings_object
            ) as events:
                do_change_user_setting(
                    self.user_profile,
                    setting_name,
                    value,
                    acting_user=self.user_profile,
                )

            check_user_settings_update("events[0]", events[0])

    def test_change_user_settings(self) -> None:
        for prop in UserProfile.property_types:
            # Notification settings have a separate test suite, which
            # handles their separate legacy event type.
            if prop not in UserProfile.notification_setting_types:
                self.do_change_user_settings_test(prop)

    def test_set_allow_private_data_export(self) -> None:
        # Verify that both 'user_settings' and 'realm_export_consent' events
        # are received by admins when they change the setting.
        do_change_user_role(
            self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None
        )
        self.assertFalse(self.user_profile.allow_private_data_export)

        num_events = 2
        with self.verify_action(num_events=num_events) as events:
            do_change_user_setting(
                self.user_profile,
                "allow_private_data_export",
                True,
                acting_user=self.user_profile,
            )
        check_user_settings_update("events[0]", events[0])
        check_realm_export_consent("events[1]", events[1])

        # Verify that only 'realm_export_consent' event is received
        # by admins when an another user changes their setting.
        cordelia = self.example_user("cordelia")
        self.assertFalse(cordelia.allow_private_data_export)
        num_events = 1
        with self.verify_action(num_events=num_events, state_change_expected=False) as events:
            do_change_user_setting(
                cordelia,
                "allow_private_data_export",
                True,
                acting_user=cordelia,
            )
        check_realm_export_consent("events[0]", events[0])

    def test_set_user_timezone(self) -> None:
        values = ["America/Denver", "Pacific/Pago_Pago", "Pacific/Galapagos", ""]
        num_events = 2

        for value in values:
            with self.verify_action(num_events=num_events) as events:
                do_change_user_setting(
                    self.user_profile,
                    "timezone",
                    value,
                    acting_user=self.user_profile,
                )

            check_user_settings_update("events[0]", events[0])
            check_realm_user_update("events[1]", events[1], "timezone")

    def test_delivery_email_events_on_changing_email_address_visibility(self) -> None:
        cordelia = self.example_user("cordelia")
        do_change_user_role(self.user_profile, UserProfile.ROLE_MODERATOR, acting_user=None)
        do_change_user_setting(
            cordelia,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
            acting_user=None,
        )

        with self.verify_action(user_settings_object=True) as events:
            do_change_user_setting(
                cordelia,
                "email_address_visibility",
                UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
                acting_user=self.user_profile,
            )
        check_realm_user_update("events[0]", events[0], "delivery_email")
        self.assertIsNone(events[0]["person"]["delivery_email"])

        with self.verify_action(user_settings_object=True) as events:
            do_change_user_setting(
                cordelia,
                "email_address_visibility",
                UserProfile.EMAIL_ADDRESS_VISIBILITY_MODERATORS,
                acting_user=self.user_profile,
            )
        check_realm_user_update("events[0]", events[0], "delivery_email")
        self.assertEqual(events[0]["person"]["delivery_email"], cordelia.delivery_email)

    def test_stream_creation_events(self) -> None:
        with self.verify_action(num_events=2) as events:
            self.subscribe(self.example_user("hamlet"), "Test stream")
        check_stream_create("events[0]", events[0])
        check_subscription_add("events[1]", events[1])

        # Check that guest user does not receive stream creation event of public
        # stream.
        self.user_profile = self.example_user("polonius")
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            self.subscribe(self.example_user("hamlet"), "Test stream 2")

        # Check that guest user receives stream creation event for web-public stream.
        with self.verify_action(num_events=2, state_change_expected=True) as events:
            self.subscribe(
                self.example_user("hamlet"), "Web public test stream", is_web_public=True
            )
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])

        self.user_profile = self.example_user("hamlet")
        with self.verify_action(num_events=2) as events:
            self.subscribe(self.example_user("hamlet"), "Private test stream", invite_only=True)
        check_stream_create("events[0]", events[0])
        check_subscription_add("events[1]", events[1])

        # A non-admin user who is not subscribed to the private stream does not
        # receive stream creation event.
        self.user_profile = self.example_user("othello")
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            self.subscribe(self.example_user("hamlet"), "Private test stream 2", invite_only=True)

        # An admin user who is not subscribed to the private stream also
        # receives stream creation event.
        self.user_profile = self.example_user("iago")
        with self.verify_action(num_events=2) as events:
            self.subscribe(self.example_user("hamlet"), "Private test stream 3", invite_only=True)
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])


class SubscribeActionTest(BaseAction):
    def test_subscribe_events(self) -> None:
        self.do_test_subscribe_events(include_subscribers=True)

    def test_subscribe_events_no_include_subscribers(self) -> None:
        self.do_test_subscribe_events(include_subscribers=False)

    def do_test_subscribe_events(self, include_subscribers: bool) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        realm = othello.realm

        # Subscribe to a totally new stream, so it's just Hamlet on it
        with self.verify_action(
            event_types=["subscription"], include_subscribers=include_subscribers
        ) as events:
            self.subscribe(hamlet, "test_stream")
        check_subscription_add("events[0]", events[0])

        # Add another user to that totally new stream
        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            self.subscribe(othello, "test_stream")
        check_subscription_peer_add("events[0]", events[0])

        stream = get_stream("test_stream", self.user_profile.realm)

        # Now remove the first user, to test the normal unsubscribe flow and
        # 'peer_remove' event for subscribed streams.
        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            bulk_remove_subscriptions(realm, [othello], [stream], acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])

        # Now remove the user himself, to test the 'remove' event flow
        with self.verify_action(
            include_subscribers=include_subscribers, include_streams=False, num_events=1
        ) as events:
            bulk_remove_subscriptions(realm, [hamlet], [stream], acting_user=None)
        check_subscription_remove("events[0]", events[0])
        self.assert_length(events[0]["subscriptions"], 1)
        self.assertEqual(
            events[0]["subscriptions"][0]["name"],
            "test_stream",
        )

        # Subscribe other user to test 'peer_add' event flow for unsubscribed stream.
        with self.verify_action(
            event_types=["subscription"],
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers,
        ) as events:
            self.subscribe(self.example_user("iago"), "test_stream")
        check_subscription_peer_add("events[0]", events[0])

        # Remove the user to test 'peer_remove' event flow for unsubscribed stream.
        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            bulk_remove_subscriptions(realm, [iago], [stream], acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])

        # Now resubscribe a user, to make sure that works on a vacated stream
        with self.verify_action(
            include_subscribers=include_subscribers, include_streams=False, num_events=1
        ) as events:
            self.subscribe(self.example_user("hamlet"), "test_stream")
        check_subscription_add("events[0]", events[0])

        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_description(
                stream, "new description", acting_user=self.example_user("hamlet")
            )
        check_stream_update("events[0]", events[0])
        check_message("events[1]", events[1])

        channel_folder = check_add_channel_folder(realm, "Frontend", "", acting_user=iago)
        with self.verify_action(include_subscribers=include_subscribers) as events:
            do_change_stream_folder(stream, channel_folder, acting_user=iago)
        check_stream_update("events[0]", events[0])
        self.assertEqual(events[0]["property"], "folder_id")
        self.assertEqual(events[0]["value"], channel_folder.id)

        with self.verify_action(include_subscribers=include_subscribers) as events:
            do_change_stream_folder(stream, None, acting_user=iago)
        check_stream_update("events[0]", events[0])
        self.assertEqual(events[0]["property"], "folder_id")
        self.assertIsNone(events[0]["value"])

        # Update stream privacy - make stream web-public
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_permission(
                stream,
                invite_only=False,
                history_public_to_subscribers=True,
                is_web_public=True,
                acting_user=iago,
            )
        check_stream_update("events[0]", events[0])
        check_message("events[1]", events[1])

        # Update stream privacy - make stream private
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_permission(
                stream,
                invite_only=True,
                history_public_to_subscribers=True,
                is_web_public=False,
                acting_user=iago,
            )
        check_stream_update("events[0]", events[0])
        check_message("events[1]", events[1])

        # Update stream privacy - make stream public
        self.user_profile = self.example_user("cordelia")
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_permission(
                stream,
                invite_only=False,
                history_public_to_subscribers=True,
                is_web_public=False,
                acting_user=iago,
            )
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])

        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=iago,
        )
        self.subscribe(self.example_user("cordelia"), stream.name)
        self.unsubscribe(self.example_user("cordelia"), stream.name)
        with self.verify_action(
            include_subscribers=include_subscribers, num_events=2, include_streams=False
        ) as events:
            do_change_stream_permission(
                stream,
                invite_only=False,
                history_public_to_subscribers=True,
                is_web_public=False,
                acting_user=iago,
            )

        # Check updating description, stream permission for an unsubscribed streams.
        self.user_profile = self.example_user("hamlet")
        self.unsubscribe(self.example_user("hamlet"), stream.name)
        with self.verify_action(include_subscribers=include_subscribers, num_events=1) as events:
            do_change_stream_description(
                stream, "description", acting_user=self.example_user("hamlet")
            )
        check_stream_update("events[0]", events[0])

        with self.verify_action(include_subscribers=include_subscribers, num_events=1) as events:
            do_change_stream_permission(
                stream,
                invite_only=False,
                history_public_to_subscribers=True,
                is_web_public=True,
                acting_user=iago,
            )
        check_stream_update("events[0]", events[0])

        with self.verify_action(include_subscribers=include_subscribers, num_events=1) as events:
            do_change_stream_permission(
                stream,
                invite_only=True,
                history_public_to_subscribers=False,
                is_web_public=False,
                acting_user=iago,
            )
        check_stream_update("events[0]", events[0])

        # Subscribe the user again for further tests.
        self.subscribe(self.example_user("hamlet"), stream.name)

        self.user_profile = self.example_user("hamlet")
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_message_retention_days(stream, self.example_user("hamlet"), -1)
        check_stream_update("events[0]", events[0])

        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_set_stream_property(
                stream,
                "topics_policy",
                StreamTopicsPolicyEnum.allow_empty_topic.value,
                self.example_user("hamlet"),
            )
        check_stream_update("events[0]", events[0])

        for setting_name in Stream.stream_permission_group_settings:
            self.do_test_subscribe_events_for_stream_permission_group_setting(
                setting_name, stream, iago, include_subscribers
            )

        # Subscribe to a totally new invite-only stream, so it's just Hamlet on it
        stream = self.make_stream("private", self.user_profile.realm, invite_only=True)
        stream.message_retention_days = 10
        stream.save(update_fields=["message_retention_days"])

        user_profile = self.example_user("hamlet")
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            bulk_add_subscriptions(user_profile.realm, [stream], [user_profile], acting_user=None)
        check_stream_create("events[0]", events[0])
        check_subscription_add("events[1]", events[1])

        self.assertEqual(
            events[0]["streams"][0]["message_retention_days"],
            10,
        )
        self.assertIsNone(events[0]["streams"][0]["stream_weekly_traffic"])

        # Add this user to make sure the stream is not deleted on unsubscribing hamlet.
        self.subscribe(self.example_user("iago"), stream.name)

        # Unsubscribe from invite-only stream.
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            bulk_remove_subscriptions(realm, [hamlet], [stream], acting_user=None)
        check_subscription_remove("events[0]", events[0])
        check_stream_delete("events[1]", events[1])

        stream.invite_only = False
        stream.save(update_fields=["invite_only"])

        # Test events for guest user.
        self.user_profile = self.example_user("polonius")

        # Guest user does not receive peer_add/peer_remove events for unsubscribed
        # public streams.
        with self.verify_action(
            include_subscribers=include_subscribers, num_events=0, state_change_expected=False
        ) as events:
            bulk_add_subscriptions(
                user_profile.realm, [stream], [self.example_user("othello")], acting_user=None
            )

        with self.verify_action(
            include_subscribers=include_subscribers, num_events=0, state_change_expected=False
        ) as events:
            bulk_remove_subscriptions(
                user_profile.realm, [self.example_user("othello")], [stream], acting_user=None
            )

        # Subscribe as a guest to a public stream.
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            bulk_add_subscriptions(
                user_profile.realm, [stream], [self.user_profile], acting_user=None
            )
        check_stream_create("events[0]", events[0])
        check_subscription_add("events[1]", events[1])

        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            bulk_add_subscriptions(
                user_profile.realm, [stream], [self.example_user("othello")], acting_user=None
            )
        check_subscription_peer_add("events[0]", events[0])

        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            bulk_remove_subscriptions(
                user_profile.realm, [self.example_user("othello")], [stream], acting_user=None
            )
        check_subscription_peer_remove("events[0]", events[0])

        # Unsubscribe guest from public stream.
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            bulk_remove_subscriptions(realm, [self.user_profile], [stream], acting_user=None)
        check_subscription_remove("events[0]", events[0])
        check_stream_delete("events[1]", events[1])

        stream = self.make_stream("web-public-stream", self.user_profile.realm, is_web_public=True)
        # Guest user receives peer_add/peer_remove events for unsubscribed
        # web-public streams.
        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            bulk_add_subscriptions(
                user_profile.realm, [stream], [self.example_user("othello")], acting_user=None
            )

        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            bulk_remove_subscriptions(
                user_profile.realm, [self.example_user("othello")], [stream], acting_user=None
            )

        # Subscribe as a guest to web-public stream. Guest does not receive stream creation
        # event for web-public stream.
        with self.verify_action(include_subscribers=include_subscribers, num_events=1) as events:
            bulk_add_subscriptions(
                user_profile.realm, [stream], [self.user_profile], acting_user=None
            )
        check_subscription_add("events[0]", events[0])

        # Unsubscribe as a guest to web-public stream. Guest does not receive stream deletion
        # event for web-public stream.
        with self.verify_action(include_subscribers=include_subscribers, num_events=1) as events:
            bulk_remove_subscriptions(
                user_profile.realm, [self.user_profile], [stream], acting_user=None
            )
        check_subscription_remove("events[0]", events[0])

    def do_test_subscribe_events_for_stream_permission_group_setting(
        self, setting_name: str, stream: Stream, acting_user: UserProfile, include_subscribers: bool
    ) -> None:
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS,
            is_system_group=True,
            realm_for_sharding=self.user_profile.realm,
        )

        num_events = 1
        if setting_name == "can_send_message_group":
            # Updating "can_send_message_group" also sends events
            # for "stream_post_policy" and "is_announcement_value"
            # and an event for notification message.
            num_events = 4

        with self.verify_action(
            include_subscribers=include_subscribers, num_events=num_events
        ) as events:
            do_change_stream_group_based_setting(
                stream,
                setting_name,
                moderators_group,
                acting_user=acting_user,
            )
        check_stream_update("events[0]", events[0])
        self.assertEqual(events[0]["value"], moderators_group.id)

        if setting_name == "can_send_message_group":
            check_stream_update("events[1]", events[1])
            self.assertEqual(events[1]["property"], "stream_post_policy")
            self.assertEqual(events[1]["value"], Stream.STREAM_POST_POLICY_MODERATORS)

            check_stream_update("events[2]", events[2])
            self.assertEqual(events[2]["property"], "is_announcement_only")
            self.assertFalse(events[2]["value"])

            check_message("events[3]", events[3])

        setting_group_member_dict = UserGroupMembersData(
            direct_members=[self.user_profile.id],
            direct_subgroups=[moderators_group.id],
        )
        with self.verify_action(
            include_subscribers=include_subscribers, num_events=num_events
        ) as events:
            do_change_stream_group_based_setting(
                stream,
                setting_name,
                setting_group_member_dict,
                acting_user=acting_user,
            )
        check_stream_update("events[0]", events[0])
        self.assertEqual(
            events[0]["value"],
            UserGroupMembersDict(
                direct_members=[self.user_profile.id], direct_subgroups=[moderators_group.id]
            ),
        )

        if setting_name == "can_send_message_group":
            check_stream_update("events[1]", events[1])
            self.assertEqual(events[1]["property"], "stream_post_policy")
            self.assertEqual(events[1]["value"], Stream.STREAM_POST_POLICY_EVERYONE)

            check_stream_update("events[2]", events[2])
            self.assertEqual(events[2]["property"], "is_announcement_only")
            self.assertFalse(events[2]["value"])

            check_message("events[3]", events[3])

    def test_user_access_events_on_changing_subscriptions(self) -> None:
        self.set_up_db_for_testing_user_access()
        self.user_profile = self.example_user("polonius")
        realm = self.user_profile.realm
        stream = get_stream("test_stream1", realm)
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        with self.verify_action(num_events=2) as events:
            bulk_add_subscriptions(realm, [stream], [othello, iago], acting_user=None)
        check_realm_user_add("events[0]", events[0])
        self.assertEqual(events[0]["person"]["user_id"], othello.id)
        check_subscription_peer_add("events[1]", events[1])
        self.assertEqual(set(events[1]["user_ids"]), {iago.id, othello.id})

        with self.verify_action(num_events=2) as events:
            bulk_remove_subscriptions(realm, [othello, iago], [stream], acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])
        self.assertEqual(set(events[0]["user_ids"]), {iago.id, othello.id})
        check_realm_user_remove("events[1]", events[1])
        self.assertEqual(events[1]["person"]["user_id"], othello.id)

        # Check the state change works correctly when user_list_complete
        # is set to True.
        self.subscribe(othello, "test_stream1")
        with self.verify_action(num_events=2, user_list_incomplete=True) as events:
            bulk_remove_subscriptions(realm, [othello], [stream], acting_user=None)
        check_subscription_peer_remove("events[0]", events[0])
        self.assertEqual(set(events[0]["user_ids"]), {othello.id})
        check_realm_user_remove("events[1]", events[1])
        self.assertEqual(events[1]["person"]["user_id"], othello.id)

    def test_user_access_events_on_changing_subscriptions_for_guests(self) -> None:
        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")
        othello = self.example_user("othello")
        self.user_profile = polonius
        realm = self.user_profile.realm
        stream = self.subscribe(self.example_user("othello"), "new_stream")
        with self.verify_action(num_events=3) as events:
            bulk_add_subscriptions(
                realm, [stream], [polonius, self.example_user("iago")], acting_user=None
            )
        check_stream_create("events[0]", events[0])
        check_subscription_add("events[1]", events[1])
        check_realm_user_add("events[2]", events[2])
        self.assertEqual(events[2]["person"]["user_id"], othello.id)

        with self.verify_action(num_events=3) as events:
            bulk_remove_subscriptions(
                realm, [polonius, self.example_user("iago")], [stream], acting_user=None
            )
        check_subscription_remove("events[0]", events[0])
        check_stream_delete("events[1]", events[1])
        check_realm_user_remove("events[2]", events[2])
        self.assertEqual(events[2]["person"]["user_id"], othello.id)

        # Check the state change works correctly when user_list_complete
        # is set to True.
        stream = self.subscribe(self.example_user("othello"), "new_stream")
        self.subscribe(polonius, "new_stream")
        with self.verify_action(num_events=3, user_list_incomplete=True) as events:
            bulk_remove_subscriptions(realm, [polonius], [stream], acting_user=None)
        check_subscription_remove("events[0]", events[0])
        check_stream_delete("events[1]", events[1])
        check_realm_user_remove("events[2]", events[2])
        self.assertEqual(events[2]["person"]["user_id"], othello.id)


class DraftActionTest(BaseAction):
    def do_enable_drafts_synchronization(self, user_profile: UserProfile) -> None:
        do_change_user_setting(
            user_profile, "enable_drafts_synchronization", True, acting_user=self.user_profile
        )

    def test_draft_create_event(self) -> None:
        self.do_enable_drafts_synchronization(self.user_profile)
        dummy_draft = DraftData(
            type="",
            to=[],
            topic="",
            content="Sample draft content",
            timestamp=1596820995,
        )
        with self.verify_action() as events:
            do_create_drafts([dummy_draft], self.user_profile)
        check_draft_add("events[0]", events[0])

    def test_draft_edit_event(self) -> None:
        self.do_enable_drafts_synchronization(self.user_profile)
        dummy_draft = DraftData(
            type="",
            to=[],
            topic="",
            content="Sample draft content",
            timestamp=1596820995,
        )
        draft_id = do_create_drafts([dummy_draft], self.user_profile)[0].id
        dummy_draft.content = "Some more sample draft content"
        with self.verify_action() as events:
            do_edit_draft(draft_id, dummy_draft, self.user_profile)
        check_draft_update("events[0]", events[0])

    def test_draft_delete_event(self) -> None:
        self.do_enable_drafts_synchronization(self.user_profile)
        dummy_draft = DraftData(
            type="",
            to=[],
            topic="",
            content="Sample draft content",
            timestamp=1596820995,
        )
        draft_id = do_create_drafts([dummy_draft], self.user_profile)[0].id
        with self.verify_action() as events:
            do_delete_draft(draft_id, self.user_profile)
        check_draft_remove("events[0]", events[0])


class ScheduledMessagesEventsTest(BaseAction):
    def test_stream_scheduled_message_create_event(self) -> None:
        # Create stream scheduled message
        with self.verify_action() as events:
            check_schedule_message(
                self.user_profile,
                get_client("website"),
                "stream",
                [self.get_stream_id("Verona")],
                "Test topic",
                "Stream message",
                convert_to_UTC(dateparser("2023-04-19 18:24:56")),
                self.user_profile.realm,
            )
        check_scheduled_message_add("events[0]", events[0])

    def test_create_event_with_existing_scheduled_messages(self) -> None:
        # Create stream scheduled message
        check_schedule_message(
            self.user_profile,
            get_client("website"),
            "stream",
            [self.get_stream_id("Verona")],
            "Test topic",
            "Stream message 1",
            convert_to_UTC(dateparser("2023-04-19 17:24:56")),
            self.user_profile.realm,
        )

        # Check that the new scheduled message gets appended correctly.
        with self.verify_action() as events:
            check_schedule_message(
                self.user_profile,
                get_client("website"),
                "stream",
                [self.get_stream_id("Verona")],
                "Test topic",
                "Stream message 2",
                convert_to_UTC(dateparser("2023-04-19 18:24:56")),
                self.user_profile.realm,
            )
        check_scheduled_message_add("events[0]", events[0])

    def test_private_scheduled_message_create_event(self) -> None:
        # Create direct scheduled message
        with self.verify_action() as events:
            check_schedule_message(
                self.user_profile,
                get_client("website"),
                "private",
                [self.example_user("hamlet").id],
                None,
                "Direct message",
                convert_to_UTC(dateparser("2023-04-19 18:24:56")),
                self.user_profile.realm,
            )
        check_scheduled_message_add("events[0]", events[0])

    def test_scheduled_message_edit_event(self) -> None:
        scheduled_message_id = check_schedule_message(
            self.user_profile,
            get_client("website"),
            "stream",
            [self.get_stream_id("Verona")],
            "Test topic",
            "Stream message",
            convert_to_UTC(dateparser("2023-04-19 18:24:56")),
            self.user_profile.realm,
        )
        with self.verify_action() as events:
            edit_scheduled_message(
                self.user_profile,
                get_client("website"),
                scheduled_message_id,
                None,
                None,
                "Edited test topic",
                "Edited stream message",
                convert_to_UTC(dateparser("2023-04-20 18:24:56")),
                self.user_profile.realm,
            )
        check_scheduled_message_update("events[0]", events[0])

    def test_scheduled_message_delete_event(self) -> None:
        scheduled_message_id = check_schedule_message(
            self.user_profile,
            get_client("website"),
            "stream",
            [self.get_stream_id("Verona")],
            "Test topic",
            "Stream message",
            convert_to_UTC(dateparser("2023-04-19 18:24:56")),
            self.user_profile.realm,
        )
        with self.verify_action() as events:
            delete_scheduled_message(self.user_profile, scheduled_message_id)
        check_scheduled_message_remove("events[0]", events[0])


class ChannelFolderActionTest(BaseAction):
    def test_channel_folder_creation_event(self) -> None:
        folder_name = "Frontend"
        folder_description = "Channels for **frontend** discussions"
        with self.verify_action() as events:
            check_add_channel_folder(
                self.user_profile.realm,
                folder_name,
                folder_description,
                acting_user=self.user_profile,
            )
        check_channel_folder_add("events[0]", events[0])

    def test_channel_folder_update_event(self) -> None:
        channel_folder = check_add_channel_folder(
            self.user_profile.realm,
            "Frontend",
            "Channels for frontend discussion",
            acting_user=self.user_profile,
        )
        iago = self.example_user("iago")

        with self.verify_action() as events:
            do_change_channel_folder_name(channel_folder, "Web frontend", acting_user=iago)
        check_channel_folder_update("events[0]", events[0], {"name"})
        self.assertEqual(events[0]["channel_folder_id"], channel_folder.id)
        self.assertEqual(events[0]["data"]["name"], "Web frontend")

        with self.verify_action() as events:
            do_change_channel_folder_description(
                channel_folder, "Channels for **frontend** discussions", acting_user=iago
            )
        check_channel_folder_update("events[0]", events[0], {"description", "rendered_description"})
        self.assertEqual(events[0]["channel_folder_id"], channel_folder.id)
        self.assertEqual(events[0]["data"]["description"], "Channels for **frontend** discussions")
        self.assertEqual(
            events[0]["data"]["rendered_description"],
            "<p>Channels for <strong>frontend</strong> discussions</p>",
        )

        with self.verify_action() as events:
            do_archive_channel_folder(channel_folder, acting_user=iago)
        check_channel_folder_update("events[0]", events[0], {"is_archived"})
        self.assertEqual(events[0]["channel_folder_id"], channel_folder.id)
        self.assertTrue(events[0]["data"]["is_archived"])

        with self.verify_action() as events:
            do_unarchive_channel_folder(channel_folder, acting_user=iago)
        check_channel_folder_update("events[0]", events[0], {"is_archived"})
        self.assertEqual(events[0]["channel_folder_id"], channel_folder.id)
        self.assertFalse(events[0]["data"]["is_archived"])

    def test_channel_folders_reordering_event(self) -> None:
        frontend_folder = check_add_channel_folder(
            self.user_profile.realm,
            "Frontend",
            "Channels for frontend discussion",
            acting_user=self.user_profile,
        )
        backend_folder = check_add_channel_folder(
            self.user_profile.realm,
            "Backend",
            "Channels for backend discussion",
            acting_user=self.user_profile,
        )
        engineering_folder = check_add_channel_folder(
            self.user_profile.realm,
            "Engineering",
            "",
            acting_user=self.user_profile,
        )

        new_order = [backend_folder.id, engineering_folder.id, frontend_folder.id]
        with self.verify_action() as events:
            try_reorder_realm_channel_folders(self.user_profile.realm, new_order)

        check_channel_folder_reorder("events[0]", events[0])
        self.assertEqual(events[0]["order"], new_order)
