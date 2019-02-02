# -*- coding: utf-8 -*-


from django.db import connection
from django.test import TestCase, override_settings
from sqlalchemy.sql import (
    and_, select, column, table,
)
from sqlalchemy.sql import compiler

from zerver.models import (
    Realm, Subscription,
    get_display_recipient, get_personal_recipient, get_realm, get_stream,
    UserMessage, get_stream_recipient, Message
)
from zerver.lib.message import (
    MessageDict,
)
from zerver.lib.narrow import (
    build_narrow_filter,
    is_web_public_compatible,
)
from zerver.lib.request import JsonableError
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_helpers import (
    POSTRequestMock,
    get_user_messages, queries_captured,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.topic import (
    MATCH_TOPIC,
    TOPIC_NAME,
)
from zerver.lib.topic_mutes import (
    set_topic_mutes,
)
from zerver.views.messages import (
    exclude_muting_conditions,
    get_messages_backend, ok_to_include_history,
    NarrowBuilder, BadNarrowOperator, Query,
    post_process_limited_query,
    find_first_unread_anchor,
    LARGER_THAN_MAX_MESSAGE_ID,
)

from typing import Dict, List, Sequence, Tuple, Union, Any, Optional
import mock
import os
import re
import ujson

def get_sqlalchemy_query_params(query: str) -> Dict[str, str]:
    dialect = get_sqlalchemy_connection().dialect
    comp = compiler.SQLCompiler(dialect, query)
    return comp.params

def fix_ws(s: str) -> str:
    return re.sub(r'\s+', ' ', str(s)).strip()

def get_recipient_id_for_stream_name(realm: Realm, stream_name: str) -> str:
    stream = get_stream(stream_name, realm)
    return get_stream_recipient(stream.id).id

def mute_stream(realm: Realm, user_profile: str, stream_name: str) -> None:
    stream = get_stream(stream_name, realm)
    recipient = get_stream_recipient(stream.id)
    subscription = Subscription.objects.get(recipient=recipient, user_profile=user_profile)
    subscription.in_home_view = False
    subscription.save()

def first_visible_id_as(message_id: int) -> Any:
    return mock.patch(
        'zerver.views.messages.get_first_visible_message_id',
        return_value=message_id,
    )

class NarrowBuilderTest(ZulipTestCase):
    def setUp(self) -> None:
        self.realm = get_realm('zulip')
        self.user_profile = self.example_user('hamlet')
        self.builder = NarrowBuilder(self.user_profile, column('id'))
        self.raw_query = select([column("id")], None, table("zerver_message"))

    def test_add_term_using_not_defined_operator(self) -> None:
        term = dict(operator='not-defined', operand='any')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_stream_operator(self) -> None:
        term = dict(operator='stream', operand='Scotland')
        self._do_add_term_test(term, 'WHERE recipient_id = :recipient_id_1')

    def test_add_term_using_stream_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator='stream', operand='Scotland', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id != :recipient_id_1')

    def test_add_term_using_stream_operator_and_non_existing_operand_should_raise_error(
            self) -> None:  # NEGATED
        term = dict(operator='stream', operand='NonExistingStream')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_is_operator_and_private_operand(self) -> None:
        term = dict(operator='is', operand='private')
        self._do_add_term_test(term, 'WHERE (flags & :flags_1) != :param_1')

    def test_add_term_using_is_operator_private_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='is', operand='private', negated=True)
        self._do_add_term_test(term, 'WHERE (flags & :flags_1) = :param_1')

    def test_add_term_using_is_operator_and_non_private_operand(self) -> None:
        for operand in ['starred', 'mentioned', 'alerted']:
            term = dict(operator='is', operand=operand)
            self._do_add_term_test(term, 'WHERE (flags & :flags_1) != :param_1')

    def test_add_term_using_is_operator_and_unread_operand(self) -> None:
        term = dict(operator='is', operand='unread')
        self._do_add_term_test(term, 'WHERE (flags & :flags_1) = :param_1')

    def test_add_term_using_is_operator_and_unread_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='is', operand='unread', negated=True)
        self._do_add_term_test(term, 'WHERE (flags & :flags_1) != :param_1')

    def test_add_term_using_is_operator_non_private_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='is', operand='starred', negated=True)
        where_clause = 'WHERE (flags & :flags_1) = :param_1'
        params = dict(
            flags_1=UserMessage.flags.starred.mask,
            param_1=0
        )
        self._do_add_term_test(term, where_clause, params)

        term = dict(operator='is', operand='alerted', negated=True)
        where_clause = 'WHERE (flags & :flags_1) = :param_1'
        params = dict(
            flags_1=UserMessage.flags.has_alert_word.mask,
            param_1=0
        )
        self._do_add_term_test(term, where_clause, params)

        term = dict(operator='is', operand='mentioned', negated=True)
        where_clause = 'WHERE NOT ((flags & :flags_1) != :param_1 OR (flags & :flags_2) != :param_2)'
        params = dict(
            flags_1=UserMessage.flags.mentioned.mask,
            param_1=0,
            flags_2=UserMessage.flags.wildcard_mentioned.mask,
            param_2=0
        )
        self._do_add_term_test(term, where_clause, params)

    def test_add_term_using_non_supported_operator_should_raise_error(self) -> None:
        term = dict(operator='is', operand='non_supported')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_topic_operator_and_lunch_operand(self) -> None:
        term = dict(operator='topic', operand='lunch')
        self._do_add_term_test(term, 'WHERE upper(subject) = upper(:param_1)')

    def test_add_term_using_topic_operator_lunch_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='topic', operand='lunch', negated=True)
        self._do_add_term_test(term, 'WHERE upper(subject) != upper(:param_1)')

    def test_add_term_using_topic_operator_and_personal_operand(self) -> None:
        term = dict(operator='topic', operand='personal')
        self._do_add_term_test(term, 'WHERE upper(subject) = upper(:param_1)')

    def test_add_term_using_topic_operator_personal_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='topic', operand='personal', negated=True)
        self._do_add_term_test(term, 'WHERE upper(subject) != upper(:param_1)')

    def test_add_term_using_sender_operator(self) -> None:
        term = dict(operator='sender', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE sender_id = :param_1')

    def test_add_term_using_sender_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator='sender', operand=self.example_email("othello"), negated=True)
        self._do_add_term_test(term, 'WHERE sender_id != :param_1')

    def test_add_term_using_sender_operator_with_non_existing_user_as_operand(
            self) -> None:  # NEGATED
        term = dict(operator='sender', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_pm_with_operator_and_not_the_same_user_as_operand(self) -> None:
        term = dict(operator='pm-with', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2')

    def test_add_term_using_pm_with_operator_not_the_same_user_as_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='pm-with', operand=self.example_email("othello"), negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2)')

    def test_add_term_using_pm_with_operator_the_same_user_as_operand(self) -> None:
        term = dict(operator='pm-with', operand=self.example_email("hamlet"))
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1')

    def test_add_term_using_pm_with_operator_the_same_user_as_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='pm-with', operand=self.example_email("hamlet"), negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1)')

    def test_add_term_using_pm_with_operator_and_self_and_user_as_operand(self) -> None:
        term = dict(operator='pm-with', operand='hamlet@zulip.com, othello@zulip.com')
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2')

    def test_add_term_using_pm_with_operator_more_than_one_user_as_operand(self) -> None:
        term = dict(operator='pm-with', operand='cordelia@zulip.com, othello@zulip.com')
        self._do_add_term_test(term, 'WHERE recipient_id = :recipient_id_1')

    def test_add_term_using_pm_with_operator_self_and_user_as_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='pm-with', operand='hamlet@zulip.com, othello@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2)')

    def test_add_term_using_pm_with_operator_more_than_one_user_as_operand_and_negated(self) -> None:
        term = dict(operator='pm-with', operand='cordelia@zulip.com, othello@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id != :recipient_id_1')

    def test_add_term_using_pm_with_operator_with_comma_noise(self) -> None:
        term = dict(operator='pm-with', operand=' ,,, ,,, ,')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_pm_with_operator_with_existing_and_non_existing_user_as_operand(self) -> None:
        term = dict(operator='pm-with', operand='othello@zulip.com,non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_id_operator(self) -> None:
        term = dict(operator='id', operand=555)
        self._do_add_term_test(term, 'WHERE id = :param_1')

    def test_add_term_using_id_operator_invalid(self) -> None:
        term = dict(operator='id', operand='')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

        term = dict(operator='id', operand='notanint')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_id_operator_and_negated(self) -> None:  # NEGATED
        term = dict(operator='id', operand=555, negated=True)
        self._do_add_term_test(term, 'WHERE id != :param_1')

    def test_add_term_using_group_pm_operator_and_not_the_same_user_as_operand(self) -> None:
        # Test wtihout any such group PM threads existing
        term = dict(operator='group-pm-with', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE 1 != 1')

        # Test with at least one such group PM thread existing
        self.send_huddle_message(self.user_profile.email, [self.example_email("othello"),
                                                           self.example_email("cordelia")])

        term = dict(operator='group-pm-with', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE recipient_id IN (:recipient_id_1)')

    def test_add_term_using_group_pm_operator_not_the_same_user_as_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='group-pm-with', operand=self.example_email("othello"), negated=True)
        self._do_add_term_test(term, 'WHERE 1 = 1')

    def test_add_term_using_group_pm_operator_with_non_existing_user_as_operand(self) -> None:
        term = dict(operator='group-pm-with', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator(self) -> None:
        term = dict(operator='search', operand='"french fries"')
        self._do_add_term_test(term, 'WHERE (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='search', operand='"french fries"', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND NOT (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_pgroonga(self) -> None:
        term = dict(operator='search', operand='"french fries"')
        self._do_add_term_test(term, 'WHERE search_pgroonga &@~ escape_html(:escape_html_1)')

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_and_negated_pgroonga(
            self) -> None:  # NEGATED
        term = dict(operator='search', operand='"french fries"', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (search_pgroonga &@~ escape_html(:escape_html_1))')

    def test_add_term_using_has_operator_and_attachment_operand(self) -> None:
        term = dict(operator='has', operand='attachment')
        self._do_add_term_test(term, 'WHERE has_attachment')

    def test_add_term_using_has_operator_attachment_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='has', operand='attachment', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_attachment')

    def test_add_term_using_has_operator_and_image_operand(self) -> None:
        term = dict(operator='has', operand='image')
        self._do_add_term_test(term, 'WHERE has_image')

    def test_add_term_using_has_operator_image_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='has', operand='image', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_image')

    def test_add_term_using_has_operator_and_link_operand(self) -> None:
        term = dict(operator='has', operand='link')
        self._do_add_term_test(term, 'WHERE has_link')

    def test_add_term_using_has_operator_link_operand_and_negated(
            self) -> None:  # NEGATED
        term = dict(operator='has', operand='link', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_link')

    def test_add_term_using_has_operator_non_supported_operand_should_raise_error(self) -> None:
        term = dict(operator='has', operand='non_supported')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_in_operator(self) -> None:
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='home')
        self._do_add_term_test(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

    def test_add_term_using_in_operator_and_negated(self) -> None:
        # negated = True should not change anything
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='home', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

    def test_add_term_using_in_operator_and_all_operand(self) -> None:
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='all')
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def test_add_term_using_in_operator_all_operand_and_negated(self) -> None:
        # negated = True should not change anything
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='all', negated=True)
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def test_add_term_using_in_operator_and_not_defined_operand(self) -> None:
        term = dict(operator='in', operand='not_defined')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_near_operator(self) -> None:
        term = dict(operator='near', operand='operand')
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def _do_add_term_test(self, term: Dict[str, Any], where_clause: str,
                          params: Optional[Dict[str, Any]]=None) -> None:
        query = self._build_query(term)
        if params is not None:
            actual_params = query.compile().params
            self.assertEqual(actual_params, params)
        self.assertIn(where_clause, str(query))

    def _build_query(self, term: Dict[str, Any]) -> Query:
        return self.builder.add_term(self.raw_query, term)

class NarrowLibraryTest(TestCase):
    def test_build_narrow_filter(self) -> None:
        fixtures_path = os.path.join(os.path.dirname(__file__),
                                     'fixtures/narrow.json')
        scenarios = ujson.loads(open(fixtures_path, 'r').read())
        self.assertTrue(len(scenarios) == 9)
        for scenario in scenarios:
            narrow = scenario['narrow']
            accept_events = scenario['accept_events']
            reject_events = scenario['reject_events']
            narrow_filter = build_narrow_filter(narrow)
            for e in accept_events:
                self.assertTrue(narrow_filter(e))
            for e in reject_events:
                self.assertFalse(narrow_filter(e))

    def test_build_narrow_filter_invalid(self) -> None:
        with self.assertRaises(JsonableError):
            build_narrow_filter(["invalid_operator", "operand"])

    def test_is_web_public_compatible(self) -> None:
        self.assertTrue(is_web_public_compatible([]))
        self.assertTrue(is_web_public_compatible([{"operator": "has",
                                                   "operand": "attachment"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "has",
                                                   "operand": "image"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "search",
                                                   "operand": "magic"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "near",
                                                   "operand": "15"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "id",
                                                   "operand": "15"},
                                                  {"operator": "has",
                                                   "operand": "attachment"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "sender",
                                                   "operand": "hamlet@zulip.com"}]))
        self.assertFalse(is_web_public_compatible([{"operator": "pm-with",
                                                    "operand": "hamlet@zulip.com"}]))
        self.assertFalse(is_web_public_compatible([{"operator": "group-pm-with",
                                                    "operand": "hamlet@zulip.com"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "stream",
                                                   "operand": "Denmark"}]))
        self.assertTrue(is_web_public_compatible([{"operator": "stream",
                                                   "operand": "Denmark"},
                                                  {"operator": "topic",
                                                   "operand": "logic"}]))
        self.assertFalse(is_web_public_compatible([{"operator": "is",
                                                    "operand": "starred"}]))
        self.assertFalse(is_web_public_compatible([{"operator": "is",
                                                    "operand": "private"}]))
        # Malformed input not allowed
        self.assertFalse(is_web_public_compatible([{"operator": "has"}]))

class IncludeHistoryTest(ZulipTestCase):
    def test_ok_to_include_history(self) -> None:
        user_profile = self.example_user("hamlet")
        self.make_stream('public_stream', realm=user_profile.realm)

        # Negated stream searches should not include history.
        narrow = [
            dict(operator='stream', operand='public_stream', negated=True),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile))

        # Definitely forbid seeing history on private streams.
        self.make_stream('private_stream', realm=user_profile.realm, invite_only=True)
        subscribed_user_profile = self.example_user("cordelia")
        self.subscribe(subscribed_user_profile, 'private_stream')
        narrow = [
            dict(operator='stream', operand='private_stream'),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile))

        # Verify that with stream.history_public_to_subscribers, subscribed
        # users can access history.
        self.make_stream('private_stream_2', realm=user_profile.realm,
                         invite_only=True, history_public_to_subscribers=True)
        subscribed_user_profile = self.example_user("cordelia")
        self.subscribe(subscribed_user_profile, 'private_stream_2')
        narrow = [
            dict(operator='stream', operand='private_stream_2'),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile))

        # History doesn't apply to PMs.
        narrow = [
            dict(operator='is', operand='private'),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile))

        # History doesn't apply to unread messages.
        narrow = [
            dict(operator='is', operand='unread'),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile))

        # If we are looking for something like starred messages, there is
        # no point in searching historical messages.
        narrow = [
            dict(operator='stream', operand='public_stream'),
            dict(operator='is', operand='starred'),
        ]
        self.assertFalse(ok_to_include_history(narrow, user_profile))

        # simple True case
        narrow = [
            dict(operator='stream', operand='public_stream'),
        ]
        self.assertTrue(ok_to_include_history(narrow, user_profile))

        narrow = [
            dict(operator='stream', operand='public_stream'),
            dict(operator='topic', operand='whatever'),
            dict(operator='search', operand='needle in haystack'),
        ]
        self.assertTrue(ok_to_include_history(narrow, user_profile))

        # Tests for guest user
        guest_user_profile = self.example_user("polonius")
        # Using 'Cordelia' to compare between a guest and a normal user
        subscribed_user_profile = self.example_user("cordelia")

        # Guest user can't access public stream
        self.subscribe(subscribed_user_profile, 'public_stream_2')
        narrow = [
            dict(operator='stream', operand='public_stream_2'),
        ]
        self.assertFalse(ok_to_include_history(narrow, guest_user_profile))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile))

        # Definitely, a guest user can't access the unsubscribed private stream
        self.subscribe(subscribed_user_profile, 'private_stream_3')
        narrow = [
            dict(operator='stream', operand='private_stream_3'),
        ]
        self.assertFalse(ok_to_include_history(narrow, guest_user_profile))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile))

        # Guest user can access (history of) subscribed private streams
        self.subscribe(guest_user_profile, 'private_stream_4')
        self.subscribe(subscribed_user_profile, 'private_stream_4')
        narrow = [
            dict(operator='stream', operand='private_stream_4'),
        ]
        self.assertTrue(ok_to_include_history(narrow, guest_user_profile))
        self.assertTrue(ok_to_include_history(narrow, subscribed_user_profile))

