from datetime import timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Union
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
from zerver.actions.message_edit import do_update_message
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
    exclude_muting_conditions,
    find_first_unread_anchor,
    is_spectator_compatible,
    ok_to_include_history,
    post_process_limited_query,
)
from zerver.lib.narrow_helpers import NarrowTerm
from zerver.lib.narrow_predicate import build_narrow_predicate
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.streams import StreamDict, create_streams_if_needed, get_public_streams_queryset
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, get_user_messages, queries_captured
from zerver.lib.topic import MATCH_TOPIC, RESOLVED_TOPIC_PREFIX, TOPIC_NAME
from zerver.lib.types import UserDisplayRecipient
from zerver.lib.upload.base import create_attachment
from zerver.lib.url_encoding import near_message_url
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
from zerver.models.recipients import get_or_create_huddle
from zerver.models.streams import get_stream
from zerver.views.message_fetch import get_messages_backend

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


def get_sqlalchemy_sql(query: ClauseElement) -> str:
    with get_sqlalchemy_connection() as conn:
        dialect = conn.dialect
    comp = query.compile(dialect=dialect)
    return str(comp)


def get_sqlalchemy_query_params(query: ClauseElement) -> Dict[str, object]:
    with get_sqlalchemy_connection() as conn:
        dialect = conn.dialect
    comp = query.compile(dialect=dialect)
    return comp.params


def get_recipient_id_for_channel_name(realm: Realm, channel_name: str) -> Optional[int]:
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
        term = dict(operator="not-defined", operand="any")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_channel_operator(self) -> None:
        term = dict(operator="channel", operand="Scotland")
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s")

    def test_add_term_using_channel_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator="channel", operand="Scotland", negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_channel_operator_and_non_existing_operand_should_raise_error(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="channel", operand="non-existing-channel")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_channels_operator_and_invalid_operand_should_raise_error(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="channels", operand="invalid_operands")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_channels_operator_and_public_operand(self) -> None:
        term = dict(operator="channels", operand="public")
        self._do_add_term_test(
            term,
            "WHERE recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

        # Add new channels
        channel_dicts: List[StreamDict] = [
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
        term = dict(operator="channels", operand="public", negated=True)
        self._do_add_term_test(
            term,
            "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))",
        )

        # Add new channels
        channel_dicts: List[StreamDict] = [
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
        term = dict(operator="is", operand="dm")
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_dm_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="is", operand="dm", negated=True)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) = %(param_1)s")

    def test_add_term_using_is_operator_and_non_dm_operand(self) -> None:
        for operand in ["starred", "mentioned", "alerted"]:
            term = dict(operator="is", operand=operand)
            self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_and_unread_operand(self) -> None:
        term = dict(operator="is", operand="unread")
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) = %(param_1)s")

    def test_add_term_using_is_operator_and_unread_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="is", operand="unread", negated=True)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_non_dm_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="is", operand="starred", negated=True)
        where_clause = "WHERE (flags & %(flags_1)s) = %(param_1)s"
        params = dict(
            flags_1=UserMessage.flags.starred.mask,
            param_1=0,
        )
        self._do_add_term_test(term, where_clause, params)

        term = dict(operator="is", operand="alerted", negated=True)
        where_clause = "WHERE (flags & %(flags_1)s) = %(param_1)s"
        params = dict(
            flags_1=UserMessage.flags.has_alert_word.mask,
            param_1=0,
        )
        self._do_add_term_test(term, where_clause, params)

        term = dict(operator="is", operand="mentioned", negated=True)
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
        term = dict(operator="is", operand="resolved")
        self._do_add_term_test(term, "WHERE (subject LIKE %(subject_1)s || '%%'")

    def test_add_term_using_is_operator_for_negated_resolved_topics(self) -> None:
        term = dict(operator="is", operand="resolved", negated=True)
        self._do_add_term_test(term, "WHERE (subject NOT LIKE %(subject_1)s || '%%'")

    def test_add_term_using_non_supported_operator_should_raise_error(self) -> None:
        term = dict(operator="is", operand="non_supported")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_topic_operator_and_lunch_operand(self) -> None:
        term = dict(operator="topic", operand="lunch")
        self._do_add_term_test(term, "WHERE upper(subject) = upper(%(param_1)s)")

    def test_add_term_using_topic_operator_lunch_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="topic", operand="lunch", negated=True)
        self._do_add_term_test(term, "WHERE upper(subject) != upper(%(param_1)s)")

    def test_add_term_using_topic_operator_and_personal_operand(self) -> None:
        term = dict(operator="topic", operand="personal")
        self._do_add_term_test(term, "WHERE upper(subject) = upper(%(param_1)s)")

    def test_add_term_using_topic_operator_personal_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="topic", operand="personal", negated=True)
        self._do_add_term_test(term, "WHERE upper(subject) != upper(%(param_1)s)")

    def test_add_term_using_sender_operator(self) -> None:
        term = dict(operator="sender", operand=self.othello_email)
        self._do_add_term_test(term, "WHERE sender_id = %(param_1)s")

    def test_add_term_using_sender_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator="sender", operand=self.othello_email, negated=True)
        self._do_add_term_test(term, "WHERE sender_id != %(param_1)s")

    def test_add_term_using_sender_operator_with_non_existing_user_as_operand(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="sender", operand="non-existing@zulip.com")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_operator_and_not_the_same_user_as_operand(self) -> None:
        term = dict(operator="dm", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s)",
        )

    def test_combined_channel_dm(self) -> None:
        expected_error_message = (
            "Invalid narrow operator: No message can be both a channel message and direct message"
        )
        term1 = dict(operator="dm", operand=self.othello_email)
        self._build_query(term1)

        topic_term = dict(operator="topic", operand="bogus")
        with self.assertRaises(BadNarrowOperatorError) as error:
            self._build_query(topic_term)
        self.assertEqual(expected_error_message, str(error.exception))

        channels_term = dict(operator="channels", operand="public")
        with self.assertRaises(BadNarrowOperatorError) as error:
            self._build_query(channels_term)
        self.assertEqual(expected_error_message, str(error.exception))

    def test_add_term_using_dm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="dm", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand(self) -> None:
        term = dict(operator="dm", operand=self.hamlet_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s",
        )

    def test_add_term_using_dm_operator_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="dm", operand=self.hamlet_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s)",
        )

    def test_add_term_using_dm_operator_and_self_and_user_as_operand(self) -> None:
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = dict(operator="dm", operand=myself_and_other)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s)",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_huddle(self) -> None:
        # If the group doesn't exist, it's a flat false
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = dict(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE false")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand(self) -> None:
        # Make the huddle first
        get_or_create_huddle(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = dict(operator="dm", operand=two_others)
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s")

    def test_add_term_using_dm_operator_self_and_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        myself_and_other = (
            f"{self.example_user('hamlet').email},{self.example_user('othello').email}"
        )
        term = dict(operator="dm", operand=myself_and_other, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s))",
        )

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_no_huddle_and_negated(
        self,
    ) -> None:  # NEGATED
        # If the group doesn't exist, it's a flat true
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = dict(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE true")

    def test_add_term_using_dm_operator_more_than_one_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        # Make the huddle first
        get_or_create_huddle(
            [
                self.example_user("hamlet").id,
                self.example_user("cordelia").id,
                self.example_user("othello").id,
            ]
        )
        two_others = f"{self.example_user('cordelia').email},{self.example_user('othello').email}"
        term = dict(operator="dm", operand=two_others, negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_dm_operator_with_comma_noise(self) -> None:
        term = dict(operator="dm", operand=" ,,, ,,, ,")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_operator_with_existing_and_non_existing_user_as_operand(
        self,
    ) -> None:
        term = dict(operator="dm", operand=self.othello_email + ",non-existing@zulip.com")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_dm_including_operator_with_logged_in_user_email(self) -> None:
        term = dict(operator="dm-including", operand=self.hamlet_email)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_dm_including_operator_with_different_user_email(self) -> None:
        # Test without any such group direct messages existing
        term = dict(operator="dm-including", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3]))",
        )

        # Test with at least one such group direct messages existing
        self.send_huddle_message(
            self.user_profile, [self.example_user("othello"), self.example_user("cordelia")]
        )

        term = dict(operator="dm-including", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3]))",
        )

    def test_add_term_using_dm_including_operator_with_different_user_email_and_negated(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="dm-including", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND (sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s OR sender_id = %(sender_id_2)s AND recipient_id = %(recipient_id_2)s OR recipient_id IN (__[POSTCOMPILE_recipient_id_3])))",
        )

    def test_add_term_using_id_operator_integer(self) -> None:
        term = dict(operator="id", operand=555)
        self._do_add_term_test(term, "WHERE id = %(param_1)s")

    def test_add_term_using_id_operator_string(self) -> None:
        term = dict(operator="id", operand="555")
        self._do_add_term_test(term, "WHERE id = %(param_1)s")

    def test_add_term_using_id_operator_invalid(self) -> None:
        term = dict(operator="id", operand="")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

        term = dict(operator="id", operand="notanint")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_id_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator="id", operand=555, negated=True)
        self._do_add_term_test(term, "WHERE id != %(param_1)s")

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator(self) -> None:
        term = dict(operator="search", operand='"french fries"')
        self._do_add_term_test(
            term,
            "WHERE (content ILIKE %(content_1)s OR subject ILIKE %(subject_1)s) AND (search_tsvector @@ plainto_tsquery(%(param_4)s, %(param_5)s))",
        )

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator="search", operand='"french fries"', negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT (content ILIKE %(content_1)s OR subject ILIKE %(subject_1)s) AND NOT (search_tsvector @@ plainto_tsquery(%(param_4)s, %(param_5)s))",
        )

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_pgroonga(self) -> None:
        term = dict(operator="search", operand='"french fries"')
        self._do_add_term_test(term, "WHERE search_pgroonga &@~ escape_html(%(escape_html_1)s)")

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_and_negated_pgroonga(self) -> None:  # NEGATED
        term = dict(operator="search", operand='"french fries"', negated=True)
        self._do_add_term_test(
            term, "WHERE NOT (search_pgroonga &@~ escape_html(%(escape_html_1)s))"
        )

    def test_add_term_using_has_operator_and_attachment_operand(self) -> None:
        term = dict(operator="has", operand="attachment")
        self._do_add_term_test(term, "WHERE has_attachment")

    def test_add_term_using_has_operator_attachment_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="has", operand="attachment", negated=True)
        self._do_add_term_test(term, "WHERE NOT has_attachment")

    def test_add_term_using_has_operator_and_image_operand(self) -> None:
        term = dict(operator="has", operand="image")
        self._do_add_term_test(term, "WHERE has_image")

    def test_add_term_using_has_operator_image_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="has", operand="image", negated=True)
        self._do_add_term_test(term, "WHERE NOT has_image")

    def test_add_term_using_has_operator_and_link_operand(self) -> None:
        term = dict(operator="has", operand="link")
        self._do_add_term_test(term, "WHERE has_link")

    def test_add_term_using_has_operator_link_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="has", operand="link", negated=True)
        self._do_add_term_test(term, "WHERE NOT has_link")

    def test_add_term_using_has_operator_and_reaction_operand(self) -> None:
        term = dict(operator="has", operand="reaction")
        self._do_add_term_test(
            term,
            "EXISTS (SELECT 1 \nFROM zerver_reaction \nWHERE zerver_message.id = zerver_reaction.message_id)",
        )

    def test_add_term_using_has_operator_and_reaction_operand_and_negated(self) -> None:
        term = dict(operator="has", operand="reaction", negated=True)
        self._do_add_term_test(
            term,
            "NOT (EXISTS (SELECT 1 \nFROM zerver_reaction \nWHERE zerver_message.id = zerver_reaction.message_id))",
        )

    def test_add_term_using_has_operator_non_supported_operand_should_raise_error(self) -> None:
        term = dict(operator="has", operand="non_supported")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_in_operator(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = dict(operator="in", operand="home")
        self._do_add_term_test(term, "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))")

    def test_add_term_using_in_operator_and_negated(self) -> None:
        # negated = True should not change anything
        mute_channel(self.realm, self.user_profile, "Verona")
        term = dict(operator="in", operand="home", negated=True)
        self._do_add_term_test(term, "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))")

    def test_add_term_using_in_operator_and_all_operand(self) -> None:
        mute_channel(self.realm, self.user_profile, "Verona")
        term = dict(operator="in", operand="all")
        query = self._build_query(term)
        self.assertEqual(get_sqlalchemy_sql(query), "SELECT id \nFROM zerver_message")

    def test_add_term_using_in_operator_all_operand_and_negated(self) -> None:
        # negated = True should not change anything
        mute_channel(self.realm, self.user_profile, "Verona")
        term = dict(operator="in", operand="all", negated=True)
        query = self._build_query(term)
        self.assertEqual(get_sqlalchemy_sql(query), "SELECT id \nFROM zerver_message")

    def test_add_term_using_in_operator_and_not_defined_operand(self) -> None:
        term = dict(operator="in", operand="not_defined")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_near_operator(self) -> None:
        term = dict(operator="near", operand="operand")
        query = self._build_query(term)
        self.assertEqual(get_sqlalchemy_sql(query), "SELECT id \nFROM zerver_message")

    def test_add_term_non_web_public_channel_in_web_public_query(self) -> None:
        self.make_stream("non-web-public-channel", realm=self.realm)
        term = dict(operator="channel", operand="non-web-public-channel")
        builder = NarrowBuilder(self.user_profile, column("id", Integer), self.realm, True)

        def _build_query(term: Dict[str, Any]) -> Select:
            return builder.add_term(self.raw_query, term)

        self.assertRaises(BadNarrowOperatorError, _build_query, term)

    # Test "is:private" (legacy alias for "is:dm")
    def test_add_term_using_is_operator_and_private_operand(self) -> None:
        term = dict(operator="is", operand="private")
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) != %(param_1)s")

    def test_add_term_using_is_operator_private_operand_and_negated(self) -> None:  # NEGATED
        term = dict(operator="is", operand="private", negated=True)
        self._do_add_term_test(term, "WHERE (flags & %(flags_1)s) = %(param_1)s")

    # Test that "pm-with" (legacy alias for "dm") works.
    def test_add_term_using_pm_with_operator(self) -> None:
        term = dict(operator="pm-with", operand=self.hamlet_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s",
        )

    # Test that the underscore version of "pm-with" works.
    def test_add_term_using_underscore_version_of_pm_with_operator(self) -> None:
        term = dict(operator="pm_with", operand=self.hamlet_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND sender_id = %(sender_id_1)s AND recipient_id = %(recipient_id_1)s",
        )

    # Test that deprecated "group-pm-with" (replaced by "dm-including" ) works.
    def test_add_term_using_dm_including_operator_with_non_existing_user(self) -> None:
        term = dict(operator="dm-including", operand="non-existing@zulip.com")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_group_pm_operator_and_not_the_same_user_as_operand(self) -> None:
        term = dict(operator="group-pm-with", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

    def test_add_term_using_group_pm_operator_not_the_same_user_as_operand_and_negated(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="group-pm-with", operand=self.othello_email, negated=True)
        self._do_add_term_test(
            term,
            "WHERE NOT ((flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND recipient_id IN (__[POSTCOMPILE_recipient_id_1]))",
        )

    def test_add_term_using_group_pm_operator_with_non_existing_user_as_operand(self) -> None:
        term = dict(operator="group-pm-with", operand="non-existing@zulip.com")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    # Test that the underscore version of "group-pm-with" works.
    def test_add_term_using_underscore_version_of_group_pm_with_operator(self) -> None:
        term = dict(operator="group_pm_with", operand=self.othello_email)
        self._do_add_term_test(
            term,
            "WHERE (flags & %(flags_1)s) != %(param_1)s AND realm_id = %(realm_id_1)s AND recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

    # Test that "stream" (legacy alias for "channel" operator) works.
    def test_add_term_using_stream_operator(self) -> None:
        term = dict(operator="stream", operand="Scotland")
        self._do_add_term_test(term, "WHERE recipient_id = %(recipient_id_1)s")

    def test_add_term_using_stream_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator="stream", operand="Scotland", negated=True)
        self._do_add_term_test(term, "WHERE recipient_id != %(recipient_id_1)s")

    def test_add_term_using_stream_operator_and_non_existing_operand_should_raise_error(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="stream", operand="non-existing-channel")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    # Test that "streams" (legacy alias for "channels" operator) works.
    def test_add_term_using_streams_operator_and_invalid_operand_should_raise_error(
        self,
    ) -> None:  # NEGATED
        term = dict(operator="streams", operand="invalid_operands")
        self.assertRaises(BadNarrowOperatorError, self._build_query, term)

    def test_add_term_using_streams_operator_and_public_operand(self) -> None:
        term = dict(operator="streams", operand="public")
        self._do_add_term_test(
            term,
            "WHERE recipient_id IN (__[POSTCOMPILE_recipient_id_1])",
        )

    def test_add_term_using_streams_operator_and_public_operand_negated(self) -> None:
        term = dict(operator="streams", operand="public", negated=True)
        self._do_add_term_test(
            term,
            "WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1]))",
        )

    def _do_add_term_test(
        self, term: Dict[str, Any], where_clause: str, params: Optional[Dict[str, Any]] = None
    ) -> None:
        query = self._build_query(term)
        if params is not None:
            actual_params = get_sqlalchemy_query_params(query)
            self.assertEqual(actual_params, params)
        self.assertIn(where_clause, get_sqlalchemy_sql(query))

    def _build_query(self, term: Dict[str, Any]) -> Select:
        return self.builder.add_term(self.raw_query, term)


class NarrowLibraryTest(ZulipTestCase):
    def test_build_narrow_predicate(self) -> None:
        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="channel", operand="devel")])

        self.assertTrue(
            narrow_predicate(
                message={"display_recipient": "devel", "type": "stream"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"type": "private"},
                flags=[],
            )
        )
        self.assertFalse(
            narrow_predicate(
                message={"display_recipient": "social", "type": "stream"},
                flags=[],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="topic", operand="bark")])

        self.assertTrue(
            narrow_predicate(
                message={"type": "stream", "subject": "BarK"},
                flags=[],
            )
        )
        self.assertTrue(
            narrow_predicate(
                message={"type": "stream", "topic": "bark"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"type": "private"},
                flags=[],
            )
        )
        self.assertFalse(
            narrow_predicate(
                message={"type": "stream", "subject": "play with tail"},
                flags=[],
            )
        )
        self.assertFalse(
            narrow_predicate(
                message={"type": "stream", "topic": "play with tail"},
                flags=[],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate(
            [
                NarrowTerm(operator="channel", operand="devel"),
                NarrowTerm(operator="topic", operand="python"),
            ]
        )

        self.assertTrue(
            narrow_predicate(
                message={"display_recipient": "devel", "type": "stream", "subject": "python"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"type": "private"},
                flags=[],
            )
        )
        self.assertFalse(
            narrow_predicate(
                message={"display_recipient": "devel", "type": "stream", "subject": "java"},
                flags=[],
            )
        )
        self.assertFalse(
            narrow_predicate(
                message={"display_recipient": "social", "type": "stream"},
                flags=[],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate(
            [NarrowTerm(operator="sender", operand="hamlet@zulip.com")]
        )

        self.assertTrue(
            narrow_predicate(
                message={"sender_email": "hamlet@zulip.com"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"sender_email": "cordelia@zulip.com"},
                flags=[],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="dm")])

        self.assertTrue(
            narrow_predicate(
                message={"type": "private"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"type": "stream"},
                flags=[],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="private")])

        self.assertTrue(
            narrow_predicate(
                message={"type": "private"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"type": "stream"},
                flags=[],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="starred")])

        self.assertTrue(
            narrow_predicate(
                message={},
                flags=["starred"],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={},
                flags=["alerted"],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="alerted")])

        self.assertTrue(
            narrow_predicate(
                message={},
                flags=["mentioned"],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={},
                flags=["starred"],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="mentioned")])

        self.assertTrue(
            narrow_predicate(
                message={},
                flags=["mentioned"],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={},
                flags=["starred"],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="unread")])

        self.assertTrue(
            narrow_predicate(
                message={},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={},
                flags=["read"],
            )
        )

        ###

        narrow_predicate = build_narrow_predicate([NarrowTerm(operator="is", operand="resolved")])

        self.assertTrue(
            narrow_predicate(
                message={"type": "stream", "subject": "✔ python"},
                flags=[],
            )
        )

        self.assertFalse(
            narrow_predicate(
                message={"type": "private"},
                flags=[],
            )
        )
        self.assertFalse(
            narrow_predicate(
                message={"type": "stream", "subject": "java"},
                flags=[],
            )
        )

    def test_build_narrow_predicate_invalid(self) -> None:
        with self.assertRaises(JsonableError):
            build_narrow_predicate([NarrowTerm(operator="invalid_operator", operand="operand")])

    def test_is_spectator_compatible(self) -> None:
        self.assertTrue(is_spectator_compatible([]))
        self.assertTrue(is_spectator_compatible([{"operator": "has", "operand": "attachment"}]))
        self.assertTrue(is_spectator_compatible([{"operator": "has", "operand": "image"}]))
        self.assertTrue(is_spectator_compatible([{"operator": "search", "operand": "magic"}]))
        self.assertTrue(is_spectator_compatible([{"operator": "near", "operand": "15"}]))
        self.assertTrue(
            is_spectator_compatible(
                [{"operator": "id", "operand": "15"}, {"operator": "has", "operand": "attachment"}]
            )
        )
        self.assertTrue(
            is_spectator_compatible([{"operator": "sender", "operand": "hamlet@zulip.com"}])
        )
        self.assertFalse(
            is_spectator_compatible([{"operator": "dm", "operand": "hamlet@zulip.com"}])
        )
        self.assertFalse(
            is_spectator_compatible([{"operator": "dm-including", "operand": "hamlet@zulip.com"}])
        )
        self.assertTrue(is_spectator_compatible([{"operator": "channel", "operand": "Denmark"}]))
        self.assertTrue(
            is_spectator_compatible(
                [
                    {"operator": "channel", "operand": "Denmark"},
                    {"operator": "topic", "operand": "logic"},
                ]
            )
        )
        self.assertFalse(is_spectator_compatible([{"operator": "is", "operand": "starred"}]))
        self.assertFalse(is_spectator_compatible([{"operator": "is", "operand": "dm"}]))
        self.assertTrue(is_spectator_compatible([{"operator": "channels", "operand": "public"}]))

        # Malformed input not allowed
        self.assertFalse(is_spectator_compatible([{"operator": "has"}]))

        # "is:private" is a legacy alias for "is:dm".
        self.assertFalse(is_spectator_compatible([{"operator": "is", "operand": "private"}]))
        # "pm-with:"" is a legacy alias for "dm:"
        self.assertFalse(
            is_spectator_compatible([{"operator": "pm-with", "operand": "hamlet@zulip.com"}])
        )
        # "group-pm-with:" was deprecated by the addition of "dm-including:"
        self.assertFalse(
            is_spectator_compatible([{"operator": "group-pm-with", "operand": "hamlet@zulip.com"}])
        )
        # "stream" is a legacy alias for "channel" operator
        self.assertTrue(is_spectator_compatible([{"operator": "stream", "operand": "Denmark"}]))
        self.assertTrue(
            is_spectator_compatible(
                [
                    {"operator": "stream", "operand": "Denmark"},
                    {"operator": "topic", "operand": "logic"},
                ]
            )
        )
        # "streams" is a legacy alias for "channels" operator
        self.assertTrue(is_spectator_compatible([{"operator": "streams", "operand": "public"}]))


