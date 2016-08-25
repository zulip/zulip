from __future__ import absolute_import

from django.utils.translation import ugettext as _
from django.utils.timezone import now
from django.conf import settings
from django.core import validators
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Any, AnyStr, Iterable, Optional, Tuple
from zerver.lib.str_utils import force_text

from zerver.decorator import authenticated_api_view, authenticated_json_post_view, \
    has_request_variables, REQ, JsonableError, \
    to_non_negative_int
from django.utils.html import escape as escape_html
from zerver.lib import bugdown
from zerver.lib.actions import recipient_for_emails, do_update_message_flags, \
    compute_mit_user_fullname, compute_irc_user_fullname, compute_jabber_user_fullname, \
    create_mirror_user_if_needed, check_send_message, do_update_message, \
    extract_recipients, truncate_body
from zerver.lib.cache import generic_bulk_cached_fetch
from zerver.lib.response import json_success, json_error
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.utils import statsd
from zerver.lib.validator import \
    check_list, check_int, check_dict, check_string, check_bool
from zerver.models import Message, UserProfile, Stream, Subscription, \
    Realm, Recipient, UserMessage, bulk_get_recipients, get_recipient, \
    get_user_profile_by_email, get_stream, \
    parse_usermessage_flags, to_dict_cache_key_id, extract_message_dict, \
    stringify_message_dict, \
    resolve_email_to_domain, get_realm, get_active_streams, \
    bulk_get_streams

from sqlalchemy import func
from sqlalchemy.sql import select, join, column, literal_column, literal, and_, \
    or_, not_, union_all, alias, Selectable

import re
import ujson
import datetime

from six.moves import map
import six

class BadNarrowOperator(JsonableError):
    def __init__(self, desc, status_code=400):
        self.desc = desc
        self.status_code = status_code

    def to_json_error_msg(self):
        return _('Invalid narrow operator: {}').format(self.desc)

