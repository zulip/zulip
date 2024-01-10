# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
#
# This module is closely integrated with zerver/lib/event_schema.py
# and zerver/lib/data_types.py systems for validating the schemas of
# events; it also uses the OpenAPI tools to validate our documentation.
import copy
import time
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from typing import Any, Dict, Iterator, List, Optional, Set
from unittest import mock

import orjson
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
from zerver.actions.hotspots import do_mark_onboarding_step_as_read
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
    do_set_realm_new_stream_announcements_stream,
    do_set_realm_property,
    do_set_realm_signup_announcements_stream,
    do_set_realm_user_default_setting,
    do_set_realm_zulip_update_announcements_stream,
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
    do_change_stream_group_based_setting,
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
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    check_add_user_group,
    check_delete_user_group,
    do_change_user_group_permission_setting,
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
    do_change_is_billing_admin,
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
    check_message,
    check_muted_topics,
    check_muted_users,
    check_onboarding_steps,
    check_presence,
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
    check_realm_linkifiers,
    check_realm_playgrounds,
    check_realm_update,
    check_realm_update_dict,
    check_realm_user_add,
    check_realm_user_remove,
    check_realm_user_update,
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
from zerver.lib.events import apply_events, fetch_initial_state_data, post_process_state
from zerver.lib.markdown import render_message_markdown
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.muted_users import get_mute_object
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_dummy_file,
    get_subscription,
    get_test_image_file,
    reset_email_visibility_to_everyone_in_zulip_realm,
    stdout_suppressed,
)
from zerver.lib.timestamp import convert_to_UTC, datetime_to_timestamp
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.types import ProfileDataElementUpdateDict
from zerver.models import (
    Attachment,
    CustomProfileField,
    Message,
    MultiuseInvite,
    NamedUserGroup,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    RealmDomain,
    RealmFilter,
    RealmPlayground,
    RealmUserDefault,
    Service,
    Stream,
    UserMessage,
    UserPresence,
    UserProfile,
    UserStatus,
    UserTopic,
)
from zerver.models.clients import get_client
from zerver.models.groups import SystemGroups
from zerver.models.streams import get_stream
from zerver.models.users import get_user_by_delivery_email
from zerver.openapi.openapi import validate_against_openapi_schema
from zerver.tornado.django_api import send_event
from zerver.tornado.event_queue import (
    allocate_client_descriptor,
    clear_client_event_queues_for_testing,
    create_heartbeat_event,
    mark_clients_to_reload,
    send_restart_events,
    send_web_reload_client_events,
)
from zerver.views.realm_playgrounds import access_playground_by_id