class IncludeHistoryTest(ZulipTestCase):
    def test_ok_to_include_history(self) -> None:
        user_profile = self.example_user("hamlet")
        self.make_stream("public_channel", realm=user_profile.realm)

        # Negated channel searches should not include history.
        narrow = [
            dict(operator="channel", operand="public_channel", negated=True),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # channels:public searches should include history for non-guest members.
        narrow = [
            dict(operator="channels", operand="public"),
        ]
        self.assertTrue(ok_to_include_history(narrow, user_profile, False))

        # Negated -channels:public searches should not include history.
        narrow = [
            dict(operator="channels", operand="public", negated=True),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # Definitely forbid seeing history on private channels.
        self.make_stream("private_channel", realm=user_profile.realm, invite_only=True)
        subscribed_user_profile = self.example_user("cordelia")
        self.subscribe(subscribed_user_profile, "private_channel")
        narrow = [
            dict(operator="channel", operand="private_channel"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # Verify that with history_public_to_subscribers, subscribed
        # users can access history.
        self.make_stream(
            "private_channel_2",
            realm=user_profile.realm,
            invite_only=True,
            history_public_to_subscribers=True,
        )
        subscribed_user_profile = self.example_user("cordelia")
        self.subscribe(subscribed_user_profile, "private_channel_2")
        narrow = [
            dict(operator="channel", operand="private_channel_2"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile, False))

        # History doesn't apply to direct messages.
        narrow = [
            dict(operator="is", operand="dm"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))
        # "is:private" is a legacy alias for "is:dm".
        narrow = [
            dict(operator="is", operand="private"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # History doesn't apply to unread messages.
        narrow = [
            dict(operator="is", operand="unread"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # If we are looking for something like starred messages, there is
        # no point in searching historical messages.
        narrow = [
            dict(operator="channel", operand="public_channel"),
            dict(operator="is", operand="starred"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # No point in searching history for is operator even if included with
        # channels:public
        narrow = [
            dict(operator="channels", operand="public"),
            dict(operator="is", operand="mentioned"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))
        narrow = [
            dict(operator="channels", operand="public"),
            dict(operator="is", operand="unread"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))
        narrow = [
            dict(operator="channels", operand="public"),
            dict(operator="is", operand="alerted"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))
        narrow = [
            dict(operator="channels", operand="public"),
            dict(operator="is", operand="resolved"),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile, False))

        # simple True case
        narrow = [
            dict(operator="channel", operand="public_channel"),
        ]
        self.assertTrue(ok_to_include_history(narrow, user_profile, False))

        narrow = [
            dict(operator="channel", operand="public_channel"),
            dict(operator="topic", operand="whatever"),
            dict(operator="search", operand="needle in haystack"),
        ]
        self.assertTrue(ok_to_include_history(narrow, user_profile, False))

        # Tests for guest user
        guest_user_profile = self.example_user("polonius")
        # Using 'Cordelia' to compare between a guest and a normal user
        subscribed_user_profile = self.example_user("cordelia")

        # channels:public searches should not include history for guest members.
        narrow = [
            dict(operator="channels", operand="public"),
        ]
        self.assertFalse(ok_to_include_history(narrow, guest_user_profile, False))

        # Guest user can't access public channel
        self.subscribe(subscribed_user_profile, "public_channel_2")
        narrow = [
            dict(operator="channel", operand="public_channel_2"),
        ]
        self.assertFalse(ok_to_include_history(narrow, guest_user_profile, False))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile, False))

        # Definitely, a guest user can't access the unsubscribed private channel
        self.subscribe(subscribed_user_profile, "private_channel_3")
        narrow = [
            dict(operator="channel", operand="private_channel_3"),
        ]
        self.assertFalse(ok_to_include_history(narrow, guest_user_profile, False))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile, False))

        # Guest user can access (history of) subscribed private channels
        self.subscribe(guest_user_profile, "private_channel_4")
        self.subscribe(subscribed_user_profile, "private_channel_4")
        narrow = [
            dict(operator="channel", operand="private_channel_4"),
        ]
        self.assertTrue(ok_to_include_history(narrow, guest_user_profile, False))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile, False))


class PostProcessTest(ZulipTestCase):
    def test_basics(self) -> None:
        def verify(
            in_ids: List[int],
            num_before: int,
            num_after: int,
            first_visible_message_id: int,
            anchor: int,
            anchored_to_left: bool,
            anchored_to_right: bool,
            out_ids: List[int],
            found_anchor: bool,
            found_oldest: bool,
            found_newest: bool,
            history_limited: bool,
        ) -> None:
            in_rows = [[row_id] for row_id in in_ids]
            out_rows = [[row_id] for row_id in out_ids]

            info = post_process_limited_query(
                rows=in_rows,
                num_before=num_before,
                num_after=num_after,
                anchor=anchor,
                anchored_to_left=anchored_to_left,
                anchored_to_right=anchored_to_right,
                first_visible_message_id=first_visible_message_id,
            )

            self.assertEqual(info.rows, out_rows)
            self.assertEqual(info.found_anchor, found_anchor)
            self.assertEqual(info.found_newest, found_newest)
            self.assertEqual(info.found_oldest, found_oldest)
            self.assertEqual(info.history_limited, history_limited)

        # typical 2-sided query, with a bunch of tests for different
        # values of first_visible_message_id.
        anchor = 10
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[8, 9, 10, 11, 12],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=8,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[8, 9, 10, 11, 12],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=9,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[9, 10, 11, 12],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=10,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[10, 11, 12],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=11,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[11, 12],
            found_anchor=False,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=12,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[12],
            found_anchor=False,
            found_oldest=True,
            found_newest=True,
            history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2,
            num_after=2,
            first_visible_message_id=13,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[],
            found_anchor=False,
            found_oldest=True,
            found_newest=True,
            history_limited=True,
        )

        # typical 2-sided query missing anchor and grabbing an extra row
        anchor = 10
        verify(
            in_ids=[7, 9, 11, 13, 15],
            num_before=2,
            num_after=2,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            first_visible_message_id=0,
            out_ids=[7, 9, 11, 13],
            found_anchor=False,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[7, 9, 11, 13, 15],
            num_before=2,
            num_after=2,
            first_visible_message_id=10,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[11, 13],
            found_anchor=False,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )
        verify(
            in_ids=[7, 9, 11, 13, 15],
            num_before=2,
            num_after=2,
            first_visible_message_id=9,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[9, 11, 13],
            found_anchor=False,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )

        # 2-sided query with old anchor
        anchor = 100
        verify(
            in_ids=[50, anchor, 150, 200],
            num_before=2,
            num_after=2,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[50, 100, 150, 200],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[50, anchor, 150, 200],
            num_before=2,
            num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[100, 150, 200],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )

        # 2-sided query with new anchor
        anchor = 900
        verify(
            in_ids=[700, 800, anchor, 1000],
            num_before=2,
            num_after=2,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[700, 800, 900, 1000],
            found_anchor=True,
            found_oldest=False,
            found_newest=True,
            history_limited=False,
        )
        verify(
            in_ids=[700, 800, anchor, 1000],
            num_before=2,
            num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[900, 1000],
            found_anchor=True,
            found_oldest=True,
            found_newest=True,
            history_limited=True,
        )

        # left-sided query with old anchor
        anchor = 100
        verify(
            in_ids=[50, anchor],
            num_before=2,
            num_after=0,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[50, 100],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[50, anchor],
            num_before=2,
            num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[100],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )

        # left-sided query with new anchor
        anchor = 900
        verify(
            in_ids=[700, 800, anchor],
            num_before=2,
            num_after=0,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[700, 800, 900],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[700, 800, anchor],
            num_before=2,
            num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[900],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )

        # left-sided query with new anchor and extra row
        anchor = 900
        verify(
            in_ids=[600, 700, 800, anchor],
            num_before=2,
            num_after=0,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[700, 800, 900],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[600, 700, 800, anchor],
            num_before=2,
            num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[900],
            found_anchor=True,
            found_oldest=True,
            found_newest=False,
            history_limited=True,
        )

        # left-sided query anchored to the right
        anchor = LARGER_THAN_MAX_MESSAGE_ID
        verify(
            in_ids=[900, 1000],
            num_before=2,
            num_after=0,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=True,
            out_ids=[900, 1000],
            found_anchor=False,
            found_oldest=False,
            found_newest=True,
            history_limited=False,
        )
        verify(
            in_ids=[900, 1000],
            num_before=2,
            num_after=0,
            first_visible_message_id=1000,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=True,
            out_ids=[1000],
            found_anchor=False,
            found_oldest=True,
            found_newest=True,
            history_limited=True,
        )
        verify(
            in_ids=[900, 1000],
            num_before=2,
            num_after=0,
            first_visible_message_id=1100,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=True,
            out_ids=[],
            found_anchor=False,
            found_oldest=True,
            found_newest=True,
            history_limited=True,
        )

        # right-sided query with old anchor
        anchor = 100
        verify(
            in_ids=[anchor, 200, 300, 400],
            num_before=0,
            num_after=2,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[100, 200, 300],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[anchor, 200, 300, 400],
            num_before=0,
            num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[100, 200, 300],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[anchor, 200, 300, 400],
            num_before=0,
            num_after=2,
            first_visible_message_id=300,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[300, 400],
            found_anchor=False,
            found_oldest=False,
            # BUG: history_limited should be False here.
            found_newest=False,
            history_limited=False,
        )

        # right-sided query with new anchor
        anchor = 900
        verify(
            in_ids=[anchor, 1000],
            num_before=0,
            num_after=2,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[900, 1000],
            found_anchor=True,
            found_oldest=False,
            found_newest=True,
            history_limited=False,
        )
        verify(
            in_ids=[anchor, 1000],
            num_before=0,
            num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[900, 1000],
            found_anchor=True,
            found_oldest=False,
            found_newest=True,
            history_limited=False,
        )

        # right-sided query with non-matching anchor
        anchor = 903
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0,
            num_after=2,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[1000, 1100],
            found_anchor=False,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0,
            num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[1000, 1100],
            found_anchor=False,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0,
            num_after=2,
            first_visible_message_id=1000,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[1000, 1100],
            found_anchor=False,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0,
            num_after=2,
            first_visible_message_id=1100,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[1100, 1200],
            found_anchor=False,
            found_oldest=False,
            # BUG: history_limited should be False here.
            found_newest=False,
            history_limited=False,
        )

        # targeted query that finds row
        anchor = 1000
        verify(
            in_ids=[1000],
            num_before=0,
            num_after=0,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[1000],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[1000],
            num_before=0,
            num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[1000],
            found_anchor=True,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )
        verify(
            in_ids=[1000],
            num_before=0,
            num_after=0,
            first_visible_message_id=1100,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[],
            found_anchor=False,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )

        # targeted query that finds nothing
        anchor = 903
        verify(
            in_ids=[],
            num_before=0,
            num_after=0,
            first_visible_message_id=0,
            anchor=anchor,
            anchored_to_left=False,
            anchored_to_right=False,
            out_ids=[],
            found_anchor=False,
            found_oldest=False,
            found_newest=False,
            history_limited=False,
        )


class GetOldMessagesTest(ZulipTestCase):
    def get_and_check_messages(
        self, modified_params: Dict[str, Union[str, int]], **kwargs: Any
    ) -> Dict[str, Any]:
        post_params: Dict[str, Union[str, int]] = {"anchor": 1, "num_before": 1, "num_after": 1}
        post_params.update(modified_params)
        payload = self.client_get("/json/messages", dict(post_params), **kwargs)
        self.assert_json_success(payload)
        self.assertEqual(
            set(payload["Cache-Control"].split(", ")),
            {"must-revalidate", "no-store", "no-cache", "max-age=0", "private"},
        )

        result = orjson.loads(payload.content)

        self.assertIn("messages", result)
        self.assertIsInstance(result["messages"], list)
        for message in result["messages"]:
            for field in (
                "content",
                "content_type",
                "display_recipient",
                "avatar_url",
                "recipient_id",
                "sender_full_name",
                "timestamp",
                "reactions",
            ):
                self.assertIn(field, message)
        return result

    def message_visibility_test(
        self, narrow: List[Dict[str, str]], message_ids: List[int], pivot_index: int
    ) -> None:
        num_before = len(message_ids)

        post_params = dict(
            narrow=orjson.dumps(narrow).decode(),
            num_before=num_before,
            num_after=0,
            anchor=LARGER_THAN_MAX_MESSAGE_ID,
        )
        payload = self.client_get("/json/messages", dict(post_params))
        self.assert_json_success(payload)
        result = orjson.loads(payload.content)

        self.assert_length(result["messages"], len(message_ids))
        for message in result["messages"]:
            assert message["id"] in message_ids

        post_params.update(num_before=len(message_ids[pivot_index:]))

        with first_visible_id_as(message_ids[pivot_index]):
            payload = self.client_get("/json/messages", dict(post_params))

        self.assert_json_success(payload)
        result = orjson.loads(payload.content)

        self.assert_length(result["messages"], len(message_ids[pivot_index:]))
        for message in result["messages"]:
            assert message["id"] in message_ids

    def get_query_ids(self) -> Dict[str, Union[int, str]]:
        hamlet_user = self.example_user("hamlet")
        othello_user = self.example_user("othello")

        query_ids: Dict[str, Union[int, str]] = {}

        scotland_channel = get_stream("Scotland", hamlet_user.realm)
        assert scotland_channel.recipient_id is not None
        assert hamlet_user.recipient_id is not None
        assert othello_user.recipient_id is not None
        query_ids["realm_id"] = hamlet_user.realm_id
        query_ids["scotland_recipient"] = scotland_channel.recipient_id
        query_ids["hamlet_id"] = hamlet_user.id
        query_ids["othello_id"] = othello_user.id
        query_ids["hamlet_recipient"] = hamlet_user.recipient_id
        query_ids["othello_recipient"] = othello_user.recipient_id
        recipients = (
            get_public_streams_queryset(hamlet_user.realm)
            .values_list("recipient_id", flat=True)
            .order_by("id")
        )
        query_ids["public_channels_recipients"] = ", ".join(str(r) for r in recipients)
        return query_ids

    def check_unauthenticated_response(
        self, result: "TestHttpResponse", www_authenticate: str = 'Session realm="zulip"'
    ) -> None:
        """
        In `JsonErrorHandler`, we convert `MissingAuthenticationError` into responses with `WWW-Authenticate`
        set depending on which endpoint encounters the error.

        This verifies the status code as well as the value of the set header.
        `www_authenticate` should be `Basic realm="zulip"` for paths starting with "/api", and
        `Session realm="zulip"` otherwise.
        """
        self.assert_json_error(
            result, "Not logged in: API authentication or user session required", status_code=401
        )
        self.assertEqual(result["WWW-Authenticate"], www_authenticate)

    def test_content_types(self) -> None:
        """
        Test old `/json/messages` returns reactions.
        """
        self.login("hamlet")

        def get_content_type(apply_markdown: bool) -> str:
            req: Dict[str, Any] = dict(
                apply_markdown=orjson.dumps(apply_markdown).decode(),
            )
            result = self.get_and_check_messages(req)
            message = result["messages"][0]
            return message["content_type"]

        self.assertEqual(
            get_content_type(apply_markdown=False),
            "text/x-markdown",
        )

        self.assertEqual(
            get_content_type(apply_markdown=True),
            "text/html",
        )

    def test_successful_get_messages_reaction(self) -> None:
        """
        Test old `/json/messages` returns reactions.
        """
        self.send_stream_message(self.example_user("iago"), "Verona")

        self.login("hamlet")

        get_messages_params: Dict[str, Union[int, str]] = {"anchor": "newest", "num_before": 1}
        messages = self.get_and_check_messages(get_messages_params)["messages"]
        self.assert_length(messages, 1)
        message_id = messages[0]["id"]
        self.assert_length(messages[0]["reactions"], 0)

        self.login("othello")
        reaction_name = "thumbs_up"
        reaction_info = {
            "emoji_name": reaction_name,
        }

        url = f"/json/messages/{message_id}/reactions"
        payload = self.client_post(url, reaction_info)
        self.assert_json_success(payload)

        self.login("hamlet")
        messages = self.get_and_check_messages(get_messages_params)["messages"]
        self.assert_length(messages, 1)
        self.assertEqual(messages[0]["id"], message_id)
        self.assert_length(messages[0]["reactions"], 1)
        self.assertEqual(messages[0]["reactions"][0]["emoji_name"], reaction_name)

    def test_successful_get_messages(self) -> None:
        """
        A call to GET /json/messages with valid parameters returns a list of
        messages.
        """
        self.login("hamlet")
        self.get_and_check_messages({})

        othello_email = self.example_user("othello").email

        # We have to support the legacy tuple style while there are old
        # clients around, which might include third party home-grown bots.
        self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(
                    [["dm", othello_email]],
                ).decode(),
            ),
        )

        self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(
                    [dict(operator="dm", operand=othello_email)],
                ).decode(),
            ),
        )

    def test_unauthenticated_get_messages(self) -> None:
        # Require channels:web-public as narrow to get web-public messages.
        get_params = {
            "anchor": 10000000000000000,
            "num_before": 5,
            "num_after": 1,
        }
        result = self.client_get("/json/messages", dict(get_params))
        self.check_unauthenticated_response(result)

        # Paths starting with /api/v1 should receive a response that asks
        # for basic auth.
        result = self.client_get("/api/v1/messages", dict(get_params))
        self.check_unauthenticated_response(result, www_authenticate='Basic realm="zulip"')

        # Successful access to web-public channel messages.
        web_public_channel_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            "narrow": orjson.dumps([dict(operator="channels", operand="web-public")]).decode(),
        }
        result = self.client_get("/json/messages", dict(web_public_channel_get_params))
        # More detailed check of message parameters is done in `test_get_messages_with_web_public`.
        self.assert_json_success(result)

        # Realm doesn't exist in our database.
        with mock.patch("zerver.context_processors.get_realm", side_effect=Realm.DoesNotExist):
            result = self.client_get("/json/messages", dict(web_public_channel_get_params))
            self.assert_json_error(result, "Invalid subdomain", status_code=404)

        # Cannot access direct messages without login.
        direct_messages_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            "narrow": orjson.dumps([dict(operator="is", operand="dm")]).decode(),
        }
        result = self.client_get("/json/messages", dict(direct_messages_get_params))
        self.check_unauthenticated_response(result)
        # "is:private" is a legacy alias for "is:dm".
        private_message_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            "narrow": orjson.dumps([dict(operator="is", operand="private")]).decode(),
        }
        result = self.client_get("/json/messages", dict(private_message_get_params))
        self.check_unauthenticated_response(result)

        # narrow should pass conditions in `is_spectator_compatible`.
        non_spectator_compatible_narrow_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            # "is:dm" is not a is_spectator_compatible narrow.
            "narrow": orjson.dumps(
                [
                    dict(operator="channels", operand="web-public"),
                    dict(operator="is", operand="dm"),
                ]
            ).decode(),
        }
        result = self.client_get("/json/messages", dict(non_spectator_compatible_narrow_get_params))
        self.check_unauthenticated_response(result)

        # Spectator login disabled in Realm.
        do_set_realm_property(
            get_realm("zulip"), "enable_spectator_access", False, acting_user=None
        )
        result = self.client_get("/json/messages", dict(web_public_channel_get_params))
        self.check_unauthenticated_response(result)
        do_set_realm_property(get_realm("zulip"), "enable_spectator_access", True, acting_user=None)
        # Verify works after enabling `realm.enable_spectator_access` again.
        result = self.client_get("/json/messages", dict(web_public_channel_get_params))
        self.assert_json_success(result)

        # Cannot access even web-public channels without channels:web-public narrow.
        non_web_public_channel_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            "narrow": orjson.dumps([dict(operator="channel", operand="Rome")]).decode(),
        }
        result = self.client_get("/json/messages", dict(non_web_public_channel_get_params))
        self.check_unauthenticated_response(result)

        # Verify that same request would work with channels:web-public added.
        rome_web_public_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            "narrow": orjson.dumps(
                [
                    dict(operator="channels", operand="web-public"),
                    # Rome is a web-channel channel.
                    dict(operator="channel", operand="Rome"),
                ]
            ).decode(),
        }
        result = self.client_get("/json/messages", dict(rome_web_public_get_params))
        self.assert_json_success(result)

        # Cannot access non-web-public channel even with channels:web-public narrow.
        scotland_web_public_get_params: Dict[str, Union[int, str, bool]] = {
            **get_params,
            "narrow": orjson.dumps(
                [
                    dict(operator="channels", operand="web-public"),
                    # Scotland is not a web-public channel.
                    dict(operator="channel", operand="Scotland"),
                ]
            ).decode(),
        }
        result = self.client_get("/json/messages", dict(scotland_web_public_get_params))
        self.assert_json_error(
            result, "Invalid narrow operator: unknown web-public channel Scotland", status_code=400
        )

    def setup_web_public_test(self, num_web_public_message: int = 1) -> None:
        """
        Send N+2 messages, N in a web-public channel, then one in a non-web-public channel
        and then a direct message.
        """
        user_profile = self.example_user("iago")
        do_set_realm_property(
            user_profile.realm, "enable_spectator_access", True, acting_user=user_profile
        )
        self.login("iago")
        web_public_channel = self.make_stream("web-public-channel", is_web_public=True)
        non_web_public_channel = self.make_stream("non-web-public-channel")
        self.subscribe(user_profile, web_public_channel.name)
        self.subscribe(user_profile, non_web_public_channel.name)

        for _ in range(num_web_public_message):
            self.send_stream_message(
                user_profile, web_public_channel.name, content="web-public message"
            )
        self.send_stream_message(
            user_profile, non_web_public_channel.name, content="non-web-public message"
        )
        self.send_personal_message(
            user_profile, self.example_user("hamlet"), content="direct message"
        )
        self.logout()

    def verify_web_public_query_result_success(
        self, result: "TestHttpResponse", expected_num_messages: int
    ) -> None:
        self.assert_json_success(result)
        messages = orjson.loads(result.content)["messages"]
        self.assert_length(messages, expected_num_messages)
        sender = self.example_user("iago")
        for msg in messages:
            self.assertEqual(msg["content"], "<p>web-public message</p>")
            self.assertEqual(msg["flags"], ["read"])
            self.assertEqual(msg["sender_email"], sender.email)
            self.assertEqual(msg["avatar_url"], avatar_url(sender))

    def test_unauthenticated_narrow_to_web_public_channels(self) -> None:
        self.setup_web_public_test()

        post_params: Dict[str, Union[int, str, bool]] = {
            "anchor": 1,
            "num_before": 1,
            "num_after": 1,
            "narrow": orjson.dumps(
                [
                    dict(operator="channels", operand="web-public"),
                    dict(operator="channel", operand="web-public-channel"),
                ]
            ).decode(),
        }
        result = self.client_get("/json/messages", dict(post_params))
        self.verify_web_public_query_result_success(result, 1)

    def test_get_messages_with_web_public(self) -> None:
        """
        An unauthenticated call to GET /json/messages with valid parameters
        including channels:web-public narrow returns list of messages in the
        web-public channels.
        """
        self.setup_web_public_test(num_web_public_message=8)

        post_params = {
            "anchor": "first_unread",
            "num_before": 5,
            "num_after": 1,
            "narrow": orjson.dumps([dict(operator="channels", operand="web-public")]).decode(),
        }
        result = self.client_get("/json/messages", dict(post_params))
        # Of the last 7 (num_before + num_after + 1) messages, only 5
        # messages are returned, which were all web-public messages.
        # The other two messages should not be returned even though
        # they are the most recent.
        self.verify_web_public_query_result_success(result, 5)

    def test_client_avatar(self) -> None:
        """
        The client_gravatar flag determines whether we send avatar_url.
        """
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
            acting_user=None,
        )

        self.send_personal_message(hamlet, self.example_user("iago"))

        result = self.get_and_check_messages(
            dict(anchor="newest", client_gravatar=orjson.dumps(False).decode())
        )
        message = result["messages"][0]
        self.assertIn("gravatar.com", message["avatar_url"])

        result = self.get_and_check_messages(
            dict(anchor="newest", client_gravatar=orjson.dumps(True).decode())
        )
        message = result["messages"][0]
        self.assertEqual(message["avatar_url"], None)

        # Now verify client_gravatar doesn't run with EMAIL_ADDRESS_VISIBILITY_ADMINS
        do_change_user_setting(
            hamlet,
            "email_address_visibility",
            UserProfile.EMAIL_ADDRESS_VISIBILITY_ADMINS,
            acting_user=None,
        )
        result = self.get_and_check_messages(
            dict(anchor="newest", client_gravatar=orjson.dumps(True).decode())
        )
        message = result["messages"][0]
        self.assertIn("gravatar.com", message["avatar_url"])

    def test_get_messages_with_narrow_dm(self) -> None:
        """
        A request for old messages with a narrow by direct message only returns
        conversations with that user.
        """
        me = self.example_user("hamlet")

        def dr_emails(dr: List[UserDisplayRecipient]) -> str:
            assert isinstance(dr, list)
            return ",".join(sorted({*(r["email"] for r in dr), me.email}))

        def dr_ids(dr: List[UserDisplayRecipient]) -> List[int]:
            assert isinstance(dr, list)
            return sorted({*(r["id"] for r in dr), self.example_user("hamlet").id})

        self.send_personal_message(me, self.example_user("iago"))

        self.send_huddle_message(
            me,
            [self.example_user("iago"), self.example_user("cordelia")],
        )

        # Send a 1:1 and group direct message containing Aaron.
        # Then deactivate Aaron to test "dm" narrow includes messages
        # from deactivated users also.
        self.send_personal_message(me, self.example_user("aaron"))
        self.send_huddle_message(
            me,
            [self.example_user("iago"), self.example_user("aaron")],
        )
        aaron = self.example_user("aaron")
        do_deactivate_user(aaron, acting_user=None)
        self.assertFalse(aaron.is_active)

        personals = [
            m for m in get_user_messages(self.example_user("hamlet")) if not m.is_stream_message()
        ]
        for personal in personals:
            emails = dr_emails(get_display_recipient(personal.recipient))
            self.login_user(me)
            narrow: List[Dict[str, Any]] = [dict(operator="dm", operand=emails)]
            result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))

            for message in result["messages"]:
                self.assertEqual(dr_emails(message["display_recipient"]), emails)

            # check passing user IDs is consistent with passing user emails as operand
            ids = dr_ids(get_display_recipient(personal.recipient))
            narrow = [dict(operator="dm", operand=ids)]
            result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))

            for message in result["messages"]:
                self.assertEqual(dr_emails(message["display_recipient"]), emails)

    def test_get_messages_with_nonexistant_group_dm(self) -> None:
        me = self.example_user("hamlet")
        # Huddle which doesn't match anything gets no results
        non_existant_huddle = [
            me.id,
            self.example_user("iago").id,
            self.example_user("othello").id,
        ]
        self.login_user(me)
        narrow: List[Dict[str, Any]] = [dict(operator="dm", operand=non_existant_huddle)]
        result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))
        self.assertEqual(result["messages"], [])

        narrow = [dict(operator="dm", operand=non_existant_huddle, negated=True)]
        result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))
        self.assertEqual([m["id"] for m in result["messages"]], [1, 3])

    def test_get_visible_messages_with_narrow_dm(self) -> None:
        me = self.example_user("hamlet")
        self.login_user(me)
        self.subscribe(self.example_user("hamlet"), "Scotland")

        message_ids = [self.send_personal_message(me, self.example_user("iago")) for i in range(5)]

        narrow = [dict(operator="dm", operand=self.example_user("iago").email)]
        self.message_visibility_test(narrow, message_ids, 2)

    def test_get_messages_with_narrow_dm_including(self) -> None:
        """
        A request for old messages with a narrow by "dm-including" only
        returns direct messages (both group and 1:1) with that user.
        """
        me = self.example_user("hamlet")

        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        matching_message_ids = [
            # group direct message, sent by current user
            self.send_huddle_message(
                me,
                [iago, cordelia, othello],
            ),
            # group direct message, sent by searched user
            self.send_huddle_message(
                cordelia,
                [me, othello],
            ),
            # group direct message, sent by another user
            self.send_huddle_message(
                othello,
                [me, cordelia],
            ),
            # direct 1:1 message, sent by current user to searched user
            self.send_personal_message(me, cordelia),
            # direct 1:1 message, sent by searched user to current user
            self.send_personal_message(cordelia, me),
        ]

        non_matching_message_ids = [
            # direct 1:1 message, does not include current user
            self.send_personal_message(iago, cordelia),
            # direct 1:1 message, does not include searched user
            self.send_personal_message(iago, me),
            # direct 1:1 message, current user to self
            self.send_personal_message(me, me),
            # group direct message, sent by current user
            self.send_huddle_message(
                me,
                [iago, othello],
            ),
            # group direct message, sent by searched user
            self.send_huddle_message(
                cordelia,
                [iago, othello],
            ),
        ]

        self.login_user(me)
        test_operands = [cordelia.email, cordelia.id]
        for operand in test_operands:
            narrow = [dict(operator="dm-including", operand=operand)]
            result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))
            for message in result["messages"]:
                self.assertIn(message["id"], matching_message_ids)
                self.assertNotIn(message["id"], non_matching_message_ids)

    def test_get_visible_messages_with_narrow_dm_including(self) -> None:
        me = self.example_user("hamlet")
        self.login_user(me)

        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        message_ids = [
            self.send_huddle_message(
                me,
                [iago, cordelia, othello],
            ),
            self.send_personal_message(me, cordelia),
            self.send_huddle_message(
                cordelia,
                [me, othello],
            ),
            self.send_personal_message(cordelia, me),
            self.send_huddle_message(
                iago,
                [cordelia, me],
            ),
        ]

        narrow = [dict(operator="dm-including", operand=cordelia.email)]
        self.message_visibility_test(narrow, message_ids, 2)

    def test_get_messages_with_narrow_group_pm_with(self) -> None:
        """
        A request for old messages with a narrow by deprecated "group-pm-with"
        only returns direct message group conversations with that user.
        """
        me = self.example_user("hamlet")

        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        matching_message_ids = [
            self.send_huddle_message(
                me,
                [iago, cordelia, othello],
            ),
            self.send_huddle_message(
                me,
                [cordelia, othello],
            ),
        ]

        non_matching_message_ids = [
            self.send_personal_message(me, cordelia),
            self.send_huddle_message(
                me,
                [iago, othello],
            ),
            self.send_huddle_message(
                self.example_user("cordelia"),
                [iago, othello],
            ),
        ]

        self.login_user(me)
        test_operands = [cordelia.email, cordelia.id]
        for operand in test_operands:
            narrow = [dict(operator="group-pm-with", operand=operand)]
            result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))
            for message in result["messages"]:
                self.assertIn(message["id"], matching_message_ids)
                self.assertNotIn(message["id"], non_matching_message_ids)

    def test_get_visible_messages_with_narrow_group_pm_with(self) -> None:
        me = self.example_user("hamlet")
        self.login_user(me)

        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        message_ids = [
            self.send_huddle_message(
                me,
                [iago, cordelia, othello],
            ),
            self.send_huddle_message(
                me,
                [cordelia, othello],
            ),
            self.send_huddle_message(
                me,
                [cordelia, iago],
            ),
        ]

        narrow = [dict(operator="group-pm-with", operand=cordelia.email)]
        self.message_visibility_test(narrow, message_ids, 1)

    def test_include_history(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        channel_name = "test channel"
        self.subscribe(cordelia, channel_name)

        old_message_id = self.send_stream_message(cordelia, channel_name, content="foo")

        self.subscribe(hamlet, channel_name)

        content = "hello @**King Hamlet**"
        new_message_id = self.send_stream_message(cordelia, channel_name, content=content)

        self.login_user(hamlet)
        narrow = [
            dict(operator="channel", operand=channel_name),
        ]

        req = dict(
            narrow=orjson.dumps(narrow).decode(),
            anchor=LARGER_THAN_MAX_MESSAGE_ID,
            num_before=100,
            num_after=100,
        )

        payload = self.client_get("/json/messages", req)
        self.assert_json_success(payload)
        result = orjson.loads(payload.content)
        messages = result["messages"]
        self.assert_length(messages, 2)

        for message in messages:
            if message["id"] == old_message_id:
                old_message = message
            elif message["id"] == new_message_id:
                new_message = message

        self.assertEqual(old_message["flags"], ["read", "historical"])
        self.assertEqual(new_message["flags"], ["mentioned"])

    def test_get_messages_with_narrow_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)
        realm = hamlet.realm

        num_messages_per_channel = 5
        channel_names = ["Scotland", "Verona", "Venice"]

        def send_messages_to_all_channels() -> None:
            Message.objects.filter(realm_id=realm.id, recipient__type=Recipient.STREAM).delete()
            for channel_name in channel_names:
                self.subscribe(hamlet, channel_name)
                for i in range(num_messages_per_channel):
                    message_id = self.send_stream_message(hamlet, channel_name, content=f"test {i}")
                    message = Message.objects.get(id=message_id)
                    self.assert_message_stream_name(message, channel_name)

        send_messages_to_all_channels()

        self.send_personal_message(hamlet, hamlet)

        messages = get_user_messages(hamlet)
        channel_messages = [msg for msg in messages if msg.is_stream_message()]
        self.assertGreater(len(messages), len(channel_messages))
        self.assert_length(channel_messages, num_messages_per_channel * len(channel_names))

        for channel_name in channel_names:
            channel = get_stream(channel_name, realm)
            for operand in [channel.name, channel.id]:
                narrow = [dict(operator="channel", operand=operand)]
                result = self.get_and_check_messages(
                    dict(narrow=orjson.dumps(narrow).decode(), num_after=100)
                )
                fetched_messages: List[Dict[str, object]] = result["messages"]
                self.assert_length(fetched_messages, num_messages_per_channel)

                for message_dict in fetched_messages:
                    self.assertEqual(message_dict["type"], "stream")
                    self.assertEqual(message_dict["display_recipient"], channel_name)
                    self.assertEqual(message_dict["recipient_id"], channel.recipient_id)

    def test_get_visible_messages_with_narrow_channel(self) -> None:
        self.login("hamlet")
        self.subscribe(self.example_user("hamlet"), "Scotland")

        message_ids = [
            self.send_stream_message(self.example_user("iago"), "Scotland") for i in range(5)
        ]

        narrow = [dict(operator="channel", operand="Scotland")]
        self.message_visibility_test(narrow, message_ids, 2)

    def test_get_messages_with_narrow_channel_mit_unicode_regex(self) -> None:
        """
        A request for old messages for a user in the mit.edu relam with Unicode
        channel name should be correctly escaped in the database query.
        """
        user = self.mit_user("starnine")
        self.login_user(user)
        # We need to subscribe to a channel and then send a message to
        # it to ensure that we actually have a channel message in this
        # narrow view.
        lambda_channel_name = "\u03bb-channel"
        channel = self.subscribe(user, lambda_channel_name)
        self.assertTrue(channel.is_in_zephyr_realm)

        lambda_channel_d_name = "\u03bb-channel.d"
        self.subscribe(user, lambda_channel_d_name)

        self.send_stream_message(user, "\u03bb-channel")
        self.send_stream_message(user, "\u03bb-channel.d")

        narrow = [dict(operator="channel", operand="\u03bb-channel")]
        result = self.get_and_check_messages(
            dict(num_after=2, narrow=orjson.dumps(narrow).decode()), subdomain="zephyr"
        )

        messages = get_user_messages(self.mit_user("starnine"))
        channel_messages = [msg for msg in messages if msg.is_stream_message()]

        self.assert_length(result["messages"], 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            channel_id = channel_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], channel_id)

    def test_get_messages_with_narrow_topic_mit_unicode_regex(self) -> None:
        """
        A request for old messages for a user in the mit.edu realm with Unicode
        topic name should be correctly escaped in the database query.
        """
        mit_user_profile = self.mit_user("starnine")
        self.login_user(mit_user_profile)
        # We need to subscribe to a channel and then send a message to
        # it to ensure that we actually have a channel message in this
        # narrow view.
        self.subscribe(mit_user_profile, "Scotland")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="\u03bb-topic")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="\u03bb-topic.d")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="\u03bb-topic.d.d")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="\u03bb-topic.d.d.d")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="\u03bb-topic.d.d.d.d")

        narrow = [dict(operator="topic", operand="\u03bb-topic")]
        result = self.get_and_check_messages(
            dict(num_after=100, narrow=orjson.dumps(narrow).decode()), subdomain="zephyr"
        )

        messages = get_user_messages(mit_user_profile)
        channel_messages = [msg for msg in messages if msg.is_stream_message()]
        self.assert_length(result["messages"], 5)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            channel_id = channel_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], channel_id)

    def test_get_messages_with_narrow_topic_mit_personal(self) -> None:
        """
        We handle .d grouping for MIT realm personal messages correctly.
        """
        mit_user_profile = self.mit_user("starnine")

        # We need to subscribe to a channel and then send a message to
        # it to ensure that we actually have a channel message in this
        # narrow view.
        self.login_user(mit_user_profile)
        self.subscribe(mit_user_profile, "Scotland")

        self.send_stream_message(mit_user_profile, "Scotland", topic_name=".d.d")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="PERSONAL")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name='(instance "").d')
        self.send_stream_message(mit_user_profile, "Scotland", topic_name=".d.d.d")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name="personal.d")
        self.send_stream_message(mit_user_profile, "Scotland", topic_name='(instance "")')
        self.send_stream_message(mit_user_profile, "Scotland", topic_name=".d.d.d.d")

        narrow = [dict(operator="topic", operand="personal.d.d")]
        result = self.get_and_check_messages(
            dict(num_before=50, num_after=50, narrow=orjson.dumps(narrow).decode()),
            subdomain="zephyr",
        )

        messages = get_user_messages(mit_user_profile)
        channel_messages = [msg for msg in messages if msg.is_stream_message()]
        self.assert_length(result["messages"], 7)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            channel_id = channel_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], channel_id)

    def test_get_messages_with_narrow_sender(self) -> None:
        """
        A request for old messages with a narrow by sender only returns
        messages sent by that person.
        """
        self.login("hamlet")

        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        iago = self.example_user("iago")

        # We need to send a message here to ensure that we actually
        # have a channel message in this narrow view.
        self.send_stream_message(hamlet, "Denmark")
        self.send_stream_message(othello, "Denmark")
        self.send_personal_message(othello, hamlet)
        self.send_stream_message(iago, "Denmark")

        test_operands = [othello.email, othello.id]
        for operand in test_operands:
            narrow = [dict(operator="sender", operand=operand)]
            result = self.get_and_check_messages(dict(narrow=orjson.dumps(narrow).decode()))

            for message in result["messages"]:
                self.assertEqual(message["sender_id"], othello.id)

    def _update_tsvector_index(self) -> None:
        # We use brute force here and update our text search index
        # for the entire zerver_message table (which is small in test
        # mode).  In production there is an async process which keeps
        # the search index up to date.
        with connection.cursor() as cursor:
            cursor.execute(
                """
            UPDATE zerver_message SET
            search_tsvector = to_tsvector('zulip.english_us_search',
            subject || rendered_content)
            """
            )

    @override_settings(USING_PGROONGA=False)
    def test_messages_in_narrow(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)

        def send(content: str) -> int:
            msg_id = self.send_stream_message(
                user,
                "Verona",
                content=content,
            )
            return msg_id

        good_id = send("KEYWORDMATCH and should work")
        bad_id = send("no match")
        msg_ids = [good_id, bad_id]
        send("KEYWORDMATCH but not in msg_ids")

        self._update_tsvector_index()

        narrow = [
            dict(operator="search", operand="KEYWORDMATCH"),
        ]

        raw_params = dict(msg_ids=msg_ids, narrow=narrow)
        params = {k: orjson.dumps(v).decode() for k, v in raw_params.items()}
        result = self.client_get("/json/messages/matches_narrow", params)
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)
        message = messages[str(good_id)]
        self.assertEqual(
            message["match_content"],
            '<p><span class="highlight">KEYWORDMATCH</span> and should work</p>',
        )

        narrow = [
            dict(operator="search", operand="KEYWORDMATCH"),
            dict(operator="search", operand="work"),
        ]

        raw_params = dict(msg_ids=msg_ids, narrow=narrow)
        params = {k: orjson.dumps(v).decode() for k, v in raw_params.items()}
        result = self.client_get("/json/messages/matches_narrow", params)
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)
        message = messages[str(good_id)]
        self.assertEqual(
            message["match_content"],
            '<p><span class="highlight">KEYWORDMATCH</span> and should <span class="highlight">work</span></p>',
        )

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search(self) -> None:
        self.login("cordelia")

        messages_to_search = [
            ("breakfast", "there are muffins in the conference room"),
            ("lunch plans", "I am hungry!"),
            ("meetings", "discuss lunch after lunch"),
            ("meetings", "please bring your laptops to take notes"),
            ("dinner", "Anybody staying late tonight?"),
            ("urltest", "https://google.com"),
            ("日本", "こんに ちは 。 今日は いい 天気ですね。"),
            ("日本", "今朝はごはんを食べました。"),
            ("日本", "昨日、日本 のお菓子を送りました。"),
            ("english", "I want to go to 日本!"),
        ]

        next_message_id = self.get_last_message().id + 1

        cordelia = self.example_user("cordelia")

        for topic, content in messages_to_search:
            self.send_stream_message(
                cordelia,
                "Verona",
                content=content,
                topic_name=topic,
            )

        self._update_tsvector_index()

        narrow = [
            dict(operator="sender", operand=cordelia.email),
            dict(operator="search", operand="lunch"),
        ]
        result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=next_message_id,
                num_before=0,
                num_after=10,
            )
        )
        self.assert_length(result["messages"], 2)
        messages = result["messages"]

        narrow = [dict(operator="search", operand="https://google.com")]
        link_search_result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=next_message_id,
                num_before=0,
                num_after=10,
            )
        )
        self.assert_length(link_search_result["messages"], 1)
        self.assertEqual(
            link_search_result["messages"][0]["match_content"],
            '<p><a href="https://google.com">https://<span class="highlight">google.com</span></a></p>',
        )

        (meeting_message,) = (m for m in messages if m[TOPIC_NAME] == "meetings")
        self.assertEqual(meeting_message[MATCH_TOPIC], "meetings")
        self.assertEqual(
            meeting_message["match_content"],
            (
                '<p>discuss <span class="highlight">lunch</span> after <span'
                ' class="highlight">lunch</span></p>'
            ),
        )

        (lunch_message,) = (m for m in messages if m[TOPIC_NAME] == "lunch plans")
        self.assertEqual(lunch_message[MATCH_TOPIC], '<span class="highlight">lunch</span> plans')
        self.assertEqual(lunch_message["match_content"], "<p>I am hungry!</p>")

        # Should not crash when multiple search operands are present
        multi_search_narrow = [
            dict(operator="search", operand="discuss"),
            dict(operator="search", operand="after"),
        ]
        multi_search_result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(multi_search_narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(multi_search_result["messages"], 1)
        self.assertEqual(
            multi_search_result["messages"][0]["match_content"],
            '<p><span class="highlight">discuss</span> lunch <span class="highlight">after</span> lunch</p>',
        )

        # Test searching in messages with Unicode characters
        narrow = [
            dict(operator="search", operand="日本"),
        ]
        result = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(result["messages"], 4)
        messages = result["messages"]

        japanese_message = [m for m in messages if m[TOPIC_NAME] == "日本"][-1]
        self.assertEqual(japanese_message[MATCH_TOPIC], '<span class="highlight">日本</span>')
        self.assertEqual(
            japanese_message["match_content"],
            '<p>昨日、<span class="highlight">日本</span> のお菓子を送りました。</p>',
        )

        (english_message,) = (m for m in messages if m[TOPIC_NAME] == "english")
        self.assertEqual(english_message[MATCH_TOPIC], "english")
        self.assertIn(
            english_message["match_content"],
            '<p>I want to go to <span class="highlight">日本</span>!</p>',
        )

        # Multiple search operands with Unicode
        multi_search_narrow = [
            dict(operator="search", operand="ちは"),
            dict(operator="search", operand="今日は"),
        ]
        multi_search_result = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(multi_search_narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(multi_search_result["messages"], 1)
        self.assertEqual(
            multi_search_result["messages"][0]["match_content"],
            '<p>こんに <span class="highlight">ちは</span> 。 <span class="highlight">今日は</span> いい 天気ですね。</p>',
        )

    @override_settings(USING_PGROONGA=False)
    def test_get_visible_messages_with_search(self) -> None:
        self.login("hamlet")
        self.subscribe(self.example_user("hamlet"), "Scotland")

        messages_to_search = [
            ("Gryffindor", "Hogwart's house which values courage, bravery, nerve, and chivalry"),
            (
                "Hufflepuff",
                "Hogwart's house which values hard work, patience, justice, and loyalty.",
            ),
            (
                "Ravenclaw",
                "Hogwart's house which values intelligence, creativity, learning, and wit",
            ),
            (
                "Slytherin",
                "Hogwart's house which  values ambition, cunning, leadership, and resourcefulness",
            ),
        ]

        message_ids = [
            self.send_stream_message(
                self.example_user("iago"), "Scotland", topic_name=topic, content=content
            )
            for topic, content in messages_to_search
        ]
        self._update_tsvector_index()
        narrow = [dict(operator="search", operand="Hogwart's")]
        self.message_visibility_test(narrow, message_ids, 2)

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_not_subscribed(self) -> None:
        """Verify support for searching a channel you're not subscribed to"""
        self.subscribe(self.example_user("hamlet"), "new-channel")
        self.send_stream_message(
            self.example_user("hamlet"),
            "new-channel",
            content="Public special content!",
            topic_name="new",
        )
        self._update_tsvector_index()

        self.login("cordelia")

        channel_search_narrow = [
            dict(operator="search", operand="special"),
            dict(operator="channel", operand="new-channel"),
        ]
        channel_search_result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(channel_search_narrow).decode(),
                anchor=0,
                num_after=10,
                num_before=10,
            )
        )
        self.assert_length(channel_search_result["messages"], 1)
        self.assertEqual(
            channel_search_result["messages"][0]["match_content"],
            '<p>Public <span class="highlight">special</span> content!</p>',
        )

    @override_settings(USING_PGROONGA=True)
    def test_get_messages_with_search_pgroonga(self) -> None:
        self.login("cordelia")

        next_message_id = self.get_last_message().id + 1

        messages_to_search = [
            ("日本語", "こんにちは。今日はいい天気ですね。"),
            ("日本語", "今朝はごはんを食べました。"),
            ("日本語", "昨日、日本のお菓子を送りました。"),
            ("english", "I want to go to 日本!"),
            ("english", "Can you speak https://en.wikipedia.org/wiki/Japanese?"),
            ("english", "https://domain.com/path/to.something-I,want/"),
            ("english", "foo.cht"),
            ("bread & butter", "chalk & cheese"),
        ]

        for topic, content in messages_to_search:
            self.send_stream_message(
                self.example_user("cordelia"),
                "Verona",
                content=content,
                topic_name=topic,
            )

        # We use brute force here and update our text search index
        # for the entire zerver_message table (which is small in test
        # mode).  In production there is an async process which keeps
        # the search index up to date.
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE zerver_message SET
                search_pgroonga = escape_html(subject) || ' ' || rendered_content
                """
            )

        narrow = [
            dict(operator="search", operand="日本"),
        ]
        result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(result["messages"], 4)
        messages = result["messages"]

        japanese_message = [m for m in messages if m[TOPIC_NAME] == "日本語"][-1]
        self.assertEqual(japanese_message[MATCH_TOPIC], '<span class="highlight">日本</span>語')
        self.assertEqual(
            japanese_message["match_content"],
            '<p>昨日、<span class="highlight">日本</span>のお菓子を送りました。</p>',
        )

        [english_message] = (m for m in messages if m[TOPIC_NAME] == "english")
        self.assertEqual(english_message[MATCH_TOPIC], "english")
        self.assertEqual(
            english_message["match_content"],
            '<p>I want to go to <span class="highlight">日本</span>!</p>',
        )

        # Should not crash when multiple search operands are present
        multi_search_narrow = [
            dict(operator="search", operand="can"),
            dict(operator="search", operand="speak"),
            dict(operator="search", operand="wiki"),
        ]
        multi_search_result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(multi_search_narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(multi_search_result["messages"], 1)
        self.assertEqual(
            multi_search_result["messages"][0]["match_content"],
            '<p><span class="highlight">Can</span> you <span class="highlight">speak</span> <a href="https://en.wikipedia.org/wiki/Japanese">https://en.<span class="highlight">wiki</span>pedia.org/<span class="highlight">wiki</span>/Japanese</a>?</p>',
        )

        # Multiple search operands with Unicode
        multi_search_narrow = [
            dict(operator="search", operand="朝は"),
            dict(operator="search", operand="べました"),
        ]
        multi_search_result = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(multi_search_narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(multi_search_result["messages"], 1)
        self.assertEqual(
            multi_search_result["messages"][0]["match_content"],
            '<p>今<span class="highlight">朝は</span>ごはんを食<span class="highlight">べました</span>。</p>',
        )

        def search(operand: str, link: Optional[str], highlight: str) -> None:
            narrow = [dict(operator="search", operand=operand)]
            link_search_result: Dict[str, Any] = self.get_and_check_messages(
                dict(
                    narrow=orjson.dumps(narrow).decode(),
                    anchor=next_message_id,
                    num_after=10,
                    num_before=0,
                )
            )
            self.assert_length(link_search_result["messages"], 1)
            self.assertEqual(
                link_search_result["messages"][0]["match_content"],
                f'<p><a href="{link}">{highlight}</a></p>' if link else f"<p>{highlight}</p>",
            )

        search("foo.cht", None, '<span class="highlight">foo.cht</span>')
        search("foo", None, '<span class="highlight">foo</span>.cht')
        search("cht", None, 'foo.<span class="highlight">cht</span>')

        url = "https://domain.com/path/to.something-I,want/"
        search(url, url, f'<span class="highlight">{url}</span>')
        search(
            "https://domain",
            url,
            '<span class="highlight">https://domain</span>.com/path/to.something-I,want/',
        )
        search(
            "domain",
            url,
            'https://<span class="highlight">domain</span>.com/path/to.something-I,want/',
        )
        search(
            "domain.",
            url,
            'https://<span class="highlight">domain.</span>com/path/to.something-I,want/',
        )
        search(
            "domain.com",
            url,
            'https://<span class="highlight">domain.com</span>/path/to.something-I,want/',
        )
        search(
            "domain.com/",
            url,
            'https://<span class="highlight">domain.com/</span>path/to.something-I,want/',
        )
        search(
            "domain.com/path",
            url,
            'https://<span class="highlight">domain.com/path</span>/to.something-I,want/',
        )
        search(
            ".something",
            url,
            'https://domain.com/path/to<span class="highlight">.something</span>-I,want/',
        )
        search(
            "to.something",
            url,
            'https://domain.com/path/<span class="highlight">to.something</span>-I,want/',
        )
        search(
            "something-I",
            url,
            'https://domain.com/path/to.<span class="highlight">something-I</span>,want/',
        )
        search(
            ",want",
            url,
            'https://domain.com/path/to.something-I<span class="highlight">,want</span>/',
        )
        search(
            "I,want",
            url,
            'https://domain.com/path/to.something-<span class="highlight">I,want</span>/',
        )

        # Search operands with HTML special characters
        special_search_narrow = [
            dict(operator="search", operand="butter"),
        ]
        special_search_result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(special_search_narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(special_search_result["messages"], 1)
        self.assertEqual(
            special_search_result["messages"][0][MATCH_TOPIC],
            'bread &amp; <span class="highlight">butter</span>',
        )

        special_search_narrow = [
            dict(operator="search", operand="&"),
        ]
        special_search_result = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(special_search_narrow).decode(),
                anchor=next_message_id,
                num_after=10,
                num_before=0,
            )
        )
        self.assert_length(special_search_result["messages"], 1)
        self.assertEqual(
            special_search_result["messages"][0][MATCH_TOPIC],
            'bread <span class="highlight">&amp;</span> butter',
        )
        self.assertEqual(
            special_search_result["messages"][0]["match_content"],
            '<p>chalk <span class="highlight">&amp;</span> cheese</p>',
        )

    def test_messages_in_narrow_for_non_search(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)

        def send(content: str) -> int:
            msg_id = self.send_stream_message(
                user,
                "Verona",
                topic_name="test_topic",
                content=content,
            )
            return msg_id

        good_id = send("http://foo.com")
        bad_id = send("no link here")
        msg_ids = [good_id, bad_id]
        send("http://bar.com but not in msg_ids")

        narrow = [
            dict(operator="has", operand="link"),
        ]

        raw_params = dict(msg_ids=msg_ids, narrow=narrow)
        params = {k: orjson.dumps(v).decode() for k, v in raw_params.items()}
        result = self.client_get("/json/messages/matches_narrow", params)
        messages = self.assert_json_success(result)["messages"]
        self.assert_length(messages, 1)
        message = messages[str(good_id)]
        self.assertIn("a href=", message["match_content"])
        self.assertIn("http://foo.com", message["match_content"])
        self.assertEqual(message[MATCH_TOPIC], "test_topic")

    def test_get_messages_with_only_searching_anchor(self) -> None:
        """
        Test that specifying an anchor but 0 for num_before and num_after
        returns at most 1 message.
        """
        self.login("cordelia")

        cordelia = self.example_user("cordelia")

        anchor = self.send_stream_message(cordelia, "Verona")

        narrow = [dict(operator="sender", operand=cordelia.email)]
        result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=anchor,
                num_before=0,
                num_after=0,
            )
        )
        self.assert_length(result["messages"], 1)

        narrow = [dict(operator="is", operand="mentioned")]
        result = self.get_and_check_messages(
            dict(narrow=orjson.dumps(narrow).decode(), anchor=anchor, num_before=0, num_after=0)
        )
        self.assert_length(result["messages"], 0)

    def test_get_messages_for_resolved_topics(self) -> None:
        self.login("cordelia")
        cordelia = self.example_user("cordelia")

        self.send_stream_message(cordelia, "Verona", "whatever1")
        resolved_topic_name = RESOLVED_TOPIC_PREFIX + "foo"
        anchor = self.send_stream_message(cordelia, "Verona", "whatever2", resolved_topic_name)
        self.send_stream_message(cordelia, "Verona", "whatever3")

        narrow = [dict(operator="is", operand="resolved")]
        result = self.get_and_check_messages(
            dict(narrow=orjson.dumps(narrow).decode(), anchor=anchor, num_before=1, num_after=1)
        )
        self.assert_length(result["messages"], 1)
        self.assertEqual(result["messages"][0]["id"], anchor)

    def test_get_visible_messages_with_anchor(self) -> None:
        def messages_matches_ids(messages: List[Dict[str, Any]], message_ids: List[int]) -> None:
            self.assert_length(messages, len(message_ids))
            for message in messages:
                assert message["id"] in message_ids

        self.login("hamlet")

        Message.objects.all().delete()

        message_ids = [
            self.send_stream_message(self.example_user("cordelia"), "Verona") for i in range(10)
        ]

        data = self.get_messages_response(anchor=message_ids[9], num_before=9, num_after=0)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids)

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[9], num_before=9, num_after=0)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], True)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[2]):
            data = self.get_messages_response(anchor=message_ids[6], num_before=9, num_after=0)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], True)
        messages_matches_ids(messages, message_ids[2:7])

        with first_visible_id_as(message_ids[9] + 1):
            data = self.get_messages_response(anchor=message_ids[9], num_before=9, num_after=0)

        messages = data["messages"]
        self.assert_length(messages, 0)
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], True)

        data = self.get_messages_response(anchor=message_ids[5], num_before=0, num_after=5)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[7]):
            data = self.get_messages_response(anchor=message_ids[5], num_before=0, num_after=5)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids[7:])

        with first_visible_id_as(message_ids[2]):
            data = self.get_messages_response(anchor=message_ids[0], num_before=0, num_after=5)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids[2:7])

        with first_visible_id_as(message_ids[9] + 1):
            data = self.get_messages_response(anchor=message_ids[0], num_before=0, num_after=5)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)
        self.assert_length(messages, 0)

        # Verify that with anchor=0 we always get found_oldest=True
        with first_visible_id_as(0):
            data = self.get_messages_response(anchor=0, num_before=0, num_after=5)

        messages = data["messages"]
        messages_matches_ids(messages, message_ids[0:5])
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)

        # Verify that with anchor=-1 we always get found_oldest=True
        # anchor=-1 is arguably invalid input, but it used to be supported
        with first_visible_id_as(0):
            data = self.get_messages_response(anchor=-1, num_before=0, num_after=5)

        messages = data["messages"]
        messages_matches_ids(messages, message_ids[0:5])
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)

        # And anchor='first' does the same thing.
        with first_visible_id_as(0):
            data = self.get_messages_response(anchor="oldest", num_before=0, num_after=5)

        messages = data["messages"]
        messages_matches_ids(messages, message_ids[0:5])
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)

        data = self.get_messages_response(anchor=message_ids[5], num_before=5, num_after=4)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids)

        data = self.get_messages_response(anchor=message_ids[5], num_before=10, num_after=10)
        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids)

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[5], num_before=5, num_after=4)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], True)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[2], num_before=5, num_after=3)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], True)
        messages_matches_ids(messages, message_ids[5:8])

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[2], num_before=10, num_after=10)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], True)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[9] + 1):
            data = self.get_messages_response(anchor=message_ids[5], num_before=5, num_after=4)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], True)
        self.assert_length(messages, 0)

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[5], num_before=0, num_after=0)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], True)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids[5:6])

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[2], num_before=0, num_after=0)

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        self.assert_length(messages, 0)

        # Verify some additional behavior of found_newest.
        with first_visible_id_as(0):
            data = self.get_messages_response(
                anchor=LARGER_THAN_MAX_MESSAGE_ID, num_before=5, num_after=0
            )

        messages = data["messages"]
        self.assert_length(messages, 5)
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)

        # The anchor value of 'last' behaves just like LARGER_THAN_MAX_MESSAGE_ID.
        with first_visible_id_as(0):
            data = self.get_messages_response(anchor="newest", num_before=5, num_after=0)

        messages = data["messages"]
        self.assert_length(messages, 5)
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)

        with first_visible_id_as(0):
            data = self.get_messages_response(
                anchor=LARGER_THAN_MAX_MESSAGE_ID + 1, num_before=5, num_after=0
            )

        messages = data["messages"]
        self.assert_length(messages, 5)
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)

        with first_visible_id_as(0):
            data = self.get_messages_response(
                anchor=LARGER_THAN_MAX_MESSAGE_ID, num_before=20, num_after=0
            )

        messages = data["messages"]
        self.assert_length(messages, 10)
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], True)
        self.assertEqual(data["found_newest"], True)
        self.assertEqual(data["history_limited"], False)

        data = self.get_messages_response(
            anchor=message_ids[5], num_before=3, num_after=0, include_anchor=False
        )

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids[2:5])

        data = self.get_messages_response(
            anchor=message_ids[5], num_before=0, num_after=3, include_anchor=False
        )

        messages = data["messages"]
        self.assertEqual(data["found_anchor"], False)
        self.assertEqual(data["found_oldest"], False)
        self.assertEqual(data["found_newest"], False)
        self.assertEqual(data["history_limited"], False)
        messages_matches_ids(messages, message_ids[6:9])

    def test_missing_params(self) -> None:
        """
        anchor, num_before, and num_after are all required
        POST parameters for get_messages.
        """
        self.login("hamlet")

        required_args: Tuple[Tuple[str, int], ...] = (("num_before", 1), ("num_after", 1))

        for i in range(len(required_args)):
            post_params = dict(required_args[:i] + required_args[i + 1 :])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result, f"Missing '{required_args[i][0]}' argument")

    def test_get_messages_limits(self) -> None:
        """
        A call to GET /json/messages requesting more than
        MAX_MESSAGES_PER_FETCH messages returns an error message.
        """
        self.login("hamlet")
        result = self.client_get("/json/messages", dict(anchor=1, num_before=3000, num_after=3000))
        self.assert_json_error(result, "Too many messages requested (maximum 5000).")
        result = self.client_get("/json/messages", dict(anchor=1, num_before=6000, num_after=0))
        self.assert_json_error(result, "Too many messages requested (maximum 5000).")
        result = self.client_get("/json/messages", dict(anchor=1, num_before=0, num_after=6000))
        self.assert_json_error(result, "Too many messages requested (maximum 5000).")

    def test_bad_int_params(self) -> None:
        """
        num_before, num_after, and narrow must all be non-negative
        integers or strings that can be converted to non-negative integers.
        """
        self.login("hamlet")

        other_params = {"narrow": {}, "anchor": 0}
        int_params = ["num_before", "num_after"]

        bad_types = (False, "", "-1", -1)
        for idx, param in enumerate(int_params):
            for type in bad_types:
                # Rotate through every bad type for every integer
                # parameter, one at a time.
                post_params = {
                    **other_params,
                    param: type,
                    **dict.fromkeys(int_params[:idx] + int_params[idx + 1 :], 0),
                }
                result = self.client_get("/json/messages", post_params)
                self.assert_json_error(result, f"Bad value for '{param}': {type}")

    def test_bad_include_anchor(self) -> None:
        self.login("hamlet")
        result = self.client_get(
            "/json/messages", dict(anchor=1, num_before=1, num_after=1, include_anchor="false")
        )
        self.assert_json_error(result, "The anchor can only be excluded at an end of the range")

    def test_bad_narrow_type(self) -> None:
        """
        narrow must be a list of string pairs.
        """
        self.login("hamlet")

        other_params = {"anchor": 0, "num_before": 0, "num_after": 0}

        bad_types: Tuple[Union[int, str, bool], ...] = (
            False,
            0,
            "",
            "{malformed json,",
            "{foo: 3}",
            "[1,2]",
            '[["x","y","z"]]',
        )
        for type in bad_types:
            post_params = {**other_params, "narrow": type}
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result, f"Bad value for 'narrow': {type}")

    def test_bad_narrow_operator(self) -> None:
        """
        Unrecognized narrow operators are rejected.
        """
        self.login("hamlet")
        for operator in ["", "foo", "channel:verona", "__init__"]:
            narrow = [dict(operator=operator, operand="")]
            params = dict(anchor=0, num_before=0, num_after=0, narrow=orjson.dumps(narrow).decode())
            result = self.client_get("/json/messages", params)
            self.assert_json_error_contains(result, "Invalid narrow operator: unknown operator")

    def test_invalid_narrow_operand_in_dict(self) -> None:
        self.login("hamlet")

        # str or int is required for "id", "sender", "channel", "dm-including" and "group-pm-with"
        # operators
        invalid_operands = [["1"], [2], None]
        error_msg = 'elem["operand"] is not a string or integer'
        for operand in ["id", "sender", "channel", "dm-including", "group-pm-with"]:
            self.exercise_bad_narrow_operand_using_dict_api(operand, invalid_operands, error_msg)

        # str or int list is required for "dm" and "pm-with" operator
        invalid_operands = [None]
        error_msg = 'elem["operand"] is not a string or an integer list'
        for operand in ["dm", "pm-with"]:
            self.exercise_bad_narrow_operand_using_dict_api(operand, invalid_operands, error_msg)

        invalid_operands = [["2"]]
        error_msg = 'elem["operand"][0] is not an integer'
        for operand in ["dm", "pm-with"]:
            self.exercise_bad_narrow_operand_using_dict_api(operand, invalid_operands, error_msg)

        # For others only str is acceptable
        invalid_operands = [2, None, [1]]
        error_msg = 'elem["operand"] is not a string'
        for operand in ["is", "near", "has"]:
            self.exercise_bad_narrow_operand_using_dict_api(operand, invalid_operands, error_msg)

        # Disallow empty search terms
        error_msg = 'elem["operand"] cannot be blank.'
        self.exercise_bad_narrow_operand_using_dict_api("search", [""], error_msg)

    # The exercise_bad_narrow_operand helper method uses legacy tuple format to
    # test bad narrow, this method uses the current dict API format
    def exercise_bad_narrow_operand_using_dict_api(
        self, operator: str, operands: Sequence[Any], error_msg: str
    ) -> None:
        for operand in operands:
            narrow = [dict(operator=operator, operand=operand)]
            params = dict(anchor=0, num_before=0, num_after=0, narrow=orjson.dumps(narrow).decode())
            result = self.client_get("/json/messages", params)
            self.assert_json_error_contains(result, error_msg)

    def exercise_bad_narrow_operand(
        self, operator: str, operands: Sequence[Any], error_msg: str
    ) -> None:
        other_params = {"anchor": "0", "num_before": "0", "num_after": "0"}
        for operand in operands:
            post_params = {**other_params, "narrow": orjson.dumps([[operator, operand]]).decode()}
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error_contains(result, error_msg)

    def test_bad_narrow_channel_content(self) -> None:
        """
        If an invalid channel name is requested in get_messages, an error is
        returned.
        """
        self.login("hamlet")
        bad_channel_content: Tuple[int, List[None], List[str]] = (0, [], ["x", "y"])
        self.exercise_bad_narrow_operand("channel", bad_channel_content, "Bad value for 'narrow'")

    def test_bad_narrow_one_on_one_email_content(self) -> None:
        """
        If an invalid "dm" narrow is requested in get_messages,
        an error is returned.
        """
        self.login("hamlet")
        bad_channel_content: Tuple[int, List[None], List[str]] = (0, [], ["x", "y"])
        self.exercise_bad_narrow_operand("dm", bad_channel_content, "Bad value for 'narrow'")

    def test_bad_narrow_nonexistent_channel(self) -> None:
        self.login("hamlet")
        self.exercise_bad_narrow_operand(
            "channel", ["non-existent channel"], "Invalid narrow operator: unknown channel"
        )

        non_existing_channel_id = 1232891381239
        self.exercise_bad_narrow_operand_using_dict_api(
            "channel", [non_existing_channel_id], "Invalid narrow operator: unknown channel"
        )

    def test_bad_narrow_nonexistent_email(self) -> None:
        self.login("hamlet")
        self.exercise_bad_narrow_operand(
            "dm", ["non-existent-user@zulip.com"], "Invalid narrow operator: unknown user"
        )

    def test_bad_narrow_dm_id_list(self) -> None:
        self.login("hamlet")
        self.exercise_bad_narrow_operand("dm", [-24], "Bad value for 'narrow': [[\"dm\",-24]]")

    def test_message_without_rendered_content(self) -> None:
        """Older messages may not have rendered_content in the database"""
        m = self.get_last_message()
        m.rendered_content = m.rendered_content_version = None
        m.content = "test content"
        wide_dict = MessageDict.wide_dict(m)
        final_dict = MessageDict.finalize_payload(
            wide_dict,
            apply_markdown=True,
            client_gravatar=False,
        )
        self.assertEqual(final_dict["content"], "<p>test content</p>")

    def common_check_get_messages_query(
        self, query_params: Dict[str, object], expected: str
    ) -> None:
        user_profile = self.example_user("hamlet")
        request = HostRequestMock(query_params, user_profile)
        with queries_captured() as queries:
            get_messages_backend(request, user_profile)

        for query in queries:
            sql = str(query.sql)
            if "/* get_messages */" in sql:
                sql = sql.replace(" /* get_messages */", "")
                self.assertEqual(sql, expected)
                return
        raise AssertionError("get_messages query not found")

    def test_find_first_unread_anchor(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")

        self.make_stream("England")
        self.subscribe(cordelia, "England")

        # Send a few messages that Hamlet won't have UserMessage rows for.
        unsub_message_id = self.send_stream_message(cordelia, "England")
        self.send_personal_message(cordelia, othello)

        self.subscribe(hamlet, "England")

        muted_topics = [
            ["England", "muted"],
        ]
        set_topic_visibility_policy(hamlet, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        # send a muted message
        muted_message_id = self.send_stream_message(cordelia, "England", topic_name="muted")

        # finally send Hamlet a "normal" message
        first_message_id = self.send_stream_message(cordelia, "England")

        # send a few more messages
        extra_message_id = self.send_stream_message(cordelia, "England")
        self.send_personal_message(cordelia, hamlet)

        user_profile = hamlet

        with get_sqlalchemy_connection() as sa_conn:
            anchor = find_first_unread_anchor(
                sa_conn=sa_conn,
                user_profile=user_profile,
                narrow=[],
            )
        self.assertEqual(anchor, first_message_id)

        # With the same data setup, we now want to test that a reasonable
        # search still gets the first message sent to Hamlet (before he
        # subscribed) and other recent messages to the channel.
        query_params = dict(
            anchor="first_unread",
            num_before=10,
            num_after=10,
            narrow='[["channel", "England"]]',
        )
        request = HostRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = orjson.loads(payload.content)
        self.assertEqual(result["anchor"], first_message_id)
        self.assertEqual(result["found_newest"], True)
        self.assertEqual(result["found_oldest"], True)

        messages = result["messages"]
        self.assertEqual(
            {msg["id"] for msg in messages},
            {unsub_message_id, muted_message_id, first_message_id, extra_message_id},
        )

    def test_parse_anchor_value(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        # Send the first message to Hamlet
        first_message_id = self.send_personal_message(cordelia, hamlet)

        # Send another message
        self.send_personal_message(cordelia, hamlet)

        user_profile = hamlet

        # Check if the anchor value in response is correct for different
        # values of anchor parameter in request

        # With anchor input as first_unread, see if response anchor
        # value is same as the id of first unread message of Hamlet
        query_params = dict(
            anchor="first_unread",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = orjson.loads(payload.content)
        self.assertEqual(result["anchor"], first_message_id)

        # With anchor input as oldest, see if response anchor value is 0
        query_params = dict(
            anchor="oldest",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = orjson.loads(payload.content)
        self.assertEqual(result["anchor"], 0)

        # With anchor input as newest, see if response
        # anchor value is LARGER_THAN_MAX_MESSAGE_ID
        query_params = dict(
            anchor="newest",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = orjson.loads(payload.content)
        self.assertEqual(result["anchor"], LARGER_THAN_MAX_MESSAGE_ID)

        # With anchor input negative, see if
        # response anchor value is clamped to 0
        query_params = dict(
            anchor="-1",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = orjson.loads(payload.content)
        self.assertEqual(result["anchor"], 0)

        # With anchor input more than LARGER_THAN_MAX_MESSAGE_ID,
        # see if response anchor value is clamped down to LARGER_THAN_MAX_MESSAGE_ID
        query_params = dict(
            anchor="10000000000000001",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = orjson.loads(payload.content)
        self.assertEqual(result["anchor"], LARGER_THAN_MAX_MESSAGE_ID)

    def test_use_first_unread_anchor_with_some_unread_messages(self) -> None:
        user_profile = self.example_user("hamlet")

        # Have Othello send messages to Hamlet that he hasn't read.
        # Here, Hamlet isn't subscribed to the channel Scotland
        self.send_stream_message(self.example_user("othello"), "Scotland")
        first_unread_message_id = self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
        )

        # Add a few messages that help us test that our query doesn't
        # look at messages that are irrelevant to Hamlet.
        self.send_personal_message(self.example_user("othello"), self.example_user("cordelia"))
        self.send_personal_message(self.example_user("othello"), self.example_user("iago"))

        query_params = dict(
            anchor="first_unread",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_messages_backend(request, user_profile)

        # Verify the query for old messages looks correct.
        queries = [q for q in all_queries if "/* get_messages */" in q.sql]
        self.assert_length(queries, 1)
        sql = queries[0].sql
        self.assertNotIn(f"AND message_id = {LARGER_THAN_MAX_MESSAGE_ID}", sql)
        self.assertIn("ORDER BY message_id ASC", sql)

        cond = (
            f"WHERE user_profile_id = {user_profile.id} AND message_id >= {first_unread_message_id}"
        )
        self.assertIn(cond, sql)
        cond = f"WHERE user_profile_id = {user_profile.id} AND message_id <= {first_unread_message_id - 1}"
        self.assertIn(cond, sql)
        self.assertIn("UNION", sql)

    def test_visible_messages_use_first_unread_anchor_with_some_unread_messages(self) -> None:
        user_profile = self.example_user("hamlet")

        # Have Othello send messages to Hamlet that he hasn't read.
        self.subscribe(self.example_user("hamlet"), "Scotland")

        first_unread_message_id = self.send_stream_message(self.example_user("othello"), "Scotland")
        self.send_stream_message(self.example_user("othello"), "Scotland")
        self.send_stream_message(self.example_user("othello"), "Scotland")
        self.send_personal_message(
            self.example_user("othello"),
            self.example_user("hamlet"),
        )

        # Add a few messages that help us test that our query doesn't
        # look at messages that are irrelevant to Hamlet.
        self.send_personal_message(self.example_user("othello"), self.example_user("cordelia"))
        self.send_personal_message(self.example_user("othello"), self.example_user("iago"))

        query_params = dict(
            anchor="first_unread",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        first_visible_message_id = first_unread_message_id + 2
        with first_visible_id_as(first_visible_message_id):
            with queries_captured() as all_queries:
                get_messages_backend(request, user_profile)

        queries = [q for q in all_queries if "/* get_messages */" in q.sql]
        self.assert_length(queries, 1)
        sql = queries[0].sql
        self.assertNotIn(f"AND message_id = {LARGER_THAN_MAX_MESSAGE_ID}", sql)
        self.assertIn("ORDER BY message_id ASC", sql)
        cond = f"WHERE user_profile_id = {user_profile.id} AND message_id <= {first_unread_message_id - 1}"
        self.assertIn(cond, sql)
        cond = f"WHERE user_profile_id = {user_profile.id} AND message_id >= {first_visible_message_id}"
        self.assertIn(cond, sql)

    def test_use_first_unread_anchor_with_no_unread_messages(self) -> None:
        user_profile = self.example_user("hamlet")

        query_params = dict(
            anchor="first_unread",
            num_before=10,
            num_after=10,
            narrow="[]",
        )
        request = HostRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_messages_backend(request, user_profile)

        queries = [q for q in all_queries if "/* get_messages */" in q.sql]
        self.assert_length(queries, 1)

        sql = queries[0].sql

        self.assertNotIn("AND message_id <=", sql)
        self.assertNotIn("AND message_id >=", sql)

        request = HostRequestMock(query_params, user_profile)
        first_visible_message_id = 5
        with first_visible_id_as(first_visible_message_id):
            with queries_captured() as all_queries:
                get_messages_backend(request, user_profile)
            queries = [q for q in all_queries if "/* get_messages */" in q.sql]
            sql = queries[0].sql
            self.assertNotIn("AND message_id <=", sql)
            self.assertNotIn("AND message_id >=", sql)

    def test_use_first_unread_anchor_with_muted_topics(self) -> None:
        """
        Test that our logic related to `use_first_unread_anchor`
        invokes the `message_id = LARGER_THAN_MAX_MESSAGE_ID` hack for
        the `/* get_messages */` query when relevant muting
        is in effect.

        This is a very arcane test on arcane, but very heavily
        field-tested, logic in get_messages_backend().  If
        this test breaks, be absolutely sure you know what you're
        doing.
        """

        realm = get_realm("zulip")
        self.make_stream("web stuff")
        self.make_stream("bogus")
        user_profile = self.example_user("hamlet")
        muted_topics = [
            ["Scotland", "golf"],
            ["web stuff", "css"],
            ["bogus", "bogus"],
        ]
        set_topic_visibility_policy(user_profile, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        query_params = dict(
            anchor="first_unread",
            num_before=0,
            num_after=0,
            narrow='[["channel", "Scotland"]]',
        )
        request = HostRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_messages_backend(request, user_profile)

        # Do some tests on the main query, to verify the muting logic
        # runs on this code path.
        queries = [q for q in all_queries if q.sql.startswith("SELECT message_id, flags")]
        self.assert_length(queries, 1)

        channel = get_stream("Scotland", realm)
        assert channel.recipient is not None
        recipient_id = channel.recipient.id
        cond = f"AND NOT (recipient_id = {recipient_id} AND upper(subject) = upper('golf'))"
        self.assertIn(cond, queries[0].sql)

        # Next, verify the use_first_unread_anchor setting invokes
        # the `message_id = LARGER_THAN_MAX_MESSAGE_ID` hack.
        queries = [q for q in all_queries if "/* get_messages */" in q.sql]
        self.assert_length(queries, 1)
        self.assertIn(f"AND zerver_message.id = {LARGER_THAN_MAX_MESSAGE_ID}", queries[0].sql)

    def test_exclude_muting_conditions(self) -> None:
        realm = get_realm("zulip")
        self.make_stream("web stuff")
        user_profile = self.example_user("hamlet")

        self.make_stream("irrelevant_channel")

        # Test the do-nothing case first.
        muted_topics = [
            ["irrelevant_channel", "irrelevant_topic"],
        ]
        set_topic_visibility_policy(user_profile, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        # If nothing relevant is muted, then exclude_muting_conditions()
        # should return an empty list.
        narrow: List[Dict[str, object]] = [
            dict(operator="channel", operand="Scotland"),
        ]
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        self.assertEqual(muting_conditions, [])

        # Also test that passing channel ID works
        channel_id = get_stream("Scotland", realm).id
        narrow = [
            dict(operator="channel", operand=channel_id),
        ]
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        self.assertEqual(muting_conditions, [])

        # Ok, now set up our muted topics to include a topic relevant to our narrow.
        muted_topics = [
            ["Scotland", "golf"],
            ["web stuff", "css"],
        ]
        set_topic_visibility_policy(user_profile, muted_topics, UserTopic.VisibilityPolicy.MUTED)

        # And verify that our query will exclude them.
        narrow = [
            dict(operator="channel", operand="Scotland"),
        ]

        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select(column("id", Integer).label("message_id")).select_from(
            table("zerver_message")
        )
        query = query.where(*muting_conditions)
        expected_query = """\
