from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.db import connection
from django.test import override_settings
from django.utils.timezone import now as timezone_now
from sqlalchemy.sql import ClauseElement, Select, and_, column, select, table
from sqlalchemy.types import Integer
from typing_extensions import override

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.actions.message_edit import build_message_edit_request, do_update_message
from zerver.actions.reactions import check_add_reaction
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.uploads import do_claim_attachments
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.users import do_deactivate_user
from zerver.lib.avatar import avatar_url
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import render_message_markdown
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.message import (
    get_first_visible_message_id,
    maybe_update_first_visible_message_id,
    update_first_visible_message_id,
)
from zerver.lib.message_cache import MessageDict
from zerver.lib.narrow import (
    LARGER_THAN_MAX_MESSAGE_ID,
    BadNarrowOperatorError,
    NarrowBuilder,
    NarrowParameter,
    add_narrow_conditions,
    exclude_muting_conditions,
    find_first_unread_anchor,
    get_base_query_for_search,
    is_spectator_compatible,
    ok_to_include_history,
    post_process_limited_query,
)
from zerver.lib.narrow_helpers import NeverNegatedNarrowTerm
from zerver.lib.narrow_predicate import build_narrow_predicate
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.streams import StreamDict, create_streams_if_needed, get_public_streams_queryset
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, get_user_messages, queries_captured
from zerver.lib.topic import MATCH_TOPIC, RESOLVED_TOPIC_PREFIX, TOPIC_NAME, messages_for_topic
from zerver.lib.types import UserDisplayRecipient
from zerver.lib.upload import create_attachment
from zerver.lib.url_encoding import message_link_url
from zerver.lib.user_groups import get_recursive_membership_groups
from zerver.lib.user_topics import set_topic_visibility_policy
from zerver.models import (
    Attachment,
    Message,
    Realm,
    Recipient,
    Subscription,
    UserMessage,
    UserProfile,
    UserTopic,
)
from zerver.models.realms import get_realm
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.streams import get_stream
from zerver.views.message_fetch import get_messages_backend

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


@dataclass
class InvalidParam:
    value: object
    expected_error: str


def get_sqlalchemy_sql(query: ClauseElement) -> str:
    with get_sqlalchemy_connection() as conn:
        dialect = conn.dialect
    comp = query.compile(dialect=dialect)
    return str(comp)


def get_sqlalchemy_query_params(query: ClauseElement) -> dict[str, object]:
    with get_sqlalchemy_connection() as conn:
        dialect = conn.dialect
    comp = query.compile(dialect=dialect)
    return comp.params


def get_recipient_id_for_channel_name(realm: Realm, channel_name: str) -> int | None:
    channel = get_stream(channel_name, realm)
    return channel.recipient.id if channel.recipient is not None else None


def mute_channel(realm: Realm, user_profile: UserProfile, channel_name: str) -> None:
    channel = get_stream(channel_name, realm)
    recipient = channel.recipient
    subscription = Subscription.objects.get(recipient=recipient, user_profile=user_profile)
    subscription.is_muted = True
    subscription.save()


def first_visible_id_as(message_id: int) -> Any:
    return mock.patch(
        "zerver.lib.narrow.get_first_visible_message_id",
        return_value=message_id,
    )


class NarrowBuilderTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.user_profile = self.example_user("hamlet")
        self.builder = NarrowBuilder(self.user_profile, column("id", Integer), self.realm)
        self.raw_query = select(column("id", Integer)).select_from(table("zerver_message"))
        self.hamlet_email = self.example_user("hamlet").email
        self.othello_email = self.example_user("othello").email

    def test_add_term_using_not_defined_operator(self) -> None:
        term = NarrowParameter(operator="not-defined", operand="any")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_channel_operator(self) -> None:
        term = NarrowParameter(operator="channel", operand="Scotland")
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s")

    def test_add_term_using_channel_operator_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="channel", operand="Scotland", negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_channel_operator_and_non_existing_operand_should_raise_error(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="channel", operand="non-existing-channel")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_channels_operator_and_invalid_operand_should_raise_error(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="channels", operand="invalid_operands")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_channels_operator_and_public_operand(self) -> None:
        term = NarrowParameter(operator="channels", operand="public")
        self._do_add_term_test(
            term,
            "WHERE recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

        # Add new channels
        channel_dicts: list[StreamDict] = [
            {
                "name": "public-channel",
                "description": "Public channel with public history",
            },
            {
                "name": "private-channel",
                "description": "Private channel with non-public history",
                "invite_only": True,
            },
            {
                "name": "private-channel-with-history",
                "description": "Private channel with public history",
                "invite_only": True,
                "history_public_to_subscribers": True,
            },
        ]
        realm = get_realm("zulip")
        created, existing = create_streams_if_needed(realm, channel_dicts)
        self.assert_length(created, 3)
        self.assert_length(existing, 0)

        # Number of recipient ids will increase by 1 and not 3
        self._do_add_term_test(
            term,
            "WHERE recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

    def test_add_term_using_channels_operator_and_public_operand_negated(self) -> None:
        term = NarrowParameter(operator="channels", operand="public", negated=True)
        self._do_add_term_test(
            term,
            "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))",
        )

        # Add new channels
        channel_dicts: list[StreamDict] = [
            {
                "name": "public-channel",
                "description": "Public channel with public history",
            },
            {
                "name": "private-channel",
                "description": "Private channel with non-public history",
                "invite_only": True,
            },
            {
                "name": "private-channel-with-history",
                "description": "Private channel with public history",
                "invite_only": True,
                "history_public_to_subscribers": True,
            },
        ]
        realm = get_realm("zulip")
        created, existing = create_streams_if_needed(realm, channel_dicts)
        self.assert_length(created, 3)
        self.assert_length(existing, 0)

        # Number of recipient ids will increase by 1 and not 3
        self._do_add_term_test(
            term,
            "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))",
        )

    def test_add_term_using_is_operator_and_dm_operand(self) -> None:
        term = NarrowParameter(operator="is", operand="dm")
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_dm_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="is", operand="dm", negated=True)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) = %(param_1)s")

    def test_add_term_using_is_operator_and_non_dm_operand(self) -> None:
        for operand in ["starred", "mentioned", "alerted"]:
            term = NarrowParameter(operator="is", operand=operand)
            self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_and_unread_operand(self) -> None:
        term = NarrowParameter(operator="is", operand="unread")
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) = %(param_1)s")

    def test_add_term_using_is_operator_and_unread_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="is", operand="unread", negated=True)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_non_dm_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="is", operand="starred", negated=True)
        where_clause = "WHERE (flags & %(flags_1)s) = %(param_1)s"
        params = dict(
            flags_1=UserMessage.flags.starred.mask,
            param_1=0,
        )
        self._do_add_term_test(term, where_clause, params)

        term = NarrowParameter(operator="is", operand="alerted", negated=True)
        where_clause = "WHERE (flags & %(flags_1)s) = %(param_1)s"
        params = dict(
            flags_1=UserMessage.flags.has_alert_word.mask,
            param_1=0,
        )
        self._do_add_term_test(term, where_clause, params)

        term = NarrowParameter(operator="is", operand="mentioned", negated=True)
        where_clause = "WHERE (flags & %(flags_1)s) = %(param_1)s"
        mention_flags_mask = (
            UserMessage.flags.mentioned.mask
            | UserMessage.flags.stream_wildcard_mentioned.mask
            | UserMessage.flags.topic_wildcard_mentioned.mask
            | UserMessage.flags.group_mentioned.mask
        )
        params = dict(
            flags_1=mention_flags_mask,
            param_1=0,
        )
        self._do_add_term_test(term, where_clause, params)

    def test_add_term_using_is_operator_for_resolved_topics(self) -> None:
        term = NarrowParameter(operator="is", operand="resolved")
        self._do_add_term_test(
            term, "WHERE (subject LIKE %(subject_1)s || '%%') AND is_channel_message"
        )

    def test_add_term_using_is_operator_for_negated_resolved_topics(self) -> None:
        term = NarrowParameter(operator="is", operand="resolved", negated=True)
        self._do_add_term_test(
            term, "WHERE NOT ((subject LIKE %(subject_1)s || '%%') AND is_channel_message)"
        )

    def test_add_term_using_is_operator_for_followed_topics(self) -> None:
        term = NarrowParameter(operator="is", operand="followed", negated=False)
        self._do_add_term_test(
            term,
            "EXISTS (SELECT 1 \nFROM zerver_usertopic \nWHERE zerver_usertopic.user_profile_id = %(param_1)s AND zerver_usertopic.visibility_policy = %(param_2)s AND upper(zerver_usertopic.topic_name) = upper(zerver_message.subject) AND zerver_message.is_channel_message AND zerver_usertopic.recipient_id = zerver_message.recipient_id)",
        )

    def test_add_term_using_is_operator_for_negated_followed_topics(self) -> None:
        term = NarrowParameter(operator="is", operand="followed", negated=True)
        self._do_add_term_test(
            term,
            "NOT (EXISTS (SELECT 1 \nFROM zerver_usertopic \nWHERE zerver_usertopic.user_profile_id = %(param_1)s AND zerver_usertopic.visibility_policy = %(param_2)s AND upper(zerver_usertopic.topic_name) = upper(zerver_message.subject) AND zerver_message.is_channel_message AND zerver_usertopic.recipient_id = zerver_message.recipient_id))",
        )

    def test_add_term_using_is_operator_for_muted_topics(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = NarrowParameter(operator="is", operand="muted", negated=False)
        self._do_add_term_test(term, "WHERE recipient_id IN (__[POSTCOMPILE_recipient_id_1])")

    def test_add_term_using_is_operator_for_negated_muted_topics(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = NarrowParameter(operator="is", operand="muted", negated=True)
        self._do_add_term_test(term, "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))")

    def test_add_term_using_non_supported_operator_should_raise_error(self) -> None:
        term = NarrowParameter(operator="is", operand="non_supported")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_topic_operator_and_lunch_operand(self) -> None:
        term = NarrowParameter(operator="topic", operand="lunch")
        self._do_add_term_test(
            term, "WHERE upper(subject) = upper(%(param_1)s) AND is_channel_message"
        )

    def test_add_term_using_topic_operator_lunch_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="topic", operand="lunch", negated=True)
        self._do_add_term_test(
            term, "WHERE NOT (upper(subject) = upper(%(param_1)s) AND is_channel_message)"
        )

    def test_add_term_using_topic_operator_and_personal_operand(self) -> None:
        term = NarrowParameter(operator="topic", operand="personal")
        self._do_add_term_test(
            term, "WHERE upper(subject) = upper(%(param_1)s) AND is_channel_message"
        )

    def test_add_term_using_topic_operator_personal_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="topic", operand="personal", negated=True)
        self._do_add_term_test(
            term, "WHERE NOT (upper(subject) = upper(%(param_1)s) AND is_channel_message)"
        )

    def test_add_term_using_sender_operator(self) -> None:
        term = NarrowParameter(operator="sender", operand=self.othello_email)
        self._do_add_term_test(term, "WHERE sender_id = %(param_1)s")

    def test_add_term_using_sender_operator_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="sender", operand=self.othello_email, negated=True)
        self._do_add_term_test(term, "WHERE sender_id != %(param_1)s")

    def test_add_term_using_sender_operator_with_non_existing_user_as_operand(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="sender", operand="non-existing@zulip.com")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_operator_and_not_the_same_user_as_operand(self) -> None:
        term = NarrowParameter(operator="dm", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s)",
        )

    def test_negated_is_dm_with_dm_operator(self) -> None:
        expected_error_message = (
            "Invalid narrow operator: No message can be both a channel message and direct message"
        )
        is_term = NarrowParameter(operator="is", operand="dm", negated=True)
        self._build_query(is_term)

        topic_term = NarrowParameter(operator="dm", operand=self.othello_email)
        with self.assertRaises(BadNarrowOperatorError) as error:
            self._build_query(topic_term)
        self.assertEqual(expected_error_message, str(error.exception))

    def test_combined_channel_dm(self) -> None:
        expected_error_message = (
            "Invalid narrow operator: No message can be both a channel message and direct message"
        )
        term1 = NarrowParameter(operator="dm", operand=self.othello_email)
        self._build_query(term1)

        topic_term = NarrowParameter(operator="topic", operand="bogus")
        with self.assertRaises(BadNarrowOperatorError) as error:
            self._build_query(topic_term)
        self.assertEqual(expected_error_message, str(error.exception))

        channels_term = NarrowParameter(operator="channels", operand="public")
        with self.assertRaises(BadNarrowOperatorError) as error:
            self._build_query(channels_term)
        self.assertEqual(expected_error_message, str(error.exception))

    def test_combined_channel_with_negated_is_dm(self) -> None:
        dm_term = NarrowParameter(operator="is", operand="dm", negated=True)
        self._build_query(dm_term)

        channel_term = NarrowParameter(operator="channels", operand="public")
        self._build_query(channel_term)

    def test_combined_negated_channel_with_is_dm(self) -> None:
        dm_term = NarrowParameter(operator="is", operand="dm")
        self._build_query(dm_term)

        channel_term = NarrowParameter(operator="channels", operand="public", negated=True)
        self._build_query(channel_term)

    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand(self) -> None:
        term = NarrowParameter(operator="dm", operand=self.hamlet_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_and_self_and_user_as_operand(self) -> None:
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand(self) -> None:
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_comma_noise(self) -> None:
        term = NarrowParameter(operator="dm", operand=" ,,, ,,, ,")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_including_operator_with_logged_in_user_email(self) -> None:
        term = NarrowParameter(operator="dm-including", operand=self.hamlet_email)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_dm_including_operator_with_different_user_email(self) -> None:
        # Test without any such group direct messages existing
        term = NarrowParameter(operator="dm-including", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3]))",
        )

        # Test with at least one such group direct messages existing
        self.send_group_direct_message(
            self.user_profile, [self.example_user("othello"), self.example_user("cordelia")]
        )

        term = NarrowParameter(operator="dm-including", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3]))",
        )

    def test_add_term_using_dm_including_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-including", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    def test_add_term_using_dm_including_operator_without_personal_recipient(self) -> None:
        # Dropping the personal recipient for Othello
        othello = self.example_user("othello")
        othello.recipient = None
        othello.save()

        term = NarrowParameter(operator="dm-including", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

    def test_add_term_using_id_operator_integer(self) -> None:
        term = NarrowParameter(operator="id", operand=555)
        self._do_add_term_test(term, "WHERE id = %(param_1)s")

    def test_add_term_using_id_operator_string(self) -> None:
        term = NarrowParameter(operator="id", operand="555")
        self._do_add_term_test(term, "WHERE id = %(param_1)s")

    def test_add_term_using_id_operator_invalid(self) -> None:
        term = NarrowParameter(operator="id", operand="")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

        term = NarrowParameter(operator="id", operand="notanint")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

        term = NarrowParameter(operator="id", operand=str(Message.MAX_POSSIBLE_MESSAGE_ID + 1))
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_id_operator_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="id", operand=555, negated=True)
        self._do_add_term_test(term, "WHERE id != %(param_1)s")

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator(self) -> None:
        term = NarrowParameter(operator="search", operand='"french fries"')
        self._do_add_term_test(
            term,
            "WHERE (content ILIKE %(content_1)s OR subject ILIKE %(subject_1)s AND is_channel_message) AND (search_tsvector @@ plainto_tsquery(%(param_4)s, %(param_5)s))",
        )

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="search", operand='"french fries"', negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT (content ILIKE %(content_1)s OR subject ILIKE %(subject_1)s AND is_channel_message) AND NOT (search_tsvector @@ plainto_tsquery(%(param_4)s, %(param_5)s))",
        )

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_pgroonga(self) -> None:
        term = NarrowParameter(operator="search", operand='"french fries"')
        self._do_add_term_test(term, "WHERE search_pgroonga &@~ escape_html(%(escape_html_1)s)")

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_and_negated_pgroonga(self) -> None:  # NEGATED
        term = NarrowParameter(operator="search", operand='"french fries"', negated=True)
        self._do_add_term_test(
            term, "WHERE NOT (search_pgroonga &@~ escape_html(%(escape_html_1)s))"
        )

    def test_add_term_using_has_operator_and_attachment_operand(self) -> None:
        term = NarrowParameter(operator="has", operand="attachment")
        self._do_add_term_test(term, "WHERE has_attachment")

    def test_add_term_using_has_operator_attachment_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="has", operand="attachment", negated=True)
        self._do_add_term_test(term, "WHERE NOT has_attachment")

    def test_add_term_using_has_operator_and_image_operand(self) -> None:
        term = NarrowParameter(operator="has", operand="image")
        self._do_add_term_test(term, "WHERE has_image")

    def test_add_term_using_has_operator_image_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="has", operand="image", negated=True)
        self._do_add_term_test(term, "WHERE NOT has_image")

    def test_add_term_using_has_operator_and_link_operand(self) -> None:
        term = NarrowParameter(operator="has", operand="link")
        self._do_add_term_test(term, "WHERE has_link")

    def test_add_term_using_has_operator_link_operand_and_negated(self) -> None:  # NEGATED
        term = NarrowParameter(operator="has", operand="link", negated=True)
        self._do_add_term_test(term, "WHERE NOT has_link")

    def test_add_term_using_has_operator_and_reaction_operand(self) -> None:
        term = NarrowParameter(operator="has", operand="reaction")
        self._do_add_term_test(
            term,
            "EXISTS (SELECT 1 \nFROM zerver_reaction \nWHERE zerver_message.id = zerver_reaction.message_id)",
        )

    def test_add_term_using_has_operator_and_reaction_operand_and_negated(self) -> None:
        term = NarrowParameter(operator="has", operand="reaction", negated=True)
        self._do_add_term_test(
            term,
            "NOT (EXISTS (SELECT 1 \nFROM zerver_reaction \nWHERE zerver_message.id = zerver_reaction.message_id))",
        )

    def test_add_term_using_has_operator_non_supported_operand_should_raise_error(self) -> None:
        term = NarrowParameter(operator="has", operand="non_supported")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_in_operator(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = NarrowParameter(operator="in", operand="home")
        self._do_add_term_test(term, "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))")

    def test_add_term_using_in_operator_and_negated(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = NarrowParameter(operator="in", operand="home", negated=True)
        self._do_add_term_test(term, "WHERE recipient_id IN (__[POSTCOMPILE_recipient_id_1])")

    def test_add_term_using_in_operator_and_all_operand(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = NarrowParameter(operator="in", operand="all")
        query = self._build_query(term)
        self.assertEqual(get_sqlalchemy_sql(query), "SELECT id \nFROM zerver_message")

    def test_add_term_using_in_operator_all_operand_and_negated(self) -> None:
        # negated = True should not change anything
        mute_channel(self.realm, self.user_profile, "Verona")
        term = NarrowParameter(operator="in", operand="all", negated=True)
        query = self._build_query(term)
        self.assertEqual(get_sqlalchemy_sql(query), "SELECT id \nFROM zerver_message")

    def test_add_term_using_in_operator_and_not_defined_operand(self) -> None:
        term = NarrowParameter(operator="in", operand="not_defined")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_near_operator(self) -> None:
        term = NarrowParameter(operator="near", operand="operand")
        query = self._build_query(term)
        self.assertEqual(get_sqlalchemy_sql(query), "SELECT id \nFROM zerver_message")

    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator(self) -> None:
        term = NarrowParameter(operator="dm-with", operand=self.hamlet_email)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_dm_with_operator_with_different_user_email(self) -> None:
        # Test without any such group direct messages existing
        term = NarrowParameter(operator="dm-with", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3]))",
        )

        # Test with at least one such group direct messages existing
        self.send_group_direct_message(
            self.user_profile, [self.example_user("othello"), self.example_user("cordelia")]
        )

        term = NarrowParameter(operator="dm-with", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3]))",
        )

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    def test_add_term_using_dm_with_operator_without_personal_recipient(self) -> None:
        # Dropping the personal recipient for Othello
        othello = self.example_user("othello")
        othello.recipient = None
        othello.save()

        term = NarrowParameter(operator="dm-with", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
            term,
            "WHERE NOT (content ILIKE %(content_1)s OR subject ILIKE %(subject_1)s AND is_channel_message) AND NOT (search_tsvector @@ plainto_tsquery(%(param_4)s, %(param_5)s))",
        )

    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_the_same_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")

        # Make the direct message group for self messages
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id])

        term = NarrowParameter(operator="dm", operand=hamlet.email)
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    @override_settings(PREFER_DIRECT_MESSAGE_GROUP=True)
    def test_add_term_using_dm_operator_and_self_and_user_as_operand_when_direct_message_group_exists(
        self,
    ) -> None:
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")

        # Make the direct message group for 1:1 messages between hamlet and othello
        direct_message_group = get_or_create_direct_message_group(id_list=[hamlet.id, othello.id])

        term = NarrowParameter(operator="dm", operand=f"{hamlet.email},{othello.email}")
        params = {"recipient_id_1": direct_message_group.recipient_id}
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s", params)

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group(
        self,
    ) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = NarrowParameter(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_direct_message_group_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the direct message group first
        get_or_create_direct_message_group(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = NarrowParameter(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = NarrowParameter(
            operator="dm", operand=self.othello_email + ",non-existing@zulip.com"
        )
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_with_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = NarrowParameter(operator="dm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=False)
    @override_settings(USING_PGROONGA=True)
    @override_settings(USING_PGROONGA=True)
    def test_has_reaction(self) -> None:
        self.login("iago")
        has_reaction_narrow = orjson.dumps([dict(operator="has", operand="reaction")]).decode()

        msg_id = self.send_stream_message(self.example_user("hamlet"), "Denmark", content="Hey")
        result = self.client_get(
            "/json/messages",
            dict(narrow=has_reaction_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)
        check_add_reaction(
            self.example_user("hamlet"), msg_id, "hamburger", "1f354", "unicode_emoji"
        )
        result = self.client_get(
            "/json/messages",
            dict(narrow=has_reaction_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)

        msg_id = self.send_personal_message(
            self.example_user("iago"), self.example_user("cordelia"), "Hello Cordelia"
        )
        result = self.client_get(
            "/json/messages",
            dict(narrow=has_reaction_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)
        check_add_reaction(self.example_user("iago"), msg_id, "hamburger", "1f354", "unicode_emoji")
        result = self.client_get(
            "/json/messages",
            dict(narrow=has_reaction_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)


class MessageIsTest(ZulipTestCase):
    def test_message_is_followed(self) -> None:
        self.login("iago")
        is_followed_narrow = orjson.dumps([dict(operator="is", operand="followed")]).decode()

        # Sending a message in a topic that isn't followed by the user.
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="hey")
        result = self.client_get(
            "/json/messages",
            dict(narrow=is_followed_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)

        stream_id = self.get_stream_id("Denmark", self.example_user("hamlet").realm)

        # Following the topic.
        payload = {
            "stream_id": stream_id,
            "topic": "hey",
            "visibility_policy": int(UserTopic.VisibilityPolicy.FOLLOWED),
        }
        self.client_post("/json/user_topics", payload)
        result = self.client_get(
            "/json/messages",
            dict(narrow=is_followed_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)

    def test_message_is_muted(self) -> None:
        self.login("iago")
        is_muted_narrow = orjson.dumps([dict(operator="is", operand="muted")]).decode()
        is_unmuted_narrow = orjson.dumps(
            [dict(operator="is", operand="muted", negated=True)]
        ).decode()
        in_home_narrow = orjson.dumps([dict(operator="in", operand="home")]).decode()
        notin_home_narrow = orjson.dumps(
            [dict(operator="in", operand="home", negated=True)]
        ).decode()

        # Have another user generate a message in a topic that isn't muted by the user.
        msg_id = self.send_stream_message(self.example_user("hamlet"), "Denmark", topic_name="hey")
        result = self.client_get(
            "/json/messages",
            dict(narrow=is_muted_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)
        result = self.client_get(
            "/json/messages",
            dict(narrow=is_unmuted_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)
        result = self.client_get(
            "/json/messages",
            dict(narrow=in_home_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)
        result = self.client_get(
            "/json/messages",
            dict(narrow=notin_home_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)

        stream_id = self.get_stream_id("Denmark", self.example_user("hamlet").realm)

        # Mute the topic.
        payload = {
            "stream_id": stream_id,
            "topic": "hey",
            "visibility_policy": int(UserTopic.VisibilityPolicy.MUTED),
        }
        self.client_post("/json/user_topics", payload)
        result = self.client_get(
            "/json/messages",
            dict(narrow=is_muted_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)

        result = self.client_get(
            "/json/messages",
            dict(narrow=is_unmuted_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)

        result = self.client_get(
            "/json/messages",
            dict(narrow=in_home_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 0)
        result = self.client_get(
            "/json/messages",
            dict(narrow=notin_home_narrow, anchor=msg_id, num_before=0, num_after=0),
        )
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)
        # We could do more tests, but test_exclude_muting_conditions
        # covers that code path pretty well.


class MessageVisibilityTest(ZulipTestCase):
    def test_update_first_visible_message_id(self) -> None:
        Message.objects.all().delete()
        message_ids = [
            self.send_stream_message(self.example_user("othello"), "Scotland") for i in range(15)
        ]

        # If message_visibility_limit is None update_first_visible_message_id
        # should set first_visible_message_id to 0
        realm = get_realm("zulip")
        realm.message_visibility_limit = None
        # Setting to a random value other than 0 as the default value of
        # first_visible_message_id is 0
        realm.first_visible_message_id = 5
        realm.save()
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), 0)

        realm.message_visibility_limit = 10
        realm.save()
        expected_message_id = message_ids[5]
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), expected_message_id)

        # If the message_visibility_limit is greater than number of messages
        # get_first_visible_message_id should return 0
        realm.message_visibility_limit = 50
        realm.save()
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), 0)

    def test_maybe_update_first_visible_message_id(self) -> None:
        realm = get_realm("zulip")
        lookback_hours = 30

        realm.message_visibility_limit = None
        realm.save()

        end_time = timezone_now() - timedelta(hours=lookback_hours - 5)
        stat = COUNT_STATS["messages_sent:is_bot:hour"]

        RealmCount.objects.create(realm=realm, property=stat.property, end_time=end_time, value=5)
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_not_called()

        realm.message_visibility_limit = 10
        realm.save()
        RealmCount.objects.all().delete()
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_not_called()

        RealmCount.objects.create(realm=realm, property=stat.property, end_time=end_time, value=5)
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_called_once_with(realm)


class PersonalMessagesTest(ZulipTestCase):
    def test_pm_message_url(self) -> None:
        realm = get_realm("zulip")
        message = dict(
            type="personal",
            id=555,
            display_recipient=[
                dict(id=77),
                dict(id=80),
            ],
        )
        url = message_link_url(
            realm=realm,
            message=message,
        )
        self.assertEqual(url, "http://zulip.testserver/#narrow/dm/77,80/near/555")

        url = message_link_url(
            realm=realm,
            message=message,
            conversation_link=True,
        )
        self.assertEqual(url, "http://zulip.testserver/#narrow/dm/77,80/with/555")
