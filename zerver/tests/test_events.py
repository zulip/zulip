# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
#
# This module is closely integrated with zerver/lib/event_schema.py
# and zerver/lib/data_types.py systems for validating the schemas of
# events; it also uses the OpenAPI tools to validate our documentation.
import copy
import time
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Set
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from zerver.actions.alert_words import do_add_alert_words, do_remove_alert_words
from zerver.actions.bots import (
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
)
from zerver.actions.create_user import do_create_user, do_reactivate_user
from zerver.actions.custom_profile_fields import (
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
from zerver.actions.hotspots import do_mark_hotspot_as_read
from zerver.actions.invites import (
    do_create_multiuse_invite_link,
    do_invite_users,
    do_revoke_multi_use_invite,
    do_revoke_user_invite,
)
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import do_update_embedded_data, do_update_message
from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.muted_users import do_mute_user, do_unmute_user
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
    do_add_linkifier,
    do_remove_linkifier,
    do_update_linkifier,
)
from zerver.actions.realm_logo import do_change_logo_source
from zerver.actions.realm_playgrounds import do_add_realm_playground, do_remove_realm_playground
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_change_realm_plan_type,
    do_deactivate_realm,
    do_set_realm_authentication_methods,
    do_set_realm_notifications_stream,
    do_set_realm_property,
    do_set_realm_signup_notifications_stream,
    do_set_realm_user_default_setting,
)
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_can_remove_subscribers_group,
    do_change_stream_description,
    do_change_stream_message_retention_days,
    do_change_stream_permission,
    do_change_stream_post_policy,
    do_change_subscription_property,
    do_deactivate_stream,
    do_rename_stream,
)
from zerver.actions.submessage import do_add_submessage
from zerver.actions.typing import check_send_typing_notification, do_send_stream_typing_notification
from zerver.actions.user_groups import (
    add_subgroups_to_user_group,
    bulk_add_members_to_user_group,
    check_add_user_group,
    check_delete_user_group,
    do_update_user_group_description,
    do_update_user_group_name,
    remove_members_from_user_group,
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
from zerver.actions.user_topics import do_mute_topic, do_unmute_topic
from zerver.actions.users import (
    do_change_user_role,
    do_deactivate_user,
    do_make_user_billing_admin,
    do_update_outgoing_webhook_service,
)
from zerver.actions.video_calls import do_set_zoom_token
from zerver.lib.drafts import do_create_drafts, do_delete_draft, do_edit_draft
from zerver.lib.event_schema import (
    check_alert_words,
    check_attachment_add,
    check_attachment_remove,
    check_attachment_update,
    check_custom_profile_fields,
    check_default_stream_groups,
    check_default_streams,
    check_delete_message,
    check_has_zoom_token,
    check_heartbeat,
    check_hotspots,
    check_invites_changed,
    check_message,
    check_muted_topics,
    check_muted_users,
    check_presence,
    check_reaction_add,
    check_reaction_remove,
    check_realm_bot_add,
    check_realm_bot_delete,
    check_realm_bot_remove,
    check_realm_bot_update,
    check_realm_deactivated,
    check_realm_default_update,
    check_realm_domains_add,
    check_realm_domains_change,
    check_realm_domains_remove,
    check_realm_emoji_update,
    check_realm_export,
    check_realm_filters,
    check_realm_linkifiers,
    check_realm_playgrounds,
    check_realm_update,
    check_realm_update_dict,
    check_realm_user_add,
    check_realm_user_remove,
    check_realm_user_update,
    check_stream_create,
    check_stream_delete,
    check_stream_update,
    check_submessage,
    check_subscription_add,
    check_subscription_peer_add,
    check_subscription_peer_remove,
    check_subscription_remove,
    check_subscription_update,
    check_typing_start,
    check_typing_stop,
    check_update_display_settings,
    check_update_global_notifications,
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
from zerver.lib.events import (
    RestartEventError,
    apply_events,
    fetch_initial_state_data,
    post_process_state,
)
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.message import render_markdown
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_dummy_file,
    get_subscription,
    get_test_image_file,
    reset_emails_in_zulip_realm,
    stdout_suppressed,
)
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.types import ProfileDataElementUpdateDict
from zerver.lib.user_groups import create_user_group
from zerver.lib.user_mutes import get_mute_object
from zerver.models import (
    Attachment,
    CustomProfileField,
    Message,
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmPlayground,
    RealmUserDefault,
    Service,
    Stream,
    UserGroup,
    UserMessage,
    UserPresence,
    UserProfile,
    UserStatus,
    get_client,
    get_stream,
    get_user_by_delivery_email,
)
from zerver.openapi.openapi import validate_against_openapi_schema
from zerver.tornado.django_api import send_event
from zerver.tornado.event_queue import (
    allocate_client_descriptor,
    clear_client_event_queues_for_testing,
    create_heartbeat_event,
    send_restart_events,
)
from zerver.views.realm_playgrounds import access_playground_by_id


class BaseAction(ZulipTestCase):
    """Core class for verifying the apply_event race handling logic as
    well as the event formatting logic of any function using send_event.

    See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html#testing
    for extensive design details for this testing system.
    """

    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")

    def verify_action(
        self,
        action: Callable[[], object],
        *,
        event_types: Optional[List[str]] = None,
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
    ) -> List[Dict[str, Any]]:
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
            )
        )

        # hybrid_state = initial fetch state + re-applying events triggered by our action
        # normal_state = do action then fetch at the end (the "normal" code path)
        hybrid_state = fetch_initial_state_data(
            self.user_profile,
            event_types=event_types,
            client_gravatar=client_gravatar,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
            include_streams=include_streams,
            pronouns_field_type_supported=pronouns_field_type_supported,
        )

        # We want even those `send_event` calls which have been hooked to
        # `transaction.on_commit` to execute in tests.
        # See the comment in `ZulipTestCase.tornado_redirected_to_list`.
        with self.captureOnCommitCallbacks(execute=True):
            action()

        events = client.event_queue.contents()
        content = {
            "queue_id": "123.12",
            # The JSON wrapper helps in converting tuples to lists
            # as tuples aren't valid JSON structure.
            "events": orjson.loads(orjson.dumps(events)),
            "msg": "",
            "result": "success",
        }
        validate_against_openapi_schema(content, "/events", "get", "200", display_brief_error=True)
        self.assert_length(events, num_events)
        initial_state = copy.deepcopy(hybrid_state)
        post_process_state(self.user_profile, initial_state, notification_settings_null)
        before = orjson.dumps(initial_state)
        apply_events(
            self.user_profile,
            state=hybrid_state,
            events=events,
            fetch_event_types=None,
            client_gravatar=client_gravatar,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
        )
        post_process_state(self.user_profile, hybrid_state, notification_settings_null)
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
            event_types=event_types,
            client_gravatar=client_gravatar,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
            include_streams=include_streams,
            pronouns_field_type_supported=pronouns_field_type_supported,
        )
        post_process_state(self.user_profile, normal_state, notification_settings_null)
        self.match_states(hybrid_state, normal_state, events)
        return events

    def match_states(
        self, state1: Dict[str, Any], state2: Dict[str, Any], events: List[Dict[str, Any]]
    ) -> None:
        def normalize(state: Dict[str, Any]) -> None:
            if "never_subscribed" in state:
                for u in state["never_subscribed"]:
                    if "subscribers" in u:
                        u["subscribers"].sort()
            if "subscriptions" in state:
                for u in state["subscriptions"]:
                    if "subscribers" in u:
                        u["subscribers"].sort()
                state["subscriptions"] = {u["name"]: u for u in state["subscriptions"]}
            if "unsubscribed" in state:
                state["unsubscribed"] = {u["name"]: u for u in state["unsubscribed"]}
            if "realm_bots" in state:
                state["realm_bots"] = {u["email"]: u for u in state["realm_bots"]}
            # Since time is different for every call, just fix the value
            state["server_timestamp"] = 0

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
            for k in state1:
                if state1[k] != state2[k]:
                    print("\nkey = " + k)
                    try:
                        self.assertEqual({k: state1[k]}, {k: state2[k]})
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
            self.verify_action(
                lambda: self.send_stream_message(self.example_user("cordelia"), "Verona", content),
            )

    def test_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = "mentioning... @**all** hello " + str(i)
            self.verify_action(
                lambda: self.send_stream_message(self.example_user("cordelia"), "Verona", content),
            )

    def test_pm_send_message_events(self) -> None:
        self.verify_action(
            lambda: self.send_personal_message(
                self.example_user("cordelia"), self.example_user("hamlet"), "hola"
            ),
        )

        # Verify private message editing - content only edit
        pm = Message.objects.order_by("-id")[0]
        content = "new content"
        rendering_result = render_markdown(pm, content)
        prior_mention_user_ids: Set[int] = set()
        mention_backend = MentionBackend(self.user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
        )

        events = self.verify_action(
            lambda: do_update_message(
                self.user_profile,
                pm,
                None,
                None,
                None,
                False,
                False,
                content,
                rendering_result,
                prior_mention_user_ids,
                mention_data,
            ),
            state_change_expected=False,
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

    def test_huddle_send_message_events(self) -> None:
        huddle = [
            self.example_user("hamlet"),
            self.example_user("othello"),
        ]
        self.verify_action(
            lambda: self.send_huddle_message(self.example_user("cordelia"), huddle, "hola"),
        )

    def test_stream_send_message_events(self) -> None:
        events = self.verify_action(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Verona", "hello"),
            client_gravatar=False,
        )
        check_message("events[0]", events[0])
        assert isinstance(events[0]["message"]["avatar_url"], str)

        events = self.verify_action(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Verona", "hello"),
            client_gravatar=True,
        )
        check_message("events[0]", events[0])
        assert events[0]["message"]["avatar_url"] is None

        # Verify stream message editing - content only
        message = Message.objects.order_by("-id")[0]
        content = "new content"
        rendering_result = render_markdown(message, content)
        prior_mention_user_ids: Set[int] = set()
        mention_backend = MentionBackend(self.user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
        )

        events = self.verify_action(
            lambda: do_update_message(
                self.user_profile,
                message,
                None,
                None,
                None,
                False,
                False,
                content,
                rendering_result,
                prior_mention_user_ids,
                mention_data,
            ),
            state_change_expected=False,
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
        topic = "new_topic"
        propagate_mode = "change_all"

        events = self.verify_action(
            lambda: do_update_message(
                self.user_profile,
                message,
                None,
                topic,
                propagate_mode,
                False,
                False,
                None,
                None,
                prior_mention_user_ids,
                mention_data,
            ),
            state_change_expected=True,
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
        rendering_result = render_markdown(message, content)
        events = self.verify_action(
            lambda: do_update_embedded_data(self.user_profile, message, content, rendering_result),
            state_change_expected=False,
        )
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

        # Send 2 messages in "test" topic.
        self.send_stream_message(self.user_profile, "Verona")
        message_id = self.send_stream_message(self.user_profile, "Verona")
        message = Message.objects.get(id=message_id)
        stream = get_stream("Denmark", self.user_profile.realm)
        propagate_mode = "change_all"
        prior_mention_user_ids = set()

        events = self.verify_action(
            lambda: do_update_message(
                self.user_profile,
                message,
                stream,
                None,
                propagate_mode,
                True,
                True,
                None,
                None,
                set(),
                None,
            ),
            state_change_expected=True,
            # There are 3 events generated for this action
            # * update_message: For updating existing messages
            # * 2 new message events: Breadcrumb messages in the new and old topics.
            num_events=3,
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

    def test_update_message_flags(self) -> None:
        # Test message flag update events
        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )
        user_profile = self.example_user("hamlet")
        events = self.verify_action(
            lambda: do_update_message_flags(user_profile, "add", "starred", [message]),
            state_change_expected=True,
        )
        check_update_message_flags_add("events[0]", events[0])

        events = self.verify_action(
            lambda: do_update_message_flags(user_profile, "remove", "starred", [message]),
            state_change_expected=True,
        )
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

            self.verify_action(
                lambda: do_update_message_flags(user_profile, "add", "read", [message]),
                state_change_expected=True,
            )

            events = self.verify_action(
                lambda: do_update_message_flags(user_profile, "remove", "read", [message]),
                state_change_expected=True,
            )
            check_update_message_flags_remove("events[0]", events[0])

            personal_message = self.send_personal_message(
                from_user=user_profile, to_user=self.example_user("cordelia"), content=content
            )
            self.verify_action(
                lambda: do_update_message_flags(user_profile, "add", "read", [personal_message]),
                state_change_expected=True,
            )

            events = self.verify_action(
                lambda: do_update_message_flags(user_profile, "remove", "read", [personal_message]),
                state_change_expected=True,
            )
            check_update_message_flags_remove("events[0]", events[0])

            huddle_message = self.send_huddle_message(
                from_user=self.example_user("cordelia"),
                to_users=[user_profile, self.example_user("othello")],
                content=content,
            )

            self.verify_action(
                lambda: do_update_message_flags(user_profile, "add", "read", [huddle_message]),
                state_change_expected=True,
            )

            events = self.verify_action(
                lambda: do_update_message_flags(user_profile, "remove", "read", [huddle_message]),
                state_change_expected=True,
            )
            check_update_message_flags_remove("events[0]", events[0])

    def test_send_message_to_existing_recipient(self) -> None:
        sender = self.example_user("cordelia")
        self.send_stream_message(
            sender,
            "Verona",
            "hello 1",
        )
        self.verify_action(
            lambda: self.send_stream_message(sender, "Verona", "hello 2"),
            state_change_expected=True,
        )

    def test_add_reaction(self) -> None:
        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        events = self.verify_action(
            lambda: do_add_reaction(self.user_profile, message, "tada", "1f389", "unicode_emoji"),
            state_change_expected=False,
        )
        check_reaction_add("events[0]", events[0])

    def test_heartbeat_event(self) -> None:
        events = self.verify_action(
            lambda: send_event(
                self.user_profile.realm,
                create_heartbeat_event(),
                [self.user_profile.id],
            ),
            state_change_expected=False,
        )
        check_heartbeat("events[0]", events[0])

    def test_add_submessage(self) -> None:
        cordelia = self.example_user("cordelia")
        stream_name = "Verona"
        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )
        events = self.verify_action(
            lambda: do_add_submessage(
                realm=cordelia.realm,
                sender_id=cordelia.id,
                message_id=message_id,
                msg_type="whatever",
                content='"stuff"',
            ),
            state_change_expected=False,
        )
        check_submessage("events[0]", events[0])

    def test_remove_reaction(self) -> None:
        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        do_add_reaction(self.user_profile, message, "tada", "1f389", "unicode_emoji")
        events = self.verify_action(
            lambda: do_remove_reaction(self.user_profile, message, "1f389", "unicode_emoji"),
            state_change_expected=False,
        )
        check_reaction_remove("events[0]", events[0])

    def test_invite_user_event(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        invite_expires_in_minutes = 2 * 24 * 60
        events = self.verify_action(
            lambda: do_invite_users(
                self.user_profile,
                ["foo@zulip.com"],
                streams,
                invite_expires_in_minutes=invite_expires_in_minutes,
            ),
            state_change_expected=False,
        )
        check_invites_changed("events[0]", events[0])

    def test_create_multiuse_invite_event(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        invite_expires_in_minutes = 2 * 24 * 60
        events = self.verify_action(
            lambda: do_create_multiuse_invite_link(
                self.user_profile,
                PreregistrationUser.INVITE_AS["MEMBER"],
                invite_expires_in_minutes,
                streams,
            ),
            state_change_expected=False,
        )
        check_invites_changed("events[0]", events[0])

    def test_deactivate_user_invites_changed_event(self) -> None:
        self.user_profile = self.example_user("iago")
        user_profile = self.example_user("cordelia")
        invite_expires_in_minutes = 2 * 24 * 60
        do_invite_users(
            user_profile,
            ["foo@zulip.com"],
            [],
            invite_expires_in_minutes=invite_expires_in_minutes,
        )

        events = self.verify_action(
            lambda: do_deactivate_user(user_profile, acting_user=None), num_events=2
        )
        check_invites_changed("events[0]", events[0])

    def test_revoke_user_invite_event(self) -> None:
        # We need set self.user_profile to be an admin, so that
        # we receive the invites_changed event.
        self.user_profile = self.example_user("iago")
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        invite_expires_in_minutes = 2 * 24 * 60
        do_invite_users(
            self.user_profile,
            ["foo@zulip.com"],
            streams,
            invite_expires_in_minutes=invite_expires_in_minutes,
        )
        prereg_users = PreregistrationUser.objects.filter(
            referred_by__realm=self.user_profile.realm
        )
        events = self.verify_action(
            lambda: do_revoke_user_invite(prereg_users[0]),
            state_change_expected=False,
        )
        check_invites_changed("events[0]", events[0])

    def test_revoke_multiuse_invite_event(self) -> None:
        self.user_profile = self.example_user("iago")
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        invite_expires_in_minutes = 2 * 24 * 60
        do_create_multiuse_invite_link(
            self.user_profile,
            PreregistrationUser.INVITE_AS["MEMBER"],
            invite_expires_in_minutes,
            streams,
        )

        multiuse_object = MultiuseInvite.objects.get()
        events = self.verify_action(
            lambda: do_revoke_multi_use_invite(multiuse_object),
            state_change_expected=False,
        )
        check_invites_changed("events[0]", events[0])

    def test_invitation_accept_invite_event(self) -> None:
        reset_emails_in_zulip_realm()

        self.user_profile = self.example_user("iago")
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        invite_expires_in_minutes = 2 * 24 * 60
        do_invite_users(
            self.user_profile,
            ["foo@zulip.com"],
            streams,
            invite_expires_in_minutes=invite_expires_in_minutes,
        )
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")

        events = self.verify_action(
            lambda: do_create_user(
                "foo@zulip.com",
                "password",
                self.user_profile.realm,
                "full name",
                prereg_user=prereg_user,
                acting_user=None,
            ),
            state_change_expected=True,
            num_events=7,
        )

        check_invites_changed("events[3]", events[3])

    def test_typing_events(self) -> None:
        events = self.verify_action(
            lambda: check_send_typing_notification(
                self.user_profile, [self.example_user("cordelia").id], "start"
            ),
            state_change_expected=False,
        )
        check_typing_start("events[0]", events[0])
        events = self.verify_action(
            lambda: check_send_typing_notification(
                self.user_profile, [self.example_user("cordelia").id], "stop"
            ),
            state_change_expected=False,
        )
        check_typing_stop("events[0]", events[0])

    def test_stream_typing_events(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        topic = "streams typing"

        events = self.verify_action(
            lambda: do_send_stream_typing_notification(
                self.user_profile,
                "start",
                stream,
                topic,
            ),
            state_change_expected=False,
        )
        check_typing_start("events[0]", events[0])

        events = self.verify_action(
            lambda: do_send_stream_typing_notification(
                self.user_profile,
                "stop",
                stream,
                topic,
            ),
            state_change_expected=False,
        )
        check_typing_stop("events[0]", events[0])

        # Having client_capability `stream_typing_notification=False`
        # shouldn't produce any events.
        events = self.verify_action(
            lambda: do_send_stream_typing_notification(
                self.user_profile,
                "start",
                stream,
                topic,
            ),
            state_change_expected=False,
            stream_typing_notifications=False,
            num_events=0,
        )
        self.assertEqual(events, [])

        events = self.verify_action(
            lambda: do_send_stream_typing_notification(
                self.user_profile,
                "stop",
                stream,
                topic,
            ),
            state_change_expected=False,
            stream_typing_notifications=False,
            num_events=0,
        )
        self.assertEqual(events, [])

    def test_custom_profile_fields_events(self) -> None:
        realm = self.user_profile.realm

        events = self.verify_action(
            lambda: try_add_realm_custom_profile_field(
                realm=realm, name="Expertise", field_type=CustomProfileField.LONG_TEXT
            )
        )
        check_custom_profile_fields("events[0]", events[0])

        field = realm.customprofilefield_set.get(realm=realm, name="Biography")
        name = field.name
        hint = "Biography of the user"
        display_in_profile_summary = False

        events = self.verify_action(
            lambda: try_update_realm_custom_profile_field(
                realm, field, name, hint=hint, display_in_profile_summary=display_in_profile_summary
            )
        )
        check_custom_profile_fields("events[0]", events[0])

        events = self.verify_action(lambda: do_remove_realm_custom_profile_field(realm, field))
        check_custom_profile_fields("events[0]", events[0])

    def test_pronouns_type_support_in_custom_profile_fields_events(self) -> None:
        realm = self.user_profile.realm
        field = CustomProfileField.objects.get(realm=realm, name="Pronouns")
        name = field.name
        hint = "What pronouns should people use for you?"

        events = self.verify_action(
            lambda: try_update_realm_custom_profile_field(realm, field, name, hint=hint),
            pronouns_field_type_supported=True,
        )
        check_custom_profile_fields("events[0]", events[0])
        pronouns_field = [
            field_obj for field_obj in events[0]["fields"] if field_obj["id"] == field.id
        ][0]
        self.assertEqual(pronouns_field["type"], CustomProfileField.PRONOUNS)

        hint = "What pronouns should people use to refer you?"
        events = self.verify_action(
            lambda: try_update_realm_custom_profile_field(realm, field, name, hint=hint),
            pronouns_field_type_supported=False,
        )
        check_custom_profile_fields("events[0]", events[0])
        pronouns_field = [
            field_obj for field_obj in events[0]["fields"] if field_obj["id"] == field.id
        ][0]
        self.assertEqual(pronouns_field["type"], CustomProfileField.SHORT_TEXT)

    def test_custom_profile_field_data_events(self) -> None:
        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name="Biography"
        ).id
        field: ProfileDataElementUpdateDict = {
            "id": field_id,
            "value": "New value",
        }
        events = self.verify_action(
            lambda: do_update_user_custom_profile_data_if_changed(self.user_profile, [field])
        )
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
        events = self.verify_action(
            lambda: do_update_user_custom_profile_data_if_changed(self.user_profile, [field])
        )
        check_realm_user_update("events[0]", events[0], "custom_profile_field")
        self.assertEqual(events[0]["person"]["custom_profile_field"].keys(), {"id", "value"})

    def test_presence_events(self) -> None:
        events = self.verify_action(
            lambda: do_update_user_presence(
                self.user_profile, get_client("website"), timezone_now(), UserPresence.ACTIVE
            ),
            slim_presence=False,
        )

        check_presence(
            "events[0]",
            events[0],
            has_email=True,
            presence_key="website",
            status="active",
        )

        events = self.verify_action(
            lambda: do_update_user_presence(
                self.example_user("cordelia"),
                get_client("website"),
                timezone_now(),
                UserPresence.ACTIVE,
            ),
            slim_presence=True,
        )

        check_presence(
            "events[0]",
            events[0],
            has_email=False,
            presence_key="website",
            status="active",
        )

    def test_presence_events_multiple_clients(self) -> None:
        self.api_post(
            self.user_profile,
            "/api/v1/users/me/presence",
            {"status": "idle"},
            HTTP_USER_AGENT="ZulipAndroid/1.0",
        )
        self.verify_action(
            lambda: do_update_user_presence(
                self.user_profile, get_client("website"), timezone_now(), UserPresence.ACTIVE
            )
        )
        events = self.verify_action(
            lambda: do_update_user_presence(
                self.user_profile, get_client("ZulipAndroid/1.0"), timezone_now(), UserPresence.IDLE
            )
        )

        check_presence(
            "events[0]",
            events[0],
            has_email=True,
            presence_key="ZulipAndroid/1.0",
            status="idle",
        )

    def test_register_events(self) -> None:
        events = self.verify_action(lambda: self.register("test1@zulip.com", "test1"), num_events=5)
        self.assert_length(events, 5)

        check_realm_user_add("events[0]", events[0])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.delivery_email, "test1@zulip.com")

        check_subscription_peer_add("events[1]", events[1])

        check_message("events[2]", events[2])
        self.assertIn(
            f'data-user-id="{new_user_profile.id}">test1_zulip.com</span> just signed up for Zulip',
            events[2]["message"]["content"],
        )

        check_user_group_add_members("events[3]", events[3])
        check_user_group_add_members("events[4]", events[4])

    def test_register_events_email_address_visibility(self) -> None:
        do_set_realm_property(
            self.user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )

        events = self.verify_action(lambda: self.register("test1@zulip.com", "test1"), num_events=5)
        self.assert_length(events, 5)
        check_realm_user_add("events[0]", events[0])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.email, f"user{new_user_profile.id}@zulip.testserver")

        check_subscription_peer_add("events[1]", events[1])

        check_message("events[2]", events[2])
        self.assertIn(
            f'data-user-id="{new_user_profile.id}">test1_zulip.com</span> just signed up for Zulip',
            events[2]["message"]["content"],
        )

        check_user_group_add_members("events[3]", events[3])
        check_user_group_add_members("events[4]", events[4])

    def test_alert_words_events(self) -> None:
        events = self.verify_action(lambda: do_add_alert_words(self.user_profile, ["alert_word"]))
        check_alert_words("events[0]", events[0])

        events = self.verify_action(
            lambda: do_remove_alert_words(self.user_profile, ["alert_word"])
        )
        check_alert_words("events[0]", events[0])

    def test_away_events(self) -> None:
        client = get_client("website")

        # Set all
        away_val = True
        events = self.verify_action(
            lambda: do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
            ),
            num_events=4,
        )

        check_user_status(
            "events[0]",
            events[0],
            {"away", "status_text", "emoji_name", "emoji_code", "reaction_type"},
        )
        check_user_settings_update("events[1]", events[1])
        check_update_global_notifications("events[2]", events[2], not away_val)
        check_presence(
            "events[3]",
            events[3],
            has_email=True,
            presence_key="website",
            status="active" if not away_val else "idle",
        )

        # Remove all
        away_val = False
        events = self.verify_action(
            lambda: do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text="",
                emoji_name="",
                emoji_code="",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
            ),
            num_events=4,
        )

        check_user_status(
            "events[0]",
            events[0],
            {"away", "status_text", "emoji_name", "emoji_code", "reaction_type"},
        )
        check_user_settings_update("events[1]", events[1])
        check_update_global_notifications("events[2]", events[2], not away_val)
        check_presence(
            "events[3]",
            events[3],
            has_email=True,
            presence_key="website",
            status="active" if not away_val else "idle",
        )

        # Only set away
        away_val = True
        events = self.verify_action(
            lambda: do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text=None,
                emoji_name=None,
                emoji_code=None,
                reaction_type=None,
                client_id=client.id,
            ),
            num_events=4,
        )

        check_user_status("events[0]", events[0], {"away"})
        check_user_settings_update("events[1]", events[1])
        check_update_global_notifications("events[2]", events[2], not away_val)
        check_presence(
            "events[3]",
            events[3],
            has_email=True,
            presence_key="website",
            status="active" if not away_val else "idle",
        )

        # Only set status_text
        events = self.verify_action(
            lambda: do_update_user_status(
                user_profile=self.user_profile,
                away=None,
                status_text="at the beach",
                emoji_name=None,
                emoji_code=None,
                reaction_type=None,
                client_id=client.id,
            )
        )

        check_user_status("events[0]", events[0], {"status_text"})

    def test_user_group_events(self) -> None:
        othello = self.example_user("othello")
        events = self.verify_action(
            lambda: check_add_user_group(
                self.user_profile.realm, "backend", [othello], "Backend team"
            )
        )
        check_user_group_add("events[0]", events[0])

        # Test name update
        backend = UserGroup.objects.get(name="backend")
        events = self.verify_action(lambda: do_update_user_group_name(backend, "backendteam"))
        check_user_group_update("events[0]", events[0], "name")

        # Test description update
        description = "Backend team to deal with backend code."
        events = self.verify_action(lambda: do_update_user_group_description(backend, description))
        check_user_group_update("events[0]", events[0], "description")

        # Test add members
        hamlet = self.example_user("hamlet")
        events = self.verify_action(lambda: bulk_add_members_to_user_group(backend, [hamlet.id]))
        check_user_group_add_members("events[0]", events[0])

        # Test remove members
        hamlet = self.example_user("hamlet")
        events = self.verify_action(lambda: remove_members_from_user_group(backend, [hamlet.id]))
        check_user_group_remove_members("events[0]", events[0])

        api_design = create_user_group(
            "api-design", [hamlet], hamlet.realm, description="API design team"
        )

        # Test add subgroups
        events = self.verify_action(lambda: add_subgroups_to_user_group(backend, [api_design]))
        check_user_group_add_subgroups("events[0]", events[0])

        # Test remove subgroups
        events = self.verify_action(lambda: remove_subgroups_from_user_group(backend, [api_design]))
        check_user_group_remove_subgroups("events[0]", events[0])

        # Test remove event
        events = self.verify_action(lambda: check_delete_user_group(backend.id, othello))
        check_user_group_remove("events[0]", events[0])

    def test_default_stream_groups_events(self) -> None:
        streams = []
        for stream_name in ["Scotland", "Rome", "Denmark"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        events = self.verify_action(
            lambda: do_create_default_stream_group(
                self.user_profile.realm, "group1", "This is group1", streams
            )
        )
        check_default_stream_groups("events[0]", events[0])

        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]
        venice_stream = get_stream("Venice", self.user_profile.realm)
        events = self.verify_action(
            lambda: do_add_streams_to_default_stream_group(
                self.user_profile.realm, group, [venice_stream]
            )
        )
        check_default_stream_groups("events[0]", events[0])

        events = self.verify_action(
            lambda: do_remove_streams_from_default_stream_group(
                self.user_profile.realm, group, [venice_stream]
            )
        )
        check_default_stream_groups("events[0]", events[0])

        events = self.verify_action(
            lambda: do_change_default_stream_group_description(
                self.user_profile.realm, group, "New description"
            )
        )
        check_default_stream_groups("events[0]", events[0])

        events = self.verify_action(
            lambda: do_change_default_stream_group_name(
                self.user_profile.realm, group, "New group name"
            )
        )
        check_default_stream_groups("events[0]", events[0])

        events = self.verify_action(
            lambda: do_remove_default_stream_group(self.user_profile.realm, group)
        )
        check_default_stream_groups("events[0]", events[0])

    def test_default_stream_group_events_guest(self) -> None:
        streams = []
        for stream_name in ["Scotland", "Rome", "Denmark"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        do_create_default_stream_group(self.user_profile.realm, "group1", "This is group1", streams)
        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]

        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST, acting_user=None)
        venice_stream = get_stream("Venice", self.user_profile.realm)
        self.verify_action(
            lambda: do_add_streams_to_default_stream_group(
                self.user_profile.realm, group, [venice_stream]
            ),
            state_change_expected=False,
            num_events=0,
        )

    def test_default_streams_events(self) -> None:
        stream = get_stream("Scotland", self.user_profile.realm)
        events = self.verify_action(lambda: do_add_default_stream(stream))
        check_default_streams("events[0]", events[0])
        events = self.verify_action(lambda: do_remove_default_stream(stream))
        check_default_streams("events[0]", events[0])

    def test_default_streams_events_guest(self) -> None:
        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST, acting_user=None)
        stream = get_stream("Scotland", self.user_profile.realm)
        self.verify_action(
            lambda: do_add_default_stream(stream), state_change_expected=False, num_events=0
        )
        self.verify_action(
            lambda: do_remove_default_stream(stream), state_change_expected=False, num_events=0
        )

    def test_muted_topics_events(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        events = self.verify_action(
            lambda: do_mute_topic(self.user_profile, stream, "topic"), num_events=2
        )
        check_muted_topics("events[0]", events[0])
        check_user_topic("events[1]", events[1])

        events = self.verify_action(
            lambda: do_unmute_topic(self.user_profile, stream, "topic"), num_events=2
        )
        check_muted_topics("events[0]", events[0])
        check_user_topic("events[1]", events[1])

        events = self.verify_action(
            lambda: do_mute_topic(self.user_profile, stream, "topic"),
            event_types=["muted_topics", "user_topic"],
        )
        check_user_topic("events[0]", events[0])

    def test_muted_users_events(self) -> None:
        muted_user = self.example_user("othello")
        events = self.verify_action(
            lambda: do_mute_user(self.user_profile, muted_user), num_events=1
        )
        check_muted_users("events[0]", events[0])

        mute_object = get_mute_object(self.user_profile, muted_user)
        assert mute_object is not None
        # This is a hack to silence mypy errors which result from it not taking
        # into account type restrictions for nested functions (here, `lambda`).
        # https://github.com/python/mypy/commit/8780d45507ab1efba33568744967674cce7184d1
        mute_object2 = mute_object

        events = self.verify_action(lambda: do_unmute_user(mute_object2))
        check_muted_users("events[0]", events[0])

    def test_change_avatar_fields(self) -> None:
        events = self.verify_action(
            lambda: do_change_avatar_fields(
                self.user_profile, UserProfile.AVATAR_FROM_USER, acting_user=self.user_profile
            ),
        )
        check_realm_user_update("events[0]", events[0], "avatar_fields")
        assert isinstance(events[0]["person"]["avatar_url"], str)
        assert isinstance(events[0]["person"]["avatar_url_medium"], str)

        events = self.verify_action(
            lambda: do_change_avatar_fields(
                self.user_profile, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=self.user_profile
            ),
        )
        check_realm_user_update("events[0]", events[0], "avatar_fields")
        self.assertEqual(events[0]["person"]["avatar_url"], None)
        self.assertEqual(events[0]["person"]["avatar_url_medium"], None)

    def test_change_full_name(self) -> None:
        events = self.verify_action(
            lambda: do_change_full_name(self.user_profile, "Sir Hamlet", self.user_profile)
        )
        check_realm_user_update("events[0]", events[0], "full_name")

    def test_change_user_delivery_email_email_address_visibility_admins(self) -> None:
        do_set_realm_property(
            self.user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )
        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()
        action = lambda: do_change_user_delivery_email(self.user_profile, "newhamlet@zulip.com")
        events = self.verify_action(action, num_events=2, client_gravatar=False)

        check_realm_user_update("events[0]", events[0], "delivery_email")
        check_realm_user_update("events[1]", events[1], "avatar_fields")
        assert isinstance(events[1]["person"]["avatar_url"], str)
        assert isinstance(events[1]["person"]["avatar_url_medium"], str)

    def test_change_user_delivery_email_email_address_visibility_everyone(self) -> None:
        do_set_realm_property(
            self.user_profile.realm,
            "email_address_visibility",
            Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )
        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()
        action = lambda: do_change_user_delivery_email(self.user_profile, "newhamlet@zulip.com")
        events = self.verify_action(action, num_events=3, client_gravatar=False)

        check_realm_user_update("events[0]", events[0], "delivery_email")
        check_realm_user_update("events[1]", events[1], "avatar_fields")
        check_realm_user_update("events[2]", events[2], "email")
        assert isinstance(events[1]["person"]["avatar_url"], str)
        assert isinstance(events[1]["person"]["avatar_url_medium"], str)

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
            with fake_backends():
                events = self.verify_action(
                    lambda: do_set_realm_authentication_methods(
                        self.user_profile.realm, auth_method_dict, acting_user=None
                    )
                )

            check_realm_update_dict("events[0]", events[0])

    def test_change_pin_stream(self) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        sub = get_subscription(stream.name, self.user_profile)
        do_change_subscription_property(
            self.user_profile, sub, stream, "pin_to_top", False, acting_user=None
        )
        for pinned in (True, False):
            events = self.verify_action(
                lambda: do_change_subscription_property(
                    self.user_profile, sub, stream, "pin_to_top", pinned, acting_user=None
                )
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

        events = self.verify_action(
            lambda: do_change_subscription_property(
                self.user_profile, sub, stream, "in_home_view", True, acting_user=None
            ),
            num_events=2,
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
        events = self.verify_action(
            lambda: do_change_subscription_property(
                self.user_profile, sub, stream, "is_muted", True, acting_user=None
            ),
            num_events=2,
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
                events = self.verify_action(
                    lambda: do_change_subscription_property(
                        self.user_profile, sub, stream, setting_name, value, acting_user=None
                    ),
                    notification_settings_null=True,
                )
                check_subscription_update(
                    "events[0]",
                    events[0],
                    property=setting_name,
                    value=value,
                )

            for value in (True, False):
                events = self.verify_action(
                    lambda: do_change_subscription_property(
                        self.user_profile, sub, stream, setting_name, value, acting_user=None
                    )
                )
                check_subscription_update(
                    "events[0]",
                    events[0],
                    property=setting_name,
                    value=value,
                )

    def test_change_realm_notifications_stream(self) -> None:
        stream = get_stream("Rome", self.user_profile.realm)

        for notifications_stream, notifications_stream_id in ((stream, stream.id), (None, -1)):
            events = self.verify_action(
                lambda: do_set_realm_notifications_stream(
                    self.user_profile.realm,
                    notifications_stream,
                    notifications_stream_id,
                    acting_user=None,
                )
            )
            check_realm_update("events[0]", events[0], "notifications_stream_id")

    def test_change_realm_signup_notifications_stream(self) -> None:
        stream = get_stream("Rome", self.user_profile.realm)

        for signup_notifications_stream, signup_notifications_stream_id in (
            (stream, stream.id),
            (None, -1),
        ):
            events = self.verify_action(
                lambda: do_set_realm_signup_notifications_stream(
                    self.user_profile.realm,
                    signup_notifications_stream,
                    signup_notifications_stream_id,
                    acting_user=None,
                )
            )
            check_realm_update("events[0]", events[0], "signup_notifications_stream_id")

    def test_change_is_admin(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        for role in [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role, acting_user=None),
                num_events=4,
            )
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_REALM_ADMINISTRATOR:
                check_user_group_remove_members("events[3]", events[3])
            else:
                check_user_group_add_members("events[3]", events[3])

    def test_change_is_billing_admin(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        events = self.verify_action(lambda: do_make_user_billing_admin(self.user_profile))
        check_realm_user_update("events[0]", events[0], "is_billing_admin")
        self.assertEqual(events[0]["person"]["is_billing_admin"], True)

    def test_change_is_owner(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        for role in [UserProfile.ROLE_REALM_OWNER, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role, acting_user=None),
                num_events=4,
            )
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_REALM_OWNER:
                check_user_group_remove_members("events[3]", events[3])
            else:
                check_user_group_add_members("events[3]", events[3])

    def test_change_is_moderator(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        for role in [UserProfile.ROLE_MODERATOR, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role, acting_user=None),
                num_events=4,
            )
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_MODERATOR:
                check_user_group_remove_members("events[3]", events[3])
            else:
                check_user_group_add_members("events[3]", events[3])

    def test_change_is_guest(self) -> None:
        stream = Stream.objects.get(name="Denmark")
        do_add_default_stream(stream)

        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        for role in [UserProfile.ROLE_GUEST, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role, acting_user=None),
                num_events=4,
            )
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_GUEST:
                check_user_group_remove_members("events[3]", events[3])
            else:
                check_user_group_add_members("events[3]", events[3])

    def test_change_notification_settings(self) -> None:
        for notification_setting, v in self.user_profile.notification_setting_types.items():
            if notification_setting in [
                "notification_sound",
                "desktop_icon_count_display",
                "presence_enabled",
            ]:
                # These settings are tested in their own tests.
                continue

            do_change_user_setting(
                self.user_profile, notification_setting, False, acting_user=self.user_profile
            )

            for setting_value in [True, False]:
                events = self.verify_action(
                    lambda: do_change_user_setting(
                        self.user_profile,
                        notification_setting,
                        setting_value,
                        acting_user=self.user_profile,
                    ),
                    num_events=2,
                )
                check_user_settings_update("events[0]", events[0])
                check_update_global_notifications("events[1]", events[1], setting_value)

                # Also test with notification_settings_null=True
                events = self.verify_action(
                    lambda: do_change_user_setting(
                        self.user_profile,
                        notification_setting,
                        setting_value,
                        acting_user=self.user_profile,
                    ),
                    notification_settings_null=True,
                    state_change_expected=False,
                    num_events=2,
                )
                check_user_settings_update("events[0]", events[0])
                check_update_global_notifications("events[1]", events[1], setting_value)

    def test_change_presence_enabled(self) -> None:
        presence_enabled_setting = "presence_enabled"

        for val in [True, False]:
            events = self.verify_action(
                lambda: do_change_user_setting(
                    self.user_profile, presence_enabled_setting, val, acting_user=self.user_profile
                ),
                num_events=3,
            )
            check_user_settings_update("events[0]", events[0])
            check_update_global_notifications("events[1]", events[1], val)
            check_presence(
                "events[2]",
                events[2],
                has_email=True,
                presence_key="website",
                status="active" if val else "idle",
            )

    def test_change_notification_sound(self) -> None:
        notification_setting = "notification_sound"

        events = self.verify_action(
            lambda: do_change_user_setting(
                self.user_profile, notification_setting, "ding", acting_user=self.user_profile
            ),
            num_events=2,
        )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], "ding")

    def test_change_desktop_icon_count_display(self) -> None:
        notification_setting = "desktop_icon_count_display"

        events = self.verify_action(
            lambda: do_change_user_setting(
                self.user_profile, notification_setting, 2, acting_user=self.user_profile
            ),
            num_events=2,
        )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], 2)

        events = self.verify_action(
            lambda: do_change_user_setting(
                self.user_profile, notification_setting, 1, acting_user=self.user_profile
            ),
            num_events=2,
        )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], 1)

    def test_realm_update_org_type(self) -> None:
        realm = self.user_profile.realm

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_org_type"], Realm.ORG_TYPES["business"]["id"])

        events = self.verify_action(
            lambda: do_change_realm_org_type(
                realm, Realm.ORG_TYPES["government"]["id"], acting_user=self.user_profile
            )
        )
        check_realm_update("events[0]", events[0], "org_type")

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_org_type"], Realm.ORG_TYPES["government"]["id"])

    def test_realm_update_plan_type(self) -> None:
        realm = self.user_profile.realm

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_plan_type"], Realm.PLAN_TYPE_SELF_HOSTED)
        self.assertEqual(state_data["zulip_plan_is_not_limited"], True)

        events = self.verify_action(
            lambda: do_change_realm_plan_type(
                realm, Realm.PLAN_TYPE_LIMITED, acting_user=self.user_profile
            ),
            num_events=2,
        )
        check_realm_update("events[0]", events[0], "enable_spectator_access")
        check_realm_update("events[1]", events[1], "plan_type")

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_plan_type"], Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(state_data["zulip_plan_is_not_limited"], False)

    def test_realm_emoji_events(self) -> None:
        author = self.example_user("iago")
        with get_test_image_file("img.png") as img_file:
            events = self.verify_action(
                lambda: check_add_realm_emoji(self.user_profile.realm, "my_emoji", author, img_file)
            )

        check_realm_emoji_update("events[0]", events[0])

        events = self.verify_action(
            lambda: do_remove_realm_emoji(
                self.user_profile.realm, "my_emoji", acting_user=self.user_profile
            )
        )
        check_realm_emoji_update("events[0]", events[0])

    def test_realm_filter_events(self) -> None:
        regex = "#(?P<id>[123])"
        url = "https://realm.com/my_realm_filter/%(id)s"

        events = self.verify_action(
            lambda: do_add_linkifier(self.user_profile.realm, regex, url, acting_user=None),
            num_events=2,
        )
        check_realm_linkifiers("events[0]", events[0])
        check_realm_filters("events[1]", events[1])

        regex = "#(?P<id>[0-9]+)"
        linkifier_id = events[0]["realm_linkifiers"][0]["id"]
        events = self.verify_action(
            lambda: do_update_linkifier(
                self.user_profile.realm, linkifier_id, regex, url, acting_user=None
            ),
            num_events=2,
        )
        check_realm_linkifiers("events[0]", events[0])
        check_realm_filters("events[1]", events[1])

        events = self.verify_action(
            lambda: do_remove_linkifier(self.user_profile.realm, regex, acting_user=None),
            num_events=2,
        )
        check_realm_linkifiers("events[0]", events[0])
        check_realm_filters("events[1]", events[1])

    def test_realm_domain_events(self) -> None:
        events = self.verify_action(
            lambda: do_add_realm_domain(
                self.user_profile.realm, "zulip.org", False, acting_user=None
            )
        )

        check_realm_domains_add("events[0]", events[0])
        self.assertEqual(events[0]["realm_domain"]["domain"], "zulip.org")
        self.assertEqual(events[0]["realm_domain"]["allow_subdomains"], False)

        test_domain = RealmDomain.objects.get(realm=self.user_profile.realm, domain="zulip.org")
        events = self.verify_action(
            lambda: do_change_realm_domain(test_domain, True, acting_user=None)
        )

        check_realm_domains_change("events[0]", events[0])
        self.assertEqual(events[0]["realm_domain"]["domain"], "zulip.org")
        self.assertEqual(events[0]["realm_domain"]["allow_subdomains"], True)

        events = self.verify_action(lambda: do_remove_realm_domain(test_domain, acting_user=None))

        check_realm_domains_remove("events[0]", events[0])
        self.assertEqual(events[0]["domain"], "zulip.org")

    def test_realm_playground_events(self) -> None:
        playground_info = dict(
            name="Python playground",
            pygments_language="Python",
            url_prefix="https://python.example.com",
        )
        events = self.verify_action(
            lambda: do_add_realm_playground(
                self.user_profile.realm, acting_user=None, **playground_info
            )
        )
        check_realm_playgrounds("events[0]", events[0])

        last_realm_playground = RealmPlayground.objects.last()
        assert last_realm_playground is not None
        last_id = last_realm_playground.id
        realm_playground = access_playground_by_id(self.user_profile.realm, last_id)
        events = self.verify_action(
            lambda: do_remove_realm_playground(
                self.user_profile.realm, realm_playground, acting_user=None
            )
        )
        check_realm_playgrounds("events[0]", events[0])

    def test_create_bot(self) -> None:
        action = lambda: self.create_bot("test")
        events = self.verify_action(action, num_events=4)
        check_realm_bot_add("events[1]", events[1])

        action = lambda: self.create_bot(
            "test_outgoing_webhook",
            full_name="Outgoing Webhook Bot",
            payload_url=orjson.dumps("https://foo.bar.com").decode(),
            interface_type=Service.GENERIC,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )
        events = self.verify_action(action, num_events=4)
        # The third event is the second call of notify_created_bot, which contains additional
        # data for services (in contrast to the first call).
        check_realm_bot_add("events[1]", events[1])

        action = lambda: self.create_bot(
            "test_embedded",
            full_name="Embedded Bot",
            service_name="helloworld",
            config_data=orjson.dumps({"foo": "bar"}).decode(),
            bot_type=UserProfile.EMBEDDED_BOT,
        )
        events = self.verify_action(action, num_events=4)
        check_realm_bot_add("events[1]", events[1])

    def test_change_bot_full_name(self) -> None:
        bot = self.create_bot("test")
        action = lambda: do_change_full_name(bot, "New Bot Name", self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_update("events[1]", events[1], "full_name")

    def test_regenerate_bot_api_key(self) -> None:
        bot = self.create_bot("test")
        action = lambda: do_regenerate_api_key(bot, self.user_profile)
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "api_key")

    def test_change_bot_avatar_source(self) -> None:
        bot = self.create_bot("test")
        action = lambda: do_change_avatar_fields(
            bot, bot.AVATAR_FROM_USER, acting_user=self.user_profile
        )
        events = self.verify_action(action, num_events=2)
        check_realm_bot_update("events[0]", events[0], "avatar_url")
        self.assertEqual(events[1]["type"], "realm_user")

    def test_change_realm_icon_source(self) -> None:
        action = lambda: do_change_icon_source(
            self.user_profile.realm, Realm.ICON_UPLOADED, acting_user=None
        )
        events = self.verify_action(action, state_change_expected=True)
        check_realm_update_dict("events[0]", events[0])

    def test_change_realm_light_theme_logo_source(self) -> None:
        action = lambda: do_change_logo_source(
            self.user_profile.realm, Realm.LOGO_UPLOADED, False, acting_user=self.user_profile
        )
        events = self.verify_action(action, state_change_expected=True)
        check_realm_update_dict("events[0]", events[0])

    def test_change_realm_dark_theme_logo_source(self) -> None:
        action = lambda: do_change_logo_source(
            self.user_profile.realm, Realm.LOGO_UPLOADED, True, acting_user=self.user_profile
        )
        events = self.verify_action(action, state_change_expected=True)
        check_realm_update_dict("events[0]", events[0])

    def test_change_bot_default_all_public_streams(self) -> None:
        bot = self.create_bot("test")
        action = lambda: do_change_default_all_public_streams(bot, True, acting_user=None)
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "default_all_public_streams")

    def test_change_bot_default_sending_stream(self) -> None:
        bot = self.create_bot("test")
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_sending_stream(bot, stream, acting_user=None)
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "default_sending_stream")

        action = lambda: do_change_default_sending_stream(bot, None, acting_user=None)
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "default_sending_stream")

    def test_change_bot_default_events_register_stream(self) -> None:
        bot = self.create_bot("test")
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_events_register_stream(bot, stream, acting_user=None)
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "default_events_register_stream")

        action = lambda: do_change_default_events_register_stream(bot, None, acting_user=None)
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "default_events_register_stream")

    def test_change_bot_owner(self) -> None:
        self.user_profile = self.example_user("iago")
        owner = self.example_user("hamlet")
        bot = self.create_bot("test")
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_update("events[0]", events[0], "owner_id")
        check_realm_user_update("events[1]", events[1], "bot_owner_id")

        self.user_profile = self.example_user("aaron")
        owner = self.example_user("hamlet")
        bot = self.create_bot("test1", full_name="Test1 Testerson")
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_delete("events[0]", events[0])
        check_realm_user_update("events[1]", events[1], "bot_owner_id")

        previous_owner = self.example_user("aaron")
        self.user_profile = self.example_user("hamlet")
        bot = self.create_test_bot("test2", previous_owner, full_name="Test2 Testerson")
        action = lambda: do_change_bot_owner(bot, self.user_profile, previous_owner)
        events = self.verify_action(action, num_events=2)
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
        action = lambda: do_update_outgoing_webhook_service(bot, 2, "http://hostname.domain2.com")
        events = self.verify_action(action)
        check_realm_bot_update("events[0]", events[0], "services")

    def test_do_deactivate_bot(self) -> None:
        bot = self.create_bot("test")
        action = lambda: do_deactivate_user(bot, acting_user=None)
        events = self.verify_action(action, num_events=2)
        check_realm_user_remove("events[0]", events[0])
        check_realm_bot_remove("events[1]", events[1])

    def test_do_deactivate_user(self) -> None:
        user_profile = self.example_user("cordelia")
        action = lambda: do_deactivate_user(user_profile, acting_user=None)
        events = self.verify_action(action, num_events=1)
        check_realm_user_remove("events[0]", events[0])

    def test_do_reactivate_user(self) -> None:
        bot = self.create_bot("test")
        self.subscribe(bot, "Denmark")
        self.make_stream("Test private stream", invite_only=True)
        self.subscribe(bot, "Test private stream")
        do_deactivate_user(bot, acting_user=None)
        action = lambda: do_reactivate_user(bot, acting_user=None)
        events = self.verify_action(action, num_events=3)
        check_realm_bot_add("events[1]", events[1])
        check_subscription_peer_add("events[2]", events[2])

        # Test 'peer_add' event for private stream is received only if user is subscribed to it.
        do_deactivate_user(bot, acting_user=None)
        self.subscribe(self.example_user("hamlet"), "Test private stream")
        action = lambda: do_reactivate_user(bot, acting_user=None)
        events = self.verify_action(action, num_events=4)
        check_realm_bot_add("events[1]", events[1])
        check_subscription_peer_add("events[2]", events[2])
        check_subscription_peer_add("events[3]", events[3])

    def test_do_deactivate_realm(self) -> None:
        realm = self.user_profile.realm
        action = lambda: do_deactivate_realm(realm, acting_user=None)

        # We delete sessions of all active users when a realm is
        # deactivated, and redirect them to a deactivated page in
        # order to inform that realm/organization has been
        # deactivated.  state_change_expected is False is kinda
        # correct because were one to somehow compute page_params (as
        # this test does), but that's not actually possible.
        events = self.verify_action(action, state_change_expected=False)
        check_realm_deactivated("events[0]", events[0])

    def test_do_mark_hotspot_as_read(self) -> None:
        self.user_profile.tutorial_status = UserProfile.TUTORIAL_WAITING
        self.user_profile.save(update_fields=["tutorial_status"])

        events = self.verify_action(
            lambda: do_mark_hotspot_as_read(self.user_profile, "intro_streams")
        )
        check_hotspots("events[0]", events[0])

    def test_rename_stream(self) -> None:
        for i, include_streams in enumerate([True, False]):
            old_name = f"old name{i}"
            new_name = f"new name{i}"

            stream = self.make_stream(old_name)
            self.subscribe(self.user_profile, stream.name)
            action = lambda: do_rename_stream(stream, new_name, self.user_profile)
            events = self.verify_action(action, num_events=3, include_streams=include_streams)

            check_stream_update("events[0]", events[0])
            self.assertEqual(events[0]["name"], old_name)

            check_stream_update("events[1]", events[1])
            self.assertEqual(events[1]["name"], old_name)

            check_message("events[2]", events[2])

            fields = dict(
                sender_email="notification-bot@zulip.com",
                display_recipient=new_name,
                sender_full_name="Notification Bot",
                is_me_message=False,
                type="stream",
                client="Internal",
            )

            fields[TOPIC_NAME] = "stream events"

            msg = events[2]["message"]
            for k, v in fields.items():
                self.assertEqual(msg[k], v)

    def test_deactivate_stream_neversubscribed(self) -> None:
        for i, include_streams in enumerate([True, False]):
            stream = self.make_stream(f"stream{i}")
            action = lambda: do_deactivate_stream(stream, acting_user=None)
            events = self.verify_action(action, include_streams=include_streams)
            check_stream_delete("events[0]", events[0])

    def test_subscribe_other_user_never_subscribed(self) -> None:
        for i, include_streams in enumerate([True, False]):
            action = lambda: self.subscribe(self.example_user("othello"), f"test_stream{i}")
            events = self.verify_action(action, num_events=2, include_streams=True)
            check_subscription_peer_add("events[1]", events[1])

    def test_remove_other_user_never_subscribed(self) -> None:
        othello = self.example_user("othello")
        realm = othello.realm
        self.subscribe(othello, "test_stream")
        stream = get_stream("test_stream", self.user_profile.realm)

        action = lambda: bulk_remove_subscriptions(realm, [othello], [stream], acting_user=None)
        events = self.verify_action(action)
        check_subscription_peer_remove("events[0]", events[0])

    def test_do_delete_message_stream(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Verona")
        msg_id_2 = self.send_stream_message(hamlet, "Verona")
        messages = [Message.objects.get(id=msg_id), Message.objects.get(id=msg_id_2)]
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, messages),
            state_change_expected=True,
        )
        check_delete_message(
            "events[0]",
            events[0],
            message_type="stream",
            num_message_ids=2,
            is_legacy=False,
        )

    def test_do_delete_message_stream_legacy(self) -> None:
        """
        Test for legacy method of deleting messages which
        sends an event per message to delete to the client.
        """
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Verona")
        msg_id_2 = self.send_stream_message(hamlet, "Verona")
        messages = [Message.objects.get(id=msg_id), Message.objects.get(id=msg_id_2)]
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, messages),
            state_change_expected=True,
            bulk_message_deletion=False,
            num_events=2,
        )
        check_delete_message(
            "events[0]",
            events[0],
            message_type="stream",
            num_message_ids=1,
            is_legacy=True,
        )

    def test_do_delete_message_personal(self) -> None:
        msg_id = self.send_personal_message(
            self.example_user("cordelia"),
            self.user_profile,
            "hello",
        )
        message = Message.objects.get(id=msg_id)
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
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
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
            bulk_message_deletion=False,
        )
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
        self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
        result = fetch_initial_state_data(user_profile)
        self.assertEqual(result["max_message_id"], -1)

    def test_add_attachment(self) -> None:
        self.login("hamlet")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        uri = None

        def do_upload() -> None:
            nonlocal uri
            result = self.client_post("/json/user_uploads", {"file": fp})

            response_dict = self.assert_json_success(result)
            self.assertIn("uri", response_dict)
            uri = response_dict["uri"]
            base = "/user_uploads/"
            self.assertEqual(base, uri[: len(base)])

        events = self.verify_action(lambda: do_upload(), num_events=1, state_change_expected=False)

        check_attachment_add("events[0]", events[0])
        self.assertEqual(events[0]["upload_space_used"], 6)

        # Verify that the DB has the attachment marked as unclaimed
        entry = Attachment.objects.get(file_name="zulip.txt")
        self.assertEqual(entry.is_claimed(), False)

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        assert uri is not None
        body = f"First message ...[zulip.txt](http://{hamlet.realm.host}" + uri + ")"
        events = self.verify_action(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test"),
            num_events=2,
        )

        check_attachment_update("events[0]", events[0])
        self.assertEqual(events[0]["upload_space_used"], 6)

        # Now remove the attachment
        events = self.verify_action(
            lambda: self.client_delete(f"/json/attachments/{entry.id}"),
            num_events=1,
            state_change_expected=False,
        )

        check_attachment_remove("events[0]", events[0])
        self.assertEqual(events[0]["upload_space_used"], 0)

    def test_notify_realm_export(self) -> None:
        do_change_user_role(
            self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None
        )
        self.login_user(self.user_profile)

        with mock.patch(
            "zerver.lib.export.do_export_realm",
            return_value=create_dummy_file("test-export.tar.gz"),
        ):
            with stdout_suppressed(), self.assertLogs(level="INFO") as info_logs:
                events = self.verify_action(
                    lambda: self.client_post("/json/export/realm"),
                    state_change_expected=True,
                    num_events=3,
                )
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
        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED
        ).first()
        assert audit_log_entry is not None
        audit_log_entry_id = audit_log_entry.id
        events = self.verify_action(
            lambda: self.client_delete(f"/json/export/realm/{audit_log_entry_id}"),
            state_change_expected=False,
            num_events=1,
        )

        check_realm_export(
            "events[0]",
            events[0],
            has_export_url=False,
            has_deleted_timestamp=True,
            has_failed_timestamp=False,
        )

    def test_notify_realm_export_on_failure(self) -> None:
        do_change_user_role(
            self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None
        )
        self.login_user(self.user_profile)

        with mock.patch(
            "zerver.lib.export.do_export_realm", side_effect=Exception("Some failure")
        ), self.assertLogs(level="ERROR") as error_log:
            with stdout_suppressed():
                events = self.verify_action(
                    lambda: self.client_post("/json/export/realm"),
                    state_change_expected=False,
                    num_events=2,
                )

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
        events = self.verify_action(
            lambda: do_set_zoom_token(self.user_profile, {"access_token": "token"}),
        )
        check_has_zoom_token("events[0]", events[0], value=True)

        events = self.verify_action(lambda: do_set_zoom_token(self.user_profile, None))
        check_has_zoom_token("events[0]", events[0], value=False)

    def test_restart_event(self) -> None:
        with self.assertRaises(RestartEventError):
            self.verify_action(lambda: send_restart_events(immediate=True))

    def test_display_setting_event_not_sent(self) -> None:
        events = self.verify_action(
            lambda: do_change_user_setting(
                self.user_profile,
                "default_view",
                "all_messages",
                acting_user=self.user_profile,
            ),
            state_change_expected=True,
            user_settings_object=True,
        )
        check_user_settings_update("events[0]", events[0])

    def test_notification_setting_event_not_sent(self) -> None:
        events = self.verify_action(
            lambda: do_change_user_setting(
                self.user_profile,
                "enable_sounds",
                False,
                acting_user=self.user_profile,
            ),
            state_change_expected=True,
            user_settings_object=True,
        )
        check_user_settings_update("events[0]", events[0])