SELECT id AS message_id \n\
FROM zerver_message \n\
WHERE NOT (recipient_id = %(recipient_id_1)s AND upper(subject) = upper(%(param_1)s))\
"""

        self.assertEqual(get_sqlalchemy_sql(query), expected_query)
        params = get_sqlalchemy_query_params(query)

        self.assertEqual(
            params["recipient_id_1"], get_recipient_id_for_channel_name(realm, "Scotland")
        )
        self.assertEqual(params["param_1"], "golf")

        mute_channel(realm, user_profile, "Verona")

        # Using a bogus channel name should be similar to using no narrow at
        # all, and we'll exclude all mutes.
        narrow = [
            dict(operator="channel", operand="bogus-channel-name"),
        ]

        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select(column("id", Integer)).select_from(table("zerver_message"))
        query = query.where(and_(*muting_conditions))

        expected_query = """\
SELECT id \n\
FROM zerver_message \n\
WHERE (recipient_id NOT IN (__[POSTCOMPILE_recipient_id_1])) \
AND NOT \
(recipient_id = %(recipient_id_2)s AND upper(subject) = upper(%(param_1)s) OR \
recipient_id = %(recipient_id_3)s AND upper(subject) = upper(%(param_2)s))\
"""
        self.assertEqual(get_sqlalchemy_sql(query), expected_query)
        params = get_sqlalchemy_query_params(query)
        self.assertEqual(
            params["recipient_id_1"], [get_recipient_id_for_channel_name(realm, "Verona")]
        )
        self.assertEqual(
            params["recipient_id_2"], get_recipient_id_for_channel_name(realm, "Scotland")
        )
        self.assertEqual(params["param_1"], "golf")
        self.assertEqual(
            params["recipient_id_3"], get_recipient_id_for_channel_name(realm, "web stuff")
        )
        self.assertEqual(params["param_2"], "css")

    def test_get_messages_queries(self) -> None:
        query_ids = self.get_query_ids()

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id = 0) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({"anchor": 0, "num_before": 0, "num_after": 0}, sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id = 0) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({"anchor": 0, "num_before": 1, "num_after": 0}, sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} ORDER BY message_id ASC \n LIMIT 2) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({"anchor": 0, "num_before": 0, "num_after": 1}, sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} ORDER BY message_id ASC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({"anchor": 0, "num_before": 0, "num_after": 10}, sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 100 ORDER BY message_id DESC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({"anchor": 100, "num_before": 10, "num_after": 0}, sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM ((SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 99 ORDER BY message_id DESC \n LIMIT 10) UNION ALL (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 100 ORDER BY message_id ASC \n LIMIT 11)) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {"anchor": 100, "num_before": 10, "num_after": 10}, sql
        )

    def test_get_messages_with_narrow_queries(self) -> None:
        query_ids = self.get_query_ids()
        hamlet_email = self.example_user("hamlet").email
        othello_email = self.example_user("othello").email

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2048) != 0 AND realm_id = {realm_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id = 0) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 0,
                "narrow": f'[["dm", "{othello_email}"]]',
            },
            sql,
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2048) != 0 AND realm_id = {realm_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id = 0) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 1,
                "num_after": 0,
                "narrow": f'[["dm", "{othello_email}"]]',
            },
            sql,
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2048) != 0 AND realm_id = {realm_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": f'[["dm", "{othello_email}"]]',
            },
            sql,
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2) != 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {"anchor": 0, "num_before": 0, "num_after": 9, "narrow": '[["is", "starred"]]'}, sql
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {othello_id} ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": f'[["sender", "{othello_email}"]]',
            },
            sql,
        )

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE realm_id = 2 AND recipient_id = {scotland_recipient} ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {"anchor": 0, "num_before": 0, "num_after": 9, "narrow": '[["channel", "Scotland"]]'},
            sql,
        )

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE realm_id = 2 AND recipient_id IN ({public_channels_recipients}) ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {"anchor": 0, "num_before": 0, "num_after": 9, "narrow": '[["channels", "public"]]'},
            sql,
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (recipient_id NOT IN ({public_channels_recipients})) ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": '[{"operator":"channels", "operand":"public", "negated": true}]',
            },
            sql,
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND upper(subject) = upper('blah') ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {"anchor": 0, "num_before": 0, "num_after": 9, "narrow": '[["topic", "blah"]]'}, sql
        )

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE realm_id = 2 AND recipient_id = {scotland_recipient} AND upper(subject) = upper('blah') ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": '[["channel", "Scotland"], ["topic", "blah"]]',
            },
            sql,
        )

        # Narrow to direct messages with yourself
        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2048) != 0 AND realm_id = {realm_id} AND sender_id = {hamlet_id} AND recipient_id = {hamlet_recipient} ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": f'[["dm", "{hamlet_email}"]]',
            },
            sql,
        )

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND recipient_id = {scotland_recipient} AND (flags & 2) != 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": '[["channel", "Scotland"], ["is", "starred"]]',
            },
            sql,
        )

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_queries(self) -> None:
        query_ids = self.get_query_ids()

        sql_template = """\
SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.topic_matches \n\
FROM (SELECT message_id, flags, subject, rendered_content, array((SELECT ARRAY[sum(length(anon_3) - 11) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) + 11, strpos(anon_3, '</ts-match>') - 1] AS anon_2 \n\
FROM unnest(string_to_array(ts_headline('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping'), 'HighlightAll = TRUE, StartSel = <ts-match>, StopSel = </ts-match>'), '<ts-match>')) AS anon_3\n\
 LIMIT ALL OFFSET 1)) AS content_matches, array((SELECT ARRAY[sum(length(anon_5) - 11) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) + 11, strpos(anon_5, '</ts-match>') - 1] AS anon_4 \n\
FROM unnest(string_to_array(ts_headline('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping'), 'HighlightAll = TRUE, StartSel = <ts-match>, StopSel = </ts-match>'), '<ts-match>')) AS anon_5\n\
 LIMIT ALL OFFSET 1)) AS topic_matches \n\
FROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \n\
WHERE user_profile_id = {hamlet_id} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) ORDER BY message_id ASC \n\
 LIMIT 10) AS anon_1 ORDER BY message_id ASC\
"""
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {"anchor": 0, "num_before": 0, "num_after": 9, "narrow": '[["search", "jumping"]]'}, sql
        )

        sql_template = """\
