
from django.utils.translation import ugettext as _
from django.utils.timezone import now as timezone_now
from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpRequest, HttpResponse
from typing import Dict, List, Set, Text, Any, Callable, Iterable, \
    Optional, Tuple, Union, Sequence
from zerver.lib.exceptions import JsonableError, ErrorCode
from zerver.lib.html_diff import highlight_html_differences
from zerver.decorator import has_request_variables, \
    REQ, to_non_negative_int
from django.utils.html import escape as escape_html
from zerver.lib import bugdown
from zerver.lib.actions import recipient_for_emails, do_update_message_flags, \
    compute_mit_user_fullname, compute_irc_user_fullname, compute_jabber_user_fullname, \
    create_mirror_user_if_needed, check_send_message, do_update_message, \
    extract_recipients, truncate_body, render_incoming_message, do_delete_message, \
    do_mark_all_as_read, do_mark_stream_messages_as_read, \
    get_user_info_for_message_updates, check_schedule_message
from zerver.lib.queue import queue_json_publish
from zerver.lib.message import (
    access_message,
    messages_for_ids,
    render_markdown,
    get_first_visible_message_id,
)
from zerver.lib.response import json_success, json_error
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.streams import access_stream_by_id, can_access_stream_history_by_name
from zerver.lib.timestamp import datetime_to_timestamp, convert_to_UTC
from zerver.lib.timezone import get_timezone
from zerver.lib.topic_mutes import exclude_topic_mutes
from zerver.lib.utils import statsd
from zerver.lib.validator import \
    check_list, check_int, check_dict, check_string, check_bool
from zerver.models import Message, UserProfile, Stream, Subscription, Client,\
    Realm, RealmDomain, Recipient, UserMessage, bulk_get_recipients, get_personal_recipient, \
    get_stream, email_to_domain, get_realm, get_active_streams, \
    get_user_including_cross_realm, get_stream_recipient

from sqlalchemy import func
from sqlalchemy.sql import select, join, column, literal_column, literal, and_, \
    or_, not_, union_all, alias, Selectable, Select, ColumnElement, table

from dateutil.parser import parse as dateparser
import re
import ujson
import datetime

LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000

class BadNarrowOperator(JsonableError):
    code = ErrorCode.BAD_NARROW
    data_fields = ['desc']

    def __init__(self, desc: str) -> None:
        self.desc = desc  # type: str

    @staticmethod
    def msg_format() -> str:
        return _('Invalid narrow operator: {desc}')

# TODO: Should be Select, but sqlalchemy stubs are busted
Query = Any

# TODO: should be Callable[[ColumnElement], ColumnElement], but sqlalchemy stubs are busted
ConditionTransform = Any

