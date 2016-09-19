# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function
from django.db import connection
from django.test import override_settings
from sqlalchemy.sql import (
    and_, select, column, compiler
)

from zerver.models import (
    Realm, Recipient, Stream, Subscription, UserProfile, Attachment,
    get_display_recipient, get_recipient, get_realm, get_stream, get_user_profile_by_email,
)
from zerver.lib.actions import create_stream_if_needed, do_add_subscription
from zerver.lib.narrow import (
    build_narrow_filter,
)
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.test_helpers import (
    ZulipTestCase, POSTRequestMock,
    TestCase,
    get_user_messages, message_ids, queries_captured,
)
from zerver.views.messages import (
    exclude_muting_conditions,
    get_old_messages_backend, ok_to_include_history,
    NarrowBuilder, BadNarrowOperator
)

from six.moves import range
import os
import re
import ujson

def get_sqlalchemy_query_params(query):
    dialect = get_sqlalchemy_connection().dialect
    comp = compiler.SQLCompiler(dialect, query)
    comp.compile()
    return comp.params

def fix_ws(s):
    return re.sub('\s+', ' ', str(s)).strip()

def get_recipient_id_for_stream_name(realm, stream_name):
    stream = get_stream(stream_name, realm)
    return get_recipient(Recipient.STREAM, stream.id).id

def mute_stream(realm, user_profile, stream_name):
    stream = Stream.objects.get(realm=realm, name=stream_name)
    recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    subscription = Subscription.objects.get(recipient=recipient, user_profile=user_profile)
    subscription.in_home_view = False
    subscription.save()