SELECT anon_1.message_id, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.topic_matches \n\
FROM (SELECT id AS message_id, subject, rendered_content, array((SELECT ARRAY[sum(length(anon_3) - 11) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) + 11, strpos(anon_3, '</ts-match>') - 1] AS anon_2 \n\
FROM unnest(string_to_array(ts_headline('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping'), 'HighlightAll = TRUE, StartSel = <ts-match>, StopSel = </ts-match>'), '<ts-match>')) AS anon_3\n\
 LIMIT ALL OFFSET 1)) AS content_matches, array((SELECT ARRAY[sum(length(anon_5) - 11) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) + 11, strpos(anon_5, '</ts-match>') - 1] AS anon_4 \n\
FROM unnest(string_to_array(ts_headline('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping'), 'HighlightAll = TRUE, StartSel = <ts-match>, StopSel = </ts-match>'), '<ts-match>')) AS anon_5\n\
 LIMIT ALL OFFSET 1)) AS topic_matches \n\
FROM zerver_message \n\
WHERE realm_id = 2 AND recipient_id = {scotland_recipient} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) ORDER BY zerver_message.id ASC \n\
 LIMIT 10) AS anon_1 ORDER BY message_id ASC\
"""
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": '[["channel", "Scotland"], ["search", "jumping"]]',
            },
            sql,
        )

        sql_template = """\
SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.topic_matches \n\
FROM (SELECT message_id, flags, subject, rendered_content, array((SELECT ARRAY[sum(length(anon_3) - 11) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) + 11, strpos(anon_3, '</ts-match>') - 1] AS anon_2 \n\
FROM unnest(string_to_array(ts_headline('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', '"jumping" quickly'), 'HighlightAll = TRUE, StartSel = <ts-match>, StopSel = </ts-match>'), '<ts-match>')) AS anon_3\n\
 LIMIT ALL OFFSET 1)) AS content_matches, array((SELECT ARRAY[sum(length(anon_5) - 11) OVER (ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) + 11, strpos(anon_5, '</ts-match>') - 1] AS anon_4 \n\
FROM unnest(string_to_array(ts_headline('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', '"jumping" quickly'), 'HighlightAll = TRUE, StartSel = <ts-match>, StopSel = </ts-match>'), '<ts-match>')) AS anon_5\n\
 LIMIT ALL OFFSET 1)) AS topic_matches \n\
FROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \n\
WHERE user_profile_id = {hamlet_id} AND (content ILIKE '%jumping%' OR subject ILIKE '%jumping%') AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', '"jumping" quickly')) ORDER BY message_id ASC \n\
 LIMIT 10) AS anon_1 ORDER BY message_id ASC\
"""
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query(
            {
                "anchor": 0,
                "num_before": 0,
                "num_after": 9,
                "narrow": '[["search", "\\"jumping\\" quickly"]]',
            },
            sql,
        )

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_using_email(self) -> None:
        self.login("cordelia")

        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")

        messages_to_search = [
            ("say hello", "How are you doing, @**Othello, the Moor of Venice**?"),
            ("lunch plans", "I am hungry!"),
        ]
        next_message_id = self.get_last_message().id + 1

        for topic, content in messages_to_search:
            self.send_stream_message(
                cordelia,
                "Verona",
                content=content,
                topic_name=topic,
            )

        self._update_tsvector_index()

        narrow = [
            dict(operator="sender", operand=cordelia.email),
            dict(operator="search", operand=othello.email),
        ]
        result: Dict[str, Any] = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=next_message_id,
                num_after=10,
            )
        )
        self.assert_length(result["messages"], 0)

        narrow = [
            dict(operator="sender", operand=cordelia.email),
            dict(operator="search", operand="othello"),
        ]
        result = self.get_and_check_messages(
            dict(
                narrow=orjson.dumps(narrow).decode(),
                anchor=next_message_id,
                num_after=10,
            )
        )
        self.assert_length(result["messages"], 1)
        messages = result["messages"]

        (hello_message,) = (m for m in messages if m[TOPIC_NAME] == "say hello")
        self.assertEqual(hello_message[MATCH_TOPIC], "say hello")
        self.assertEqual(
            hello_message["match_content"],
            f'<p>How are you doing, <span class="user-mention" data-user-id="{othello.id}">'
            '@<span class="highlight">Othello</span>, the Moor of Venice</span>?</p>',
        )