class BaseAction(ZulipTestCase):
    """Core class for verifying the apply_event race handling logic as
    well as the event formatting logic of any function using send_event.

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
        linkifier_url_template: bool = True,
        user_list_incomplete: bool = False,
        client_is_old: bool = False,
    ) -> Iterator[List[Dict[str, Any]]]:
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
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
        )

        if client_is_old:
            mark_clients_to_reload([client.event_queue.id])

        events: List[Dict[str, Any]] = []

        # We want even those `send_event` calls which have been hooked to
        # `transaction.on_commit` to execute in tests.
        # See the comment in `ZulipTestCase.capture_send_event_calls`.
        with self.captureOnCommitCallbacks(execute=True):
            yield events

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
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
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
            linkifier_url_template=linkifier_url_template,
            user_list_incomplete=user_list_incomplete,
        )
        post_process_state(self.user_profile, normal_state, notification_settings_null)
        self.match_states(hybrid_state, normal_state, events)

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
            with self.verify_action():
                self.send_stream_message(self.example_user("cordelia"), "Verona", content)

    def test_automatically_follow_topic_where_mentioned(self) -> None:
        user = self.example_user("hamlet")

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
                self.send_stream_message(self.example_user("cordelia"), "Verona", content)

    def test_topic_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = "mentioning... @**topic** hello " + str(i)
            with self.verify_action():
                self.send_stream_message(self.example_user("cordelia"), "Verona", content)

    def test_stream_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = "mentioning... @**all** hello " + str(i)
            with self.verify_action():
                self.send_stream_message(self.example_user("cordelia"), "Verona", content)

    def test_pm_send_message_events(self) -> None:
        with self.verify_action():
            self.send_personal_message(
                self.example_user("cordelia"), self.example_user("hamlet"), "hola"
            )

        # Verify direct message editing - content only edit
        pm = Message.objects.order_by("-id")[0]
        content = "new content"
        rendering_result = render_message_markdown(pm, content)
        prior_mention_user_ids: Set[int] = set()
        mention_backend = MentionBackend(self.user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
            message_sender=self.example_user("cordelia"),
        )

        with self.verify_action(state_change_expected=False) as events:
            do_update_message(
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
        with self.verify_action():
            self.send_huddle_message(self.example_user("cordelia"), huddle, "hola")

    def test_user_creation_events_on_sending_messages(self) -> None:
        self.set_up_db_for_testing_user_access()
        polonius = self.example_user("polonius")
        cordelia = self.example_user("cordelia")

        self.user_profile = polonius

        # Test that guest will not receive creation event
        # for bots as they can access all the bots.
        bot = self.create_test_bot("test2", cordelia, full_name="Test bot")
        with self.verify_action(num_events=1) as events:
            self.send_personal_message(bot, polonius, "hola")
        check_direct_message("events[0]", events[0])

        with self.verify_action(num_events=2) as events:
            self.send_personal_message(cordelia, polonius, "hola")
        check_direct_message("events[0]", events[0])
        check_realm_user_add("events[1]", events[1])
        self.assertEqual(events[1]["person"]["user_id"], cordelia.id)

        othello = self.example_user("othello")
        desdemona = self.example_user("desdemona")

        with self.verify_action(num_events=3) as events:
            self.send_huddle_message(othello, [polonius, desdemona, bot], "hola")
        check_direct_message("events[0]", events[0])
        check_realm_user_add("events[1]", events[1])
        check_realm_user_add("events[2]", events[2])
        user_creation_user_ids = {events[1]["person"]["user_id"], events[2]["person"]["user_id"]}
        self.assertEqual(user_creation_user_ids, {othello.id, desdemona.id})

    def test_stream_send_message_events(self) -> None:
        hamlet = self.example_user("hamlet")
        for stream_name in ["Verona", "Denmark", "core team"]:
            stream = get_stream(stream_name, hamlet.realm)
            sub = get_subscription(stream.name, hamlet)
            do_change_subscription_property(hamlet, sub, stream, "is_muted", True, acting_user=None)

        def verify_events_generated_and_reset_visibility_policy(
            events: List[Dict[str, Any]], stream_name: str, topic_name: str
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
                self.send_stream_message(hamlet, "Verona", "hello", "topic")
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
                self.send_stream_message(hamlet, "Denmark", "hello", f"new topic {index}")
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
                self.send_stream_message(hamlet, "core team", "hello", "topic")
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
            self.send_stream_message(hamlet, "core team", "hello", "new Topic")

        do_change_user_setting(
            user_profile=hamlet,
            setting_name="automatically_unmute_topics_in_muted_streams_policy",
            setting_value=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_NEVER,
            acting_user=None,
        )
        # Only one message event is generated
        with self.verify_action(client_gravatar=True) as events:
            self.send_stream_message(hamlet, "core team", "hello")
        # event-type: message
        check_message("events[0]", events[0])
        assert isinstance(events[0]["message"]["avatar_url"], str)

        do_change_user_setting(
            self.example_user("hamlet"),
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )

        with self.verify_action(client_gravatar=True) as events:
            self.send_stream_message(hamlet, "core team", "hello")
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
            self.send_stream_message(self.example_user("aaron"), "Verona", "hello")

    def test_stream_update_message_events(self) -> None:
        iago = self.example_user("iago")
        self.send_stream_message(iago, "Verona", "hello")

        # Verify stream message editing - content only
        message = Message.objects.order_by("-id")[0]
        content = "new content"
        rendering_result = render_message_markdown(message, content)
        prior_mention_user_ids: Set[int] = set()
        mention_backend = MentionBackend(self.user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
            message_sender=iago,
        )

        with self.verify_action(state_change_expected=False) as events:
            do_update_message(
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

        with self.verify_action(state_change_expected=True) as events:
            do_update_message(
                self.user_profile,
                message,
                None,
                topic_name,
                propagate_mode,
                False,
                False,
                None,
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
        rendering_result = render_message_markdown(message, content)
        with self.verify_action(state_change_expected=False) as events:
            do_update_embedded_data(self.user_profile, message, content, rendering_result)
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
        self.send_stream_message(iago, "Verona")
        message_id = self.send_stream_message(self.user_profile, "Verona")
        message = Message.objects.get(id=message_id)
        stream = get_stream("Denmark", self.user_profile.realm)
        propagate_mode = "change_all"
        prior_mention_user_ids = set()

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
                stream,
                None,
                propagate_mode,
                True,
                True,
                None,
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

        # Move both stream and topic, with update_message_flags
        # excluded from event types.
        self.send_stream_message(self.user_profile, "Verona")
        message_id = self.send_stream_message(self.user_profile, "Verona")
        message = Message.objects.get(id=message_id)
        stream = get_stream("Denmark", self.user_profile.realm)
        propagate_mode = "change_all"
        prior_mention_user_ids = set()

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
                stream,
                "final_topic",
                propagate_mode,
                True,
                True,
                None,
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

            huddle_message = self.send_huddle_message(
                from_user=self.example_user("cordelia"),
                to_users=[user_profile, self.example_user("othello")],
                content=content,
            )

            with self.verify_action(state_change_expected=True):
                do_update_message_flags(user_profile, "add", "read", [huddle_message])

            with self.verify_action(state_change_expected=True) as events:
                do_update_message_flags(user_profile, "remove", "read", [huddle_message])
            check_update_message_flags_remove("events[0]", events[0])

    def test_send_message_to_existing_recipient(self) -> None:
        sender = self.example_user("cordelia")
        self.send_stream_message(
            sender,
            "Verona",
            "hello 1",
        )
        with self.verify_action(state_change_expected=True):
            self.send_stream_message(sender, "Verona", "hello 2")

    def test_events_for_message_from_inaccessible_sender(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()
        self.set_up_db_for_testing_user_access()
        othello = self.example_user("othello")
        self.user_profile = self.example_user("polonius")

        with self.verify_action() as events:
            self.send_stream_message(
                othello, "test_stream1", "hello 2", allow_unsubscribed_sender=True
            )
        check_message("events[0]", events[0])
        message_obj = events[0]["message"]
        self.assertEqual(message_obj["sender_full_name"], "Unknown user")
        self.assertEqual(message_obj["sender_email"], f"user{othello.id}@zulip.testserver")
        self.assertTrue(message_obj["avatar_url"].endswith("images/unknown-user-avatar.png"))

        iago = self.example_user("iago")
        with self.verify_action() as events:
            self.send_stream_message(
                iago, "test_stream1", "hello 2", allow_unsubscribed_sender=True
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
            send_event(
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
                invite_expires_in_minutes=invite_expires_in_minutes,
            )

        with self.verify_action(num_events=2) as events:
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
                invite_expires_in_minutes=invite_expires_in_minutes,
            )
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")

        with self.verify_action(state_change_expected=True, num_events=7) as events:
            do_create_user(
                "foo@zulip.com",
                "password",
                self.user_profile.realm,
                "full name",
                prereg_user=prereg_user,
                acting_user=None,
            )

        check_invites_changed("events[6]", events[6])

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
            check_remove_custom_profile_field_value(self.user_profile, field_id)
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

    def test_presence_events(self) -> None:
        with self.verify_action(slim_presence=False) as events:
            do_update_user_presence(
                self.user_profile,
                get_client("website"),
                timezone_now(),
                UserPresence.LEGACY_STATUS_ACTIVE_INT,
            )

        check_presence(
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

        check_presence(
            "events[0]",
            events[0],
            has_email=False,
            presence_key="website",
            status="active",
        )

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

        check_presence(
            "events[0]",
            events[0],
            has_email=True,
            # We no longer store information about the client and we simply
            # set the field to 'website' for backwards compatibility.
            presence_key="website",
            status="active",
        )

    def test_register_events(self) -> None:
        with self.verify_action(num_events=5) as events:
            self.register("test1@zulip.com", "test1")
        self.assert_length(events, 5)

        check_realm_user_add("events[1]", events[1])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.delivery_email, "test1@zulip.com")

        check_subscription_peer_add("events[4]", events[4])

        check_message("events[0]", events[0])
        self.assertIn(
            f'data-user-id="{new_user_profile.id}">test1_zulip.com</span> joined this organization.',
            events[0]["message"]["content"],
        )

        check_user_group_add_members("events[2]", events[2])
        check_user_group_add_members("events[3]", events[3])

    def test_register_events_email_address_visibility(self) -> None:
        realm_user_default = RealmUserDefault.objects.get(realm=self.user_profile.realm)
        do_set_realm_user_default_setting(
            realm_user_default,
            "email_address_visibility",
            RealmUserDefault.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )

        with self.verify_action(num_events=5) as events:
            self.register("test1@zulip.com", "test1")
        self.assert_length(events, 5)
        check_realm_user_add("events[1]", events[1])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.email, f"user{new_user_profile.id}@zulip.testserver")

        check_subscription_peer_add("events[4]", events[4])

        check_message("events[0]", events[0])
        self.assertIn(
            f'data-user-id="{new_user_profile.id}">test1_zulip.com</span> joined this organization',
            events[0]["message"]["content"],
        )

        check_user_group_add_members("events[2]", events[2])
        check_user_group_add_members("events[3]", events[3])

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

    def test_away_events(self) -> None:
        client = get_client("website")

        # Updating user status to away activates the codepath of disabling
        # the presence_enabled user setting. Correctly simulating the presence
        # event status for a typical user requires settings the user's date_joined
        # further into the past. See test_change_presence_enabled for more details,
        # since it tests that codepath directly.
        self.user_profile.date_joined = timezone_now() - timedelta(days=15)
        self.user_profile.save()

        # Set all
        away_val = True
        with self.verify_action(num_events=4) as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text="out to lunch",
                emoji_name="car",
                emoji_code="1f697",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
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
        with self.verify_action(num_events=4) as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text="",
                emoji_name="",
                emoji_code="",
                reaction_type=UserStatus.UNICODE_EMOJI,
                client_id=client.id,
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
        with self.verify_action(num_events=4) as events:
            do_update_user_status(
                user_profile=self.user_profile,
                away=away_val,
                status_text=None,
                emoji_name=None,
                emoji_code=None,
                reaction_type=None,
                client_id=client.id,
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
        with self.settings(CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE=True):
            with self.verify_action(num_events=0, state_change_expected=False) as events:
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
        check_presence(
            "events[0]",
            events[0],
            has_email=True,
            # We no longer store information about the client and we simply
            # set the field to 'website' for backwards compatibility.
            presence_key="website",
            status="idle",
        )

    def test_user_group_events(self) -> None:
        othello = self.example_user("othello")
        with self.verify_action() as events:
            check_add_user_group(
                self.user_profile.realm, "backend", [othello], "Backend team", acting_user=None
            )
        check_user_group_add("events[0]", events[0])

        # Test name update
        backend = NamedUserGroup.objects.get(name="backend")
        with self.verify_action() as events:
            do_update_user_group_name(backend, "backendteam", acting_user=None)
        check_user_group_update("events[0]", events[0], "name")

        # Test description update
        description = "Backend team to deal with backend code."
        with self.verify_action() as events:
            do_update_user_group_description(backend, description, acting_user=None)
        check_user_group_update("events[0]", events[0], "description")

        # Test can_mention_group setting update
        moderators_group = NamedUserGroup.objects.get(
            name="role:moderators", realm=self.user_profile.realm, is_system_group=True
        )
        with self.verify_action() as events:
            do_change_user_group_permission_setting(
                backend, "can_mention_group", moderators_group, acting_user=None
            )
        check_user_group_update("events[0]", events[0], "can_mention_group")

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
            hamlet.realm, "api-design", [hamlet], description="API design team", acting_user=None
        )

        # Test add subgroups
        with self.verify_action() as events:
            add_subgroups_to_user_group(backend, [api_design], acting_user=None)
        check_user_group_add_subgroups("events[0]", events[0])

        # Test remove subgroups
        with self.verify_action() as events:
            remove_subgroups_from_user_group(backend, [api_design], acting_user=None)
        check_user_group_remove_subgroups("events[0]", events[0])

        # Test remove event
        with self.verify_action() as events:
            check_delete_user_group(backend, acting_user=othello)
        check_user_group_remove("events[0]", events[0])

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
        with self.verify_action() as events:
            do_change_full_name(self.user_profile, "Sir Hamlet", self.user_profile)
        check_realm_user_update("events[0]", events[0], "full_name")

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
            do_change_user_delivery_email(self.user_profile, "newhamlet@zulip.com")

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
            do_change_user_delivery_email(self.user_profile, "newhamlet@zulip.com")

        check_realm_user_update("events[0]", events[0], "delivery_email")
        check_realm_user_update("events[1]", events[1], "avatar_fields")
        check_realm_user_update("events[2]", events[2], "email")
        assert isinstance(events[1]["person"]["avatar_url"], str)
        assert isinstance(events[1]["person"]["avatar_url_medium"], str)

        # Reset hamlet's email to original email.
        do_change_user_delivery_email(self.user_profile, "hamlet@zulip.com")

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
            do_change_user_delivery_email(cordelia, "newcordelia@zulip.com")

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
                with self.verify_action() as events:
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

    def test_change_is_admin(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)

        self.make_stream("Test private stream", invite_only=True)
        self.subscribe(self.example_user("othello"), "Test private stream")

        for role in [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_MEMBER]:
            if role == UserProfile.ROLE_REALM_ADMINISTRATOR:
                num_events = 6
            else:
                num_events = 5

            with self.verify_action(num_events=num_events) as events:
                do_change_user_role(self.user_profile, role, acting_user=None)
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_REALM_ADMINISTRATOR:
                check_user_group_remove_members("events[3]", events[3])
                check_stream_create("events[4]", events[4])
                check_subscription_peer_add("events[5]", events[5])
            else:
                check_user_group_add_members("events[3]", events[3])
                check_stream_delete("events[4]", events[4])

    def test_change_is_billing_admin(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        with self.verify_action() as events:
            do_change_is_billing_admin(self.user_profile, True)
        check_realm_user_update("events[0]", events[0], "is_billing_admin")
        self.assertEqual(events[0]["person"]["is_billing_admin"], True)

        with self.verify_action() as events:
            do_change_is_billing_admin(self.user_profile, False)
        check_realm_user_update("events[0]", events[0], "is_billing_admin")
        self.assertEqual(events[0]["person"]["is_billing_admin"], False)

    def test_change_is_owner(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)

        self.make_stream("Test private stream", invite_only=True)
        self.subscribe(self.example_user("othello"), "Test private stream")

        for role in [UserProfile.ROLE_REALM_OWNER, UserProfile.ROLE_MEMBER]:
            if role == UserProfile.ROLE_REALM_OWNER:
                num_events = 6
            else:
                num_events = 5
            with self.verify_action(num_events=num_events) as events:
                do_change_user_role(self.user_profile, role, acting_user=None)
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_REALM_OWNER:
                check_user_group_remove_members("events[3]", events[3])
                check_stream_create("events[4]", events[4])
                check_subscription_peer_add("events[5]", events[5])
            else:
                check_user_group_add_members("events[3]", events[3])
                check_stream_delete("events[4]", events[4])

    def test_change_is_moderator(self) -> None:
        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        for role in [UserProfile.ROLE_MODERATOR, UserProfile.ROLE_MEMBER]:
            with self.verify_action(num_events=4) as events:
                do_change_user_role(self.user_profile, role, acting_user=None)
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

        reset_email_visibility_to_everyone_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER, acting_user=None)
        for role in [UserProfile.ROLE_GUEST, UserProfile.ROLE_MEMBER]:
            if role == UserProfile.ROLE_MEMBER:
                # When changing role from guest to member, peer_add events are also sent
                # to make sure the subscribers info is provided to the clients for the
                # streams added by stream creation event.
                num_events = 7
            else:
                num_events = 5
            with self.verify_action(num_events=num_events) as events:
                do_change_user_role(self.user_profile, role, acting_user=None)
            check_realm_user_update("events[0]", events[0], "role")
            self.assertEqual(events[0]["person"]["role"], role)

            check_user_group_remove_members("events[1]", events[1])
            check_user_group_add_members("events[2]", events[2])

            if role == UserProfile.ROLE_GUEST:
                check_user_group_remove_members("events[3]", events[3])
                check_stream_delete("events[4]", events[4])
            else:
                check_user_group_add_members("events[3]", events[3])
                check_stream_create("events[4]", events[4])
                check_subscription_peer_add("events[5]", events[5])
                check_subscription_peer_add("events[6]", events[6])

    def test_change_user_role_for_restricted_users(self) -> None:
        self.set_up_db_for_testing_user_access()
        self.user_profile = self.example_user("polonius")

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

            num_events = 2
            is_modern_notification_setting = (
                notification_setting in self.user_profile.modern_notification_settings
            )
            if is_modern_notification_setting:
                # The legacy event format is not sent for modern_notification_settings
                # as it exists only for backwards-compatibility with
                # clients that don't support the new user_settings event type.
                # We only send the legacy event for settings added before Feature level 89.
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
                if not is_modern_notification_setting:
                    check_update_global_notifications("events[1]", events[1], setting_value)

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
                if not is_modern_notification_setting:
                    check_update_global_notifications("events[1]", events[1], setting_value)

    def test_change_presence_enabled(self) -> None:
        presence_enabled_setting = "presence_enabled"

        # Disabling presence will lead to the creation of a UserPresence object for the user
        # with a last_connected_time slightly preceding the moment of flipping the setting
        # and last_active_time set to None. The presence API defaults to user_profile.date_joined
        # for backwards compatibility when dealing with a None value. Thus for this test to properly
        # check that the presence event emitted will have "idle" status, we need to simulate
        # the (more realistic) scenario where date_joined is further in the past and not super recent.
        self.user_profile.date_joined = timezone_now() - timedelta(days=15)
        self.user_profile.save()

        for val in [True, False]:
            with self.verify_action(num_events=3) as events:
                do_change_user_setting(
                    self.user_profile,
                    presence_enabled_setting,
                    val,
                    acting_user=self.user_profile,
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

        with self.verify_action(num_events=2) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, "ding", acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], "ding")

    def test_change_desktop_icon_count_display(self) -> None:
        notification_setting = "desktop_icon_count_display"

        with self.verify_action(num_events=2) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 2, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], 2)

        with self.verify_action(num_events=2) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 1, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], 1)

    def test_change_realm_name_in_email_notifications_policy(self) -> None:
        notification_setting = "realm_name_in_email_notifications_policy"

        with self.verify_action(num_events=2) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 3, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], 3)

        with self.verify_action(num_events=2) as events:
            do_change_user_setting(
                self.user_profile, notification_setting, 2, acting_user=self.user_profile
            )
        check_user_settings_update("events[0]", events[0])
        check_update_global_notifications("events[1]", events[1], 2)

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

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_org_type"], Realm.ORG_TYPES["business"]["id"])

        with self.verify_action() as events:
            do_change_realm_org_type(
                realm, Realm.ORG_TYPES["government"]["id"], acting_user=self.user_profile
            )
        check_realm_update("events[0]", events[0], "org_type")

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_org_type"], Realm.ORG_TYPES["government"]["id"])

    def test_realm_update_plan_type(self) -> None:
        realm = self.user_profile.realm
        members_group = NamedUserGroup.objects.get(name=SystemGroups.MEMBERS, realm=realm)
        do_change_realm_permission_group_setting(
            realm, "can_access_all_users_group", members_group, acting_user=None
        )

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_plan_type"], Realm.PLAN_TYPE_SELF_HOSTED)
        self.assertEqual(state_data["zulip_plan_is_not_limited"], True)

        with self.verify_action(num_events=3) as events:
            do_change_realm_plan_type(realm, Realm.PLAN_TYPE_LIMITED, acting_user=self.user_profile)
        check_realm_update("events[0]", events[0], "enable_spectator_access")
        check_realm_update_dict("events[1]", events[1])
        check_realm_update("events[2]", events[2], "plan_type")

        state_data = fetch_initial_state_data(self.user_profile)
        self.assertEqual(state_data["realm_plan_type"], Realm.PLAN_TYPE_LIMITED)
        self.assertEqual(state_data["zulip_plan_is_not_limited"], False)

    def test_realm_emoji_events(self) -> None:
        author = self.example_user("iago")
        with get_test_image_file("img.png") as img_file:
            with self.verify_action() as events:
                check_add_realm_emoji(self.user_profile.realm, "my_emoji", author, img_file)

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

    def test_peer_remove_events_on_changing_bot_owner(self) -> None:
        previous_owner = self.example_user("aaron")
        self.user_profile = self.example_user("iago")
        bot = self.create_test_bot("test2", previous_owner, full_name="Test2 Testerson")
        private_stream = self.make_stream("private_stream", invite_only=True)
        self.make_stream("public_stream")
        self.subscribe(bot, "private_stream")
        self.subscribe(self.example_user("aaron"), "private_stream")
        self.subscribe(bot, "public_stream")
        self.subscribe(self.example_user("aaron"), "public_stream")

        self.make_stream("private_stream_test", invite_only=True)
        self.subscribe(self.example_user("iago"), "private_stream_test")
        self.subscribe(bot, "private_stream_test")

        with self.verify_action(num_events=3) as events:
            do_change_bot_owner(bot, self.user_profile, previous_owner)

        check_realm_bot_update("events[0]", events[0], "owner_id")
        check_realm_user_update("events[1]", events[1], "bot_owner_id")
        check_subscription_peer_remove("events[2]", events[2])
        self.assertEqual(events[2]["stream_ids"], [private_stream.id])

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
            do_update_outgoing_webhook_service(bot, 2, "http://hostname.domain2.com")
        check_realm_bot_update("events[0]", events[0], "services")

    def test_do_deactivate_bot(self) -> None:
        bot = self.create_bot("test")
        with self.verify_action(num_events=2) as events:
            do_deactivate_user(bot, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")
        check_realm_bot_update("events[1]", events[1], "is_active")

    def test_do_deactivate_user(self) -> None:
        user_profile = self.example_user("cordelia")
        with self.verify_action(num_events=1) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")

        do_reactivate_user(user_profile, acting_user=None)
        self.set_up_db_for_testing_user_access()

        # Test that guest users receive event only
        # if they can access the deactivated user.
        user_profile = self.example_user("cordelia")
        self.user_profile = self.example_user("polonius")
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_deactivate_user(user_profile, acting_user=None)

        user_profile = self.example_user("shiva")
        with self.verify_action(num_events=1) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_realm_user_update("events[0]", events[0], "is_active")

        # Guest loses access to deactivated user if the user
        # was not involved in DMs.
        user_profile = self.example_user("hamlet")
        with self.verify_action(num_events=1) as events:
            do_deactivate_user(user_profile, acting_user=None)
        check_realm_user_remove("events[0]", events[0])

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
        with self.verify_action(num_events=3) as events:
            do_reactivate_user(bot, acting_user=None)
        check_realm_bot_update("events[1]", events[1], "is_active")
        check_subscription_peer_add("events[2]", events[2])

        # Test 'peer_add' event for private stream is received only if user is subscribed to it.
        do_deactivate_user(bot, acting_user=None)
        self.subscribe(self.example_user("hamlet"), "Test private stream")
        with self.verify_action(num_events=4) as events:
            do_reactivate_user(bot, acting_user=None)
        check_realm_bot_update("events[1]", events[1], "is_active")
        check_subscription_peer_add("events[2]", events[2])
        check_subscription_peer_add("events[3]", events[3])

        do_deactivate_user(bot, acting_user=None)
        do_deactivate_user(self.example_user("hamlet"), acting_user=None)

        reset_email_visibility_to_everyone_in_zulip_realm()
        bot.refresh_from_db()

        self.user_profile = self.example_user("iago")
        with self.verify_action(num_events=7) as events:
            do_reactivate_user(bot, acting_user=self.example_user("iago"))
        check_realm_bot_update("events[1]", events[1], "is_active")
        check_realm_bot_update("events[2]", events[2], "owner_id")
        check_realm_user_update("events[3]", events[3], "bot_owner_id")
        check_subscription_peer_remove("events[4]", events[4])
        check_stream_delete("events[5]", events[5])

    def test_do_deactivate_realm(self) -> None:
        realm = self.user_profile.realm

        # We delete sessions of all active users when a realm is
        # deactivated, and redirect them to a deactivated page in
        # order to inform that realm/organization has been
        # deactivated.  state_change_expected is False is kinda
        # correct because were one to somehow compute page_params (as
        # this test does), but that's not actually possible.
        with self.verify_action(state_change_expected=False) as events:
            do_deactivate_realm(realm, acting_user=None)
        check_realm_deactivated("events[0]", events[0])

    def test_do_mark_onboarding_step_as_read(self) -> None:
        self.user_profile.tutorial_status = UserProfile.TUTORIAL_WAITING
        self.user_profile.save(update_fields=["tutorial_status"])

        with self.verify_action() as events:
            do_mark_onboarding_step_as_read(self.user_profile, "intro_streams")
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
            with self.verify_action(include_streams=include_streams) as events:
                do_deactivate_stream(stream, acting_user=None)
            check_stream_delete("events[0]", events[0])
            self.assertIsNone(events[0]["streams"][0]["stream_weekly_traffic"])

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

        with self.verify_action(num_events=2) as events:
            do_deactivate_stream(stream, acting_user=None)
        check_stream_delete("events[0]", events[0])
        check_realm_user_remove("events[1]", events[1])
        self.assertEqual(events[1]["person"]["user_id"], hamlet.id)

        # Test that if the subscribers of deactivated stream are involved in
        # DMs with guest, then the guest does not get "remove" event for them.
        stream = get_stream("test_stream2", self.user_profile.realm)
        shiva = self.example_user("shiva")
        iago = self.example_user("iago")
        self.subscribe(shiva, stream.name)
        self.assertCountEqual(
            self.users_subscribed_to_stream(stream.name, realm), [iago, polonius, shiva]
        )

        with self.verify_action(num_events=2) as events:
            do_deactivate_stream(stream, acting_user=None)
        check_stream_delete("events[0]", events[0])
        check_realm_user_remove("events[1]", events[1])
        self.assertEqual(events[1]["person"]["user_id"], iago.id)

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
        messages = [Message.objects.get(id=msg_id), Message.objects.get(id=msg_id_2)]
        with self.verify_action(state_change_expected=True) as events:
            do_delete_messages(self.user_profile.realm, messages)
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
        with self.verify_action(
            state_change_expected=True, bulk_message_deletion=False, num_events=2
        ) as events:
            do_delete_messages(self.user_profile.realm, messages)
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
        with self.verify_action(state_change_expected=True) as events:
            do_delete_messages(self.user_profile.realm, [message])
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
            do_delete_messages(self.user_profile.realm, [message])
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
            do_delete_messages(self.user_profile.realm, [message])
        result = fetch_initial_state_data(user_profile)
        self.assertEqual(result["max_message_id"], -1)

    def test_do_delete_message_with_no_messages(self) -> None:
        with self.verify_action(num_events=0, state_change_expected=False) as events:
            do_delete_messages(self.user_profile.realm, [])
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
            url = response_dict["uri"]
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
            self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test")

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
            return_value=create_dummy_file("test-export.tar.gz"),
        ):
            with stdout_suppressed(), self.assertLogs(level="INFO") as info_logs:
                with self.verify_action(state_change_expected=True, num_events=3) as events:
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
        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED
        ).first()
        assert audit_log_entry is not None
        audit_log_entry_id = audit_log_entry.id
        with self.verify_action(state_change_expected=False, num_events=1) as events:
            self.client_delete(f"/json/export/realm/{audit_log_entry_id}")

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
                with self.verify_action(state_change_expected=False, num_events=2) as events:
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
            bot_creation_policy=Realm.BOT_CREATION_POLICY_TYPES,
            video_chat_provider=[
                Realm.VIDEO_CHAT_PROVIDERS["jitsi_meet"]["id"],
            ],
            jitsi_server_url=["https://jitsi1.example.com", "https://jitsi2.example.com"],
            giphy_rating=[
                Realm.GIPHY_RATING_OPTIONS["disabled"]["id"],
            ],
            default_code_block_language=["python", "javascript"],
            message_content_delete_limit_seconds=[1000, 1100, 1200],
            invite_to_realm_policy=Realm.INVITE_TO_REALM_POLICY_TYPES,
            move_messages_between_streams_policy=Realm.MOVE_MESSAGES_BETWEEN_STREAMS_POLICY_TYPES,
            add_custom_emoji_policy=Realm.COMMON_POLICY_TYPES,
            delete_own_message_policy=Realm.COMMON_MESSAGE_POLICY_TYPES,
            edit_topic_policy=Realm.COMMON_MESSAGE_POLICY_TYPES,
            message_content_edit_limit_seconds=[1000, 1100, 1200, None],
            move_messages_within_stream_limit_seconds=[1000, 1100, 1200],
            move_messages_between_streams_limit_seconds=[1000, 1100, 1200],
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

        if vals[0] != original_val:
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

            with self.verify_action(
                state_change_expected=state_change_expected, num_events=num_events
            ) as events:
                do_set_realm_property(
                    self.user_profile.realm,
                    name,
                    val,
                    acting_user=self.user_profile,
                )

            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data={
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: val,
                        "property": name,
                    },
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

    def do_set_realm_permission_group_setting_test(self, setting_name: str) -> None:
        all_system_user_groups = NamedUserGroup.objects.filter(
            realm=self.user_profile.realm,
            is_system_group=True,
        )

        setting_permission_configuration = Realm.REALM_PERMISSION_GROUP_SETTINGS[setting_name]

        default_group_name = setting_permission_configuration.default_group_name
        default_group = all_system_user_groups.get(name=default_group_name)
        old_group_id = default_group.id

        now = timezone_now()

        do_change_realm_permission_group_setting(
            self.user_profile.realm,
            setting_name,
            default_group,
            acting_user=self.user_profile,
        )

        self.assertEqual(
            RealmAuditLog.objects.filter(
                realm=self.user_profile.realm,
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now,
                acting_user=self.user_profile,
            ).count(),
            1,
        )
        for user_group in all_system_user_groups:
            if user_group.name == default_group_name:
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
                    event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
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

    def test_change_realm_property(self) -> None:
        for prop in Realm.property_types:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_property_test(prop)

        for prop in Realm.REALM_PERMISSION_GROUP_SETTINGS:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_permission_group_setting_test(prop)

    def do_set_realm_user_default_setting_test(self, name: str) -> None:
        bool_tests: List[bool] = [True, False, True]
        test_values: Dict[str, Any] = dict(
            web_font_size_px=[UserProfile.WEB_FONT_SIZE_PX_LEGACY],
            web_line_height_percent=[UserProfile.WEB_LINE_HEIGHT_PERCENT_LEGACY],
            color_scheme=UserProfile.COLOR_SCHEME_CHOICES,
            web_home_view=["recent_topics", "inbox", "all_messages"],
            emojiset=[emojiset["key"] for emojiset in RealmUserDefault.emojiset_choices()],
            demote_inactive_streams=UserProfile.DEMOTE_STREAMS_CHOICES,
            web_mark_read_on_scroll_policy=UserProfile.WEB_MARK_READ_ON_SCROLL_POLICY_CHOICES,
            user_list_style=UserProfile.USER_LIST_STYLE_CHOICES,
            web_stream_unreads_count_display_policy=UserProfile.WEB_STREAM_UNREADS_COUNT_DISPLAY_POLICY_CHOICES,
            desktop_icon_count_display=UserProfile.DESKTOP_ICON_COUNT_DISPLAY_CHOICES,
            notification_sound=["zulip", "ding"],
            email_notifications_batching_period_seconds=[120, 300],
            email_address_visibility=UserProfile.EMAIL_ADDRESS_VISIBILITY_TYPES,
            realm_name_in_email_notifications_policy=UserProfile.REALM_NAME_IN_EMAIL_NOTIFICATIONS_POLICY_CHOICES,
            automatically_follow_topics_policy=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES,
            automatically_unmute_topics_in_muted_streams_policy=UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_CHOICES,
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
            with self.verify_action(state_change_expected=state_change_expected) as events:
                do_set_realm_user_default_setting(
                    realm_user_default,
                    name,
                    val,
                    acting_user=self.user_profile,
                )

            old_value = vals[count]
            self.assertEqual(
                RealmAuditLog.objects.filter(
                    realm=self.user_profile.realm,
                    event_type=RealmAuditLog.REALM_DEFAULT_USER_SETTINGS_CHANGED,
                    event_time__gte=now,
                    acting_user=self.user_profile,
                    extra_data={
                        RealmAuditLog.OLD_VALUE: old_value,
                        RealmAuditLog.NEW_VALUE: val,
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
                event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
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

        test_changes: Dict[str, Any] = dict(
            emojiset=["twitter"],
            default_language=["es", "de", "en"],
            web_home_view=["all_messages", "inbox", "recent_topics"],
            demote_inactive_streams=[2, 3, 1],
            web_mark_read_on_scroll_policy=[2, 3, 1],
            user_list_style=[1, 2, 3],
            web_stream_unreads_count_display_policy=[1, 2, 3],
            web_font_size_px=[12, 16, 18],
            web_line_height_percent=[105, 120, 160],
            color_scheme=[2, 3, 1],
            email_address_visibility=[5, 4, 1, 2, 3],
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
            if legacy_setting:
                # Only settings added before feature level 89
                # generate this event.
                self.assert_length(events, 2)
                check_update_display_settings("events[1]", events[1])

    def test_change_user_settings(self) -> None:
        for prop in UserProfile.property_types:
            # Notification settings have a separate test suite, which
            # handles their separate legacy event type.
            if prop not in UserProfile.notification_setting_types:
                self.do_change_user_settings_test(prop)

    def test_set_user_timezone(self) -> None:
        values = ["America/Denver", "Pacific/Pago_Pago", "Pacific/Galapagos", ""]
        num_events = 3

        for value in values:
            with self.verify_action(num_events=num_events) as events:
                do_change_user_setting(
                    self.user_profile,
                    "timezone",
                    value,
                    acting_user=self.user_profile,
                )

            check_user_settings_update("events[0]", events[0])
            check_update_display_settings("events[1]", events[1])
            check_realm_user_update("events[2]", events[2], "timezone")

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
        # Subscribe to a totally new stream, so it's just Hamlet on it
        with self.verify_action(
            event_types=["subscription"], include_subscribers=include_subscribers
        ) as events:
            self.subscribe(self.example_user("hamlet"), "test_stream")
        check_subscription_add("events[0]", events[0])

        # Add another user to that totally new stream
        with self.verify_action(
            include_subscribers=include_subscribers, state_change_expected=include_subscribers
        ) as events:
            self.subscribe(self.example_user("othello"), "test_stream")
        check_subscription_peer_add("events[0]", events[0])

        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        othello = self.example_user("othello")
        realm = othello.realm
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

        # Update stream privacy - make stream web-public
        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_permission(
                stream,
                invite_only=False,
                history_public_to_subscribers=True,
                is_web_public=True,
                acting_user=self.example_user("hamlet"),
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
                acting_user=self.example_user("hamlet"),
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
                acting_user=self.example_user("hamlet"),
            )
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
        with self.verify_action(
            include_subscribers=include_subscribers, num_events=2, include_streams=False
        ) as events:
            do_change_stream_permission(
                stream,
                invite_only=False,
                history_public_to_subscribers=True,
                is_web_public=False,
                acting_user=self.example_user("hamlet"),
            )

        self.user_profile = self.example_user("hamlet")
        # Update stream stream_post_policy property
        with self.verify_action(include_subscribers=include_subscribers, num_events=3) as events:
            do_change_stream_post_policy(
                stream, Stream.STREAM_POST_POLICY_ADMINS, acting_user=self.example_user("hamlet")
            )
        check_stream_update("events[0]", events[0])
        check_message("events[2]", events[2])

        with self.verify_action(include_subscribers=include_subscribers, num_events=2) as events:
            do_change_stream_message_retention_days(stream, self.example_user("hamlet"), -1)
        check_stream_update("events[0]", events[0])

        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS,
            is_system_group=True,
            realm=self.user_profile.realm,
        )
        with self.verify_action(include_subscribers=include_subscribers, num_events=1) as events:
            do_change_stream_group_based_setting(
                stream,
                "can_remove_subscribers_group",
                moderators_group,
                acting_user=self.example_user("hamlet"),
            )
        check_stream_update("events[0]", events[0])

        # Subscribe to a totally new invite-only stream, so it's just Hamlet on it
        stream = self.make_stream("private", self.user_profile.realm, invite_only=True)
        stream.message_retention_days = 10
        stream.save()

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
        stream.save()

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