class NarrowBuilderTest(ZulipTestCase):
    def setUp(self):
        self.realm = get_realm('zulip.com')
        self.user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.builder = NarrowBuilder(self.user_profile, column('id'))
        self.raw_query = select([column("id")], None, "zerver_message")

    def test_add_term_using_not_defined_operator(self):
        term = dict(operator='not-defined', operand='any')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_stream_operator(self):
        term = dict(operator='stream', operand='Scotland')
        self._do_add_term_test(term, 'WHERE recipient_id = :recipient_id_1')

    def test_add_term_using_stream_operator_and_negated(self):  # NEGATED
        term = dict(operator='stream', operand='Scotland', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id != :recipient_id_1')

    def test_add_term_using_stream_operator_and_non_existing_operand_should_raise_error(self):  # NEGATED
        term = dict(operator='stream', operand='NonExistingStream')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_is_operator_and_private_operand(self):
        term = dict(operator='is', operand='private')
        self._do_add_term_test(term, 'WHERE type = :type_1 OR type = :type_2')

    def test_add_term_using_is_operator_private_operand_and_negated(self):  # NEGATED
        term = dict(operator='is', operand='private', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (type = :type_1 OR type = :type_2)')

    def test_add_term_using_is_operator_and_non_private_operand(self):
        for operand in ['starred', 'mentioned', 'alerted']:
            term = dict(operator='is', operand=operand)
            self._do_add_term_test(term, 'WHERE (flags & :flags_1) != :param_1')

    def test_add_term_using_is_operator_non_private_operand_and_negated(self):  # NEGATED
        for operand in ['starred', 'mentioned', 'alerted']:
            term = dict(operator='is', operand=operand, negated=True)
            self._do_add_term_test(term, 'WHERE (flags & :flags_1) = :param_1')

    def test_add_term_using_non_supported_operator_should_raise_error(self):
        term = dict(operator='is', operand='non_supported')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_topic_operator_and_lunch_operand(self):
        term = dict(operator='topic', operand='lunch')
        self._do_add_term_test(term, 'WHERE upper(subject) = upper(:param_1)')

    def test_add_term_using_topic_operator_lunch_operand_and_negated(self):  # NEGATED
        term = dict(operator='topic', operand='lunch', negated=True)
        self._do_add_term_test(term, 'WHERE upper(subject) != upper(:param_1)')

    def test_add_term_using_topic_operator_and_personal_operand(self):
        term = dict(operator='topic', operand='personal')
        self._do_add_term_test(term, 'WHERE upper(subject) = upper(:param_1)')

    def test_add_term_using_topic_operator_personal_operand_and_negated(self):  # NEGATED
        term = dict(operator='topic', operand='personal', negated=True)
        self._do_add_term_test(term, 'WHERE upper(subject) != upper(:param_1)')

    def test_add_term_using_sender_operator(self):
        term = dict(operator='sender', operand='othello@zulip.com')
        self._do_add_term_test(term, 'WHERE sender_id = :param_1')

    def test_add_term_using_sender_operator_and_negated(self):  # NEGATED
        term = dict(operator='sender', operand='othello@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE sender_id != :param_1')

    def test_add_term_using_sender_operator_with_non_existing_user_as_operand(self):  # NEGATED
        term = dict(operator='sender', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_pm_with_operator_and_not_the_same_user_as_operand(self):
        term = dict(operator='pm-with', operand='othello@zulip.com')
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2')

    def test_add_term_using_pm_with_operator_not_the_same_user_as_operand_and_negated(self):  # NEGATED
        term = dict(operator='pm-with', operand='othello@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2)')

    def test_add_term_using_pm_with_operator_the_same_user_as_operand(self):
        term = dict(operator='pm-with', operand='hamlet@zulip.com')
        self._do_add_term_test(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1')

    def test_add_term_using_pm_with_operator_the_same_user_as_operand_and_negated(self):  # NEGATED
        term = dict(operator='pm-with', operand='hamlet@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (sender_id = :sender_id_1 AND recipient_id = :recipient_id_1)')

    def test_add_term_using_pm_with_operator_and_more_than_user_as_operand(self):
        term = dict(operator='pm-with', operand='hamlet@zulip.com, othello@zulip.com')
        self._do_add_term_test(term, 'WHERE recipient_id = :recipient_id_1')

    def test_add_term_using_pm_with_operator_more_than_user_as_operand_and_negated(self):  # NEGATED
        term = dict(operator='pm-with', operand='hamlet@zulip.com, othello@zulip.com', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id != :recipient_id_1')

    def test_add_term_using_pm_with_operator_with_non_existing_user_as_operand(self):
        term = dict(operator='pm-with', operand='non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_pm_with_operator_with_existing_and_non_existing_user_as_operand(self):
        term = dict(operator='pm-with', operand='othello@zulip.com,non-existing@zulip.com')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_id_operator(self):
        term = dict(operator='id', operand=555)
        self._do_add_term_test(term, 'WHERE id = :param_1')

    def test_add_term_using_id_operator_and_negated(self):  # NEGATED
        term = dict(operator='id', operand=555, negated=True)
        self._do_add_term_test(term, 'WHERE id != :param_1')

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator(self):
        term = dict(operator='search', operand='"french fries"')
        self._do_add_term_test(term, 'WHERE (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

    @override_settings(USING_PGROONGA=False)
    def test_add_term_using_search_operator_and_negated(self):  # NEGATED
        term = dict(operator='search', operand='"french fries"', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND NOT (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_pgroonga(self):
        term = dict(operator='search', operand='"french fries"')
        self._do_add_term_test(term, 'WHERE search_pgroonga @@ :search_pgroonga_1')

    @override_settings(USING_PGROONGA=True)
    def test_add_term_using_search_operator_and_negated_pgroonga(self):  # NEGATED
        term = dict(operator='search', operand='"french fries"', negated=True)
        self._do_add_term_test(term, 'WHERE NOT (search_pgroonga @@ :search_pgroonga_1)')

    def test_add_term_using_has_operator_and_attachment_operand(self):
        term = dict(operator='has', operand='attachment')
        self._do_add_term_test(term, 'WHERE has_attachment')

    def test_add_term_using_has_operator_attachment_operand_and_negated(self):  # NEGATED
        term = dict(operator='has', operand='attachment', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_attachment')

    def test_add_term_using_has_operator_and_image_operand(self):
        term = dict(operator='has', operand='image')
        self._do_add_term_test(term, 'WHERE has_image')

    def test_add_term_using_has_operator_image_operand_and_negated(self):  # NEGATED
        term = dict(operator='has', operand='image', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_image')

    def test_add_term_using_has_operator_and_link_operand(self):
        term = dict(operator='has', operand='link')
        self._do_add_term_test(term, 'WHERE has_link')

    def test_add_term_using_has_operator_link_operand_and_negated(self):  # NEGATED
        term = dict(operator='has', operand='link', negated=True)
        self._do_add_term_test(term, 'WHERE NOT has_link')

    def test_add_term_using_has_operator_non_supported_operand_should_raise_error(self):
        term = dict(operator='has', operand='non_supported')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_in_operator(self):
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='home')
        self._do_add_term_test(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

    def test_add_term_using_in_operator_and_negated(self):
        # negated = True should not change anything
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='home', negated=True)
        self._do_add_term_test(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

    def test_add_term_using_in_operator_and_all_operand(self):
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='all')
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def test_add_term_using_in_operator_all_operand_and_negated(self):
        # negated = True should not change anything
        mute_stream(self.realm, self.user_profile, 'Verona')
        term = dict(operator='in', operand='all', negated=True)
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def test_add_term_using_in_operator_and_not_defined_operand(self):
        term = dict(operator='in', operand='not_defined')
        self.assertRaises(BadNarrowOperator, self._build_query, term)

    def test_add_term_using_near_operator(self):
        term = dict(operator='near', operand='operand')
        query = self._build_query(term)
        self.assertEqual(str(query), 'SELECT id \nFROM zerver_message')

    def _do_add_term_test(self, term, where_clause):
        self.assertTrue(where_clause in str(self._build_query(term)))

    def _build_query(self, term):
        return self.builder.add_term(self.raw_query, term)

class BuildNarrowFilterTest(TestCase):
    def test_build_narrow_filter(self):
        fixtures_path = os.path.join(os.path.dirname(__file__),
                                     '../fixtures/narrow.json')
        scenarios = ujson.loads(open(fixtures_path, 'r').read())
        self.assertTrue(len(scenarios) == 8)
        for scenario in scenarios:
            narrow = scenario['narrow']
            accept_events = scenario['accept_events']
            reject_events = scenario['reject_events']
            narrow_filter = build_narrow_filter(narrow)
            for e in accept_events:
                self.assertTrue(narrow_filter(e))
            for e in reject_events:
                self.assertFalse(narrow_filter(e))

class IncludeHistoryTest(ZulipTestCase):
    def test_ok_to_include_history(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'public_stream')

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

    def get_and_check_messages(self, modified_params):
        post_params = {"anchor": 1, "num_before": 1, "num_after": 1}
        post_params.update(modified_params)
        payload = self.client_get("/json/messages", dict(post_params))
        self.assert_json_success(payload)
        result = ujson.loads(payload.content)

        self.assertIn("messages", result)
        self.assertIsInstance(result["messages"], list)
        for message in result["messages"]:
            for field in ("content", "content_type", "display_recipient",
                          "avatar_url", "recipient_id", "sender_full_name",
                          "sender_short_name", "timestamp"):
                self.assertIn(field, message)
            # TODO: deprecate soon in favor of avatar_url
            self.assertIn('gravatar_hash', message)

        return result

    def get_query_ids(self):
        hamlet_user = get_user_profile_by_email('hamlet@zulip.com')
        othello_user = get_user_profile_by_email('othello@zulip.com')

        query_ids = {}

        scotland_stream = get_stream('Scotland', hamlet_user.realm)
        query_ids['scotland_recipient'] = get_recipient(Recipient.STREAM, scotland_stream.id).id
        query_ids['hamlet_id'] = hamlet_user.id
        query_ids['othello_id'] = othello_user.id
        query_ids['hamlet_recipient'] = get_recipient(Recipient.PERSONAL, hamlet_user.id).id
        query_ids['othello_recipient'] = get_recipient(Recipient.PERSONAL, othello_user.id).id

        return query_ids

    def test_successful_get_old_messages(self):
        """
        A call to GET /json/messages with valid parameters returns a list of
        messages.
        """
        self.login("hamlet@zulip.com")
        self.get_and_check_messages(dict())

        # We have to support the legacy tuple style while there are old
        # clients around, which might include third party home-grown bots.
        narrow = [['pm-with', 'othello@zulip.com']]
        self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        narrow = [dict(operator='pm-with', operand='othello@zulip.com')]
        self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

    def test_get_old_messages_with_narrow_pm_with(self):
        """
        A request for old messages with a narrow by pm-with only returns
        conversations with that user.
        """
        me = 'hamlet@zulip.com'
        def dr_emails(dr):
            return ','.join(sorted(set([r['email'] for r in dr] + [me])))

        personals = [m for m in get_user_messages(get_user_profile_by_email(me))
            if m.recipient.type == Recipient.PERSONAL
            or m.recipient.type == Recipient.HUDDLE]
        if not personals:
            # FIXME: This is bad.  We should use test data that is guaranteed
            # to contain some personals for every user.  See #617.
            return
        emails = dr_emails(get_display_recipient(personals[0].recipient))

        self.login(me)
        narrow = [dict(operator='pm-with', operand=emails)]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(dr_emails(message['display_recipient']), emails)

    def test_get_old_messages_with_narrow_stream(self):
        """
        A request for old messages with a narrow by stream only returns
        messages for that stream.
        """
        self.login("hamlet@zulip.com")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = get_realm("zulip.com")
        stream, _ = create_stream_if_needed(realm, "Scotland")
        do_add_subscription(get_user_profile_by_email("hamlet@zulip.com"),
                            stream, no_log=True)
        self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        messages = get_user_messages(get_user_profile_by_email("hamlet@zulip.com"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        stream_name = get_display_recipient(stream_messages[0].recipient)
        stream_id = stream_messages[0].recipient.id

        narrow = [dict(operator='stream', operand=stream_name)]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(message["type"], "stream")
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_old_messages_with_narrow_stream_mit_unicode_regex(self):
        """
        A request for old messages for a user in the mit.edu relam with unicode
        stream name should be correctly escaped in the database query.
        """
        self.login("starnine@mit.edu")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = get_realm("mit.edu")
        lambda_stream, _ = create_stream_if_needed(realm, u"\u03bb-stream")
        do_add_subscription(get_user_profile_by_email("starnine@mit.edu"),
                            lambda_stream, no_log=True)

        lambda_stream_d, _ = create_stream_if_needed(realm, u"\u03bb-stream.d")
        do_add_subscription(get_user_profile_by_email("starnine@mit.edu"),
                            lambda_stream_d, no_log=True)

        self.send_message("starnine@mit.edu", u"\u03bb-stream", Recipient.STREAM)
        self.send_message("starnine@mit.edu", u"\u03bb-stream.d", Recipient.STREAM)

        narrow = [dict(operator='stream', operand=u'\u03bb-stream')]
        result = self.get_and_check_messages(dict(num_after=2,
                                                  narrow=ujson.dumps(narrow)))

        messages = get_user_messages(get_user_profile_by_email("starnine@mit.edu"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]

        self.assertEqual(len(result["messages"]), 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_old_messages_with_narrow_topic_mit_unicode_regex(self):
        """
        A request for old messages for a user in the mit.edu relam with unicode
        topic name should be correctly escaped in the database query.
        """
        self.login("starnine@mit.edu")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = get_realm("mit.edu")
        stream, _ = create_stream_if_needed(realm, "Scotland")
        do_add_subscription(get_user_profile_by_email("starnine@mit.edu"),
                            stream, no_log=True)

        self.send_message("starnine@mit.edu", "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic")
        self.send_message("starnine@mit.edu", "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic.d")

        narrow = [dict(operator='topic', operand=u'\u03bb-topic')]
        result = self.get_and_check_messages(dict(
            num_after=2,
            narrow=ujson.dumps(narrow)))

        messages = get_user_messages(get_user_profile_by_email("starnine@mit.edu"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        self.assertEqual(len(result["messages"]), 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)


    def test_get_old_messages_with_narrow_sender(self):
        """
        A request for old messages with a narrow by sender only returns
        messages sent by that person.
        """
        self.login("hamlet@zulip.com")
        # We need to send a message here to ensure that we actually
        # have a stream message in this narrow view.
        self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        self.send_message("othello@zulip.com", "Scotland", Recipient.STREAM)
        self.send_message("othello@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL)
        self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM)

        narrow = [dict(operator='sender', operand='othello@zulip.com')]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow)))

        for message in result["messages"]:
            self.assertEqual(message["sender_email"], "othello@zulip.com")

    @override_settings(USING_PGROONGA=False)
    def test_get_old_messages_with_search(self):
        self.login("cordelia@zulip.com")

        messages_to_search = [
            ('breakfast', 'there are muffins in the conference room'),
            ('lunch plans', 'I am hungry!'),
            ('meetings', 'discuss lunch after lunch'),
            ('meetings', 'please bring your laptops to take notes'),
            ('dinner', 'Anybody staying late tonight?'),
        ]

        for topic, content in messages_to_search:
            self.send_message(
                sender_name="cordelia@zulip.com",
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
            search_tsvector = to_tsvector('zulip.english_us_search',
            subject || rendered_content)
            """)

        narrow = [
            dict(operator='sender', operand='cordelia@zulip.com'),
            dict(operator='search', operand='lunch'),
        ]
        result = self.get_and_check_messages(dict(
            narrow=ujson.dumps(narrow),
            anchor=0,
            num_after=10,
        ))
        self.assertEqual(len(result['messages']), 2)
        messages = result['messages']

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

    @override_settings(USING_PGROONGA=True)
    def test_get_old_messages_with_search_pgroonga(self):
        self.login("cordelia@zulip.com")

        messages_to_search = [
            (u'日本語', u'こんにちは。今日はいい天気ですね。'),
            (u'日本語', u'今朝はごはんを食べました。'),
            (u'日本語', u'昨日、日本のお菓子を送りました。'),
            ('english', u'I want to go to 日本!'),
            ('english', 'Can you speak Japanese?'),
        ]

        for topic, content in messages_to_search:
            self.send_message(
                sender_name="cordelia@zulip.com",
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
            anchor=0,
            num_after=10,
        ))
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
        self.assertEqual(
            english_message['match_content'],
            u'<p>I want to go to <span class="highlight">日本</span>!</p>')

    def test_get_old_messages_with_only_searching_anchor(self):
        """
        Test that specifying an anchor but 0 for num_before and num_after
        returns at most 1 message.
        """
        self.login("cordelia@zulip.com")
        anchor = self.send_message("cordelia@zulip.com", "Verona", Recipient.STREAM)

        narrow = [dict(operator='sender', operand='cordelia@zulip.com')]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow),
                                                  anchor=anchor, num_before=0,
                                                  num_after=0))
        self.assertEqual(len(result['messages']), 1)

        narrow = [dict(operator='is', operand='mentioned')]
        result = self.get_and_check_messages(dict(narrow=ujson.dumps(narrow),
                                                  anchor=anchor, num_before=0,
                                                  num_after=0))
        self.assertEqual(len(result['messages']), 0)

    def test_missing_params(self):
        """
        anchor, num_before, and num_after are all required
        POST parameters for get_old_messages.
        """
        self.login("hamlet@zulip.com")

        required_args = (("anchor", 1), ("num_before", 1), ("num_after", 1))

        for i in range(len(required_args)):
            post_params = dict(required_args[:i] + required_args[i + 1:])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result,
                                   "Missing '%s' argument" % (required_args[i][0],))

    def test_bad_int_params(self):
        """
        num_before, num_after, and narrow must all be non-negative
        integers or strings that can be converted to non-negative integers.
        """
        self.login("hamlet@zulip.com")

        other_params = [("narrow", {}), ("anchor", 0)]
        int_params = ["num_before", "num_after"]

        bad_types = (False, "", "-1", -1)
        for idx, param in enumerate(int_params):
            for type in bad_types:
                # Rotate through every bad type for every integer
                # parameter, one at a time.
                post_params = dict(other_params + [(param, type)] + \
                                       [(other_param, 0) for other_param in \
                                            int_params[:idx] + int_params[idx + 1:]]
                                   )
                result = self.client_get("/json/messages", post_params)
                self.assert_json_error(result,
                                       "Bad value for '%s': %s" % (param, type))

    def test_bad_narrow_type(self):
        """
        narrow must be a list of string pairs.
        """
        self.login("hamlet@zulip.com")

        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]

        bad_types = (False, 0, '', '{malformed json,',
            '{foo: 3}', '[1,2]', '[["x","y","z"]]')
        for type in bad_types:
            post_params = dict(other_params + [("narrow", type)])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error(result,
                                   "Bad value for 'narrow': %s" % (type,))

    def test_old_empty_narrow(self):
        """
        '{}' is accepted to mean 'no narrow', for use by old mobile clients.
        """
        self.login("hamlet@zulip.com")
        all_result    = self.get_and_check_messages({})
        narrow_result = self.get_and_check_messages({'narrow': '{}'})

        self.assertEqual(message_ids(all_result), message_ids(narrow_result))

    def test_bad_narrow_operator(self):
        """
        Unrecognized narrow operators are rejected.
        """
        self.login("hamlet@zulip.com")
        for operator in ['', 'foo', 'stream:verona', '__init__']:
            narrow = [dict(operator=operator, operand='')]
            params = dict(anchor=0, num_before=0, num_after=0, narrow=ujson.dumps(narrow))
            result = self.client_get("/json/messages", params)
            self.assert_json_error_contains(result,
                "Invalid narrow operator: unknown operator")

    def test_non_string_narrow_operand_in_dict(self):
        """
        We expect search operands to be strings, not integers.
        """
        self.login("hamlet@zulip.com")
        not_a_string = 42
        narrow = [dict(operator='stream', operand=not_a_string)]
        params = dict(anchor=0, num_before=0, num_after=0, narrow=ujson.dumps(narrow))
        result = self.client_get("/json/messages", params)
        self.assert_json_error_contains(result, 'elem["operand"] is not a string')

    def exercise_bad_narrow_operand(self, operator, operands, error_msg):
        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]
        for operand in operands:
            post_params = dict(other_params + [
                ("narrow", ujson.dumps([[operator, operand]]))])
            result = self.client_get("/json/messages", post_params)
            self.assert_json_error_contains(result, error_msg)

    def test_bad_narrow_stream_content(self):
        """
        If an invalid stream name is requested in get_old_messages, an error is
        returned.
        """
        self.login("hamlet@zulip.com")
        bad_stream_content = (0, [], ["x", "y"])
        self.exercise_bad_narrow_operand("stream", bad_stream_content,
            "Bad value for 'narrow'")

    def test_bad_narrow_one_on_one_email_content(self):
        """
        If an invalid 'pm-with' is requested in get_old_messages, an
        error is returned.
        """
        self.login("hamlet@zulip.com")
        bad_stream_content = (0, [], ["x", "y"])
        self.exercise_bad_narrow_operand("pm-with", bad_stream_content,
            "Bad value for 'narrow'")

    def test_bad_narrow_nonexistent_stream(self):
        self.login("hamlet@zulip.com")
        self.exercise_bad_narrow_operand("stream", ['non-existent stream'],
            "Invalid narrow operator: unknown stream")

    def test_bad_narrow_nonexistent_email(self):
        self.login("hamlet@zulip.com")
        self.exercise_bad_narrow_operand("pm-with", ['non-existent-user@zulip.com'],
            "Invalid narrow operator: unknown user")

    def test_message_without_rendered_content(self):
        """Older messages may not have rendered_content in the database"""
        m = self.get_last_message()
        m.rendered_content = m.rendered_content_version = None
        m.content = 'test content'
        # Use to_dict_uncached_helper directly to avoid having to deal with remote cache
        d = m.to_dict_uncached_helper(True)
        self.assertEqual(d['content'], '<p>test content</p>')

    def common_check_get_old_messages_query(self, query_params, expected):
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        request = POSTRequestMock(query_params, user_profile)
        with queries_captured() as queries:
            get_old_messages_backend(request, user_profile)

        for query in queries:
            if "/* get_old_messages */" in query['sql']:
                sql = query['sql'].replace(" /* get_old_messages */", '')
                self.assertEqual(sql, expected)
                return
        self.fail("get_old_messages query not found")

    def test_use_first_unread_anchor_with_some_unread_messages(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'devel')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")

        # Have Othello send messages to Hamlet that he hasn't read.
        self.send_message("othello@zulip.com", "Scotland", Recipient.STREAM)
        last_message_id_to_hamlet = self.send_message("othello@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL)

        # Add a few messages that help us test that our query doesn't
        # look at messages that are irrelevant to Hamlet.
        self.send_message("othello@zulip.com", "cordelia@zulip.com", Recipient.PERSONAL)
        self.send_message("othello@zulip.com", "iago@zulip.com", Recipient.PERSONAL)

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=0,
            num_after=0,
            narrow='[]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_old_messages_backend(request, user_profile)

        # Verify the query for old messages looks correct.
        queries = [q for q in all_queries if '/* get_old_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        sql = queries[0]['sql']
        self.assertNotIn('AND message_id = 10000000000000000', sql)
        self.assertIn('ORDER BY message_id ASC', sql)

        cond = 'WHERE user_profile_id = %d AND message_id = %d' % (user_profile.id, last_message_id_to_hamlet)
        self.assertIn(cond, sql)

    def test_use_first_unread_anchor_with_no_unread_messages(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'devel')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=0,
            num_after=0,
            narrow='[]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_old_messages_backend(request, user_profile)

        # Next, verify the use_first_unread_anchor setting invokes
        # the `message_id = 10000000000000000` hack.
        queries = [q for q in all_queries if '/* get_old_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        self.assertIn('AND message_id = 10000000000000000', queries[0]['sql'])

    def test_use_first_unread_anchor_with_muted_topics(self):
        """
        Test that our logic related to `use_first_unread_anchor`
        invokes the `message_id = 10000000000000000` hack for
        the `/* get_old_messages */` query when relevant muting
        is in effect.

        This is a very arcane test on arcane, but very heavily
        field-tested, logic in get_old_messages_backend().  If
        this test breaks, be absolutely sure you know what you're
        doing.
        """

        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'devel')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        user_profile.muted_topics = ujson.dumps([['Scotland', 'golf'], ['devel', 'css'], ['bogus', 'bogus']])
        user_profile.save()

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=0,
            num_after=0,
            narrow='[["stream", "Scotland"]]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as all_queries:
            get_old_messages_backend(request, user_profile)

        # Do some tests on the main query, to verify the muting logic
        # runs on this code path.
        queries = [q for q in all_queries if q['sql'].startswith("SELECT message_id, flags")]
        self.assertEqual(len(queries), 1)

        stream = get_stream('Scotland', realm)
        recipient_id = get_recipient(Recipient.STREAM, stream.id).id
        cond = '''AND NOT (recipient_id = {scotland} AND upper(subject) = upper('golf'))'''.format(scotland=recipient_id)
        self.assertIn(cond, queries[0]['sql'])

        # Next, verify the use_first_unread_anchor setting invokes
        # the `message_id = 10000000000000000` hack.
        queries = [q for q in all_queries if '/* get_old_messages */' in q['sql']]
        self.assertEqual(len(queries), 1)
        self.assertIn('AND message_id = 10000000000000000', queries[0]['sql'])

    def test_exclude_muting_conditions(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'devel')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")

        # Test the do-nothing case first.
        user_profile.muted_topics = ujson.dumps([['irrelevant_stream', 'irrelevant_topic']])
        user_profile.save()

        # If nothing relevant is muted, then exclude_muting_conditions()
        # should return an empty list.
        narrow = [
            dict(operator='stream', operand='Scotland'),
        ]
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        self.assertEqual(muting_conditions, [])

        # Ok, now set up our muted topics to include a topic relevant to our narrow.
        user_profile.muted_topics = ujson.dumps([['Scotland', 'golf'], ['devel', 'css'], ['bogus', 'bogus']])
        user_profile.save()

        # And verify that our query will exclude them.
        narrow = [
            dict(operator='stream', operand='Scotland'),
        ]

        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select([column("id").label("message_id")], None, "zerver_message")
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
        narrow = []
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select([column("id")], None, "zerver_message")
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
        self.assertEqual(params['recipient_id_3'], get_recipient_id_for_stream_name(realm, 'devel'))
        self.assertEqual(params['upper_2'], 'css')

    def test_get_old_messages_queries(self):
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 100 ORDER BY message_id DESC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 0}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM ((SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 99 ORDER BY message_id DESC \n LIMIT 10) UNION ALL (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 100 ORDER BY message_id ASC \n LIMIT 11)) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 10}, sql)

    def test_get_old_messages_with_narrow_queries(self):
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["pm-with", "othello@zulip.com"]]'},
                                                 sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2) != 0 AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["is", "starred"]]'},
                                                 sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {othello_id} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["sender", "othello@zulip.com"]]'},
                                                sql)

        sql_template = 'SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"]]'},
                                                 sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND upper(subject) = upper('blah') AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["topic", "blah"]]'},
                                                 sql)

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND upper(subject) = upper('blah') AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"], ["topic", "blah"]]'},
                                                 sql)

        # Narrow to pms with yourself
        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {hamlet_id} AND recipient_id = {hamlet_recipient} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["pm-with", "hamlet@zulip.com"]]'},
                                                sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND recipient_id = {scotland_recipient} AND (flags & 2) != 0 AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"], ["is", "starred"]]'},
                                                 sql)

    @override_settings(USING_PGROONGA=False)
    def test_get_old_messages_with_search_queries(self):
        query_ids = self.get_query_ids()

        sql_template = "SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS subject_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["search", "jumping"]]'},
                                                 sql)

        sql_template = "SELECT anon_1.message_id, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT id AS message_id, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS subject_matches \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"], ["search", "jumping"]]'},
                                                 sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array(\'zulip.english_us_search\', rendered_content, plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS content_matches, ts_match_locs_array(\'zulip.english_us_search\', escape_html(subject), plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS subject_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (content ILIKE \'%jumping%\' OR subject ILIKE \'%jumping%\') AND (search_tsvector @@ plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["search", "\\"jumping\\" quickly"]]'},
                                                 sql)