# When you add a new operator to this, also update zerver/lib/narrow.py
class NarrowBuilder:
    '''
    Build up a SQLAlchemy query to find messages matching a narrow.
    '''

    # This class has an important security invariant:
    #
    #   None of these methods ever *add* messages to a query's result.
    #
    # That is, the `add_term` method, and its helpers the `by_*` methods,
    # are passed a Query object representing a query for messages; they may
    # call some methods on it, and then they return a resulting Query
    # object.  Things these methods may do to the queries they handle
    # include
    #  * add conditions to filter out rows (i.e., messages), with `query.where`
    #  * add columns for more information on the same message, with `query.column`
    #  * add a join for more information on the same message
    #
    # Things they may not do include
    #  * anything that would pull in additional rows, or information on
    #    other messages.

    def __init__(self, user_profile: UserProfile, msg_id_column: str) -> None:
        self.user_profile = user_profile
        self.msg_id_column = msg_id_column
        self.user_realm = user_profile.realm

    def add_term(self, query: Query, term: Dict[str, Any]) -> Query:
        """
        Extend the given query to one narrowed by the given term, and return the result.

        This method satisfies an important security property: the returned
        query never includes a message that the given query didn't.  In
        particular, if the given query will only find messages that a given
        user can legitimately see, then so will the returned query.
        """
        # To maintain the security property, we hold all the `by_*`
        # methods to the same criterion.  See the class's block comment
        # for details.

        # We have to be careful here because we're letting users call a method
        # by name! The prefix 'by_' prevents it from colliding with builtin
        # Python __magic__ stuff.
        operator = term['operator']
        operand = term['operand']

        negated = term.get('negated', False)

        method_name = 'by_' + operator.replace('-', '_')
        method = getattr(self, method_name, None)
        if method is None:
            raise BadNarrowOperator('unknown operator ' + operator)

        if negated:
            maybe_negate = not_
        else:
            maybe_negate = lambda cond: cond

        return method(query, operand, maybe_negate)

    def by_has(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        if operand not in ['attachment', 'image', 'link']:
            raise BadNarrowOperator("unknown 'has' operand " + operand)
        col_name = 'has_' + operand
        cond = column(col_name)
        return query.where(maybe_negate(cond))

    def by_in(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        if operand == 'home':
            conditions = exclude_muting_conditions(self.user_profile, [])
            return query.where(and_(*conditions))
        elif operand == 'all':
            return query

        raise BadNarrowOperator("unknown 'in' operand " + operand)

    def by_is(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        if operand == 'private':
            # The `.select_from` method extends the query with a join.
            query = query.select_from(join(query.froms[0], table("zerver_recipient"),
                                           column("recipient_id") ==
                                           literal_column("zerver_recipient.id")))
            cond = or_(column("type") == Recipient.PERSONAL,
                       column("type") == Recipient.HUDDLE)
            return query.where(maybe_negate(cond))
        elif operand == 'starred':
            cond = column("flags").op("&")(UserMessage.flags.starred.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == 'unread':
            cond = column("flags").op("&")(UserMessage.flags.read.mask) == 0
            return query.where(maybe_negate(cond))
        elif operand == 'mentioned':
            cond1 = column("flags").op("&")(UserMessage.flags.mentioned.mask) != 0
            cond2 = column("flags").op("&")(UserMessage.flags.wildcard_mentioned.mask) != 0
            cond = or_(cond1, cond2)
            return query.where(maybe_negate(cond))
        elif operand == 'alerted':
            cond = column("flags").op("&")(UserMessage.flags.has_alert_word.mask) != 0
            return query.where(maybe_negate(cond))
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    _alphanum = frozenset(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

    def _pg_re_escape(self, pattern: Text) -> Text:
        """
        Escape user input to place in a regex

        Python's re.escape escapes unicode characters in a way which postgres
        fails on, '\u03bb' to '\\\u03bb'. This function will correctly escape
        them for postgres, '\u03bb' to '\\u03bb'.
        """
        s = list(pattern)
        for i, c in enumerate(s):
            if c not in self._alphanum:
                if ord(c) >= 128:
                    # convert the character to hex postgres regex will take
                    # \uXXXX
                    s[i] = '\\u{:0>4x}'.format(ord(c))
                else:
                    s[i] = '\\' + c
        return ''.join(s)

    def by_stream(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        try:
            # Because you can see your own message history for
            # private streams you are no longer subscribed to, we
            # need get_stream, not access_stream, here.
            stream = get_stream(operand, self.user_profile.realm)
        except Stream.DoesNotExist:
            raise BadNarrowOperator('unknown stream ' + operand)

        if self.user_profile.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to "social" to also show messages to
            # /^(un)*social(.d)*$/ (unsocial, ununsocial, social.d, ...).

            # In `ok_to_include_history`, we assume that a non-negated
            # `stream` term for a public stream will limit the query to
            # that specific stream.  So it would be a bug to hit this
            # codepath after relying on this term there.  But all streams in
            # a Zephyr realm are private, so that doesn't happen.
            assert(not stream.is_public())

            m = re.search(r'^(?:un)*(.+?)(?:\.d)*$', stream.name, re.IGNORECASE)
            # Since the regex has a `.+` in it and "" is invalid as a
            # stream name, this will always match
            assert(m is not None)
            base_stream_name = m.group(1)

            matching_streams = get_active_streams(self.user_profile.realm).filter(
                name__iregex=r'^(un)*%s(\.d)*$' % (self._pg_re_escape(base_stream_name),))
            matching_stream_ids = [matching_stream.id for matching_stream in matching_streams]
            recipients_map = bulk_get_recipients(Recipient.STREAM, matching_stream_ids)
            cond = column("recipient_id").in_([recipient.id for recipient in recipients_map.values()])
            return query.where(maybe_negate(cond))

        recipient = get_stream_recipient(stream.id)
        cond = column("recipient_id") == recipient.id
        return query.where(maybe_negate(cond))

    def by_topic(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        if self.user_profile.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
            # (foo, foo.d, foo.d.d, etc)
            m = re.search(r'^(.*?)(?:\.d)*$', operand, re.IGNORECASE)
            # Since the regex has a `.*` in it, this will always match
            assert(m is not None)
            base_topic = m.group(1)

            # Additionally, MIT users expect the empty instance and
            # instance "personal" to be the same.
            if base_topic in ('', 'personal', '(instance "")'):
                cond = or_(
                    func.upper(column("subject")) == func.upper(literal("")),
                    func.upper(column("subject")) == func.upper(literal(".d")),
                    func.upper(column("subject")) == func.upper(literal(".d.d")),
                    func.upper(column("subject")) == func.upper(literal(".d.d.d")),
                    func.upper(column("subject")) == func.upper(literal(".d.d.d.d")),
                    func.upper(column("subject")) == func.upper(literal("personal")),
                    func.upper(column("subject")) == func.upper(literal("personal.d")),
                    func.upper(column("subject")) == func.upper(literal("personal.d.d")),
                    func.upper(column("subject")) == func.upper(literal("personal.d.d.d")),
                    func.upper(column("subject")) == func.upper(literal("personal.d.d.d.d")),
                    func.upper(column("subject")) == func.upper(literal('(instance "")')),
                    func.upper(column("subject")) == func.upper(literal('(instance "").d')),
                    func.upper(column("subject")) == func.upper(literal('(instance "").d.d')),
                    func.upper(column("subject")) == func.upper(literal('(instance "").d.d.d')),
                    func.upper(column("subject")) == func.upper(literal('(instance "").d.d.d.d')),
                )
            else:
                # We limit `.d` counts, since postgres has much better
                # query planning for this than they do for a regular
                # expression (which would sometimes table scan).
                cond = or_(
                    func.upper(column("subject")) == func.upper(literal(base_topic)),
                    func.upper(column("subject")) == func.upper(literal(base_topic + ".d")),
                    func.upper(column("subject")) == func.upper(literal(base_topic + ".d.d")),
                    func.upper(column("subject")) == func.upper(literal(base_topic + ".d.d.d")),
                    func.upper(column("subject")) == func.upper(literal(base_topic + ".d.d.d.d")),
                )
            return query.where(maybe_negate(cond))

        cond = func.upper(column("subject")) == func.upper(literal(operand))
        return query.where(maybe_negate(cond))

    def by_sender(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        try:
            sender = get_user_including_cross_realm(operand, self.user_realm)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator('unknown user ' + operand)

        cond = column("sender_id") == literal(sender.id)
        return query.where(maybe_negate(cond))

    def by_near(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        return query

    def by_id(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        cond = self.msg_id_column == literal(operand)
        return query.where(maybe_negate(cond))

    def by_pm_with(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        if ',' in operand:
            # Huddle
            try:
                # Ignore our own email if it is in this list
                emails = [e.strip() for e in operand.split(',') if e.strip() != self.user_profile.email]
                recipient = recipient_for_emails(emails, False,
                                                 self.user_profile, self.user_profile)
            except ValidationError:
                raise BadNarrowOperator('unknown recipient ' + operand)
            cond = column("recipient_id") == recipient.id
            return query.where(maybe_negate(cond))
        else:
            # Personal message
            self_recipient = get_personal_recipient(self.user_profile.id)
            if operand == self.user_profile.email:
                # Personals with self
                cond = and_(column("sender_id") == self.user_profile.id,
                            column("recipient_id") == self_recipient.id)
                return query.where(maybe_negate(cond))

            # Personals with other user; include both directions.
            try:
                narrow_profile = get_user_including_cross_realm(operand, self.user_realm)
            except UserProfile.DoesNotExist:
                raise BadNarrowOperator('unknown user ' + operand)

            narrow_recipient = get_personal_recipient(narrow_profile.id)
            cond = or_(and_(column("sender_id") == narrow_profile.id,
                            column("recipient_id") == self_recipient.id),
                       and_(column("sender_id") == self.user_profile.id,
                            column("recipient_id") == narrow_recipient.id))
            return query.where(maybe_negate(cond))

    def by_group_pm_with(self, query: Query, operand: str,
                         maybe_negate: ConditionTransform) -> Query:
        try:
            narrow_profile = get_user_including_cross_realm(operand, self.user_realm)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator('unknown user ' + operand)

        self_recipient_ids = [
            recipient_tuple['recipient_id'] for recipient_tuple
            in Subscription.objects.filter(
                user_profile=self.user_profile,
                recipient__type=Recipient.HUDDLE
            ).values("recipient_id")]
        narrow_recipient_ids = [
            recipient_tuple['recipient_id'] for recipient_tuple
            in Subscription.objects.filter(
                user_profile=narrow_profile,
                recipient__type=Recipient.HUDDLE
            ).values("recipient_id")]

        recipient_ids = set(self_recipient_ids) & set(narrow_recipient_ids)
        cond = column("recipient_id").in_(recipient_ids)
        return query.where(maybe_negate(cond))

    def by_search(self, query: Query, operand: str, maybe_negate: ConditionTransform) -> Query:
        if settings.USING_PGROONGA:
            return self._by_search_pgroonga(query, operand, maybe_negate)
        else:
            return self._by_search_tsearch(query, operand, maybe_negate)

    def _by_search_pgroonga(self, query: Query, operand: str,
                            maybe_negate: ConditionTransform) -> Query:
        match_positions_character = func.pgroonga.match_positions_character
        query_extract_keywords = func.pgroonga.query_extract_keywords
        keywords = query_extract_keywords(operand)
        query = query.column(match_positions_character(column("rendered_content"),
                                                       keywords).label("content_matches"))
        query = query.column(match_positions_character(column("subject"),
                                                       keywords).label("subject_matches"))
        condition = column("search_pgroonga").op("@@")(operand)
        return query.where(maybe_negate(condition))

    def _by_search_tsearch(self, query: Query, operand: str,
                           maybe_negate: ConditionTransform) -> Query:
        tsquery = func.plainto_tsquery(literal("zulip.english_us_search"), literal(operand))
        ts_locs_array = func.ts_match_locs_array
        query = query.column(ts_locs_array(literal("zulip.english_us_search"),
                                           column("rendered_content"),
                                           tsquery).label("content_matches"))
        # We HTML-escape the subject in Postgres to avoid doing a server round-trip
        query = query.column(ts_locs_array(literal("zulip.english_us_search"),
                                           func.escape_html(column("subject")),
                                           tsquery).label("subject_matches"))

        # Do quoted string matching.  We really want phrase
        # search here so we can ignore punctuation and do
        # stemming, but there isn't a standard phrase search
        # mechanism in Postgres
        for term in re.findall('"[^"]+"|\S+', operand):
            if term[0] == '"' and term[-1] == '"':
                term = term[1:-1]
                term = '%' + connection.ops.prep_for_like_query(term) + '%'
                cond = or_(column("content").ilike(term),
                           column("subject").ilike(term))
                query = query.where(maybe_negate(cond))

        cond = column("search_tsvector").op("@@")(tsquery)
        return query.where(maybe_negate(cond))

# The offsets we get from PGroonga are counted in characters
# whereas the offsets from tsearch_extras are in bytes, so we
# have to account for both cases in the logic below.
def highlight_string(text: Text, locs: Iterable[Tuple[int, int]]) -> Text:
    highlight_start = '<span class="highlight">'
    highlight_stop = '</span>'
    pos = 0
    result = ''
    in_tag = False

    text_utf8 = text.encode('utf8')

    for loc in locs:
        (offset, length) = loc

        # These indexes are in byte space for tsearch,
        # and they are in string space for pgroonga.
        prefix_start = pos
        prefix_end = offset
        match_start = offset
        match_end = offset + length

        if settings.USING_PGROONGA:
            prefix = text[prefix_start:prefix_end]
            match = text[match_start:match_end]
        else:
            prefix = text_utf8[prefix_start:prefix_end].decode()
            match = text_utf8[match_start:match_end].decode()

        for character in (prefix + match):
            if character == '<':
                in_tag = True
            elif character == '>':
                in_tag = False
        if in_tag:
            result += prefix
            result += match
        else:
            result += prefix
            result += highlight_start
            result += match
            result += highlight_stop
        pos = match_end

    if settings.USING_PGROONGA:
        final_frag = text[pos:]
    else:
        final_frag = text_utf8[pos:].decode()

    result += final_frag
    return result

def get_search_fields(rendered_content: Text, subject: Text, content_matches: Iterable[Tuple[int, int]],
                      subject_matches: Iterable[Tuple[int, int]]) -> Dict[str, Text]:
    return dict(match_content=highlight_string(rendered_content, content_matches),
                match_subject=highlight_string(escape_html(subject), subject_matches))

def narrow_parameter(json: str) -> Optional[List[Dict[str, Any]]]:

    data = ujson.loads(json)
    if not isinstance(data, list):
        raise ValueError("argument is not a list")
    if len(data) == 0:
        # The "empty narrow" should be None, and not []
        return None

    def convert_term(elem: Union[Dict[str, Any], List[str]]) -> Dict[str, Any]:

        # We have to support a legacy tuple format.
        if isinstance(elem, list):
            if (len(elem) != 2 or
                any(not isinstance(x, str) and not isinstance(x, Text)
                    for x in elem)):
                raise ValueError("element is not a string pair")
            return dict(operator=elem[0], operand=elem[1])

        if isinstance(elem, dict):
            validator = check_dict([
                ('operator', check_string),
                ('operand', check_string),
            ])

            error = validator('elem', elem)
            if error:
                raise JsonableError(error)

            # whitelist the fields we care about for now
            return dict(
                operator=elem['operator'],
                operand=elem['operand'],
                negated=elem.get('negated', False),
            )

        raise ValueError("element is not a dictionary")

    return list(map(convert_term, data))

def ok_to_include_history(narrow: Optional[Iterable[Dict[str, Any]]], user_profile: UserProfile) -> bool:
    # There are occasions where we need to find Message rows that
    # have no corresponding UserMessage row, because the user is
    # reading a public stream that might include messages that
    # were sent while the user was not subscribed, but which they are
    # allowed to see.  We have to be very careful about constructing
    # queries in those situations, so this function should return True
    # only if we are 100% sure that we're gonna add a clause to the
    # query that narrows to a particular public stream on the user's realm.
    # If we screw this up, then we can get into a nasty situation of
    # polluting our narrow results with messages from other realms.
    include_history = False
    if narrow is not None:
        for term in narrow:
            if term['operator'] == "stream" and not term.get('negated', False):
                if can_access_stream_history_by_name(user_profile, term['operand']):
                    include_history = True
        # Disable historical messages if the user is narrowing on anything
        # that's a property on the UserMessage table.  There cannot be
        # historical messages in these cases anyway.
        for term in narrow:
            if term['operator'] == "is":
                include_history = False

    return include_history

def get_stream_name_from_narrow(narrow: Optional[Iterable[Dict[str, Any]]]) -> Optional[Text]:
    if narrow is not None:
        for term in narrow:
            if term['operator'] == 'stream':
                return term['operand'].lower()
    return None

def exclude_muting_conditions(user_profile: UserProfile,
                              narrow: Optional[Iterable[Dict[str, Any]]]) -> List[Selectable]:
    conditions = []
    stream_name = get_stream_name_from_narrow(narrow)

    stream_id = None
    if stream_name is not None:
        try:
            # Note that this code works around a lint rule that
            # says we should use access_stream_by_name to get the
            # stream.  It is okay here, because we are only using
            # the stream id to exclude data, not to include results.
            stream_id = get_stream(stream_name, user_profile.realm).id
        except Stream.DoesNotExist:
            pass

    if stream_id is None:
        rows = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            in_home_view=False,
            recipient__type=Recipient.STREAM
        ).values('recipient_id')
        muted_recipient_ids = [row['recipient_id'] for row in rows]
        if len(muted_recipient_ids) > 0:
            # Only add the condition if we have muted streams to simplify/avoid warnings.
            condition = not_(column("recipient_id").in_(muted_recipient_ids))
            conditions.append(condition)

    conditions = exclude_topic_mutes(conditions, user_profile, stream_id)

    return conditions

def get_base_query_for_search(user_profile: UserProfile,
                              need_message: bool,
                              need_user_message: bool) -> Tuple[Query, ColumnElement]:
    if need_message and need_user_message:
        query = select([column("message_id"), column("flags")],
                       column("user_profile_id") == literal(user_profile.id),
                       join(table("zerver_usermessage"), table("zerver_message"),
                            literal_column("zerver_usermessage.message_id") ==
                            literal_column("zerver_message.id")))
        inner_msg_id_col = column("message_id")
        return (query, inner_msg_id_col)

    if need_user_message:
        query = select([column("message_id"), column("flags")],
                       column("user_profile_id") == literal(user_profile.id),
                       table("zerver_usermessage"))
        inner_msg_id_col = column("message_id")
        return (query, inner_msg_id_col)

    else:
        assert(need_message)
        query = select([column("id").label("message_id")],
                       None,
                       table("zerver_message"))
        inner_msg_id_col = literal_column("zerver_message.id")
        return (query, inner_msg_id_col)

def add_narrow_conditions(user_profile: UserProfile,
                          inner_msg_id_col: ColumnElement,
                          query: Query,
                          narrow: List[Dict[str, Any]]) -> Tuple[Query, bool]:
    first_visible_message_id = get_first_visible_message_id(user_profile.realm)
    if first_visible_message_id > 0:
        query = query.where(inner_msg_id_col >= first_visible_message_id)

    is_search = False  # for now

    if narrow is None:
        return (query, is_search)

    # Build the query for the narrow
    builder = NarrowBuilder(user_profile, inner_msg_id_col)
    search_operands = []

    # As we loop through terms, builder does most of the work to extend
    # our query, but we need to collect the search operands and handle
    # them after the loop.
    for term in narrow:
        if term['operator'] == 'search':
            search_operands.append(term['operand'])
        else:
            query = builder.add_term(query, term)

    if search_operands:
        is_search = True
        query = query.column(column("subject")).column(column("rendered_content"))
        search_term = dict(
            operator='search',
            operand=' '.join(search_operands)
        )
        query = builder.add_term(query, search_term)

    return (query, is_search)

def find_first_unread_anchor(sa_conn: Any,
                             user_profile: UserProfile,
                             narrow: List[Dict[str, Any]]) -> int:
    # We always need UserMessage in our query, because it has the unread
    # flag for the user.
    need_user_message = True

    # Because we will need to call exclude_muting_conditions, unless
    # the user hasn't muted anything, we will need to include Message
    # in our query.  It may be worth eventually adding an optimization
    # for the case of a user who hasn't muted anything to avoid the
    # join in that case, but it's low priority.
    need_message = True

    query, inner_msg_id_col = get_base_query_for_search(
        user_profile=user_profile,
        need_message=need_message,
        need_user_message=need_user_message,
    )

    query, is_search = add_narrow_conditions(
        user_profile=user_profile,
        inner_msg_id_col=inner_msg_id_col,
        query=query,
        narrow=narrow,
    )

    condition = column("flags").op("&")(UserMessage.flags.read.mask) == 0

    # We exclude messages on muted topics when finding the first unread
    # message in this narrow
    muting_conditions = exclude_muting_conditions(user_profile, narrow)
    if muting_conditions:
        condition = and_(condition, *muting_conditions)

    # The mobile app uses narrow=[] and use_first_unread_anchor=True to
    # determine what messages to show when you first load the app.
    # Unfortunately, this means that if you have a years-old unread
    # message, the mobile app could get stuck in the past.
    #
    # To fix this, we enforce that the "first unread anchor" must be on or
    # after the user's current pointer location. Since the pointer
    # location refers to the latest the user has read in the home view,
    # we'll only apply this logic in the home view (ie, when narrow is
    # empty).
    if not narrow:
        pointer_condition = inner_msg_id_col >= user_profile.pointer
        condition = and_(condition, pointer_condition)

    first_unread_query = query.where(condition)
    first_unread_query = first_unread_query.order_by(inner_msg_id_col.asc()).limit(1)
    first_unread_result = list(sa_conn.execute(first_unread_query).fetchall())
    if len(first_unread_result) > 0:
        anchor = first_unread_result[0][0]
    else:
        anchor = LARGER_THAN_MAX_MESSAGE_ID

    return anchor

@has_request_variables
def get_messages_backend(request: HttpRequest, user_profile: UserProfile,
                         anchor: int=REQ(converter=int),
                         num_before: int=REQ(converter=to_non_negative_int),
                         num_after: int=REQ(converter=to_non_negative_int),
                         narrow: Optional[List[Dict[str, Any]]]=REQ('narrow', converter=narrow_parameter,
                                                                    default=None),
                         use_first_unread_anchor: bool=REQ(validator=check_bool, default=False),
                         client_gravatar: bool=REQ(validator=check_bool, default=False),
                         apply_markdown: bool=REQ(validator=check_bool, default=True)) -> HttpResponse:
    include_history = ok_to_include_history(narrow, user_profile)

    if include_history:
        # The initial query in this case doesn't use `zerver_usermessage`,
        # and isn't yet limited to messages the user is entitled to see!
        #
        # This is OK only because we've made sure this is a narrow that
        # will cause us to limit the query appropriately later.
        # See `ok_to_include_history` for details.
        need_message = True
        need_user_message = False
    elif narrow is None:
        # We need to limit to messages the user has received, but we don't actually
        # need any fields from Message
        need_message = False
        need_user_message = True
    else:
        need_message = True
        need_user_message = True

    query, inner_msg_id_col = get_base_query_for_search(
        user_profile=user_profile,
        need_message=need_message,
        need_user_message=need_user_message,
    )

    query, is_search = add_narrow_conditions(
        user_profile=user_profile,
        inner_msg_id_col=inner_msg_id_col,
        query=query,
        narrow=narrow,
    )

    if narrow is not None:
        # Add some metadata to our logging data for narrows
        verbose_operators = []
        for term in narrow:
            if term['operator'] == "is":
                verbose_operators.append("is:" + term['operand'])
            else:
                verbose_operators.append(term['operator'])
        request._log_data['extra'] = "[%s]" % (",".join(verbose_operators),)

    sa_conn = get_sqlalchemy_connection()

    if use_first_unread_anchor:
        anchor = find_first_unread_anchor(
            sa_conn,
            user_profile,
            narrow,
        )

    anchored_to_left = (anchor == 0)

    # Set values that will be used to short circuit the after_query
    # altogether and avoid needless conditions in the before_query.
    anchored_to_right = (anchor == LARGER_THAN_MAX_MESSAGE_ID)
    if anchored_to_right:
        num_after = None

    query = limit_query_to_range(
        query=query,
        num_before=num_before,
        num_after=num_after,
        anchor=anchor,
        anchored_to_left=anchored_to_left,
        anchored_to_right=anchored_to_right,
        id_col=inner_msg_id_col,
    )

    main_query = alias(query)
    query = select(main_query.c, None, main_query).order_by(column("message_id").asc())
    # This is a hack to tag the query we use for testing
    query = query.prefix_with("/* get_messages */")
    rows = list(sa_conn.execute(query).fetchall())

    query_info = post_process_limited_query(
        rows=rows,
        num_before=num_before,
        num_after=num_after,
        anchor=anchor,
        anchored_to_left=anchored_to_left,
        anchored_to_right=anchored_to_right,
    )

    rows = query_info['rows']

    # The following is a little messy, but ensures that the code paths
    # are similar regardless of the value of include_history.  The
    # 'user_messages' dictionary maps each message to the user's
    # UserMessage object for that message, which we will attach to the
    # rendered message dict before returning it.  We attempt to
    # bulk-fetch rendered message dicts from remote cache using the
    # 'messages' list.
    message_ids = []  # type: List[int]
    user_message_flags = {}  # type: Dict[int, List[str]]
    if include_history:
        message_ids = [row[0] for row in rows]

        # TODO: This could be done with an outer join instead of two queries
        um_rows = UserMessage.objects.filter(user_profile=user_profile,
                                             message__id__in=message_ids)
        user_message_flags = {um.message_id: um.flags_list() for um in um_rows}

        for message_id in message_ids:
            if message_id not in user_message_flags:
                user_message_flags[message_id] = ["read", "historical"]
    else:
        for row in rows:
            message_id = row[0]
            flags = row[1]
            user_message_flags[message_id] = UserMessage.flags_list_for_flags(flags)
            message_ids.append(message_id)

    search_fields = dict()  # type: Dict[int, Dict[str, Text]]
    if is_search:
        for row in rows:
            message_id = row[0]
            (subject, rendered_content, content_matches, subject_matches) = row[-4:]

            try:
                search_fields[message_id] = get_search_fields(rendered_content, subject,
                                                              content_matches, subject_matches)
            except UnicodeDecodeError as err:  # nocoverage
                # No coverage for this block since it should be
                # impossible, and we plan to remove it once we've
                # debugged the case that makes it happen.
                raise Exception(str(err), message_id, narrow)

    message_list = messages_for_ids(
        message_ids=message_ids,
        user_message_flags=user_message_flags,
        search_fields=search_fields,
        apply_markdown=apply_markdown,
        client_gravatar=client_gravatar,
        allow_edit_history=user_profile.realm.allow_edit_history,
    )

    statsd.incr('loaded_old_messages', len(message_list))

    ret = dict(
        messages=message_list,
        result='success',
        msg='',
        found_anchor=query_info['found_anchor'],
        found_oldest=query_info['found_oldest'],
        found_newest=query_info['found_newest'],
        anchor=anchor,
    )
    return json_success(ret)

def limit_query_to_range(query: Query,
                         num_before: int,
                         num_after: int,
                         anchor: int,
                         anchored_to_left: bool,
                         anchored_to_right: bool,
                         id_col: ColumnElement) -> Query:
    '''
    This code is actually generic enough that we could move it to a
    library, but our only caller for now is message search.
    '''
    need_before_query = (not anchored_to_left) and (num_before > 0)
    need_after_query = (not anchored_to_right) and (num_after > 0)

    need_both_sides = need_before_query and need_after_query

    # The semantics of our flags are as follows:
    #
    # num_after = number of rows < anchor
    # num_after = number of rows > anchor
    #
    # But we also want the row where id == anchor (if it exists),
    # and we don't want to union up to 3 queries.  So in some cases
    # we do things like `after_limit = num_after + 1` to grab the
    # anchor row in the "after" query.
    #
    # Note that in some cases, if the anchor row isn't found, we
    # actually may fetch an extra row at one of the extremes.
    if need_both_sides:
        before_anchor = anchor - 1
        after_anchor = anchor
        before_limit = num_before
        after_limit = num_after + 1
    elif need_before_query:
        before_anchor = anchor
        before_limit = num_before
        if not anchored_to_right:
            before_limit += 1
    elif need_after_query:
        after_anchor = anchor
        after_limit = num_after + 1

    if need_before_query:
        before_query = query

        if not anchored_to_right:
            before_query = before_query.where(id_col <= before_anchor)

        before_query = before_query.order_by(id_col.desc())
        before_query = before_query.limit(before_limit)

    if need_after_query:
        after_query = query

        if not anchored_to_left:
            after_query = after_query.where(id_col >= after_anchor)

        after_query = after_query.order_by(id_col.asc())
        after_query = after_query.limit(after_limit)

    if need_both_sides:
        query = union_all(before_query.self_group(), after_query.self_group())
    elif need_before_query:
        query = before_query
    elif need_after_query:
        query = after_query
    else:
        # If we don't have either a before_query or after_query, it's because
        # some combination of num_before/num_after/anchor are zero or
        # use_first_unread_anchor logic found no unread messages.
        #
        # The most likely reason is somebody is doing an id search, so searching
        # for something like `message_id = 42` is exactly what we want.  In other
        # cases, which could possibly be buggy API clients, at least we will
        # return at most one row here.
        query = query.where(id_col == anchor)

    return query

def post_process_limited_query(rows: List[Any],
                               num_before: int,
                               num_after: int,
                               anchor: int,
                               anchored_to_left: bool,
                               anchored_to_right: bool) -> Dict[str, Any]:
    # Our queries may have fetched extra rows if they added
    # "headroom" to the limits, but we want to truncate those
    # rows.
    #
    # Also, in cases where we had non-zero values of num_before or
    # num_after, we want to know found_oldest and found_newest, so
    # that the clients will know that they got complete results.

    if anchored_to_right:
        num_after = 0
        before_rows = rows[:]
        anchor_rows = []  # type: List[Any]
        after_rows = []  # type: List[Any]
    else:
        before_rows = [r for r in rows if r[0] < anchor]
        anchor_rows = [r for r in rows if r[0] == anchor]
        after_rows = [r for r in rows if r[0] > anchor]

    if num_before:
        before_rows = before_rows[-1 * num_before:]

    if num_after:
        after_rows = after_rows[:num_after]

    rows = before_rows + anchor_rows + after_rows

    found_anchor = len(anchor_rows) == 1
    found_oldest = anchored_to_left or (len(before_rows) < num_before)
    found_newest = anchored_to_right or (len(after_rows) < num_after)

    return dict(
        rows=rows,
        found_anchor=found_anchor,
        found_newest=found_newest,
        found_oldest=found_oldest,
    )

@has_request_variables
def update_message_flags(request: HttpRequest, user_profile: UserProfile,
                         messages: List[int]=REQ(validator=check_list(check_int)),
                         operation: Text=REQ('op'), flag: Text=REQ()) -> HttpResponse:

    count = do_update_message_flags(user_profile, operation, flag, messages)

    target_count_str = str(len(messages))
    log_data_str = "[%s %s/%s] actually %s" % (operation, flag, target_count_str, count)
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'messages': messages,
                         'msg': ''})

@has_request_variables
def mark_all_as_read(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    count = do_mark_all_as_read(user_profile)

    log_data_str = "[%s updated]" % (count,)
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'msg': ''})

@has_request_variables
def mark_stream_as_read(request: HttpRequest,
                        user_profile: UserProfile,
                        stream_id: int=REQ(validator=check_int)) -> HttpResponse:
    stream, recipient, sub = access_stream_by_id(user_profile, stream_id)
    count = do_mark_stream_messages_as_read(user_profile, stream)

    log_data_str = "[%s updated]" % (count,)
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'msg': ''})

@has_request_variables
def mark_topic_as_read(request: HttpRequest,
                       user_profile: UserProfile,
                       stream_id: int=REQ(validator=check_int),
                       topic_name: Text=REQ()) -> HttpResponse:
    stream, recipient, sub = access_stream_by_id(user_profile, stream_id)

    if topic_name:
        topic_exists = UserMessage.objects.filter(user_profile=user_profile,
                                                  message__recipient=recipient,
                                                  message__subject__iexact=topic_name).exists()
        if not topic_exists:
            raise JsonableError(_('No such topic \'%s\'') % (topic_name,))

    count = do_mark_stream_messages_as_read(user_profile, stream, topic_name)

    log_data_str = "[%s updated]" % (count,)
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'msg': ''})

def create_mirrored_message_users(request: HttpRequest, user_profile: UserProfile,
                                  recipients: Iterable[Text]) -> Tuple[bool, Optional[UserProfile]]:
    if "sender" not in request.POST:
        return (False, None)

    sender_email = request.POST["sender"].strip().lower()
    referenced_users = set([sender_email])
    if request.POST['type'] == 'private':
        for email in recipients:
            referenced_users.add(email.lower())

    if request.client.name == "zephyr_mirror":
        user_check = same_realm_zephyr_user
        fullname_function = compute_mit_user_fullname
    elif request.client.name == "irc_mirror":
        user_check = same_realm_irc_user
        fullname_function = compute_irc_user_fullname
    elif request.client.name in ("jabber_mirror", "JabberMirror"):
        user_check = same_realm_jabber_user
        fullname_function = compute_jabber_user_fullname
    else:
        # Unrecognized mirroring client
        return (False, None)

    for email in referenced_users:
        # Check that all referenced users are in our realm:
        if not user_check(user_profile, email):
            return (False, None)

    # Create users for the referenced users, if needed.
    for email in referenced_users:
        create_mirror_user_if_needed(user_profile.realm, email, fullname_function)

    sender = get_user_including_cross_realm(sender_email, user_profile.realm)
    return (True, sender)

def same_realm_zephyr_user(user_profile: UserProfile, email: Text) -> bool:
    #
    # Are the sender and recipient both addresses in the same Zephyr
    # mirroring realm?  We have to handle this specially, inferring
    # the domain from the e-mail address, because the recipient may
    # not existing in Zulip and we may need to make a stub Zephyr
    # mirroring user on the fly.
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = email_to_domain(email)

    # Assumes allow_subdomains=False for all RealmDomain's corresponding to
    # these realms.
    return user_profile.realm.is_zephyr_mirror_realm and \
        RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists()

def same_realm_irc_user(user_profile: UserProfile, email: Text) -> bool:
    # Check whether the target email address is an IRC user in the
    # same realm as user_profile, i.e. if the domain were example.com,
    # the IRC user would need to be username@irc.example.com
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = email_to_domain(email).replace("irc.", "")

    # Assumes allow_subdomains=False for all RealmDomain's corresponding to
    # these realms.
    return RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists()

def same_realm_jabber_user(user_profile: UserProfile, email: Text) -> bool:
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    # If your Jabber users have a different email domain than the
    # Zulip users, this is where you would do any translation.
    domain = email_to_domain(email)

    # Assumes allow_subdomains=False for all RealmDomain's corresponding to
    # these realms.
    return RealmDomain.objects.filter(realm=user_profile.realm, domain=domain).exists()

def handle_deferred_message(sender: UserProfile, client: Client,
                            message_type_name: Text, message_to: Sequence[Text],
                            topic_name: Optional[Text],
                            message_content: Text, delivery_type: Text,
                            defer_until: Text, tz_guess: Text,
                            forwarder_user_profile: UserProfile,
                            realm: Optional[Realm]) -> HttpResponse:
    deliver_at = None
    local_tz = 'UTC'
    if tz_guess:
        local_tz = tz_guess
    elif sender.timezone:
        local_tz = sender.timezone
    try:
        deliver_at = dateparser(defer_until)
    except ValueError:
        return json_error(_("Invalid timestamp for scheduling message."))

    deliver_at_usertz = deliver_at
    if deliver_at_usertz.tzinfo is None:
        user_tz = get_timezone(local_tz)
        # Since mypy is not able to recognize localize and normalize as attributes of tzinfo we use ignore.
        deliver_at_usertz = user_tz.normalize(user_tz.localize(deliver_at))  # type: ignore # Reason in comment on previous line.
    deliver_at = convert_to_UTC(deliver_at_usertz)

    if deliver_at <= timezone_now():
        return json_error(_("Invalid timestamp for scheduling message. Choose a time in future."))

    check_schedule_message(sender, client, message_type_name, message_to,
                           topic_name, message_content, delivery_type,
                           deliver_at, realm=realm,
                           forwarder_user_profile=forwarder_user_profile)
    return json_success({"deliver_at": str(deliver_at_usertz)})

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
@has_request_variables
def send_message_backend(request: HttpRequest, user_profile: UserProfile,
                         message_type_name: Text=REQ('type'),
                         message_to: List[Text]=REQ('to', converter=extract_recipients, default=[]),
                         forged: bool=REQ(default=False),
                         topic_name: Optional[Text]= REQ('subject',
                                                         converter=lambda x: x.strip(), default=None),
                         message_content: Text=REQ('content'),
                         realm_str: Optional[Text]=REQ('realm_str', default=None),
                         local_id: Optional[Text]=REQ(default=None),
                         queue_id: Optional[Text]=REQ(default=None),
                         delivery_type: Optional[Text]=REQ('delivery_type', default='send_now'),
                         defer_until: Optional[Text]=REQ('deliver_at', default=None),
                         tz_guess: Optional[Text]=REQ('tz_guess', default=None)) -> HttpResponse:
    client = request.client
    is_super_user = request.user.is_api_super_user
    if forged and not is_super_user:
        return json_error(_("User not authorized for this query"))

    realm = None
    if realm_str and realm_str != user_profile.realm.string_id:
        if not is_super_user:
            # The email gateway bot needs to be able to send messages in
            # any realm.
            return json_error(_("User not authorized for this query"))
        realm = get_realm(realm_str)
        if not realm:
            return json_error(_("Unknown organization '%s'") % (realm_str,))

    if client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror", "JabberMirror"]:
        # Here's how security works for mirroring:
        #
        # For private messages, the message must be (1) both sent and
        # received exclusively by users in your realm, and (2)
        # received by the forwarding user.
        #
        # For stream messages, the message must be (1) being forwarded
        # by an API superuser for your realm and (2) being sent to a
        # mirrored stream.
        #
        # The security checks are split between the below code
        # (especially create_mirrored_message_users which checks the
        # same-realm constraint) and recipient_for_emails (which
        # checks that PMs are received by the forwarding user)
        if "sender" not in request.POST:
            return json_error(_("Missing sender"))
        if message_type_name != "private" and not is_super_user:
            return json_error(_("User not authorized for this query"))
        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user_profile, message_to)
        if not valid_input:
            return json_error(_("Invalid mirrored message"))
        if client.name == "zephyr_mirror" and not user_profile.realm.is_zephyr_mirror_realm:
            return json_error(_("Zephyr mirroring is not allowed in this organization"))
        sender = mirror_sender
    else:
        sender = user_profile

    if (delivery_type == 'send_later' or delivery_type == 'remind') and defer_until is None:
        return json_error(_("Missing deliver_at in a request for delayed message delivery"))

    if (delivery_type == 'send_later' or delivery_type == 'remind') and defer_until is not None:
        return handle_deferred_message(sender, client, message_type_name,
                                       message_to, topic_name, message_content,
                                       delivery_type, defer_until, tz_guess,
                                       forwarder_user_profile=user_profile,
                                       realm=realm)

    ret = check_send_message(sender, client, message_type_name, message_to,
                             topic_name, message_content, forged=forged,
                             forged_timestamp = request.POST.get('time'),
                             forwarder_user_profile=user_profile, realm=realm,
                             local_id=local_id, sender_queue_id=queue_id)
    return json_success({"id": ret})

def fill_edit_history_entries(message_history: List[Dict[str, Any]], message: Message) -> None:
    """This fills out the message edit history entries from the database,
    which are designed to have the minimum data possible, to instead
    have the current topic + content as of that time, plus data on
    whatever changed.  This makes it much simpler to do future
    processing.

    Note that this mutates what is passed to it, which is sorta a bad pattern.
    """
    prev_content = message.content
    prev_rendered_content = message.rendered_content
    prev_topic = message.subject
    assert(datetime_to_timestamp(message.last_edit_time) == message_history[0]['timestamp'])

    for entry in message_history:
        entry['topic'] = prev_topic
        if 'prev_subject' in entry:
            # We replace use of 'subject' with 'topic' for downstream simplicity
            prev_topic = entry['prev_subject']
            entry['prev_topic'] = prev_topic
            del entry['prev_subject']

        entry['content'] = prev_content
        entry['rendered_content'] = prev_rendered_content
        if 'prev_content' in entry:
            del entry['prev_rendered_content_version']
            prev_content = entry['prev_content']
            prev_rendered_content = entry['prev_rendered_content']
            entry['content_html_diff'] = highlight_html_differences(
                prev_rendered_content,
                entry['rendered_content'],
                message.id)

    message_history.append(dict(
        topic = prev_topic,
        content = prev_content,
        rendered_content = prev_rendered_content,
        timestamp = datetime_to_timestamp(message.pub_date),
        user_id = message.sender_id,
    ))

@has_request_variables
def get_message_edit_history(request: HttpRequest, user_profile: UserProfile,
                             message_id: int=REQ(converter=to_non_negative_int)) -> HttpResponse:
    if not user_profile.realm.allow_edit_history:
        return json_error(_("Message edit history is disabled in this organization"))
    message, ignored_user_message = access_message(user_profile, message_id)

    # Extract the message edit history from the message
    message_edit_history = ujson.loads(message.edit_history)

    # Fill in all the extra data that will make it usable
    fill_edit_history_entries(message_edit_history, message)
    return json_success({"message_history": reversed(message_edit_history)})

@has_request_variables
def update_message_backend(request: HttpRequest, user_profile: UserMessage,
                           message_id: int=REQ(converter=to_non_negative_int),
                           subject: Optional[Text]=REQ(default=None),
                           propagate_mode: Optional[str]=REQ(default="change_one"),
                           content: Optional[Text]=REQ(default=None)) -> HttpResponse:
    if not user_profile.realm.allow_message_editing:
        return json_error(_("Your organization has turned off message editing"))

    message, ignored_user_message = access_message(user_profile, message_id)

    # You only have permission to edit a message if:
    # you change this value also change those two parameters in message_edit.js.
    # 1. You sent it, OR:
    # 2. This is a topic-only edit for a (no topic) message, OR:
    # 3. This is a topic-only edit and you are an admin, OR:
    # 4. This is a topic-only edit and your realm allows users to edit topics.
    if message.sender == user_profile:
        pass
    elif (content is None) and ((message.topic_name() == "(no topic)") or
                                user_profile.is_realm_admin or
                                user_profile.realm.allow_community_topic_editing):
        pass
    else:
        raise JsonableError(_("You don't have permission to edit this message"))

    # If there is a change to the content, check that it hasn't been too long
    # Allow an extra 20 seconds since we potentially allow editing 15 seconds
    # past the limit, and in case there are network issues, etc. The 15 comes
    # from (min_seconds_to_edit + seconds_left_buffer) in message_edit.js; if
    # you change this value also change those two parameters in message_edit.js.
    edit_limit_buffer = 20
    if content is not None and user_profile.realm.message_content_edit_limit_seconds > 0:
        deadline_seconds = user_profile.realm.message_content_edit_limit_seconds + edit_limit_buffer
        if (timezone_now() - message.pub_date) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has past"))

    # If there is a change to the topic, check that the user is allowed to
    # edit it and that it has not been too long. If this is not the user who
    # sent the message, they are not the admin, and the time limit for editing
    # topics is passed, raise an error.
    if content is None and message.sender != user_profile and not user_profile.is_realm_admin:
        deadline_seconds = Realm.DEFAULT_COMMUNITY_TOPIC_EDITING_LIMIT_SECONDS + edit_limit_buffer
        if (timezone_now() - message.pub_date) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has past"))

    if subject is None and content is None:
        return json_error(_("Nothing to change"))
    if subject is not None:
        subject = subject.strip()
        if subject == "":
            raise JsonableError(_("Topic can't be empty"))
    rendered_content = None
    links_for_embed = set()  # type: Set[Text]
    prior_mention_user_ids = set()  # type: Set[int]
    mention_user_ids = set()  # type: Set[int]
    if content is not None:
        content = content.strip()
        if content == "":
            content = "(deleted)"
        content = truncate_body(content)

        user_info = get_user_info_for_message_updates(message.id)
        prior_mention_user_ids = user_info['mention_user_ids']

        # We render the message using the current user's realm; since
        # the cross-realm bots never edit messages, this should be
        # always correct.
        # Note: If rendering fails, the called code will raise a JsonableError.
        rendered_content = render_incoming_message(message,
                                                   content,
                                                   user_info['message_user_ids'],
                                                   user_profile.realm)
        links_for_embed |= message.links_for_preview

        mention_user_ids = message.mentions_user_ids

    number_changed = do_update_message(user_profile, message, subject,
                                       propagate_mode, content, rendered_content,
                                       prior_mention_user_ids,
                                       mention_user_ids)

    # Include the number of messages changed in the logs
    request._log_data['extra'] = "[%s]" % (number_changed,)
    if links_for_embed and bugdown.url_embed_preview_enabled_for_realm(message):
        event_data = {
            'message_id': message.id,
            'message_content': message.content,
            # The choice of `user_profile.realm_id` rather than
            # `sender.realm_id` must match the decision made in the
            # `render_incoming_message` call earlier in this function.
            'message_realm_id': user_profile.realm_id,
            'urls': links_for_embed}
        queue_json_publish('embed_links', event_data)
    return json_success()


@has_request_variables
def delete_message_backend(request: HttpRequest, user_profile: UserProfile,
                           message_id: int=REQ(converter=to_non_negative_int)) -> HttpResponse:
    message, ignored_user_message = access_message(user_profile, message_id)
    is_user_allowed_to_delete_message = user_profile.is_realm_admin or \
        (message.sender == user_profile and user_profile.realm.allow_message_deleting)
    if not is_user_allowed_to_delete_message:
        raise JsonableError(_("You don't have permission to edit this message"))
    do_delete_message(user_profile, message)
    return json_success()

@has_request_variables
def json_fetch_raw_message(request: HttpRequest, user_profile: UserProfile,
                           message_id: int=REQ(converter=to_non_negative_int)) -> HttpResponse:
    (message, user_message) = access_message(user_profile, message_id)
    return json_success({"raw_content": message.content})

@has_request_variables
def render_message_backend(request: HttpRequest, user_profile: UserProfile,
                           content: Text=REQ()) -> HttpResponse:
    message = Message()
    message.sender = user_profile
    message.content = content
    message.sending_client = request.client

    rendered_content = render_markdown(message, content, realm=user_profile.realm)
    return json_success({"rendered": rendered_content})

@has_request_variables
def messages_in_narrow_backend(request: HttpRequest, user_profile: UserProfile,
                               msg_ids: List[int]=REQ(validator=check_list(check_int)),
                               narrow: Optional[List[Dict[str, Any]]]=REQ(converter=narrow_parameter)
                               ) -> HttpResponse:

    first_visible_message_id = get_first_visible_message_id(user_profile.realm)
    msg_ids = [message_id for message_id in msg_ids if message_id >= first_visible_message_id]
    # This query is limited to messages the user has access to because they
    # actually received them, as reflected in `zerver_usermessage`.
    query = select([column("message_id"), column("subject"), column("rendered_content")],
                   and_(column("user_profile_id") == literal(user_profile.id),
                        column("message_id").in_(msg_ids)),
                   join(table("zerver_usermessage"), table("zerver_message"),
                        literal_column("zerver_usermessage.message_id") ==
                        literal_column("zerver_message.id")))

    builder = NarrowBuilder(user_profile, column("message_id"))
    if narrow is not None:
        for term in narrow:
            query = builder.add_term(query, term)

    sa_conn = get_sqlalchemy_connection()
    query_result = list(sa_conn.execute(query).fetchall())

    search_fields = dict()
    for row in query_result:
        message_id = row['message_id']
        subject = row['subject']
        rendered_content = row['rendered_content']

        if 'content_matches' in row:
            content_matches = row['content_matches']
            subject_matches = row['subject_matches']
            search_fields[message_id] = get_search_fields(rendered_content, subject,
                                                          content_matches, subject_matches)
        else:
            search_fields[message_id] = dict(
                match_content=rendered_content,
                match_subject=subject
            )

    return json_success({"messages": search_fields})