class RealmPropertyActionTest(BaseAction):
    def do_set_realm_property_test(self, name: str) -> None:
        bool_tests: List[bool] = [True, False, True]
        test_values: Dict[str, Any] = dict(
            default_language=["es", "de", "en"],
            description=["Realm description", "New description"],
            digest_weekday=[0, 1, 2],
            message_retention_days=[10, 20],
            name=["Zulip", "New Name"],
            waiting_period_threshold=[1000, 2000],
            create_public_stream_policy=Realm.COMMON_POLICY_TYPES,
            create_private_stream_policy=Realm.COMMON_POLICY_TYPES,
            create_web_public_stream_policy=Realm.CREATE_WEB_PUBLIC_STREAM_POLICY_TYPES,
            invite_to_stream_policy=Realm.COMMON_POLICY_TYPES,
            private_message_policy=Realm.PRIVATE_MESSAGE_POLICY_TYPES,
            user_group_edit_policy=Realm.COMMON_POLICY_TYPES,
            wildcard_mention_policy=Realm.WILDCARD_MENTION_POLICY_TYPES,
            email_address_visibility=Realm.EMAIL_ADDRESS_VISIBILITY_TYPES,
            bot_creation_policy=Realm.BOT_CREATION_POLICY_TYPES,
            video_chat_provider=[
                Realm.VIDEO_CHAT_PROVIDERS["jitsi_meet"]["id"],
            ],
            giphy_rating=[
                Realm.GIPHY_RATING_OPTIONS["disabled"]["id"],
            ],
            default_code_block_language=["python", "javascript"],
            message_content_delete_limit_seconds=[1000, 1100, 1200],
            invite_to_realm_policy=Realm.INVITE_TO_REALM_POLICY_TYPES,
            move_messages_between_streams_policy=Realm.COMMON_POLICY_TYPES,
            add_custom_emoji_policy=Realm.COMMON_POLICY_TYPES,
            delete_own_message_policy=Realm.COMMON_MESSAGE_POLICY_TYPES,
            edit_topic_policy=Realm.COMMON_MESSAGE_POLICY_TYPES,
            message_content_edit_limit_seconds=[1000, 1100, 1200, None],
        )

        vals = test_values.get(name)
        property_type = Realm.property_types[name]
        if property_type is bool:
            vals = bool_tests

        if vals is None:
            raise AssertionError(f"No test created for {name}")
        now = timezone_now()
        do_set_realm_property(self.user_profile.realm, name, vals[0], acting_user=self.user_profile)
        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=self.user_profile.realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )
        for count, val in enumerate(vals[1:]):
            now = timezone_now()
            state_change_expected = True
            old_value = vals[count]
            num_events = 1
            if name == "email_address_visibility" and Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE in [
                old_value,
                val,
            ]:
                # email update event is sent for each user.
                num_events = 11

            events = self.verify_action(
                lambda: do_set_realm_property(
                    self.user_profile.realm, name, val, acting_user=self.user_profile
                ),
                state_change_expected=state_change_expected,
                num_events=num_events,
            )

            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data=orjson.dumps(
                        {
                            RealmAuditLog.OLD_VALUE: old_value,
                            RealmAuditLog.NEW_VALUE: val,
                            "property": name,
                        }
                    ).decode(),
                ).count(),
                1,
            )

            if name in [
                "allow_message_editing",
                "edit_topic_policy",
                "message_content_edit_limit_seconds",
            ]:
                check_realm_update_dict("events[0]", events[0])
            else:
                check_realm_update("events[0]", events[0], name)

            if name == "email_address_visibility" and Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE in [
                old_value,
                val,
            ]:
                check_realm_user_update("events[1]", events[1], "email")

    def test_change_realm_property(self) -> None:
        for prop in Realm.property_types:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_property_test(prop)

    def do_set_realm_user_default_setting_test(self, name: str) -> None:
        bool_tests: List[bool] = [True, False, True]
        test_values: Dict[str, Any] = dict(
            color_scheme=UserProfile.COLOR_SCHEME_CHOICES,
            default_view=["recent_topics", "all_messages"],
            emojiset=[emojiset["key"] for emojiset in RealmUserDefault.emojiset_choices()],
            demote_inactive_streams=UserProfile.DEMOTE_STREAMS_CHOICES,
            user_list_style=UserProfile.USER_LIST_STYLE_CHOICES,
            desktop_icon_count_display=[1, 2, 3],
            notification_sound=["zulip", "ding"],
            email_notifications_batching_period_seconds=[120, 300],
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
                event_type=RealmAuditLog.REALM_DEFAULT_USER_SETTINGS_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )
        for count, val in enumerate(vals[1:]):
            now = timezone_now()
            state_change_expected = True
            events = self.verify_action(
                lambda: do_set_realm_user_default_setting(
                    realm_user_default, name, val, acting_user=self.user_profile
                ),
                state_change_expected=state_change_expected,
            )

            old_value = vals[count]
            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=RealmAuditLog.REALM_DEFAULT_USER_SETTINGS_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data=orjson.dumps(
                        {
                            RealmAuditLog.OLD_VALUE: old_value,
                            RealmAuditLog.NEW_VALUE: val,
                            "property": name,
                        }
                    ).decode(),
                ).count(),
                1,
            )
            check_realm_default_update("events[0]", events[0], name)

    def test_change_realm_user_default_setting(self) -> None:
        for prop in RealmUserDefault.property_types:
            if prop == "default_language":
                continue
            self.do_set_realm_user_default_setting_test(prop)