class MessageHasKeywordsTest(ZulipTestCase):
    """Test for keywords like has_link, has_image, has_attachment."""

    def setup_dummy_attachments(self, user_profile: UserProfile) -> List[str]:
        sample_size = 10
        realm_id = user_profile.realm_id
        dummy_files = [
            ("zulip.txt", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt", sample_size),
            ("temp_file.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py", sample_size),
            ("abc.py", f"{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py", sample_size),
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, user_profile.realm, size)

        # return path ids
        return [x[1] for x in dummy_files]

    def test_claim_attachment(self) -> None:
        user_profile = self.example_user("hamlet")
        dummy_path_ids = self.setup_dummy_attachments(user_profile)
        dummy_urls = [f"http://zulip.testserver/user_uploads/{x}" for x in dummy_path_ids]

        # Send message referring the attachment
        self.subscribe(user_profile, "Denmark")

        def assert_attachment_claimed(path_id: str, claimed: bool) -> None:
            attachment = Attachment.objects.get(path_id=path_id)
            self.assertEqual(attachment.is_claimed(), claimed)

        # This message should claim attachments 1 only because attachment 2
        # is not being parsed as a link by Markdown.
        body = (
            f"Some files here ...[zulip.txt]({dummy_urls[0]})"
            f"{dummy_urls[1]}.... Some more...."
            f"{dummy_urls[1]}"
        )
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[0], True)
        assert_attachment_claimed(dummy_path_ids[1], False)

        # This message tries to claim the third attachment but fails because
        # Markdown would not set has_attachments = True here.
        body = f"Link in code: `{dummy_urls[2]}`"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], False)

        # Another scenario where we wouldn't parse the link.
        body = f"Link to not parse: .{dummy_urls[2]}.`"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], False)

        # Finally, claim attachment 3.
        body = f"Link: {dummy_urls[2]}"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], True)
        assert_attachment_claimed(dummy_path_ids[1], False)

    def test_finds_all_links(self) -> None:
        msg_contents = ["foo.org", "[bar](baz.gov)", "http://quux.ca"]
        msg_ids = [
            self.send_stream_message(self.example_user("hamlet"), "Denmark", content=msg_content)
            for msg_content in msg_contents
        ]
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertTrue(all(msg.has_link for msg in msgs))

    def test_finds_only_links(self) -> None:
        msg_contents = ["`example.org`", "``example.org```", "$$https://example.org$$", "foo"]
        msg_ids = [
            self.send_stream_message(self.example_user("hamlet"), "Denmark", content=msg_content)
            for msg_content in msg_contents
        ]
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertFalse(all(msg.has_link for msg in msgs))

    def update_message(self, msg: Message, content: str) -> None:
        hamlet = self.example_user("hamlet")
        realm_id = hamlet.realm.id
        rendering_result = render_message_markdown(msg, content)
        mention_backend = MentionBackend(realm_id)
        mention_data = MentionData(mention_backend, content, msg.sender)
        do_update_message(
            hamlet,
            msg,
            None,
            None,
            "change_one",
            False,
            False,
            content,
            rendering_result,
            set(),
            mention_data=mention_data,
        )

    def test_finds_link_after_edit(self) -> None:
        hamlet = self.example_user("hamlet")
        msg_id = self.send_stream_message(hamlet, "Denmark", content="a")
        msg = Message.objects.get(id=msg_id)

        self.assertFalse(msg.has_link)
        self.update_message(msg, "a http://foo.com")
        self.assertTrue(msg.has_link)
        self.update_message(msg, "a")
        self.assertFalse(msg.has_link)
        # Check in blockquotes work
        self.update_message(msg, "> http://bar.com")
        self.assertTrue(msg.has_link)
        self.update_message(msg, "a `http://foo.com`")
        self.assertFalse(msg.has_link)

    def test_has_image(self) -> None:
        msg_contents = [
            "Link: foo.org",
            "Image: https://www.google.com/images/srpr/logo4w.png",
            "Image: https://www.google.com/images/srpr/logo4w.pdf",
            "[Google link](https://www.google.com/images/srpr/logo4w.png)",
        ]
        msg_ids = [
            self.send_stream_message(self.example_user("hamlet"), "Denmark", content=msg_content)
            for msg_content in msg_contents
        ]
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertEqual([False, True, False, True], [msg.has_image for msg in msgs])

        self.update_message(msgs[0], "https://www.google.com/images/srpr/logo4w.png")
        self.assertTrue(msgs[0].has_image)
        self.update_message(msgs[0], "No image again")
        self.assertFalse(msgs[0].has_image)

    def test_has_attachment(self) -> None:
        hamlet = self.example_user("hamlet")
        dummy_path_ids = self.setup_dummy_attachments(hamlet)
        dummy_urls = [f"http://zulip.testserver/user_uploads/{x}" for x in dummy_path_ids]
        self.subscribe(hamlet, "Denmark")

        body = f"Files ...[zulip.txt]({dummy_urls[0]}) {dummy_urls[1]} {dummy_urls[2]}"

        msg_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        msg = Message.objects.get(id=msg_id)
        self.assertTrue(msg.has_attachment)
        self.update_message(msg, "No attachments")
        self.assertFalse(msg.has_attachment)
        self.update_message(msg, body)
        self.assertTrue(msg.has_attachment)
        self.update_message(msg, f"Link in code: `{dummy_urls[1]}`")
        self.assertFalse(msg.has_attachment)
        # Test blockquotes
        self.update_message(msg, f"> {dummy_urls[1]}")
        self.assertTrue(msg.has_attachment)

        # Additional test to check has_attachment is being set is due to the correct attachment.
        self.update_message(msg, f"Outside: {dummy_urls[0]}. In code: `{dummy_urls[1]}`.")
        self.assertTrue(msg.has_attachment)
        self.assertTrue(msg.attachment_set.filter(path_id=dummy_path_ids[0]))
        self.assertEqual(msg.attachment_set.count(), 1)

        self.update_message(msg, f"Outside: {dummy_urls[1]}. In code: `{dummy_urls[0]}`.")
        self.assertTrue(msg.has_attachment)
        self.assertTrue(msg.attachment_set.filter(path_id=dummy_path_ids[1]))
        self.assertEqual(msg.attachment_set.count(), 1)

        self.update_message(msg, f"Both in code: `{dummy_urls[1]} {dummy_urls[0]}`.")
        self.assertFalse(msg.has_attachment)
        self.assertEqual(msg.attachment_set.count(), 0)

    def test_potential_attachment_path_ids(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        dummy_path_ids = self.setup_dummy_attachments(hamlet)

        body = "Hello"
        msg_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        msg = Message.objects.get(id=msg_id)

        with mock.patch(
            "zerver.actions.uploads.do_claim_attachments", wraps=do_claim_attachments
        ) as m:
            self.update_message(
                msg, f"[link](http://{hamlet.realm.host}/user_uploads/{dummy_path_ids[0]})"
            )
            self.assertTrue(m.called)
            m.reset_mock()

            self.update_message(msg, f"[link](/user_uploads/{dummy_path_ids[1]})")
            self.assertTrue(m.called)
            m.reset_mock()

            self.update_message(msg, f"[new text link](/user_uploads/{dummy_path_ids[1]})")
            self.assertFalse(m.called)
            m.reset_mock()

            # It's not clear this is correct behavior
            self.update_message(msg, f"[link](user_uploads/{dummy_path_ids[2]})")
            self.assertFalse(m.called)
            m.reset_mock()

            self.update_message(msg, f"[link](https://github.com/user_uploads/{dummy_path_ids[0]})")
            self.assertFalse(m.called)
            m.reset_mock()

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


class PersonalMessagesNearTest(ZulipTestCase):
    def test_near_pm_message_url(self) -> None:
        realm = get_realm("zulip")
        message = dict(
            type="personal",
            id=555,
            display_recipient=[
                dict(id=77),
                dict(id=80),
            ],
        )
        url = near_message_url(
            realm=realm,
            message=message,
        )
        self.assertEqual(url, "http://zulip.testserver/#narrow/dm/77,80-pm/near/555")
