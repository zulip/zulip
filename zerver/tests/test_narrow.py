# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import print_function
from django.db import connection
from django.test import override_settings
from sqlalchemy.sql import (
    and_, select, column, table,
)
from sqlalchemy.sql import compiler

from zerver.models import (
    Realm, Recipient, Stream, Subscription, UserProfile, Attachment,
    get_display_recipient, get_recipient, get_realm, get_stream, get_user,
    Reaction, UserMessage
)
from zerver.lib.message import (
    MessageDict,
)
from zerver.lib.narrow import (
    build_narrow_filter,
)
from zerver.lib.request import JsonableError
from zerver.lib.str_utils import force_bytes
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_helpers import (
    POSTRequestMock,
    TestCase,
    get_user_messages, queries_captured,
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.topic_mutes import (
    set_topic_mutes,
)
from zerver.views.messages import (
    exclude_muting_conditions,
    get_messages_backend, ok_to_include_history,
    NarrowBuilder, BadNarrowOperator, Query,
    LARGER_THAN_MAX_MESSAGE_ID,
)

from typing import Dict, List, Mapping, Sequence, Tuple, Generic, Union, Any, Optional, Text
from six.moves import range
import os
import re
import ujson

def get_sqlalchemy_query_params(query):
    # type: (Text) -> Dict[Text, Text]
    dialect = get_sqlalchemy_connection().dialect
    comp = compiler.SQLCompiler(dialect, query)
    return comp.params

def fix_ws(s):
    # type: (Text) -> Text
    return re.sub('\s+', ' ', str(s)).strip()

def get_recipient_id_for_stream_name(realm, stream_name):
    # type: (Realm, Text) -> Text
    stream = get_stream(stream_name, realm)
    return get_recipient(Recipient.STREAM, stream.id).id

def mute_stream(realm, user_profile, stream_name):
    # type: (Realm, Text, Text) -> None
    stream = get_stream(stream_name, realm)
    recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    subscription = Subscription.objects.get(recipient=recipient, user_profile=user_profile)
    subscription.in_home_view = False
    subscription.save()

class NarrowBuilderTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.realm = get_realm('zulip')
        self.user_profile = self.example_user('hamlet')
        self.builder = NarrowBuilder(self.user_profile, column('id'))
        self.raw_query = select([column("id")], None, table("zerver_message"))

    def test_add_term_using_not_defined_operator(self):
        # type: () -> None
        term = dict(operator='not-defined', operand='any')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_stream_operator(self):
        # type: () -> None
        term = dict(operator='stream', operand='Scotland')
        self._do_add_term_test(term, 'WHERE recipient_id = :recipient_id_1')

    def test_add_term_using_stream_operator_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='stream', operand='Scotland', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id != :recipient_id_1')

    def test_add_term_using_stream_operator_and_non_existing_operand_should_raise_error(self):  # NEGATED
        # type: () -> None
        term = dict(operator='stream', operand='NonExistingStream')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_is_operator_and_private_operand(self):
        # type: () -> None
        term = dict(operator='is', operand='private')
        self._do_add_term_test(term, 'WHERE type = :type_1 OR type = :type_2')

    def test_add_term_using_is_operator_private_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='is', operand='private', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (type = :type_1 OR type = :type_2)')

    def test_add_term_using_is_operator_and_non_private_operand(self):
        # type: () -> None
        for operand in ['starred', 'mentioned', 'alerted']:
            term = dict(operator='is', operand=operand)
            self._do_add_term_test(term, 'WHERE (flags & :flags_1) != :param_1')

    def test_add_term_using_is_operator_and_unread_operand(self):
        # type: () -> None
        term = dict(operator='is', operand='unread')
        self._do_add_term_test(term, 'WHERE (flags & :flags_1) = :param_1')

    def test_add_term_using_is_operator_and_unread_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='is', operand='unread', negated=True)
        self._do_add_term_test(term, 'WHERE (flags & :flags_1) != :param_1')

    def test_add_term_using_is_operator_non_private_operand_and_negated(self):  # NEGATED
        # type: () -> None
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

    def test_add_term_using_non_supported_operator_should_raise_error(self):
        # type: () -> None
        term = dict(operator='is', operand='non_supported')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_topic_operator_and_lunch_operand(self):
        # type: () -> None
        term = dict(operator='topic', operand='lunch')
        self._do_add_term_test(term, 'WHERE upper(subject) = upper(:param_1)')

    def test_add_term_using_topic_operator_lunch_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='topic', operand='lunch', negated=True)
        self._do_add_term_test(term, 'WHERE upper(subject) != upper(:param_1)')

    def test_add_term_using_topic_operator_and_personal_operand(self):
        # type: () -> None
        term = dict(operator='topic', operand='personal')
        self._do_add_term_test(term, 'WHERE upper(subject) = upper(:param_1)')

    def test_add_term_using_topic_operator_personal_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='topic', operand='personal', negated=True)
        self._do_add_term_test(term, 'WHERE upper(subject) != upper(:param_1)')

    def test_add_term_using_sender_operator(self):
        # type: () -> None
        term = dict(operator='sender', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE sender_id = :param_1')

    def test_add_term_using_sender_operator_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='sender', operand=self.example_email("othello"), negated=True)
        self._do_add_term_test(term, 'WHERE sender_id != :param_1')

    def test_add_term_using_sender_operator_with_non_existing_user_as_operand(self):  # NEGATED
        # type: () -> None
        term = dict(operator='sender', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_pm_with_operator_and_not_the_same_user_as_operand(self):
        # type: () -> None
        term = dict(operator='pm-with', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2')

    def test_add_term_using_pm_with_operator_not_the_same_user_as_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='pm-with', operand=self.example_email("othello"), negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2)')

    def test_add_term_using_pm_with_operator_the_same_user_as_operand(self):
        # type: () -> None
        term = dict(operator='pm-with', operand=self.example_email("hamlet"))
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1')

    def test_add_term_using_pm_with_operator_the_same_user_as_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='pm-with', operand=self.example_email("hamlet"), negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1)')

    def test_add_term_using_pm_with_operator_and_more_than_user_as_operand(self):
        # type: () -> None
        term = dict(operator='pm-with', operand='hamlet@zulip.com, othello@zulip.com')
        self._do_add_term_test(term, 'WHERE recipient_id = :recipient_id_1')

    def test_add_term_using_pm_with_operator_more_than_user_as_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='pm-with', operand='hamlet@zulip.com, othello@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id != :recipient_id_1')

    def test_add_term_using_pm_with_operator_with_non_existing_user_as_operand(self):
        # type: () -> None
        term = dict(operator='pm-with', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_pm_with_operator_with_existing_and_non_existing_user_as_operand(self):
        # type: () -> None
        term = dict(operator='pm-with', operand='othello@zulip.com,non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_id_operator(self):
        # type: () -> None
        term = dict(operator='id', operand=555)
        self._do_add_term_test(term, 'WHERE id = :param_1')

    def test_add_term_using_id_operator_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='id', operand=555, negated=True)
        self._do_add_term_test(term, 'WHERE id != :param_1')

    def test_add_term_using_group_pm_operator_and_not_the_same_user_as_operand(self):
        # type: () -> None
        term = dict(operator='group-pm-with', operand=self.example_email("othello"))
        self._do_add_term_test(term, 'WHERE recipient_id != recipient_id')

    def test_add_term_using_group_pm_operator_not_the_same_user_as_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='group-pm-with', operand=self.example_email("othello"), negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id = recipient_id')

    def test_add_term_using_group_pm_operator_with_non_existing_user_as_operand(self):
        # type: () -> None
        term = dict(operator='group-pm-with', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator(self):
        # type: () -> None
        term = dict(operator='search', operand='"french fries"')
        self._do_add_term_test(term, 'WHERE (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='search', operand='"french fries"', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND NOT (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_pgroonga(self):
        # type: () -> None
        term = dict(operator='search', operand='"french fries"')
        self._do_add_term_test(term, 'WHERE search_pgroonga @@ :search_pgroonga_1')

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_and_negated_pgroonga(self):  # NEGATED
        # type: () -> None
        term = dict(operator='search', operand='"french fries"', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (search_pgroonga @@ :search_pgroonga_1)')

    def test_add_term_using_has_operator_and_attachment_operand(self):
        # type: () -> None
        term = dict(operator='has', operand='attachment')
        self._do_add_term_test(term, 'WHERE has_attachment')

    def test_add_term_using_has_operator_attachment_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='has', operand='attachment', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_attachment')

    def test_add_term_using_has_operator_and_image_operand(self):
        # type: () -> None
        term = dict(operator='has', operand='image')
        self._do_add_term_test(term, 'WHERE has_image')

    def test_add_term_using_has_operator_image_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='has', operand='image', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_image')

    def test_add_term_using_has_operator_and_link_operand(self):
        # type: () -> None
        term = dict(operator='has', operand='link')
        self._do_add_term_test(term, 'WHERE has_link')

    def test_add_term_using_has_operator_link_operand_and_negated(self):  # NEGATED
        # type: () -> None
        term = dict(operator='has', operand='link', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_link')

    def test_add_term_using_has_operator_non_supported_operand_should_raise_error(self):
        # type: () -> None
        term = dict(operator='has', operand='non_supported')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_in_operator(self):
        # type: () -> None
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='home')
        self._do_add_term_test(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

    def test_add_term_using_in_operator_and_negated(self):
        # type: () -> None
        # negated = True should not change anything
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='home', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

    def test_add_term_using_in_operator_and_all_operand(self):
        # type: () -> None
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='all')
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def test_add_term_using_in_operator_all_operand_and_negated(self):
        # type: () -> None
        # negated = True should not change anything
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='all', negated=True)
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def test_add_term_using_in_operator_and_not_defined_operand(self):
        # type: () -> None
        term = dict(operator='in', operand='not_defined')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_near_operator(self):
        # type: () -> None
        term = dict(operator='near', operand='operand')
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def _do_add_term_test(self, term, where_clause, params=None):
        # type: (Dict[str, Any], Text, Optional[Dict[str, Any]]) -> None
        query = self._build_query(term)
        if params is not None:
            actual_params = query.compile().params
            self.assertEqual(actual_params, params)
        self.assertTrue(where_clause in str(query))

    def _build_query(self, term):
        # type: (Dict[str, Any]) -> Query
        return self.builder.add_term(self.raw_query, term)

class BuildNarrowFilterTest(TestCase):
    def test_build_narrow_filter(self):
        # type: () -> None
        fixtures_path = os.path.join(os.path.dirname(__file__),
                                     '../fixtures/narrow.json')
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

    def test_build_narrow_filter_invalid(self):
        # type: () -> None
        with self.assertRaises(JsonableError):
            build_narrow_filter(["invalid_operator", "operand"])

class IncludeHistoryTest(ZulipTestCase):
    def test_ok_to_include_history(self):
        # type: () -> None
        realm = get_realm('zulip')
        self.make_stream('public_stream', realm=realm)

        # Negated stream searches should not include history.
        narrow = [
            dict(operator='stream', operand='public_stream', negated=True),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # Definitely forbid seeing history on private streams.
        narrow = [
            dict(operator='stream', operand='private_stream'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # History doesn't apply to PMs.
        narrow = [
            dict(operator='is', operand='private'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # History doesn't apply to unread messages.
        narrow = [
            dict(operator='is', operand='unread'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # If we are looking for something like starred messages, there is
        # no point in searching historical messages.
        narrow = [
            dict(operator='stream', operand='public_stream'),
            dict(operator='is', operand='starred'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # simple True case
        narrow = [
            dict(operator='stream', operand='public_stream'),
        ]
        self.assertTrue(ok_to_include_history(narrow, realm))

        narrow = [
            dict(operator='stream', operand='public_stream'),
            dict(operator='topic', operand='whatever'),
            dict(operator='search', operand='needle in haystack'),
        ]
        self.assertTrue(ok_to_include_history(narrow, realm))

class GetOldMessagesTest(ZulipTestCase):

    def get_and_check_messages(self, modified_params, **kwargs):
        # type: (Dict[str, Union[str, int]], **Any) -> Dict[str, Dict]
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

    def get_query_ids(self):
        # type: () -> Dict[Text, int]
        hamlet_user = self.example_user('hamlet')
        othello_user = self.example_user('othello')

        query_ids = {}  # type: Dict[Text, int]

        scotland_stream = get_stream('Scotland', hamlet_user.realm)
        query_ids['scotland_recipient'] = get_recipient(Recipient.STREAM, scotland_stream.id).id
        query_ids['hamlet_id'] = hamlet_user.id
        query_ids['othello_id'] = othello_user.id
        query_ids['hamlet_recipient'] = get_recipient(Recipient.PERSONAL, hamlet_user.id).id
        query_ids['othello_recipient'] = get_recipient(Recipient.PERSONAL, othello_user.id).id

        return query_ids

    def test_successful_get_messages_reaction(self):
        # type: () -> None
        """
        Test old `/json/messages` returns reactions.
        """
        self.login(self.example_email("hamlet"))
        messages = self.get_and_check_messages(dict())
        message_id = messages['messages'][0]['id']

        self.login(self.example_email("othello"))
        reaction_name = 'slightly_smiling_face'

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

    def test_successful_get_messages(self):
        # type: () -> None
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

    def test_get_messages_with_narrow_pm_with(self):
        # type: () -> None
        """
        A request for old messages with a narrow by pm-with only returns
        conversations with that user.
        """
        me = self.example_email('hamlet')

        def dr_emails(dr):
            # type: (Union[Text, List[Dict[str, Any]]]) -> Text
            assert isinstance(dr, list)
            return ','.join(sorted(set([r['email'] for r in dr] + [me])))

        self.send_message(me, self.example_email("iago"), Recipient.PERSONAL)
        self.send_message(me,
                          [self.example_email("iago"), self.example_email("cordelia")],
                          Recipient.HUDDLE)
        personals = [m for m in get_user_messages(self.example_user('hamlet'))
                     if m.recipient.type == Recipient.PERSONAL or
                     m.recipient.type == Recipient.HUDDLE]
        for personal in personals:
            emails = dr_emails(get_display_recipient(personal.recipient))

            self.login(me)
            narrow = [dict(operator='pm-with', operand=emails)]
            result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

            for message in result["messages"]:
                self.assertEqual(dr_emails(message['display_recipient']), emails)

    def test_get_messages_with_narrow_group_pm_with(self):
        # type: () -> None
        """
        A request for old messages with a narrow by group-pm-with only returns
        group-private conversations with that user.
        """
        me = self.example_email("hamlet")

        matching_message_ids = []
        matching_message_ids.append(self.send_message(me, [self.example_email("iago"), self.example_email("cordelia"), self.example_email("othello")], Recipient.HUDDLE))
        matching_message_ids.append(self.send_message(me, [self.example_email("cordelia"), self.example_email("othello")], Recipient.HUDDLE))

        non_matching_message_ids = []
        non_matching_message_ids.append(self.send_message(me, self.example_email("cordelia"), Recipient.PERSONAL))
        non_matching_message_ids.append(self.send_message(me, [self.example_email("iago"), self.example_email("othello")], Recipient.HUDDLE))
        non_matching_message_ids.append(self.send_message(self.example_email("cordelia"), [self.example_email("iago"), self.example_email("othello")], Recipient.HUDDLE))

        self.login(me)
        narrow = [dict(operator='group-pm-with', operand=self.example_email("cordelia"))]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))
        for message in result["messages"]:
            self.assertIn(message["id"], matching_message_ids)
            self.assertNotIn(message["id"], non_matching_message_ids)

    def test_get_messages_with_narrow_stream(self):
        # type: () -> None
        """
        A request for old messages with a narrow by stream only returns
        messages for that stream.
        """
        self.login(self.example_email('hamlet'))
        # We need to subscribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        self.subscribe(self.example_user("hamlet"), 'Scotland')
        self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM)
        messages = get_user_messages(self.example_user('hamlet'))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        stream_name = get_display_recipient(stream_messages[0].recipient)
        stream_id = stream_messages[0].recipient.id

        narrow = [dict(operator='stream', operand=stream_name)]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(message["type"], "stream")
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_stream_mit_unicode_regex(self):
        # type: () -> None
        """
        A request for old messages for a user in the mit.edu relam with unicode
        stream name should be correctly escaped in the database query.
        """
        self.login(self.mit_email("starnine"))
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        lambda_stream_name = u"\u03bb-stream"
        self.subscribe(self.mit_user("starnine"), lambda_stream_name)

        lambda_stream_d_name = u"\u03bb-stream.d"
        self.subscribe(self.mit_user("starnine"), lambda_stream_d_name)

        self.send_message(self.mit_email("starnine"), u"\u03bb-stream", Recipient.STREAM)
        self.send_message(self.mit_email("starnine"), u"\u03bb-stream.d", Recipient.STREAM)

        narrow = [dict(operator='stream', operand=u'\u03bb-stream')]
        result = self.get_and_check_messages(dict(num_after=2,
                                                  narrow=ujson.dumps(narrow)),
                                             subdomain="zephyr")

        messages = get_user_messages(self.mit_user("starnine"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]

        self.assertEqual(len(result["messages"]), 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_topic_mit_unicode_regex(self):
        # type: () -> None
        """
        A request for old messages for a user in the mit.edu realm with unicode
        topic name should be correctly escaped in the database query.
        """
        mit_user_profile = self.mit_user("starnine")
        email = mit_user_profile.email
        self.login(email)
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        self.subscribe(mit_user_profile, "Scotland")

        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic.d")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic.d.d")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic.d.d.d")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic.d.d.d.d")

        narrow = [dict(operator='topic', operand=u'\u03bb-topic')]
        result = self.get_and_check_messages(
            dict(num_after=100, narrow=ujson.dumps(narrow)),
            subdomain="zephyr")

        messages = get_user_messages(mit_user_profile)
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        self.assertEqual(len(result["messages"]), 5)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_topic_mit_personal(self):
        # type: () -> None
        """
        We handle .d grouping for MIT realm personal messages correctly.
        """
        mit_user_profile = self.mit_user("starnine")
        email = mit_user_profile.email
        self.login(email)  # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        self.subscribe(mit_user_profile, "Scotland")

        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u".d.d")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"PERSONAL")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u'(instance "").d')
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u".d.d.d")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u"personal.d")
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u'(instance "")')
        self.send_message(email, "Scotland", Recipient.STREAM,
                          subject=u".d.d.d.d")

        narrow = [dict(operator='topic', operand=u'personal.d.d')]
        result = self.get_and_check_messages(
            dict(num_before=50,
                 num_after=50,
                 narrow=ujson.dumps(narrow)),
            subdomain="zephyr")

        messages = get_user_messages(mit_user_profile)
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        self.assertEqual(len(result["messages"]), 7)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_messages_with_narrow_sender(self):
        # type: () -> None
        """
        A request for old messages with a narrow by sender only returns
        messages sent by that person.
        """
        self.login(self.example_email("hamlet"))
        # We need to send a message here to ensure that we actually
        # have a stream message in this narrow view.
        self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM)
        self.send_message(self.example_email("othello"), "Scotland", Recipient.STREAM)
        self.send_message(self.example_email("othello"), self.example_email("hamlet"), Recipient.PERSONAL)
        self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM)

        narrow = [dict(operator='sender', operand=self.example_email("othello"))]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(message["sender_email"], self.example_email("othello"))

    def _update_tsvector_index(self):
        # type: () -> None
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
    def test_messages_in_narrow(self):
        # type: () -> None
        email = self.example_email("cordelia")
        self.login(email)

        def send(content):
            # type: (Text) -> int
            msg_id = self.send_message(
                sender_name=email,
                raw_recipients="Verona",
                message_type=Recipient.STREAM,
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
    def test_get_messages_with_search(self):
        # type: () -> None
        self.login(self.example_email("cordelia"))

        messages_to_search = [
            ('breakfast', 'there are muffins in the conference room'),
            ('lunch plans', 'I am hungry!'),
            ('meetings', 'discuss lunch after lunch'),
            ('meetings', 'please bring your laptops to take notes'),
            ('dinner', 'Anybody staying late tonight?'),
            ('urltest', 'https://google.com'),
        ]

        next_message_id = self.get_last_message().id + 1

        for topic, content in messages_to_search:
            self.send_message(
                sender_name=self.example_email("cordelia"),
                raw_recipients="Verona",
                message_type=Recipient.STREAM,
                content=content,
                subject=topic,
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
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(result['messages']), 2)
        messages = result['messages']

        narrow = [dict(operator='search', operand='https://google.com')]
        link_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_before=0,
            num_after=10,
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(link_search_result['messages']), 1)
        self.assertEqual(link_search_result['messages'][0]['match_content'],
                         '<p><a href="https://google.com" target="_blank" title="https://google.com">https://<span class="highlight">google.com</span></a></p>')

        meeting_message = [m for m in messages if m['subject'] == 'meetings'][0]
        self.assertEqual(
            meeting_message['match_subject'],
            'meetings')
        self.assertEqual(
            meeting_message['match_content'],
            '<p>discuss <span class="highlight">lunch</span> after ' +
            '<span class="highlight">lunch</span></p>')

        meeting_message = [m for m in messages if m['subject'] == 'lunch plans'][0]
        self.assertEqual(
            meeting_message['match_subject'],
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
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(multi_search_result['messages']), 1)
        self.assertEqual(multi_search_result['messages'][0]['match_content'], '<p><span class="highlight">discuss</span> lunch <span class="highlight">after</span> lunch</p>')

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_not_subscribed(self):
        # type: () -> None
        """Verify support for searching a stream you're not subscribed to"""
        self.subscribe(self.example_user("hamlet"), "newstream")
        self.send_message(
            sender_name=self.example_email("hamlet"),
            raw_recipients="newstream",
            message_type=Recipient.STREAM,
            content="Public special content!",
            subject="new",
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
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(stream_search_result['messages']), 1)
        self.assertEqual(stream_search_result['messages'][0]['match_content'],
                         '<p>Public <span class="highlight">special</span> content!</p>')

    @override_settings(USING_PGROONGA=True)
    def test_get_messages_with_search_pgroonga(self):
        # type: () -> None
        self.login(self.example_email("cordelia"))

        next_message_id = self.get_last_message().id + 1

        messages_to_search = [
            (u'日本語', u'こんにちは。今日はいい天気ですね。'),
            (u'日本語', u'今朝はごはんを食べました。'),
            (u'日本語', u'昨日、日本のお菓子を送りました。'),
            ('english', u'I want to go to 日本!'),
            ('english', 'Can you speak https://en.wikipedia.org/wiki/Japanese?'),
            ('english', 'https://google.com'),
        ]

        for topic, content in messages_to_search:
            self.send_message(
                sender_name=self.example_email("cordelia"),
                raw_recipients="Verona",
                message_type=Recipient.STREAM,
                content=content,
                subject=topic,
            )

        # We use brute force here and update our text search index
        # for the entire zerver_message table (which is small in test
        # mode).  In production there is an async process which keeps
        # the search index up to date.
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE zerver_message SET
                search_pgroonga = subject || ' ' || rendered_content
                """)

        narrow = [
            dict(operator='search', operand=u'日本'),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(result['messages']), 4)
        messages = result['messages']

        japanese_message = [m for m in messages if m['subject'] == u'日本語'][-1]
        self.assertEqual(
            japanese_message['match_subject'],
            u'<span class="highlight">日本</span>語')
        self.assertEqual(
            japanese_message['match_content'],
            u'<p>昨日、<span class="highlight">日本</span>の' +
            u'お菓子を送りました。</p>')

        english_message = [m for m in messages if m['subject'] == 'english'][0]
        self.assertEqual(
            english_message['match_subject'],
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
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(multi_search_result['messages']), 1)
        self.assertEqual(multi_search_result['messages'][0]['match_content'],
                         '<p><span class="highlight">Can</span> you <span class="highlight">speak</span> <a href="https://en.wikipedia.org/wiki/Japanese" target="_blank" title="https://en.wikipedia.org/wiki/Japanese">https://en.<span class="highlight">wiki</span>pedia.org/<span class="highlight">wiki</span>/Japanese</a>?</p>')

        narrow = [dict(operator='search', operand='https://google.com')]
        link_search_result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=next_message_id,
            num_after=10,
            num_before=0,
        ))  # type: Dict[str, Dict]
        self.assertEqual(len(link_search_result['messages']), 1)
        self.assertEqual(link_search_result['messages'][0]['match_content'],
                         '<p><a href="https://google.com" target="_blank" title="https://google.com"><span class="highlight">https://google.com</span></a></p>')

    def test_messages_in_narrow_for_non_search(self):
        # type: () -> None
        email = self.example_email("cordelia")
        self.login(email)

        def send(content):
            # type: (Text) -> int
            msg_id = self.send_message(
                sender_name=email,
                raw_recipients="Verona",
                message_type=Recipient.STREAM,
                subject='test_topic',
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
        self.assertEqual(message['match_subject'], 'test_topic')

    def test_get_messages_with_only_searching_anchor(self):
        # type: () -> None
        """
        Test that specifying an anchor but 0 for num_before and num_after
        returns at most 1 message.
        """
        self.login(self.example_email("cordelia"))
        anchor = self.send_message(self.example_email("cordelia"), "Verona", Recipient.STREAM)

        narrow = [dict(operator='sender', operand=self.example_email("cordelia"))]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow),
                                                  anchor=anchor, num_before=0,
                                                  num_after=0))  # type: Dict[str, Dict]
        self.assertEqual(len(result['messages']), 1)

        narrow = [dict(operator='is', operand='mentioned')]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow),
                                                  anchor=anchor, num_before=0,
                                                  num_after=0))
        self.assertEqual(len(result['messages']), 0)

    def test_missing_params(self):
        # type: () -> None
        """
        anchor, num_before, and num_after are all required
        POST parameters for get_messages.
        """
        self.login(self.example_email("hamlet"))

        required_args = (("anchor", 1), ("num_before", 1), ("num_after", 1))  # type: Tuple[Tuple[Text, int], ...]

        for i in range(len(required_args)):
            post_params = dict(required_args[:i] + required_args[i + 1:])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result,
                                   "Missing '%s' argument" % (required_args[i][0],))

    def test_bad_int_params(self):
        # type: () -> None
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

    def test_bad_narrow_type(self):
        # type: () -> None
        """
        narrow must be a list of string pairs.
        """
        self.login(self.example_email("hamlet"))

        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]  # type: List[Tuple[Text, Union[int, str, bool]]]

        bad_types = (False, 0, '', '{malformed json,',
                     '{foo: 3}', '[1,2]', '[["x","y","z"]]')  # type: Tuple[Union[int, str, bool], ...]
        for type in bad_types:
            post_params = dict(other_params + [("narrow", type)])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result,
                                   "Bad value for 'narrow': %s" % (type,))

    def test_bad_narrow_operator(self):
        # type: () -> None
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

    def test_non_string_narrow_operand_in_dict(self):
        # type: () -> None
        """
        We expect search operands to be strings, not integers.
        """
        self.login(self.example_email("hamlet"))
        not_a_string = 42
        narrow = [dict(operator='stream', operand=not_a_string)]
        params = dict(anchor=0, num_before=0, num_after=0, narrow=ujson.dumps(narrow))
        result = self.client_get("/json/messages", params)
        self.assert_json_error_contains(result, 'elem["operand"] is not a string')

    def exercise_bad_narrow_operand(self, operator, operands, error_msg):
        # type: (Text, Sequence, Text) -> None
        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]  # type: List
        for operand in operands:
            post_params = dict(other_params + [
                ("narrow", ujson.dumps([[operator, operand]]))])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error_contains(result, error_msg)

    def test_bad_narrow_stream_content(self):
        # type: () -> None
        """
        If an invalid stream name is requested in get_messages, an error is
        returned.
        """
        self.login(self.example_email("hamlet"))
        bad_stream_content = (0, [], ["x", "y"])  # type: Sequence
        self.exercise_bad_narrow_operand("stream", bad_stream_content,
                                         "Bad value for 'narrow'")

    def test_bad_narrow_one_on_one_email_content(self):
        # type: () -> None
        """
        If an invalid 'pm-with' is requested in get_messages, an
        error is returned.
        """
        self.login(self.example_email("hamlet"))
        bad_stream_content = (0, [], ["x", "y"])  # type: Tuple[int, List[None], List[Text]]
        self.exercise_bad_narrow_operand("pm-with", bad_stream_content,
                                         "Bad value for 'narrow'")

    def test_bad_narrow_nonexistent_stream(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        self.exercise_bad_narrow_operand("stream", ['non-existent stream'],
                                         "Invalid narrow operator: unknown stream")

    def test_bad_narrow_nonexistent_email(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        self.exercise_bad_narrow_operand("pm-with", ['non-existent-user@zulip.com'],
                                         "Invalid narrow operator: unknown user")

    def test_message_without_rendered_content(self):
        # type: () -> None
        """Older messages may not have rendered_content in the database"""
        m = self.get_last_message()
        m.rendered_content = m.rendered_content_version = None
        m.content = 'test content'
        # Use to_dict_uncached_helper directly to avoid having to deal with remote cache
        d = MessageDict.to_dict_uncached_helper(m, True)
        self.assertEqual(d['content'], '<p>test content</p>')

    def common_check_get_messages_query(self, query_params, expected):
        # type: (Dict[str, object], Text) -> None
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

    def test_use_first_unread_anchor_with_some_unread_messages(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')

        # Have Othello send messages to Hamlet that he hasn't read.
        self.send_message(self.example_email("othello"), "Scotland", Recipient.STREAM)
        last_message_id_to_hamlet = self.send_message(self.example_email("othello"), self.example_email("hamlet"), Recipient.PERSONAL)

        # Add a few messages that help us test that our query doesn't
        # look at messages that are irrelevant to Hamlet.
        self.send_message(self.example_email("othello"), self.example_email("cordelia"), Recipient.PERSONAL)
        self.send_message(self.example_email("othello"), self.example_email("iago"), Recipient.PERSONAL)

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

        cond = 'WHERE user_profile_id = %d AND message_id >= %d' % (user_profile.id, last_message_id_to_hamlet)
        self.assertIn(cond, sql)
        cond = 'WHERE user_profile_id = %d AND message_id <= %d' % (user_profile.id, last_message_id_to_hamlet - 1)
        self.assertIn(cond, sql)

    def test_use_first_unread_anchor_with_no_unread_messages(self):
        # type: () -> None
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

        # Next, verify the use_first_unread_anchor setting invokes
        # the `message_id = LARGER_THAN_MAX_MESSAGE_ID` hack.
        queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        self.assertIn('AND message_id <= %d' % (LARGER_THAN_MAX_MESSAGE_ID - 1,), queries[0]['sql'])
        # There should not be an after_query in this case, since it'd be useless
        self.assertNotIn('AND message_id >= %d' % (LARGER_THAN_MAX_MESSAGE_ID,), queries[0]['sql'])

    def test_use_first_unread_anchor_with_muted_topics(self):
        # type: () -> None
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
        recipient_id = get_recipient(Recipient.STREAM, stream.id).id
        cond = '''AND NOT (recipient_id = {scotland} AND upper(subject) = upper('golf'))'''.format(scotland=recipient_id)
        self.assertIn(cond, queries[0]['sql'])

        # Next, verify the use_first_unread_anchor setting invokes
        # the `message_id = LARGER_THAN_MAX_MESSAGE_ID` hack.
        queries = [q for q in all_queries if '/* get_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        self.assertIn('AND message_id = %d' % (LARGER_THAN_MAX_MESSAGE_ID,),
                      queries[0]['sql'])

    def test_exclude_muting_conditions(self):
        # type: () -> None
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
            WHERE NOT (recipient_id = :recipient_id_1 AND upper(subject) = upper(:upper_1))
            '''
        self.assertEqual(fix_ws(query), fix_ws(expected_query))
        params = get_sqlalchemy_query_params(query)

        self.assertEqual(params['recipient_id_1'], get_recipient_id_for_stream_name(realm, 'Scotland'))
        self.assertEqual(params['upper_1'], 'golf')

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
               (recipient_id = :recipient_id_2 AND upper(subject) = upper(:upper_1) OR
                recipient_id = :recipient_id_3 AND upper(subject) = upper(:upper_2))'''
        self.assertEqual(fix_ws(query), fix_ws(expected_query))
        params = get_sqlalchemy_query_params(query)
        self.assertEqual(params['recipient_id_1'], get_recipient_id_for_stream_name(realm, 'Verona'))
        self.assertEqual(params['recipient_id_2'], get_recipient_id_for_stream_name(realm, 'Scotland'))
        self.assertEqual(params['upper_1'], 'golf')
        self.assertEqual(params['recipient_id_3'], get_recipient_id_for_stream_name(realm, 'web stuff'))
        self.assertEqual(params['upper_2'], 'css')

    def test_get_messages_queries(self):
        # type: () -> None
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 100 ORDER BY message_id DESC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 0}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM ((SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 99 ORDER BY message_id DESC \n LIMIT 10) UNION ALL (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 100 ORDER BY message_id ASC \n LIMIT 11)) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 10}, sql)

    def test_get_messages_with_narrow_queries(self):
        # type: () -> None
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["pm-with", "%s"]]' % (self.example_email("othello"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2) != 0 AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["is", "starred"]]'},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {othello_id} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["sender", "%s"]]' % (self.example_email("othello"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["stream", "Scotland"]]'},
                                             sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND upper(subject) = upper('blah') AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["topic", "blah"]]'},
                                             sql)

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND upper(subject) = upper('blah') AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["stream", "Scotland"], ["topic", "blah"]]'},
                                             sql)

        # Narrow to pms with yourself
        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {hamlet_id} AND recipient_id = {hamlet_recipient} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["pm-with", "%s"]]' % (self.example_email("hamlet"),)},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND recipient_id = {scotland_recipient} AND (flags & 2) != 0 AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["stream", "Scotland"], ["is", "starred"]]'},
                                             sql)

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_queries(self):
        # type: () -> None
        query_ids = self.get_query_ids()

        sql_template = "SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS subject_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"  # type: Text
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["search", "jumping"]]'},
                                             sql)

        sql_template = "SELECT anon_1.message_id, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT id AS message_id, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS subject_matches \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["stream", "Scotland"], ["search", "jumping"]]'},
                                             sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array(\'zulip.english_us_search\', rendered_content, plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS content_matches, ts_match_locs_array(\'zulip.english_us_search\', escape_html(subject), plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS subject_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (content ILIKE \'%jumping%\' OR subject ILIKE \'%jumping%\') AND (search_tsvector @@ plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                              'narrow': '[["search", "\\"jumping\\" quickly"]]'},
                                             sql)

    @override_settings(USING_PGROONGA=False)
    def test_get_messages_with_search_using_email(self):
        # type: () -> None
        self.login(self.example_email("cordelia"))

        messages_to_search = [
            ('say hello', 'How are you doing, @**Othello, the Moor of Venice**?'),
            ('lunch plans', 'I am hungry!'),
        ]
        next_message_id = self.get_last_message().id + 1

        for topic, content in messages_to_search:
            self.send_message(
                sender_name=self.example_email("cordelia"),
                raw_recipients="Verona",
                message_type=Recipient.STREAM,
                content=content,
                subject=topic,
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
        ))  # type: Dict[str, Dict]
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

        meeting_message = [m for m in messages if m['subject'] == 'say hello'][0]
        self.assertEqual(
            meeting_message['match_subject'],
            'say hello')
        self.assertEqual(
            meeting_message['match_content'],
            ('<p>How are you doing, <span class="user-mention" data-user-email="%s" data-user-id="6">' +
             '@<span class="highlight">Othello</span>, the Moor of Venice</span>?</p>') % (
                 self.example_email("othello"),))