class UserDisplayActionTest(BaseAction):
    def do_change_user_settings_test(self, setting_name: str) -> None:
        """Test updating each setting in UserProfile.property_types dict."""

        test_changes: Dict[str, Any] = dict(
            emojiset=["twitter"],
            default_language=["es", "de", "en"],
            default_view=["all_messages", "recent_topics"],
            demote_inactive_streams=[2, 3, 1],
            user_list_style=[1, 2, 3],
            color_scheme=[2, 3, 1],
        )

        user_settings_object = True
        num_events = 1

        legacy_setting = setting_name in UserProfile.display_settings_legacy
        if legacy_setting:
            # Two events:`update_display_settings` and `user_settings`.
            # `update_display_settings` is only sent for settings added
            # before feature level 89 which introduced `user_settings`.
            # We send both events so that older clients that do not
            # rely on `user_settings` don't break.
            num_events = 2
            user_settings_object = False

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
            events = self.verify_action(
                lambda: do_change_user_setting(
                    self.user_profile, setting_name, value, acting_user=self.user_profile
                ),
                num_events=num_events,
                user_settings_object=user_settings_object,
            )

            check_user_settings_update("events[0]", events[0])
            if legacy_setting:
                # Only settings added before feature level 89
                # generate this event.
                self.assert_length(events, 2)
                check_update_display_settings("events[1]", events[1])

    def test_change_user_settings(self) -> None:
        for prop in UserProfile.property_types:
            # Notification settings have a separate test suite, which
            # handles their separate legacy event type.
            if prop not in UserProfile.notification_settings_legacy:
                self.do_change_user_settings_test(prop)

    def test_set_user_timezone(self) -> None:
        values = ["America/Denver", "Pacific/Pago_Pago", "Pacific/Galapagos", ""]
        num_events = 3

        for value in values:
            events = self.verify_action(
                lambda: do_change_user_setting(
                    self.user_profile, "timezone", value, acting_user=self.user_profile
                ),
                num_events=num_events,
            )

            check_user_settings_update("events[0]", events[0])
            check_update_display_settings("events[1]", events[1])
            check_realm_user_update("events[2]", events[2], "timezone")