class PostProcessTest(ZulipTestCase):
    def test_basics(self) -> None:
        def verify(in_ids: List[int],
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
                   history_limited: bool) -> None:
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

            self.assertEqual(info['rows'], out_rows)
            self.assertEqual(info['found_anchor'], found_anchor)
            self.assertEqual(info['found_newest'], found_newest)
            self.assertEqual(info['found_oldest'], found_oldest)
            self.assertEqual(info['history_limited'], history_limited)

        # typical 2-sided query, with a bunch of tests for different
        # values of first_visible_message_id.
        anchor = 10
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[8, 9, 10, 11, 12],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=8,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[8, 9, 10, 11, 12],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=9,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[9, 10, 11, 12],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=10,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[10, 11, 12],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=11,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[11, 12],
            found_anchor=False, found_oldest=True,
            found_newest=False, history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=12,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[12],
            found_anchor=False, found_oldest=True,
            found_newest=True, history_limited=True,
        )
        verify(
            in_ids=[8, 9, anchor, 11, 12],
            num_before=2, num_after=2,
            first_visible_message_id=13,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[],
            found_anchor=False, found_oldest=True,
            found_newest=True, history_limited=True,
        )

        # typical 2-sided query missing anchor and grabbing an extra row
        anchor = 10
        verify(
            in_ids=[7, 9, 11, 13, 15],
            num_before=2, num_after=2,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            first_visible_message_id=0,
            out_ids=[7, 9, 11, 13],
            found_anchor=False, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[7, 9, 11, 13, 15],
            num_before=2, num_after=2,
            first_visible_message_id=10,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[11, 13],
            found_anchor=False, found_oldest=True,
            found_newest=False, history_limited=True,
        )
        verify(
            in_ids=[7, 9, 11, 13, 15],
            num_before=2, num_after=2,
            first_visible_message_id=9,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[9, 11, 13],
            found_anchor=False, found_oldest=True,
            found_newest=False, history_limited=True,
        )

        # 2-sided query with old anchor
        anchor = 100
        verify(
            in_ids=[50, anchor, 150, 200],
            num_before=2, num_after=2,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[50, 100, 150, 200],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[50, anchor, 150, 200],
            num_before=2, num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[100, 150, 200],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=True,
        )

        # 2-sided query with new anchor
        anchor = 900
        verify(
            in_ids=[700, 800, anchor, 1000],
            num_before=2, num_after=2,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[700, 800, 900, 1000],
            found_anchor=True, found_oldest=False,
            found_newest=True, history_limited=False,
        )
        verify(
            in_ids=[700, 800, anchor, 1000],
            num_before=2, num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[900, 1000],
            found_anchor=True, found_oldest=True,
            found_newest=True, history_limited=True,
        )

        # left-sided query with old anchor
        anchor = 100
        verify(
            in_ids=[50, anchor],
            num_before=2, num_after=0,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[50, 100],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[50, anchor],
            num_before=2, num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[100],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=True,
        )

        # left-sided query with new anchor
        anchor = 900
        verify(
            in_ids=[700, 800, anchor],
            num_before=2, num_after=0,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[700, 800, 900],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[700, 800, anchor],
            num_before=2, num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[900],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=True,
        )

        # left-sided query with new anchor and extra row
        anchor = 900
        verify(
            in_ids=[600, 700, 800, anchor],
            num_before=2, num_after=0,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[700, 800, 900],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[600, 700, 800, anchor],
            num_before=2, num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[900],
            found_anchor=True, found_oldest=True,
            found_newest=False, history_limited=True,
        )

        # left-sided query anchored to the right
        anchor = None
        verify(
            in_ids=[900, 1000],
            num_before=2, num_after=0,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=True,
            out_ids=[900, 1000],
            found_anchor=False, found_oldest=False,
            found_newest=True, history_limited=False,
        )
        verify(
            in_ids=[900, 1000],
            num_before=2, num_after=0,
            first_visible_message_id=1000,
            anchor=anchor, anchored_to_left=False, anchored_to_right=True,
            out_ids=[1000],
            found_anchor=False, found_oldest=True,
            found_newest=True, history_limited=True,
        )
        verify(
            in_ids=[900, 1000],
            num_before=2, num_after=0,
            first_visible_message_id=1100,
            anchor=anchor, anchored_to_left=False, anchored_to_right=True,
            out_ids=[],
            found_anchor=False, found_oldest=True,
            found_newest=True, history_limited=True,
        )

        # right-sided query with old anchor
        anchor = 100
        verify(
            in_ids=[anchor, 200, 300, 400],
            num_before=0, num_after=2,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[100, 200, 300],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[anchor, 200, 300, 400],
            num_before=0, num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[100, 200, 300],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[anchor, 200, 300, 400],
            num_before=0, num_after=2,
            first_visible_message_id=300,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[300, 400],
            found_anchor=False, found_oldest=False,
            # BUG: history_limited should be False here.
            found_newest=False, history_limited=False,
        )

        # right-sided query with new anchor
        anchor = 900
        verify(
            in_ids=[anchor, 1000],
            num_before=0, num_after=2,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[900, 1000],
            found_anchor=True, found_oldest=False,
            found_newest=True, history_limited=False,
        )
        verify(
            in_ids=[anchor, 1000],
            num_before=0, num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[900, 1000],
            found_anchor=True, found_oldest=False,
            found_newest=True, history_limited=False,
        )

        # right-sided query with non-matching anchor
        anchor = 903
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0, num_after=2,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[1000, 1100],
            found_anchor=False, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0, num_after=2,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[1000, 1100],
            found_anchor=False, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0, num_after=2,
            first_visible_message_id=1000,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[1000, 1100],
            found_anchor=False, found_oldest=False,
            found_newest=False, history_limited=False,
        )
        verify(
            in_ids=[1000, 1100, 1200],
            num_before=0, num_after=2,
            first_visible_message_id=1100,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[1100, 1200],
            found_anchor=False, found_oldest=False,
            # BUG: history_limited should be False here.
            found_newest=False, history_limited=False,
        )

        # targeted query that finds row
        anchor = 1000
        verify(
            in_ids=[1000],
            num_before=0, num_after=0,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[1000],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False
        )
        verify(
            in_ids=[1000],
            num_before=0, num_after=0,
            first_visible_message_id=anchor,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[1000],
            found_anchor=True, found_oldest=False,
            found_newest=False, history_limited=False
        )
        verify(
            in_ids=[1000],
            num_before=0, num_after=0,
            first_visible_message_id=1100,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[],
            found_anchor=False, found_oldest=False,
            found_newest=False, history_limited=False,
        )

        # targeted query that finds nothing
        anchor = 903
        verify(
            in_ids=[],
            num_before=0, num_after=0,
            first_visible_message_id=0,
            anchor=anchor, anchored_to_left=False, anchored_to_right=False,
            out_ids=[],
            found_anchor=False, found_oldest=False,
            found_newest=False, history_limited=False
        )