# When you add a new operator to this, also update zerver/lib/narrow.py
class NarrowBuilder(object):
    def __init__(self, user_profile, msg_id_column):
        # type: (UserProfile, str) -> None
        self.user_profile = user_profile
        self.msg_id_column = msg_id_column

    def add_term(self, query, term):
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

    def by_has(self, query, operand, maybe_negate):
        if operand not in ['attachment', 'image', 'link']:
            raise BadNarrowOperator("unknown 'has' operand " + operand)
        col_name = 'has_' + operand
        cond = column(col_name)
        return query.where(maybe_negate(cond))

    def by_in(self, query, operand, maybe_negate):
        if operand == 'home':
            conditions = exclude_muting_conditions(self.user_profile, [])
            return query.where(and_(*conditions))
        elif operand == 'all':
            return query

        raise BadNarrowOperator("unknown 'in' operand " + operand)

    def by_is(self, query, operand, maybe_negate):
        if operand == 'private':
            query = query.select_from(join(query.froms[0], "zerver_recipient",
                                           column("recipient_id") ==
                                           literal_column("zerver_recipient.id")))
            cond = or_(column("type") == Recipient.PERSONAL,
                       column("type") == Recipient.HUDDLE)
            return query.where(maybe_negate(cond))
        elif operand == 'starred':
            cond = column("flags").op("&")(UserMessage.flags.starred.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == 'mentioned' or operand == 'alerted':
            cond = column("flags").op("&")(UserMessage.flags.mentioned.mask) != 0
            return query.where(maybe_negate(cond))
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    _alphanum = frozenset(
        'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')

    def _pg_re_escape(self, pattern):
        """
        Escape user input to place in a regex

        Python's re.escape escapes unicode characters in a way which postgres
        fails on, u'\u03bb' to u'\\\u03bb'. This function will correctly escape
        them for postgres, u'\u03bb' to u'\\u03bb'.
        """
        s = list(pattern)
        for i, c in enumerate(s):
            if c not in self._alphanum:
                if c == '\000':
                    s[1] = '\\000'
                elif ord(c) >= 128:
                    # convert the character to hex postgres regex will take
                    # \uXXXX
                    s[i] = '\\u{:0>4x}'.format(ord(c))
                else:
                    s[i] = '\\' + c
        return ''.join(s)

    def by_stream(self, query, operand, maybe_negate):
        stream = get_stream(operand, self.user_profile.realm)
        if stream is None:
            raise BadNarrowOperator('unknown stream ' + operand)

        if self.user_profile.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to "social" to also show messages to /^(un)*social(.d)*$/
            # (unsocial, ununsocial, social.d, etc)
            m = re.search(r'^(?:un)*(.+?)(?:\.d)*$', stream.name, re.IGNORECASE)
            if m:
                base_stream_name = m.group(1)
            else:
                base_stream_name = stream.name

            matching_streams = get_active_streams(self.user_profile.realm).filter(
                name__iregex=r'^(un)*%s(\.d)*$' % (self._pg_re_escape(base_stream_name),))
            matching_stream_ids = [matching_stream.id for matching_stream in matching_streams]
            recipients_map = bulk_get_recipients(Recipient.STREAM, matching_stream_ids)
            cond = column("recipient_id").in_([recipient.id for recipient in recipients_map.values()])
            return query.where(maybe_negate(cond))

        recipient = get_recipient(Recipient.STREAM, type_id=stream.id)
        cond = column("recipient_id") == recipient.id
        return query.where(maybe_negate(cond))

    def by_topic(self, query, operand, maybe_negate):
        if self.user_profile.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
            # (foo, foo.d, foo.d.d, etc)
            m = re.search(r'^(.*?)(?:\.d)*$', operand, re.IGNORECASE)
            if m:
                base_topic = m.group(1)
            else:
                base_topic = operand

            # Additionally, MIT users expect the empty instance and
            # instance "personal" to be the same.
            if base_topic in ('', 'personal', '(instance "")'):
                regex = r'^(|personal|\(instance ""\))(\.d)*$'
            else:
                regex = r'^%s(\.d)*$' % (self._pg_re_escape(base_topic),)

            cond = column("subject").op("~*")(regex)
            return query.where(maybe_negate(cond))

        cond = func.upper(column("subject")) == func.upper(literal(operand))
        return query.where(maybe_negate(cond))

    def by_sender(self, query, operand, maybe_negate):
        try:
            sender = get_user_profile_by_email(operand)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator('unknown user ' + operand)

        cond = column("sender_id") == literal(sender.id)
        return query.where(maybe_negate(cond))

    def by_near(self, query, operand, maybe_negate):
        return query

    def by_id(self, query, operand, maybe_negate):
        cond = self.msg_id_column == literal(operand)
        return query.where(maybe_negate(cond))

    def by_pm_with(self, query, operand, maybe_negate):
        if ',' in operand:
            # Huddle
            try:
                emails = [e.strip() for e in operand.split(',')]
                recipient = recipient_for_emails(emails, False,
                    self.user_profile, self.user_profile)
            except ValidationError:
                raise BadNarrowOperator('unknown recipient ' + operand)
            cond = column("recipient_id") == recipient.id
            return query.where(maybe_negate(cond))
        else:
            # Personal message
            self_recipient = get_recipient(Recipient.PERSONAL, type_id=self.user_profile.id)
            if operand == self.user_profile.email:
                # Personals with self
                cond = and_(column("sender_id") == self.user_profile.id,
                            column("recipient_id") == self_recipient.id)
                return query.where(maybe_negate(cond))

            # Personals with other user; include both directions.
            try:
                narrow_profile = get_user_profile_by_email(operand)
            except UserProfile.DoesNotExist:
                raise BadNarrowOperator('unknown user ' + operand)

            narrow_recipient = get_recipient(Recipient.PERSONAL, narrow_profile.id)
            cond = or_(and_(column("sender_id") == narrow_profile.id,
                            column("recipient_id") == self_recipient.id),
                       and_(column("sender_id") == self.user_profile.id,
                            column("recipient_id") == narrow_recipient.id))
            return query.where(maybe_negate(cond))

    def by_search(self, query, operand, maybe_negate):
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

# Apparently, the offsets we get from tsearch_extras are counted in
# unicode characters, not in bytes, so we do our processing with text,
# not bytes.
def highlight_string(text, locs):
    # type: (AnyStr, Iterable[Tuple[int, int]]) -> text_type
    string = force_text(text)
    highlight_start = u'<span class="highlight">'
    highlight_stop = u'</span>'
    pos = 0
    result = u''
    for loc in locs:
        (offset, length) = loc
        result += string[pos:offset]
        result += highlight_start
        result += string[offset:offset + length]
        result += highlight_stop
        pos = offset + length
    result += string[pos:]
    return result

def get_search_fields(rendered_content, subject, content_matches, subject_matches):
    # type: (text_type, text_type, Iterable[Tuple[int, int]], Iterable[Tuple[int, int]]) -> Dict[str, text_type]
    return dict(match_content=highlight_string(rendered_content, content_matches),
                match_subject=highlight_string(escape_html(subject), subject_matches))

def narrow_parameter(json):
    # type: (str) -> List[Dict[str, Any]]

    # FIXME: A hack to support old mobile clients
    if json == '{}':
        return None

    data = ujson.loads(json)
    if not isinstance(data, list):
        raise ValueError("argument is not a list")

    def convert_term(elem):
        # We have to support a legacy tuple format.
        if isinstance(elem, list):
            if (len(elem) != 2
                or any(not isinstance(x, str) and not isinstance(x, six.text_type)
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

def is_public_stream(stream_name, realm):
    # type: (text_type, Realm) -> bool
    """
    Determine whether a stream is public, so that
    our caller can decide whether we can get
    historical messages for a narrowing search.

    Because of the way our search is currently structured,
    we may be passed an invalid stream here.  We return
    False in that situation, and subsequent code will do
    validation and raise the appropriate JsonableError.
    """
    stream = get_stream(stream_name, realm)
    if stream is None:
        return False
    return stream.is_public()


def ok_to_include_history(narrow, realm):
    # type: (Iterable[Dict[str, Any]], Realm) -> bool

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
                if is_public_stream(term['operand'], realm):
                    include_history = True
        # Disable historical messages if the user is narrowing on anything
        # that's a property on the UserMessage table.  There cannot be
        # historical messages in these cases anyway.
        for term in narrow:
            if term['operator'] == "is":
                include_history = False

    return include_history

def get_stream_name_from_narrow(narrow):
    # type: (Iterable[Dict[str, Any]]) -> Optional[text_type]
    for term in narrow:
        if term['operator'] == 'stream':
            return term['operand'].lower()
    return None

def exclude_muting_conditions(user_profile, narrow):
    # type: (UserProfile, Iterable[Dict[str, Any]]) -> List[Selectable]
    conditions = []
    stream_name = get_stream_name_from_narrow(narrow)

    if stream_name is None:
        rows = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            in_home_view=False,
            recipient__type=Recipient.STREAM
        ).values('recipient_id')
        muted_recipient_ids = [row['recipient_id'] for row in rows]
        condition = not_(column("recipient_id").in_(muted_recipient_ids))
        conditions.append(condition)

    muted_topics = ujson.loads(user_profile.muted_topics)
    if muted_topics:
        if stream_name is not None:
            muted_topics = [m for m in muted_topics if m[0].lower() == stream_name]
            if not muted_topics:
                return conditions

        muted_streams = bulk_get_streams(user_profile.realm,
                                         [muted[0] for muted in muted_topics])
        muted_recipients = bulk_get_recipients(Recipient.STREAM,
                                               [stream.id for stream in six.itervalues(muted_streams)])
        recipient_map = dict((s.name.lower(), muted_recipients[s.id].id)
                             for s in six.itervalues(muted_streams))

        muted_topics = [m for m in muted_topics if m[0].lower() in recipient_map]

        if muted_topics:
            def mute_cond(muted):
                stream_cond = column("recipient_id") == recipient_map[muted[0].lower()]
                topic_cond = func.upper(column("subject")) == func.upper(muted[1])
                return and_(stream_cond, topic_cond)

            condition = not_(or_(*list(map(mute_cond, muted_topics))))
            return conditions + [condition]

    return conditions

@has_request_variables
def get_old_messages_backend(request, user_profile,
                             anchor = REQ(converter=int),
                             num_before = REQ(converter=to_non_negative_int),
                             num_after = REQ(converter=to_non_negative_int),
                             narrow = REQ('narrow', converter=narrow_parameter, default=None),
                             use_first_unread_anchor = REQ(default=False, converter=ujson.loads),
                             apply_markdown=REQ(default=True,
                                                converter=ujson.loads)):
    # type: (HttpRequest, UserProfile, int, int, int, Optional[List[Dict[str, Any]]], bool, bool) -> HttpResponse
    include_history = ok_to_include_history(narrow, user_profile.realm)

    if include_history and not use_first_unread_anchor:
        query = select([column("id").label("message_id")], None, "zerver_message")
        inner_msg_id_col = literal_column("zerver_message.id")
    elif narrow is None:
        query = select([column("message_id"), column("flags")],
                       column("user_profile_id") == literal(user_profile.id),
                       "zerver_usermessage")
        inner_msg_id_col = column("message_id")
    else:
        # TODO: Don't do this join if we're not doing a search
        query = select([column("message_id"), column("flags")],
                       column("user_profile_id") == literal(user_profile.id),
                       join("zerver_usermessage", "zerver_message",
                            literal_column("zerver_usermessage.message_id") ==
                            literal_column("zerver_message.id")))
        inner_msg_id_col = column("message_id")

    num_extra_messages = 1
    is_search = False

    if narrow is not None:
        # Add some metadata to our logging data for narrows
        verbose_operators = []
        for term in narrow:
            if term['operator'] == "is":
                verbose_operators.append("is:" + term['operand'])
            else:
                verbose_operators.append(term['operator'])
        request._log_data['extra'] = "[%s]" % (",".join(verbose_operators),)

        # Build the query for the narrow
        num_extra_messages = 0
        builder = NarrowBuilder(user_profile, inner_msg_id_col)
        for term in narrow:
            if term['operator'] == 'search' and not is_search:
                query = query.column("subject").column("rendered_content")
                is_search = True
            query = builder.add_term(query, term)

    # We add 1 to the number of messages requested if no narrow was
    # specified to ensure that the resulting list always contains the
    # anchor message.  If a narrow was specified, the anchor message
    # might not match the narrow anyway.
    if num_after != 0:
        num_after += num_extra_messages
    else:
        num_before += num_extra_messages

    sa_conn = get_sqlalchemy_connection()
    if use_first_unread_anchor:
        condition = column("flags").op("&")(UserMessage.flags.read.mask) == 0

        # We exclude messages on muted topics when finding the first unread
        # message in this narrow
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        if muting_conditions:
            condition = and_(condition, *muting_conditions)

        first_unread_query = query.where(condition)
        first_unread_query = first_unread_query.order_by(inner_msg_id_col.asc()).limit(1)
        first_unread_result = list(sa_conn.execute(first_unread_query).fetchall())
        if len(first_unread_result) > 0:
            anchor = first_unread_result[0][0]
        else:
            anchor = 10000000000000000

    before_query = None
    after_query = None
    if num_before != 0:
        before_anchor = anchor
        if num_after != 0:
            # Don't include the anchor in both the before query and the after query
            before_anchor = anchor - 1
        before_query = query.where(inner_msg_id_col <= before_anchor) \
                            .order_by(inner_msg_id_col.desc()).limit(num_before)
    if num_after != 0:
        after_query = query.where(inner_msg_id_col >= anchor) \
                           .order_by(inner_msg_id_col.asc()).limit(num_after)

    if num_before == 0 and num_after == 0:
        # This can happen when a narrow is specified.
        after_query = query.where(inner_msg_id_col == anchor)

    if before_query is not None:
        if after_query is not None:
            query = union_all(before_query.self_group(), after_query.self_group())
        else:
            query = before_query
    else:
        query = after_query
    main_query = alias(query)
    query = select(main_query.c, None, main_query).order_by(column("message_id").asc())
    # This is a hack to tag the query we use for testing
    query = query.prefix_with("/* get_old_messages */")
    query_result = list(sa_conn.execute(query).fetchall())

    # The following is a little messy, but ensures that the code paths
    # are similar regardless of the value of include_history.  The
    # 'user_messages' dictionary maps each message to the user's
    # UserMessage object for that message, which we will attach to the
    # rendered message dict before returning it.  We attempt to
    # bulk-fetch rendered message dicts from remote cache using the
    # 'messages' list.
    search_fields = dict() # type: Dict[int, Dict[str, text_type]]
    message_ids = [] # type: List[int]
    user_message_flags = {} # type: Dict[int, List[str]]
    if include_history:
        message_ids = [row[0] for row in query_result]

        # TODO: This could be done with an outer join instead of two queries
        user_message_flags = dict((user_message.message_id, user_message.flags_list()) for user_message in
                                  UserMessage.objects.filter(user_profile=user_profile,
                                                             message__id__in=message_ids))
        for row in query_result:
            message_id = row[0]
            if user_message_flags.get(message_id) is None:
                user_message_flags[message_id] = ["read", "historical"]
            if is_search:
                (_, subject, rendered_content, content_matches, subject_matches) = row
                search_fields[message_id] = get_search_fields(rendered_content, subject,
                                                              content_matches, subject_matches)
    else:
        for row in query_result:
            message_id = row[0]
            flags = row[1]
            user_message_flags[message_id] = parse_usermessage_flags(flags)

            message_ids.append(message_id)

            if is_search:
                (_, _, subject, rendered_content, content_matches, subject_matches) = row
                search_fields[message_id] = get_search_fields(rendered_content, subject,
                                                              content_matches, subject_matches)

    cache_transformer = lambda row: Message.build_dict_from_raw_db_row(row, apply_markdown)
    id_fetcher = lambda row: row['id']

    message_dicts = generic_bulk_cached_fetch(lambda message_id: to_dict_cache_key_id(message_id, apply_markdown),
                                              Message.get_raw_db_rows,
                                              message_ids,
                                              id_fetcher=id_fetcher,
                                              cache_transformer=cache_transformer,
                                              extractor=extract_message_dict,
                                              setter=stringify_message_dict)

    message_list = []
    for message_id in message_ids:
        msg_dict = message_dicts[message_id]
        msg_dict.update({"flags": user_message_flags[message_id]})
        msg_dict.update(search_fields.get(message_id, {}))
        message_list.append(msg_dict)

    statsd.incr('loaded_old_messages', len(message_list))
    ret = {'messages': message_list,
           "result": "success",
           "msg": ""}
    return json_success(ret)

@has_request_variables
def update_message_flags(request, user_profile,
                         messages=REQ(validator=check_list(check_int)),
                         operation=REQ('op'), flag=REQ(),
                         all=REQ(validator=check_bool, default=False),
                         stream_name=REQ(default=None),
                         topic_name=REQ(default=None)):
    # type: (HttpRequest, UserProfile, List[int], text_type, text_type, bool, Optional[text_type], Optional[text_type]) -> HttpResponse
    if all:
        target_count_str = "all"
    else:
        target_count_str = str(len(messages))
    log_data_str = "[%s %s/%s]" % (operation, flag, target_count_str)
    request._log_data["extra"] = log_data_str
    stream = None
    if stream_name is not None:
        stream = get_stream(stream_name, user_profile.realm)
        if not stream:
            raise JsonableError(_('No such stream \'%s\'') % (stream_name,))
        if topic_name:
            topic_exists = UserMessage.objects.filter(user_profile=user_profile,
                                                      message__recipient__type_id=stream.id,
                                                      message__recipient__type=Recipient.STREAM,
                                                      message__subject__iexact=topic_name).exists()
            if not topic_exists:
                raise JsonableError(_('No such topic \'%s\'') % (topic_name,))
    count = do_update_message_flags(user_profile, operation, flag, messages,
                                    all, stream, topic_name)

    # If we succeed, update log data str with the actual count for how
    # many messages were updated.
    if count != len(messages):
        log_data_str = "[%s %s/%s] actually %s" % (operation, flag, target_count_str, count)
    request._log_data["extra"] = log_data_str

    return json_success({'result': 'success',
                         'messages': messages,
                         'msg': ''})

def create_mirrored_message_users(request, user_profile, recipients):
    # type: (HttpResponse, UserProfile, Iterable[text_type]) -> Tuple[bool, UserProfile]
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

    sender = get_user_profile_by_email(sender_email)
    return (True, sender)

def same_realm_zephyr_user(user_profile, email):
    # type: (UserProfile, text_type) -> bool
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

    domain = resolve_email_to_domain(email)

    return user_profile.realm.domain == domain and user_profile.realm.is_zephyr_mirror_realm

def same_realm_irc_user(user_profile, email):
    # type: (UserProfile, text_type) -> bool
    # Check whether the target email address is an IRC user in the
    # same realm as user_profile, i.e. if the domain were example.com,
    # the IRC user would need to be username@irc.example.com
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = resolve_email_to_domain(email)

    return user_profile.realm.domain == domain.replace("irc.", "")

def same_realm_jabber_user(user_profile, email):
    # type: (UserProfile, text_type) -> bool
    try:
        validators.validate_email(email)
    except ValidationError:
        return False

    domain = resolve_email_to_domain(email)
    # The ist.mit.edu realm uses mit.edu email addresses so that their accounts
    # can receive mail.
    if user_profile.realm.domain == 'ist.mit.edu' and domain == 'mit.edu':
        return True

    return user_profile.realm.domain == domain


@authenticated_api_view(is_webhook=False)
def api_send_message(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return send_message_backend(request, user_profile)

# We do not @require_login for send_message_backend, since it is used
# both from the API and the web service.  Code calling
# send_message_backend should either check the API key or check that
# the user is logged in.
@has_request_variables
def send_message_backend(request, user_profile,
                         message_type_name = REQ('type'),
                         message_to = REQ('to', converter=extract_recipients, default=[]),
                         forged = REQ(default=False),
                         subject_name = REQ('subject', lambda x: x.strip(), None),
                         message_content = REQ('content'),
                         domain = REQ('domain', default=None),
                         local_id = REQ(default=None),
                         queue_id = REQ(default=None)):
    # type: (HttpRequest, UserProfile, text_type, List[text_type], bool, Optional[text_type], text_type, Optional[text_type], Optional[text_type], Optional[text_type]) -> HttpResponse
    client = request.client
    is_super_user = request.user.is_api_super_user
    if forged and not is_super_user:
        return json_error(_("User not authorized for this query"))

    realm = None
    if domain and domain != user_profile.realm.domain:
        if not is_super_user:
            # The email gateway bot needs to be able to send messages in
            # any realm.
            return json_error(_("User not authorized for this query"))
        realm = get_realm(domain)
        if not realm:
            return json_error(_("Unknown domain %s") % (domain,))

    if client.name in ["zephyr_mirror", "irc_mirror", "jabber_mirror", "JabberMirror"]:
        # Here's how security works for mirroring:
        #
        # For private messages, the message must be (1) both sent and
        # received exclusively by users in your realm, and (2)
        # received by the forwarding user.
        #
        # For stream messages, the message must be (1) being forwarded
        # by an API superuser for your realm and (2) being sent to a
        # mirrored stream (any stream for the Zephyr and Jabber
        # mirrors, but only streams with names starting with a "#" for
        # IRC mirrors)
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
            return json_error(_("Invalid mirrored realm"))
        if (client.name == "irc_mirror" and message_type_name != "private" and
            not message_to[0].startswith("#")):
            return json_error(_("IRC stream names must start with #"))
        sender = mirror_sender
    else:
        sender = user_profile

    ret = check_send_message(sender, client, message_type_name, message_to,
                             subject_name, message_content, forged=forged,
                             forged_timestamp = request.POST.get('time'),
                             forwarder_user_profile=user_profile, realm=realm,
                             local_id=local_id, sender_queue_id=queue_id)
    return json_success({"id": ret})

@authenticated_json_post_view
def json_update_message(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return update_message_backend(request, user_profile)

@has_request_variables
def update_message_backend(request, user_profile,
                           message_id=REQ(converter=to_non_negative_int),
                           subject=REQ(default=None),
                           propagate_mode=REQ(default="change_one"),
                           content=REQ(default=None)):
    # type: (HttpRequest, UserProfile, int, Optional[text_type], Optional[str], Optional[text_type]) -> HttpResponse
    if not user_profile.realm.allow_message_editing:
        return json_error(_("Your organization has turned off message editing."))

    try:
        message = Message.objects.select_related().get(id=message_id)
    except Message.DoesNotExist:
        raise JsonableError(_("Unknown message id"))

    # You only have permission to edit a message if:
    # 1. You sent it, OR:
    # 2. This is a topic-only edit for a (no topic) message, OR:
    # 3. This is a topic-only edit and you are an admin.
    if message.sender == user_profile:
        pass
    elif (content is None) and ((message.topic_name() == "(no topic)") or
                                user_profile.is_realm_admin):
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
        if (now() - message.pub_date) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has past"))

    if subject is None and content is None:
        return json_error(_("Nothing to change"))
    if subject is not None:
        subject = subject.strip()
        if subject == "":
            raise JsonableError(_("Topic can't be empty"))
    rendered_content = None
    if content is not None:
        content = content.strip()
        if content == "":
            raise JsonableError(_("Content can't be empty"))
        content = truncate_body(content)
        rendered_content = message.render_markdown(content)
        if not rendered_content:
            raise JsonableError(_("We were unable to render your updated message"))

    do_update_message(user_profile, message, subject, propagate_mode, content, rendered_content)
    return json_success()

@authenticated_json_post_view
@has_request_variables
def json_fetch_raw_message(request, user_profile,
                           message_id=REQ(converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, int) -> HttpResponse
    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        return json_error(_("No such message"))

    if message.sender != user_profile:
        return json_error(_("Message was not sent by you"))

    return json_success({"raw_content": message.content})

@has_request_variables
def render_message_backend(request, user_profile, content=REQ()):
    # type: (HttpRequest, UserProfile, text_type) -> HttpResponse
    rendered_content = bugdown.convert(content, user_profile.realm.domain)
    return json_success({"rendered": rendered_content})

@authenticated_json_post_view
def json_messages_in_narrow(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return messages_in_narrow_backend(request, user_profile)

@has_request_variables
def messages_in_narrow_backend(request, user_profile,
                               msg_ids = REQ(validator=check_list(check_int)),
                               narrow = REQ(converter=narrow_parameter)):
    # type: (HttpRequest, UserProfile, List[int], List[Dict[str, Any]]) -> HttpResponse

    # Note that this function will only work on messages the user
    # actually received

    # TODO: We assume that the narrow is a search.  For now this works because
    # the browser only ever calls this function for searches, since it can't
    # apply that narrow operator itself.

    query = select([column("message_id"), column("subject"), column("rendered_content")],
                   and_(column("user_profile_id") == literal(user_profile.id),
                        column("message_id").in_(msg_ids)),
                   join("zerver_usermessage", "zerver_message",
                        literal_column("zerver_usermessage.message_id") ==
                        literal_column("zerver_message.id")))

    builder = NarrowBuilder(user_profile, column("message_id"))
    for term in narrow:
        query = builder.add_term(query, term)

    sa_conn = get_sqlalchemy_connection()
    query_result = list(sa_conn.execute(query).fetchall())

    search_fields = dict()
    for row in query_result:
        (message_id, subject, rendered_content, content_matches, subject_matches) = row
        search_fields[message_id] = get_search_fields(rendered_content, subject,
                                                      content_matches, subject_matches)

    return json_success({"messages": search_fields})