class SubscribeActionTest(BaseAction):
    def test_subscribe_events(self) -> None:
        self.do_test_subscribe_events(include_subscribers=True)

    def test_subscribe_events_no_include_subscribers(self) -> None:
        self.do_test_subscribe_events(include_subscribers=False)

    def do_test_subscribe_events(self, include_subscribers: bool) -> None:
        # Subscribe to a totally new stream, so it's just Hamlet on it
        action: Callable[[], object] = lambda: self.subscribe(
            self.example_user("hamlet"), "test_stream"
        )
        events = self.verify_action(
            action, event_types=["subscription"], include_subscribers=include_subscribers
        )
        check_subscription_add("events[0]", events[0])

        # Add another user to that totally new stream
        action = lambda: self.subscribe(self.example_user("othello"), "test_stream")
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers,
        )
        check_subscription_peer_add("events[0]", events[0])

        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        realm = othello.realm
        stream = get_stream("test_stream", self.user_profile.realm)

        # Now remove the first user, to test the normal unsubscribe flow and
        # 'peer_remove' event for subscribed streams.
        action = lambda: bulk_remove_subscriptions(realm, [othello], [stream], acting_user=None)
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers,
        )
        check_subscription_peer_remove("events[0]", events[0])

        # Now remove the user himself, to test the 'remove' event flow
        action = lambda: bulk_remove_subscriptions(realm, [hamlet], [stream], acting_user=None)
        events = self.verify_action(
            action, include_subscribers=include_subscribers, include_streams=False, num_events=1
        )
        check_subscription_remove("events[0]", events[0])
        self.assert_length(events[0]["subscriptions"], 1)
        self.assertEqual(
            events[0]["subscriptions"][0]["name"],
            "test_stream",
        )

        # Subscribe other user to test 'peer_add' event flow for unsubscribed stream.
        action = lambda: self.subscribe(self.example_user("iago"), "test_stream")
        events = self.verify_action(
            action,
            event_types=["subscription"],
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers,
        )
        check_subscription_peer_add("events[0]", events[0])

        # Remove the user to test 'peer_remove' event flow for unsubscribed stream.
        action = lambda: bulk_remove_subscriptions(realm, [iago], [stream], acting_user=None)
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers,
        )
        check_subscription_peer_remove("events[0]", events[0])

        # Now resubscribe a user, to make sure that works on a vacated stream
        action = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")
        events = self.verify_action(
            action, include_subscribers=include_subscribers, include_streams=False, num_events=1
        )
        check_subscription_add("events[0]", events[0])

        action = lambda: do_change_stream_description(
            stream, "new description", acting_user=self.example_user("hamlet")
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=2)
        check_stream_update("events[0]", events[0])
        check_message("events[1]", events[1])

        # Update stream privacy - make stream web-public
        action = lambda: do_change_stream_permission(
            stream,
            invite_only=False,
            history_public_to_subscribers=True,
            is_web_public=True,
            acting_user=self.example_user("hamlet"),
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=2)
        check_stream_update("events[0]", events[0])
        check_message("events[1]", events[1])

        # Update stream privacy - make stream private
        action = lambda: do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=self.example_user("hamlet"),
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=2)
        check_stream_update("events[0]", events[0])
        check_message("events[1]", events[1])

        # Update stream privacy - make stream public
        self.user_profile = self.example_user("cordelia")
        action = lambda: do_change_stream_permission(
            stream,
            invite_only=False,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=self.example_user("hamlet"),
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=2)
        check_stream_create("events[0]", events[0])
        check_subscription_peer_add("events[1]", events[1])

        do_change_stream_permission(
            stream,
            invite_only=True,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=self.example_user("hamlet"),
        )
        self.subscribe(self.example_user("cordelia"), stream.name)
        self.unsubscribe(self.example_user("cordelia"), stream.name)
        action = lambda: do_change_stream_permission(
            stream,
            invite_only=False,
            history_public_to_subscribers=True,
            is_web_public=False,
            acting_user=self.example_user("hamlet"),
        )
        events = self.verify_action(
            action, include_subscribers=include_subscribers, num_events=2, include_streams=False
        )

        self.user_profile = self.example_user("hamlet")
        # Update stream stream_post_policy property
        action = lambda: do_change_stream_post_policy(
            stream, Stream.STREAM_POST_POLICY_ADMINS, acting_user=self.example_user("hamlet")
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=3)
        check_stream_update("events[0]", events[0])
        check_message("events[2]", events[2])

        action = lambda: do_change_stream_message_retention_days(
            stream, self.example_user("hamlet"), -1
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=2)
        check_stream_update("events[0]", events[0])

        moderators_group = UserGroup.objects.get(
            name=UserGroup.MODERATORS_GROUP_NAME,
            is_system_group=True,
            realm=self.user_profile.realm,
        )
        action = lambda: do_change_can_remove_subscribers_group(
            stream, moderators_group, acting_user=self.example_user("hamlet")
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=1)
        check_stream_update("events[0]", events[0])

        # Subscribe to a totally new invite-only stream, so it's just Hamlet on it
        stream = self.make_stream("private", self.user_profile.realm, invite_only=True)
        stream.message_retention_days = 10
        stream.save()

        user_profile = self.example_user("hamlet")
        action = lambda: bulk_add_subscriptions(
            user_profile.realm, [stream], [user_profile], acting_user=None
        )
        events = self.verify_action(action, include_subscribers=include_subscribers, num_events=2)
        check_stream_create("events[0]", events[0])
        check_subscription_add("events[1]", events[1])

        self.assertEqual(
            events[0]["streams"][0]["message_retention_days"],
            10,
        )