class GetOldMessagesTest(ZulipTestCase):

    def get_and_check_messages(self,
                               modified_params: Dict[str, Union[str, int]],
                               **kwargs: Any) -> Dict[str, Any]:
        post_params = {"anchor": 1, "num_before": 1, "num_after": 1}  # type: Dict[str, Union[str, int]]
        post_params.update(modified_params)
        payload = self.client_get("/json/messages", dict(post_params),
                                  **kwargs)
        self.assert_json_success(payload)
        result = ujson.loads(payload.content)

        self.assertIn("messages", result)
        self.assertIsInstance(result["messages"], list)
        for message in result["messages"]:
            for field in ("content", "content_type", "display_recipient",
                          "avatar_url", "recipient_id", "sender_full_name",
                          "sender_short_name", "timestamp", "reactions"):
                self.assertIn(field, message)
        return result

    def message_visibility_test(self, narrow: List[Dict[str, str]],
                                message_ids: List[int], pivot_index: int) -> None:
        num_before = len(message_ids)

        post_params = dict(narrow=ujson.dumps(narrow), num_before=num_before,
                           num_after=0, anchor=LARGER_THAN_MAX_MESSAGE_ID)
        payload = self.client_get("/json/messages", dict(post_params))
        self.assert_json_success(payload)
        result = ujson.loads(payload.content)

        self.assertEqual(len(result["messages"]), len(message_ids))
        for message in result["messages"]:
            assert(message["id"] in message_ids)

        post_params.update({"num_before": len(message_ids[pivot_index:])})

        with first_visible_id_as(message_ids[pivot_index]):
            payload = self.client_get("/json/messages", dict(post_params))

        self.assert_json_success(payload)
        result = ujson.loads(payload.content)

        self.assertEqual(len(result["messages"]), len(message_ids[pivot_index:]))
        for message in result["messages"]:
            assert(message["id"] in message_ids)

    def get_query_ids(self) -> Dict[str, int]:
        hamlet_user = self.example_user('hamlet')
        othello_user = self.example_user('othello')

        query_ids = {}  # type: Dict[str, int]

        scotland_stream = get_stream('Scotland', hamlet_user.realm)
        query_ids['scotland_recipient'] = get_stream_recipient(scotland_stream.id).id
        query_ids['hamlet_id'] = hamlet_user.id
        query_ids['othello_id'] = othello_user.id
        query_ids['hamlet_recipient'] = get_personal_recipient(hamlet_user.id).id
        query_ids['othello_recipient'] = get_personal_recipient(othello_user.id).id

        return query_ids

    def test_content_types(self) -> None:
        """
        Test old `/json/messages` returns reactions.
        """
        self.login(self.example_email("hamlet"))

        def get_content_type(apply_markdown: bool) -> str:
            req = dict(
                apply_markdown=ujson.dumps(apply_markdown),
            )  # type: Dict[str, Any]
            result = self.get_and_check_messages(req)
            message = result['messages'][0]
            return message['content_type']

        self.assertEqual(
            get_content_type(apply_markdown=False),
            'text/x-markdown',
        )

        self.assertEqual(
            get_content_type(apply_markdown=True),
            'text/html',
        )

    def test_successful_get_messages_reaction(self) -> None:
        """
        Test old `/json/messages` returns reactions.
        """
        self.login(self.example_email("hamlet"))
        messages = self.get_and_check_messages(dict())
        message_id = messages['messages'][0]['id']

        self.login(self.example_email("othello"))
        reaction_name = 'thumbs_up'

        url = '/json/messages/{}/emoji_reactions/{}'.format(message_id, reaction_name)
        payload = self.client_put(url)
        self.assert_json_success(payload)

        self.login(self.example_email("hamlet"))
        messages = self.get_and_check_messages({})
        message_to_assert = None
        for message in messages['messages']:
            if message['id'] == message_id:
                message_to_assert = message
                break
        assert(message_to_assert is not None)
        self.assertEqual(len(message_to_assert['reactions']), 1)
        self.assertEqual(message_to_assert['reactions'][0]['emoji_name'],
                         reaction_name)

    def test_successful_get_messages(self) -> None:
        """
        A call to GET /json/messages with valid parameters returns a list of
        messages.
        """
        self.login(self.example_email("hamlet"))
        self.get_and_check_messages(dict())

        # We have to support the legacy tuple style while there are old
        # clients around, which might include third party home-grown bots.
        self.get_and_check_messages(dict(narrow=ujson.dumps([['pm-with', self.example_email("othello")]])))

        self.get_and_check_messages(dict(narrow=ujson.dumps([dict(operator='pm-with', operand=self.example_email("othello"))])))

    def test_client_avatar(self) -> None:
        """
        The client_gravatar flag determines whether we send avatar_url.
        """
        hamlet = self.example_user('hamlet')
        self.login(hamlet.email)

        self.send_personal_message(hamlet.email, self.example_email("iago"))

        result = self.get_and_check_messages({})
        message = result['messages'][0]
        self.assertIn('gravatar.com', message['avatar_url'])

        result = self.get_and_check_messages(dict(client_gravatar=ujson.dumps(True)))
        message = result['messages'][0]
        self.assertEqual(message['avatar_url'], None)

    def test_get_messages_with_narrow_pm_with(self) -> None:
        """
        A request for old messages with a narrow by pm-with only returns
        conversations with that user.
        """
        me = self.example_email('hamlet')

        def dr_emails(dr: Union[str, List[Dict[str, Any]]]) -> str:
            assert isinstance(dr, list)
            return ','.join(sorted(set([r['email'] for r in dr] + [me])))

        self.send_personal_message(me, self.example_email("iago"))
        self.send_huddle_message(
            me,
            [self.example_email("iago"), self.example_email("cordelia")],
        )
        personals = [m for m in get_user_messages(self.example_user('hamlet'))
                     if not m.is_stream_message()]
        for personal in personals:
            emails = dr_emails(get_display_recipient(personal.recipient))

            self.login(me)
            narrow = [dict(operator='pm-with', operand=emails)]
            result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

            for message in result["messages"]:
                self.assertEqual(dr_emails(message['display_recipient']), emails)

    def test_get_visible_messages_with_narrow_pm_with(self) -> None:
        me = self.example_email('hamlet')
        self.login(me)
        self.subscribe(self.example_user("hamlet"), 'Scotland')

        message_ids = []
        for i in range(5):
            message_ids.append(self.send_personal_message(me, self.example_email("iago")))

        narrow = [dict(operator='pm-with', operand=self.example_email("iago"))]
        self.message_visibility_test(narrow, message_ids, 2)

    def test_get_messages_with_narrow_group_pm_with(self) -> None:
        """
        A request for old messages with a narrow by group-pm-with only returns
        group-private conversations with that user.
        """
        me = self.example_email("hamlet")

        matching_message_ids = []

        matching_message_ids.append(
            self.send_huddle_message(
                me,
                [
                    self.example_email("iago"),
                    self.example_email("cordelia"),
                    self.example_email("othello"),
                ],
            ),
        )

        matching_message_ids.append(
            self.send_huddle_message(
                me,
                [
                    self.example_email("cordelia"),
                    self.example_email("othello"),
                ],
            ),
        )

        non_matching_message_ids = []

        non_matching_message_ids.append(
            self.send_personal_message(me, self.example_email("cordelia")),
        )

        non_matching_message_ids.append(
            self.send_huddle_message(
                me,
                [
                    self.example_email("iago"),
                    self.example_email("othello"),
                ],
            ),
        )

        non_matching_message_ids.append(
            self.send_huddle_message(
                self.example_email("cordelia"),
                [
                    self.example_email("iago"),
                    self.example_email("othello"),
                ],
            ),
        )

        self.login(me)
        narrow = [dict(operator='group-pm-with', operand=self.example_email("cordelia"))]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))
        for message in result["messages"]:
            self.assertIn(message["id"], matching_message_ids)
            self.assertNotIn(message["id"], non_matching_message_ids)

    def test_get_visible_messages_with_narrow_group_pm_with(self) -> None:
        me = self.example_email('hamlet')
        self.login(me)

        message_ids = []
        message_ids.append(
            self.send_huddle_message(
                me,
                [
                    self.example_email("iago"),
                    self.example_email("cordelia"),
                    self.example_email("othello"),
                ],
            ),
        )
        message_ids.append(
            self.send_huddle_message(
                me,
                [
                    self.example_email("cordelia"),
                    self.example_email("othello"),
                ],
            ),
        )
        message_ids.append(
            self.send_huddle_message(
                me,
                [
                    self.example_email("cordelia"),
                    self.example_email("iago"),
                ],
            ),
        )

        narrow = [dict(operator='group-pm-with', operand=self.example_email("cordelia"))]
        self.message_visibility_test(narrow, message_ids, 1)

    def test_include_history(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        stream_name = 'test stream'
        self.subscribe(cordelia, stream_name)

        old_message_id = self.send_stream_message(cordelia.email, stream_name, content='foo')

        self.subscribe(hamlet, stream_name)

        content = 'hello @**King Hamlet**'
        new_message_id = self.send_stream_message(cordelia.email, stream_name, content=content)

        self.login(hamlet.email)
        narrow = [
            dict(operator='stream', operand=stream_name)
        ]

        req = dict(
            narrow=ujson.dumps(narrow),
            anchor=LARGER_THAN_MAX_MESSAGE_ID,
            num_before=100,
            num_after=100,
        )

        payload = self.client_get('/json/messages', req)
        self.assert_json_success(payload)
        result = ujson.loads(payload.content)
        messages = result['messages']
        self.assertEqual(len(messages), 2)

        for message in messages:
            if message['id'] == old_message_id:
                old_message = message
            elif message['id'] == new_message_id:
                new_message = message

        self.assertEqual(old_message['flags'], ['read', 'historical'])
        self.assertEqual(new_message['flags'], ['mentioned'])

    def test_get_messages_with_narrow_stream(self) -> None:
        """
        A request for old messages with a narrow by stream only returns
        messages for that stream.
        """
        self.login(self.example_email('hamlet'))
        # We need to subscribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        self.subscribe(self.example_user("hamlet"), 'Scotland')
        self.send_stream_message(self.example_email("hamlet"), "Scotland")
        messages = get_user_messages(self.example_user('hamlet'))
        stream_messages = [msg for msg in messages if msg.is_stream_message()]
        stream_name = get_display_recipient(stream_messages[0].recipient)
        stream_id = stream_messages[0].recipient.id

        narrow = [dict(operator='stream', operand=stream_name)]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(message["type"], "stream")
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_visible_messages_with_narrow_stream(self) -> None:
        self.login(self.example_email('hamlet'))
        self.subscribe(self.example_user("hamlet"), 'Scotland')

        message_ids = []
        for i in range(5):
            message_ids.append(self.send_stream_message(self.example_email("iago"), "Scotland"))

        narrow = [dict(operator='stream', operand="Scotland")]
        self.message_visibility_test(narrow, message_ids, 2)

    def test_get_messages_with_narrow_stream_mit_unicode_regex(self) -> None:
        """
        A request for old messages for a user in the mit.edu relam with unicode
        stream name should be correctly escaped in the database query.
        """
        self.login(self.mit_email("starnine"), realm=get_realm("zephyr"))
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        lambda_stream_name = u"\u03bb-stream"
        stream = self.subscribe(self.mit_user("starnine"), lambda_stream_name)
        self.assertTrue(stream.is_in_zephyr_realm)

        lambda_stream_d_name = u"\u03bb-stream.d"
        self.subscribe(self.mit_user("starnine"), lambda_stream_d_name)

        self.send_stream_message(self.mit_email("starnine"), u"\u03bb-stream", sender_realm="zephyr")
        self.send_stream_message(self.mit_email("starnine"), u"\u03bb-stream.d", sender_realm="zephyr")

        narrow = [dict(operator='stream', operand=u'\u03bb-stream')]
        result = self.get_and_check_messages(dict(num_after=2,
                                                  narrow=ujson.dumps(narrow)),
                                             subdomain="zephyr")

        messages = get_user_messages(self.mit_user("starnine"))
        stream_messages = [msg for msg in messages if msg.is_stream_message()]

        self.assertEqual(len(result["messages"]), 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_topic_mit_unicode_regex(self) -> None:
        """
        A request for old messages for a user in the mit.edu realm with unicode
        topic name should be correctly escaped in the database query.
        """
        mit_user_profile = self.mit_user("starnine")
        email = mit_user_profile.email
        self.login(email, realm=get_realm("zephyr"))
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        self.subscribe(mit_user_profile, "Scotland")
        self.send_stream_message(email, "Scotland", topic_name=u"\u03bb-topic",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u"\u03bb-topic.d",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u"\u03bb-topic.d.d",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u"\u03bb-topic.d.d.d",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u"\u03bb-topic.d.d.d.d",
                                 sender_realm="zephyr")

        narrow = [dict(operator='topic', operand=u'\u03bb-topic')]
        result = self.get_and_check_messages(
            dict(num_after=100, narrow=ujson.dumps(narrow)),
            subdomain="zephyr")

        messages = get_user_messages(mit_user_profile)
        stream_messages = [msg for msg in messages if msg.is_stream_message()]
        self.assertEqual(len(result["messages"]), 5)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_topic_mit_personal(self) -> None:
        """
        We handle .d grouping for MIT realm personal messages correctly.
        """
        mit_user_profile = self.mit_user("starnine")
        email = mit_user_profile.email

        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        self.login(email, realm=mit_user_profile.realm)
        self.subscribe(mit_user_profile, "Scotland")

        self.send_stream_message(email, "Scotland", topic_name=u".d.d",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u"PERSONAL",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u'(instance "").d',
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u".d.d.d",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u"personal.d",
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u'(instance "")',
                                 sender_realm="zephyr")
        self.send_stream_message(email, "Scotland", topic_name=u".d.d.d.d",
                                 sender_realm="zephyr")

        narrow = [dict(operator='topic', operand=u'personal.d.d')]
        result = self.get_and_check_messages(
            dict(num_before=50,
                 num_after=50,
                 narrow=ujson.dumps(narrow)),
            subdomain="zephyr")

        messages = get_user_messages(mit_user_profile)
        stream_messages = [msg for msg in messages if msg.is_stream_message()]
        self.assertEqual(len(result["messages"]), 7)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_sender(self) -> None:
        """
        A request for old messages with a narrow by sender only returns
        messages sent by that person.
        """
        self.login(self.example_email("hamlet"))
        # We need to send a message here to ensure that we actually
        # have a stream message in this narrow view.
        self.send_stream_message(self.example_email("hamlet"), "Scotland")
        self.send_stream_message(self.example_email("othello"), "Scotland")
        self.send_personal_message(self.example_email("othello"), self.example_email("hamlet"))
        self.send_stream_message(self.example_email("iago"), "Scotland")

        narrow = [dict(operator='sender', operand=self.example_email("othello"))]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(message["sender_email"], self.example_email("othello"))

    def _update_tsvector_index(self) -> None:
        # We use brute force here and update our text search index
        # for the entire zerver_message table (which is small in test
        # mode).  In production there is an async process which keeps
        # the search index up to date.
        with connection.cursor() as cursor:
            cursor.execute("""
            UPDATE zerver_message SET
            search_tsvector = to_tsvector('zulip.english_us_search',
            subject || rendered_content)
            """)

    @override_settings(USING_PGROONGA=False)
    def test_messages_in_narrow(self) -> None:
        email = self.example_email("cordelia")
        self.login(email)

        def send(content: str) -> int:
            msg_id = self.send_stream_message(
                sender_email=email,
                stream_name="Verona",
                content=content,
            )
            return msg_id

        good_id = send('KEYWORDMATCH and should work')
        bad_id = send('no match')
        msg_ids = [good_id, bad_id]
        send('KEYWORDMATCH but not in msg_ids')

        self._update_tsvector_index()

        narrow = [
            dict(operator='search', operand='KEYWORDMATCH'),
        ]

        raw_params = dict(msg_ids=msg_ids, narrow=narrow)
        params = {k: ujson.dumps(v) for k, v in raw_params.items()}
        result = self.client_get('/json/messages/matches_narrow', params)
        self.assert_json_success(result)
        messages = result.json()['messages']
        self.assertEqual(len(list(messages.keys())), 1)
        message = messages[str(good_id)]
        self.assertEqual(message['match_content'],
                         u'<p><span class="highlight">KEYWORDMATCH</span> and should work</p>')

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search(self) -> None:
        self.login(self.example_email("cordelia"))

        messages_to_search = [
            ('breakfast', 'there are muffins in the conference room'),
            ('lunch plans', 'I am hungry!'),
            ('meetings', 'discuss lunch after lunch'),
            ('meetings', 'please bring your laptops to take notes'),
            ('dinner', 'Anybody staying late tonight?'),
            ('urltest', 'https://google.com'),
            (u'日本', u'こんに ちは 。 今日は いい 天気ですね。'),
            (u'日本', u'今朝はごはんを食べました。'),
            (u'日本', u'昨日、日本 のお菓子を送りました。'),
            ('english', u'I want to go to 日本!'),
        ]

        next_message_id = self.get_last_message().id + 1

        for topic, content in messages_to_search:
            self.send_stream_message(
                sender_email=self.example_email("cordelia"),
                stream_name="Verona",
                content=content,
                topic_name=topic,
            )

        self._update_tsvector_index()

        narrow = [
            dict(operator='sender', operand=self.example_email("cordelia")),
            dict(operator='search', operand='lunch'),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_before=0,
            num_after=10,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(result['messages']), 2)
        messages = result['messages']

        narrow = [dict(operator='search', operand='https://google.com')]
        link_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_before=0,
            num_after=10,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(link_search_result['messages']), 1)
        self.assertEqual(link_search_result['messages'][0]['match_content'],
                         '<p><a href="https://google.com" target="_blank" title="https://google.com">https://<span class="highlight">google.com</span></a></p>')

        meeting_message = [m for m in messages if m[TOPIC_NAME] == 'meetings'][0]
        self.assertEqual(
            meeting_message[MATCH_TOPIC],
            'meetings')
        self.assertEqual(
            meeting_message['match_content'],
            '<p>discuss <span class="highlight">lunch</span> after ' +
            '<span class="highlight">lunch</span></p>')

        meeting_message = [m for m in messages if m[TOPIC_NAME] == 'lunch plans'][0]
        self.assertEqual(
            meeting_message[MATCH_TOPIC],
            '<span class="highlight">lunch</span> plans')
        self.assertEqual(
            meeting_message['match_content'],
            '<p>I am hungry!</p>')

        # Should not crash when multiple search operands are present
        multi_search_narrow = [
            dict(operator='search', operand='discuss'),
            dict(operator='search', operand='after'),
        ]
        multi_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(multi_search_narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(multi_search_result['messages']), 1)
        self.assertEqual(multi_search_result['messages'][0]['match_content'], '<p><span class="highlight">discuss</span> lunch <span class="highlight">after</span> lunch</p>')

        # Test searching in messages with unicode characters
        narrow = [
            dict(operator='search', operand=u'日本'),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))
        self.assertEqual(len(result['messages']), 4)
        messages = result['messages']

        japanese_message = [m for m in messages if m[TOPIC_NAME] == u'日本'][-1]
        self.assertEqual(
            japanese_message[MATCH_TOPIC],
            u'<span class="highlight">日本</span>')
        self.assertEqual(
            japanese_message['match_content'],
            u'<p>昨日、<span class="highlight">日本</span>' +
            u' のお菓子を送りました。</p>')

        english_message = [m for m in messages if m[TOPIC_NAME] == 'english'][0]
        self.assertEqual(
            english_message[MATCH_TOPIC],
            'english')
        self.assertIn(
            english_message['match_content'],
            u'<p>I want to go to <span class="highlight">日本</span>!</p>')

        # Multiple search operands with unicode
        multi_search_narrow = [
            dict(operator='search', operand='ちは'),
            dict(operator='search', operand='今日は'),
        ]
        multi_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(multi_search_narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))
        self.assertEqual(len(multi_search_result['messages']), 1)
        self.assertEqual(multi_search_result['messages'][0]['match_content'],
                         '<p>こんに <span class="highlight">ちは</span> 。 <span class="highlight">今日は</span> いい 天気ですね。</p>')

    @override_settings(USING_PGROONGA=False)
    def test_get_visible_messages_with_search(self) -> None:
        self.login(self.example_email('hamlet'))
        self.subscribe(self.example_user("hamlet"), 'Scotland')

        messages_to_search = [
            ("Gryffindor", "Hogwart's house which values courage, bravery, nerve, and chivalry"),
            ("Hufflepuff", "Hogwart's house which values hard work, patience, justice, and loyalty."),
            ("Ravenclaw", "Hogwart's house which values intelligence, creativity, learning, and wit"),
            ("Slytherin", "Hogwart's house which  values ambition, cunning, leadership, and resourcefulness"),
        ]

        message_ids = []
        for topic, content in messages_to_search:
            message_ids.append(self.send_stream_message(self.example_email("iago"), "Scotland",
                                                        topic_name=topic, content=content))
        self._update_tsvector_index()
        narrow = [dict(operator='search', operand="Hogwart's")]
        self.message_visibility_test(narrow, message_ids, 2)

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_not_subscribed(self) -> None:
        """Verify support for searching a stream you're not subscribed to"""
        self.subscribe(self.example_user("hamlet"), "newstream")
        self.send_stream_message(
            sender_email=self.example_email("hamlet"),
            stream_name="newstream",
            content="Public special content!",
            topic_name="new",
        )
        self._update_tsvector_index()

        self.login(self.example_email("cordelia"))

        stream_search_narrow = [
            dict(operator='search', operand='special'),
            dict(operator='stream', operand='newstream'),
        ]
        stream_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(stream_search_narrow),
            anchor=0,
            num_after=10,
            num_before=10,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(stream_search_result['messages']), 1)
        self.assertEqual(stream_search_result['messages'][0]['match_content'],
                         '<p>Public <span class="highlight">special</span> content!</p>')

    @override_settings(USING_PGROONGA=True)
    def test_get_messages_with_search_pgroonga(self) -> None:
        self.login(self.example_email("cordelia"))

        next_message_id = self.get_last_message().id + 1

        messages_to_search = [
            (u'日本語', u'こんにちは。今日はいい天気ですね。'),
            (u'日本語', u'今朝はごはんを食べました。'),
            (u'日本語', u'昨日、日本のお菓子を送りました。'),
            ('english', u'I want to go to 日本!'),
            ('english', 'Can you speak https://en.wikipedia.org/wiki/Japanese?'),
            ('english', 'https://google.com'),
            ('bread & butter', 'chalk & cheese'),
        ]

        for topic, content in messages_to_search:
            self.send_stream_message(
                sender_email=self.example_email("cordelia"),
                stream_name="Verona",
                content=content,
                topic_name=topic,
            )

        # We use brute force here and update our text search index
        # for the entire zerver_message table (which is small in test
        # mode).  In production there is an async process which keeps
        # the search index up to date.
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE zerver_message SET
                search_pgroonga = escape_html(subject) || ' ' || rendered_content
                """)

        narrow = [
            dict(operator='search', operand=u'日本'),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(result['messages']), 4)
        messages = result['messages']

        japanese_message = [m for m in messages if m[TOPIC_NAME] == u'日本語'][-1]
        self.assertEqual(
            japanese_message[MATCH_TOPIC],
            u'<span class="highlight">日本</span>語')
        self.assertEqual(
            japanese_message['match_content'],
            u'<p>昨日、<span class="highlight">日本</span>の' +
            u'お菓子を送りました。</p>')

        english_message = [m for m in messages if m[TOPIC_NAME] == 'english'][0]
        self.assertEqual(
            english_message[MATCH_TOPIC],
            'english')
        self.assertIn(
            english_message['match_content'],
            # NOTE: The whitespace here is off due to a pgroonga bug.
            # This bug is a pgroonga regression and according to one of
            # the author, this should be fixed in its next release.
            [u'<p>I want to go to <span class="highlight">日本</span>!</p>',  # This is correct.
             u'<p>I want to go to<span class="highlight"> 日本</span>!</p>', ])

        # Should not crash when multiple search operands are present
        multi_search_narrow = [
            dict(operator='search', operand='can'),
            dict(operator='search', operand='speak'),
            dict(operator='search', operand='wiki'),
        ]
        multi_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(multi_search_narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(multi_search_result['messages']), 1)
        self.assertEqual(multi_search_result['messages'][0]['match_content'],
                         '<p><span class="highlight">Can</span> you <span class="highlight">speak</span> <a href="https://en.wikipedia.org/wiki/Japanese" target="_blank" title="https://en.wikipedia.org/wiki/Japanese">https://en.<span class="highlight">wiki</span>pedia.org/<span class="highlight">wiki</span>/Japanese</a>?</p>')

        # Multiple search operands with unicode
        multi_search_narrow = [
            dict(operator='search', operand='朝は'),
            dict(operator='search', operand='べました'),
        ]
        multi_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(multi_search_narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))
        self.assertEqual(len(multi_search_result['messages']), 1)
        self.assertEqual(multi_search_result['messages'][0]['match_content'],
                         '<p>今<span class="highlight">朝は</span>ごはんを食<span class="highlight">べました</span>。</p>')

        narrow = [dict(operator='search', operand='https://google.com')]
        link_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(link_search_result['messages']), 1)
        self.assertEqual(link_search_result['messages'][0]['match_content'],
                         '<p><a href="https://google.com" target="_blank" title="https://google.com"><span class="highlight">https://google.com</span></a></p>')

        # Search operands with HTML Special Characters
        special_search_narrow = [
            dict(operator='search', operand='butter'),
        ]
        special_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(special_search_narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(special_search_result['messages']), 1)
        self.assertEqual(special_search_result['messages'][0][MATCH_TOPIC],
                         'bread &amp; <span class="highlight">butter</span>')

        special_search_narrow = [
            dict(operator='search', operand='&'),
        ]
        special_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(special_search_narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))
        self.assertEqual(len(special_search_result['messages']), 1)
        self.assertEqual(special_search_result['messages'][0][MATCH_TOPIC],
                         'bread <span class="highlight">&amp;</span> butter')
        self.assertEqual(special_search_result['messages'][0]['match_content'],
                         '<p>chalk <span class="highlight">&amp;</span> cheese</p>')

    def test_messages_in_narrow_for_non_search(self) -> None:
        email = self.example_email("cordelia")
        self.login(email)

        def send(content: str) -> int:
            msg_id = self.send_stream_message(
                sender_email=email,
                stream_name="Verona",
                topic_name='test_topic',
                content=content,
            )
            return msg_id

        good_id = send('http://foo.com')
        bad_id = send('no link here')
        msg_ids = [good_id, bad_id]
        send('http://bar.com but not in msg_ids')

        narrow = [
            dict(operator='has', operand='link'),
        ]

        raw_params = dict(msg_ids=msg_ids, narrow=narrow)
        params = {k: ujson.dumps(v) for k, v in raw_params.items()}
        result = self.client_get('/json/messages/matches_narrow', params)
        self.assert_json_success(result)
        messages = result.json()['messages']
        self.assertEqual(len(list(messages.keys())), 1)
        message = messages[str(good_id)]
        self.assertIn('a href=', message['match_content'])
        self.assertIn('http://foo.com', message['match_content'])
        self.assertEqual(message[MATCH_TOPIC], 'test_topic')

    def test_get_messages_with_only_searching_anchor(self) -> None:
        """
        Test that specifying an anchor but 0 for num_before and num_after
        returns at most 1 message.
        """
        self.login(self.example_email("cordelia"))
        anchor = self.send_stream_message(self.example_email("cordelia"), "Verona")

        narrow = [dict(operator='sender', operand=self.example_email("cordelia"))]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow),
                                                  anchor=anchor, num_before=0,
                                                  num_after=0))  # type: Dict[str, Any]
        self.assertEqual(len(result['messages']), 1)

        narrow = [dict(operator='is', operand='mentioned')]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow),
                                                  anchor=anchor, num_before=0,
                                                  num_after=0))
        self.assertEqual(len(result['messages']), 0)

    def test_get_visible_messages_with_anchor(self) -> None:
        def messages_matches_ids(messages: List[Dict[str, Any]], message_ids: List[int]) -> None:
            self.assertEqual(len(messages), len(message_ids))
            for message in messages:
                assert(message["id"] in message_ids)

        self.login(self.example_email("hamlet"))

        Message.objects.all().delete()

        message_ids = []
        for i in range(10):
            message_ids.append(self.send_stream_message(self.example_email("cordelia"), "Verona"))

        data = self.get_messages_response(anchor=message_ids[9], num_before=9, num_after=0)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids)

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[9], num_before=9, num_after=0)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], True)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[2]):
            data = self.get_messages_response(anchor=message_ids[6], num_before=9, num_after=0)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], True)
        messages_matches_ids(messages, message_ids[2:7])

        with first_visible_id_as(message_ids[9] + 1):
            data = self.get_messages_response(anchor=message_ids[9], num_before=9, num_after=0)

        messages = data['messages']
        self.assert_length(messages, 0)
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], True)

        data = self.get_messages_response(anchor=message_ids[5], num_before=0, num_after=5)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], True)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[7]):
            data = self.get_messages_response(anchor=message_ids[5], num_before=0, num_after=5)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], True)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids[7:])

        with first_visible_id_as(message_ids[2]):
            data = self.get_messages_response(anchor=message_ids[0], num_before=0, num_after=5)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids[2:7])

        with first_visible_id_as(message_ids[9] + 1):
            data = self.get_messages_response(anchor=message_ids[0], num_before=0, num_after=5)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], True)
        self.assertEqual(data['history_limited'], False)
        self.assert_length(messages, 0)

        data = self.get_messages_response(anchor=message_ids[5], num_before=5, num_after=4)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids)

        data = self.get_messages_response(anchor=message_ids[5], num_before=10, num_after=10)
        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], True)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids)

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[5], num_before=5, num_after=4)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], True)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[2], num_before=5, num_after=3)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], True)
        messages_matches_ids(messages, message_ids[5:8])

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[2], num_before=10, num_after=10)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], True)
        messages_matches_ids(messages, message_ids[5:])

        with first_visible_id_as(message_ids[9] + 1):
            data = self.get_messages_response(anchor=message_ids[5], num_before=5, num_after=4)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], True)
        self.assertEqual(data['found_newest'], True)
        self.assertEqual(data['history_limited'], True)
        self.assert_length(messages, 0)

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[5], num_before=0, num_after=0)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], True)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], False)
        messages_matches_ids(messages, message_ids[5:6])

        with first_visible_id_as(message_ids[5]):
            data = self.get_messages_response(anchor=message_ids[2], num_before=0, num_after=0)

        messages = data['messages']
        self.assertEqual(data['found_anchor'], False)
        self.assertEqual(data['found_oldest'], False)
        self.assertEqual(data['found_newest'], False)
        self.assertEqual(data['history_limited'], False)
        self.assert_length(messages, 0)

    def test_missing_params(self) -> None:
        """
        anchor, num_before, and num_after are all required
        POST parameters for get_messages.
        """
        self.login(self.example_email("hamlet"))

        required_args = (("num_before", 1), ("num_after", 1))  # type: Tuple[Tuple[str, int], ...]

        for i in range(len(required_args)):
            post_params = dict(required_args[:i] + required_args[i + 1:])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result,
                                   "Missing '%s' argument" % (required_args[i][0],))

    def test_get_messages_limits(self) -> None:
        """
        A call to GET /json/messages requesting more than
        MAX_MESSAGES_PER_FETCH messages returns an error message.
        """
        self.login(self.example_email("hamlet"))
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
        self.login(self.example_email("hamlet"))

        other_params = [("narrow", {}), ("anchor", 0)]
        int_params = ["num_before", "num_after"]

        bad_types = (False, "", "-1", -1)
        for idx, param in enumerate(int_params):
            for type in bad_types:
                # Rotate through every bad type for every integer
                # parameter, one at a time.
                post_params = dict(other_params + [(param, type)] +
                                   [(other_param, 0) for other_param in
                                    int_params[:idx] + int_params[idx + 1:]]
                                   )
                result = self.client_get("/json/messages", post_params)
                self.assert_json_error(result,
                                       "Bad value for '%s': %s" % (param, type))

    def test_bad_narrow_type(self) -> None:
        """
        narrow must be a list of string pairs.
        """
        self.login(self.example_email("hamlet"))

        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]  # type: List[Tuple[str, Union[int, str, bool]]]

        bad_types = (False, 0, '', '{malformed json,',
                     '{foo: 3}', '[1,2]', '[["x","y","z"]]')  # type: Tuple[Union[int, str, bool], ...]
        for type in bad_types:
            post_params = dict(other_params + [("narrow", type)])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result,
                                   "Bad value for 'narrow': %s" % (type,))

    def test_bad_narrow_operator(self) -> None:
        """
        Unrecognized narrow operators are rejected.
        """
        self.login(self.example_email("hamlet"))
        for operator in ['', 'foo', 'stream:verona', '__init__']:
            narrow = [dict(operator=operator, operand='')]
            params = dict(anchor=0, num_before=0, num_after=0, narrow=ujson.dumps(narrow))
            result = self.client_get("/json/messages", params)
            self.assert_json_error_contains(result,
                                            "Invalid narrow operator: unknown operator")

    def test_non_string_narrow_operand_in_dict(self) -> None:
        """
        We expect search operands to be strings, not integers.
        """
        self.login(self.example_email("hamlet"))
        not_a_string = 42
        narrow = [dict(operator='stream', operand=not_a_string)]
        params = dict(anchor=0, num_before=0, num_after=0, narrow=ujson.dumps(narrow))
        result = self.client_get("/json/messages", params)
        self.assert_json_error_contains(result, 'elem["operand"] is not a string')

    def exercise_bad_narrow_operand(self, operator: str,
                                    operands: Sequence[Any],
                                    error_msg: str) -> None:
        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]  # type: List[Tuple[str, Any]]
        for operand in operands:
            post_params = dict(other_params + [
                ("narrow", ujson.dumps([[operator, operand]]))])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error_contains(result, error_msg)

    def test_bad_narrow_stream_content(self) -> None:
        """
        If an invalid stream name is requested in get_messages, an error is
        returned.
        """
        self.login(self.example_email("hamlet"))
        bad_stream_content = (0, [], ["x", "y"])  # type: Tuple[int, List[None], List[str]]
        self.exercise_bad_narrow_operand("stream", bad_stream_content,
                                         "Bad value for 'narrow'")

    def test_bad_narrow_one_on_one_email_content(self) -> None:
        """
        If an invalid 'pm-with' is requested in get_messages, an
        error is returned.
        """
        self.login(self.example_email("hamlet"))
        bad_stream_content = (0, [], ["x", "y"])  # type: Tuple[int, List[None], List[str]]
        self.exercise_bad_narrow_operand("pm-with", bad_stream_content,
                                         "Bad value for 'narrow'")

    def test_bad_narrow_nonexistent_stream(self) -> None:
        self.login(self.example_email("hamlet"))
        self.exercise_bad_narrow_operand("stream", ['non-existent stream'],
                                         "Invalid narrow operator: unknown stream")

    def test_bad_narrow_nonexistent_email(self) -> None:
        self.login(self.example_email("hamlet"))
        self.exercise_bad_narrow_operand("pm-with", ['non-existent-user@zulip.com'],
                                         "Invalid narrow operator: unknown user")

    def test_message_without_rendered_content(self) -> None:
        """Older messages may not have rendered_content in the database"""
        m = self.get_last_message()
        m.rendered_content = m.rendered_content_version = None
        m.content = 'test content'
        d = MessageDict.wide_dict(m)
        MessageDict.finalize_payload(d, apply_markdown=True, client_gravatar=False)
        self.assertEqual(d['content'], '<p>test content</p>')

    def common_check_get_messages_query(self, query_params: Dict[str, object], expected: str) -> None:
        user_profile = self.example_user('hamlet')
        request = POSTRequestMock(query_params, user_profile)
        with queries_captured() as queries:
            get_messages_backend(request, user_profile)

        for query in queries:
            if "/* get_messages */" in query['sql']:
                sql = str(query['sql']).replace(" /* get_messages */", '')
                self.assertEqual(sql, expected)
                return
        raise AssertionError("get_messages query not found")

    def test_find_first_unread_anchor(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')

        self.make_stream('England')

        # Send a few messages that Hamlet won't have UserMessage rows for.
        unsub_message_id = self.send_stream_message(cordelia.email, 'England')
        self.send_personal_message(cordelia.email, othello.email)

        self.subscribe(hamlet, 'England')

        muted_topics = [
            ['England', 'muted'],
        ]
        set_topic_mutes(hamlet, muted_topics)

        # send a muted message
        muted_message_id = self.send_stream_message(cordelia.email, 'England', topic_name='muted')

        # finally send Hamlet a "normal" message
        first_message_id = self.send_stream_message(cordelia.email, 'England')

        # send a few more messages
        extra_message_id = self.send_stream_message(cordelia.email, 'England')
        self.send_personal_message(cordelia.email, hamlet.email)

        sa_conn = get_sqlalchemy_connection()

        user_profile = hamlet

        anchor = find_first_unread_anchor(
            sa_conn=sa_conn,
            user_profile=user_profile,
            narrow=[],
        )
        self.assertEqual(anchor, first_message_id)

        # With the same data setup, we now want to test that a reasonable
        # search still gets the first message sent to Hamlet (before he
        # subscribed) and other recent messages to the stream.
        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=10,
            num_after=10,
            narrow='[["stream", "England"]]'
        )
        request = POSTRequestMock(query_params, user_profile)

        payload = get_messages_backend(request, user_profile)
        result = ujson.loads(payload.content)
        self.assertEqual(result['anchor'], first_message_id)
        self.assertEqual(result['found_newest'], True)
        self.assertEqual(result['found_oldest'], True)

        messages = result['messages']
        self.assertEqual(
            {msg['id'] for msg in messages},
            {unsub_message_id, muted_message_id, first_message_id, extra_message_id}
        )

    def test_use_first_unread_anchor_with_some_unread_messages(self) -> None:
        user_profile = self.example_user('hamlet')

        # Have Othello send messages to Hamlet that he hasn't read.
        # Here, Hamlet isn't subscribed to the stream Scotland
        self.send_stream_message(self.example_email("othello"), "Scotland")
        first_unread_message_id = self.send_personal_message(
            self.example_email("othello"),
            self.example_email("hamlet"),
        )

        # Add a few messages that help us test that our query doesn't
        # look at messages that are irrelevant to Hamlet.
        self.send_personal_message(self.example_email("othello"), self.example_email("cordelia"))
        self.send_personal_message(self.example_email("othello"), self.example_email("iago"))

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=10,
            num_after=10,
            narrow='[]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_messages_backend(request, user_profile)

        # Verify the query for old messages looks correct.
        queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        sql = queries[0]['sql']
        self.assertNotIn('AND message_id = %s' % (LARGER_THAN_MAX_MESSAGE_ID,), sql)
        self.assertIn('ORDER BY message_id ASC', sql)

        cond = 'WHERE user_profile_id = %d AND message_id >= %d' % (
            user_profile.id, first_unread_message_id,
        )
        self.assertIn(cond, sql)
        cond = 'WHERE user_profile_id = %d AND message_id <= %d' % (
            user_profile.id, first_unread_message_id - 1,
        )
        self.assertIn(cond, sql)
        self.assertIn('UNION', sql)

    def test_visible_messages_use_first_unread_anchor_with_some_unread_messages(self) -> None:
        user_profile = self.example_user('hamlet')

        # Have Othello send messages to Hamlet that he hasn't read.
        self.subscribe(self.example_user("hamlet"), 'Scotland')

        first_unread_message_id = self.send_stream_message(self.example_email("othello"), "Scotland")
        self.send_stream_message(self.example_email("othello"), "Scotland")
        self.send_stream_message(self.example_email("othello"), "Scotland")
        self.send_personal_message(
            self.example_email("othello"),
            self.example_email("hamlet"),
        )

        # Add a few messages that help us test that our query doesn't
        # look at messages that are irrelevant to Hamlet.
        self.send_personal_message(self.example_email("othello"), self.example_email("cordelia"))
        self.send_personal_message(self.example_email("othello"), self.example_email("iago"))

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=10,
            num_after=10,
            narrow='[]'
        )
        request = POSTRequestMock(query_params, user_profile)

        first_visible_message_id = first_unread_message_id + 2
        with first_visible_id_as(first_visible_message_id):
            with queries_captured() as all_queries:
                get_messages_backend(request, user_profile)

        queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        sql = queries[0]['sql']
        self.assertNotIn('AND message_id = %s' % (LARGER_THAN_MAX_MESSAGE_ID,), sql)
        self.assertIn('ORDER BY message_id ASC', sql)
        cond = 'WHERE user_profile_id = %d AND message_id <= %d' % (
            user_profile.id, first_unread_message_id - 1
        )
        self.assertIn(cond, sql)
        cond = 'WHERE user_profile_id = %d AND message_id >= %d' % (
            user_profile.id, first_visible_message_id
        )
        self.assertIn(cond, sql)

    def test_use_first_unread_anchor_with_no_unread_messages(self) -> None:
        user_profile = self.example_user('hamlet')

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=10,
            num_after=10,
            narrow='[]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_messages_backend(request, user_profile)

        queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)

        sql = queries[0]['sql']

        self.assertNotIn('AND message_id <=', sql)
        self.assertNotIn('AND message_id >=', sql)

        first_visible_message_id = 5
        with first_visible_id_as(first_visible_message_id):
            with queries_captured() as all_queries:
                get_messages_backend(request, user_profile)
            queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
            sql = queries[0]['sql']
            self.assertNotIn('AND message_id <=', sql)
            self.assertNotIn('AND message_id >=', sql)

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

        realm = get_realm('zulip')
        self.make_stream('web stuff')
        self.make_stream('bogus')
        user_profile = self.example_user('hamlet')
        muted_topics = [
            ['Scotland', 'golf'],
            ['web stuff', 'css'],
            ['bogus', 'bogus']
        ]
        set_topic_mutes(user_profile, muted_topics)

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=0,
            num_after=0,
            narrow='[["stream", "Scotland"]]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_messages_backend(request, user_profile)

        # Do some tests on the main query, to verify the muting logic
        # runs on this code path.
        queries = [q for q in all_queries if str(q['sql']).startswith("SELECT message_id, flags")]
        self.assertEqual(len(queries), 1)

        stream = get_stream('Scotland', realm)
        recipient_id = get_stream_recipient(stream.id).id
        cond = '''AND NOT (recipient_id = {scotland} AND upper(subject) = upper('golf'))'''.format(scotland=recipient_id)
        self.assertIn(cond, queries[0]['sql'])

        # Next, verify the use_first_unread_anchor setting invokes
        # the `message_id = LARGER_THAN_MAX_MESSAGE_ID` hack.
        queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        self.assertIn('AND zerver_message.id = %d' % (LARGER_THAN_MAX_MESSAGE_ID,),
                      queries[0]['sql'])

    def test_exclude_muting_conditions(self) -> None:
        realm = get_realm('zulip')
        self.make_stream('web stuff')
        user_profile = self.example_user('hamlet')

        self.make_stream('irrelevant_stream')

        # Test the do-nothing case first.
        muted_topics = [
            ['irrelevant_stream', 'irrelevant_topic']
        ]
        set_topic_mutes(user_profile, muted_topics)

        # If nothing relevant is muted, then exclude_muting_conditions()
        # should return an empty list.
        narrow = [
            dict(operator='stream', operand='Scotland'),
        ]
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        self.assertEqual(muting_conditions, [])

        # Ok, now set up our muted topics to include a topic relevant to our narrow.
        muted_topics = [
            ['Scotland', 'golf'],
            ['web stuff', 'css'],
        ]
        set_topic_mutes(user_profile, muted_topics)

        # And verify that our query will exclude them.
        narrow = [
            dict(operator='stream', operand='Scotland'),
        ]

        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select([column("id").label("message_id")], None, table("zerver_message"))
        query = query.where(*muting_conditions)
        expected_query = '''
            SELECT id AS message_id
            FROM zerver_message
            WHERE NOT (recipient_id = :recipient_id_1 AND upper(subject) = upper(:param_1))
            '''
        self.assertEqual(fix_ws(query), fix_ws(expected_query))
        params = get_sqlalchemy_query_params(query)

        self.assertEqual(params['recipient_id_1'], get_recipient_id_for_stream_name(realm, 'Scotland'))
        self.assertEqual(params['param_1'], 'golf')

        mute_stream(realm, user_profile, 'Verona')

        # Using a bogus stream name should be similar to using no narrow at
        # all, and we'll exclude all mutes.
        narrow = [
            dict(operator='stream', operand='bogus-stream-name'),
        ]

        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select([column("id")], None, table("zerver_message"))
        query = query.where(and_(*muting_conditions))

        expected_query = '''
            SELECT id
            FROM zerver_message
            WHERE recipient_id NOT IN (:recipient_id_1)
            AND NOT
               (recipient_id = :recipient_id_2 AND upper(subject) = upper(:param_1) OR
                recipient_id = :recipient_id_3 AND upper(subject) = upper(:param_2))'''
        self.assertEqual(fix_ws(query), fix_ws(expected_query))
        params = get_sqlalchemy_query_params(query)
        self.assertEqual(params['recipient_id_1'], get_recipient_id_for_stream_name(realm, 'Verona'))
        self.assertEqual(params['recipient_id_2'], get_recipient_id_for_stream_name(realm, 'Scotland'))
        self.assertEqual(params['param_1'], 'golf')
        self.assertEqual(params['recipient_id_3'], get_recipient_id_for_stream_name(realm, 'web stuff'))
        self.assertEqual(params['param_2'], 'css')

    def test_get_messages_queries(self) -> None:
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id = 0) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 0}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id = 0) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 1, 'num_after': 0}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} ORDER BY message_id ASC \n LIMIT 2) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 1}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} ORDER BY message_id ASC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 100 ORDER BY message_id DESC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 0}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM ((SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 99 ORDER BY message_id DESC \n LIMIT 10) UNION ALL (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 100 ORDER BY message_id ASC \n LIMIT 11)) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 10}, sql)

    def test_get_messages_with_narrow_queries(self) -> None:
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id = 0) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 0,
                                              'narrow': '[["pm-with", "%s"]]' % (self.example_email("othello"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id = 0) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 1, 'num_after': 0,
                                              'narrow': '[["pm-with", "%s"]]' % (self.example_email("othello"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["pm-with", "%s"]]' % (self.example_email("othello"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2) != 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["is", "starred"]]'},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {othello_id} ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["sender", "%s"]]' % (self.example_email("othello"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["stream", "Scotland"]]'},
                                             sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND upper(subject) = upper('blah') ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["topic", "blah"]]'},
                                             sql)

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND upper(subject) = upper('blah') ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["stream", "Scotland"], ["topic", "blah"]]'},
                                             sql)

        # Narrow to pms with yourself
        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {hamlet_id} AND recipient_id = {hamlet_recipient} ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["pm-with", "%s"]]' % (self.example_email("hamlet"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND recipient_id = {scotland_recipient} AND (flags & 2) != 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["stream", "Scotland"], ["is", "starred"]]'},
                                             sql)

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_queries(self) -> None:
        query_ids = self.get_query_ids()

        sql_template = "SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.topic_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS topic_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"  # type: str
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["search", "jumping"]]'},
                                             sql)

        sql_template = "SELECT anon_1.message_id, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.topic_matches \nFROM (SELECT id AS message_id, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS topic_matches \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["stream", "Scotland"], ["search", "jumping"]]'},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.topic_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array(\'zulip.english_us_search\', rendered_content, plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS content_matches, ts_match_locs_array(\'zulip.english_us_search\', escape_html(subject), plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS topic_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (content ILIKE \'%jumping%\' OR subject ILIKE \'%jumping%\') AND (search_tsvector @@ plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 9,
                                              'narrow': '[["search", "\\"jumping\\" quickly"]]'},
                                             sql)

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_using_email(self) -> None:
        self.login(self.example_email("cordelia"))

        messages_to_search = [
            ('say hello', 'How are you doing, @**Othello, the Moor of Venice**?'),
            ('lunch plans', 'I am hungry!'),
        ]
        next_message_id = self.get_last_message().id + 1

        for topic, content in messages_to_search:
            self.send_stream_message(
                sender_email=self.example_email("cordelia"),
                stream_name="Verona",
                content=content,
                topic_name=topic,
            )

        self._update_tsvector_index()

        narrow = [
            dict(operator='sender', operand=self.example_email("cordelia")),
            dict(operator='search', operand=self.example_email("othello")),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
        ))  # type: Dict[str, Any]
        self.assertEqual(len(result['messages']), 0)

        narrow = [
            dict(operator='sender', operand=self.example_email("cordelia")),
            dict(operator='search', operand='othello'),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
        ))
        self.assertEqual(len(result['messages']), 1)
        messages = result['messages']

        meeting_message = [m for m in messages if m[TOPIC_NAME] == 'say hello'][0]
        self.assertEqual(
            meeting_message[MATCH_TOPIC],
            'say hello')
        othello = self.example_user('othello')
        self.assertEqual(
            meeting_message['match_content'],
            ('<p>How are you doing, <span class="user-mention" data-user-id="%s">' +
             '@<span class="highlight">Othello</span>, the Moor of Venice</span>?</p>') % (
                 othello.id))