class DraftActionTest(BaseAction):
    def do_enable_drafts_synchronization(self, user_profile: UserProfile) -> None:
        do_change_user_setting(
            user_profile, "enable_drafts_synchronization", True, acting_user=self.user_profile
        )

    def test_draft_create_event(self) -> None:
        self.do_enable_drafts_synchronization(self.user_profile)
        dummy_draft = {
            "type": "draft",
            "to": "",
            "topic": "",
            "content": "Sample draft content",
            "timestamp": 1596820995,
        }
        action = lambda: do_create_drafts([dummy_draft], self.user_profile)
        self.verify_action(action)

    def test_draft_edit_event(self) -> None:
        self.do_enable_drafts_synchronization(self.user_profile)
        dummy_draft = {
            "type": "draft",
            "to": "",
            "topic": "",
            "content": "Sample draft content",
            "timestamp": 1596820995,
        }
        draft_id = do_create_drafts([dummy_draft], self.user_profile)[0].id
        dummy_draft["content"] = "Some more sample draft content"
        action = lambda: do_edit_draft(draft_id, dummy_draft, self.user_profile)
        self.verify_action(action)

    def test_draft_delete_event(self) -> None:
        self.do_enable_drafts_synchronization(self.user_profile)
        dummy_draft = {
            "type": "draft",
            "to": "",
            "topic": "",
            "content": "Sample draft content",
            "timestamp": 1596820995,
        }
        draft_id = do_create_drafts([dummy_draft], self.user_profile)[0].id
        action = lambda: do_delete_draft(draft_id, self.user_profile)
        self.verify_action(action)
