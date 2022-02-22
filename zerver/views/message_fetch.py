import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import orjson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.utils.html import escape as escape_html
from django.utils.translation import gettext as _
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Row
from sqlalchemy.sql import (
    ClauseElement,
    ColumnElement,
    Select,
    and_,
    column,
    func,
    join,
    literal,
    literal_column,
    not_,
    or_,
    select,
    table,
    union_all,
)
from sqlalchemy.sql.selectable import SelectBase
from sqlalchemy.types import ARRAY, Boolean, Integer, Text

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.actions import recipient_for_user_profiles
from zerver.lib.addressee import get_user_profiles, get_user_profiles_by_ids
from zerver.lib.exceptions import ErrorCode, JsonableError, MissingAuthenticationError
from zerver.lib.message import get_first_visible_message_id, messages_for_ids
from zerver.lib.narrow import is_spectator_compatible, is_web_public_narrow
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.streams import (
    can_access_stream_history_by_id,
    can_access_stream_history_by_name,
    get_public_streams_queryset,
    get_stream_by_narrow_operand_access_unchecked,
    get_web_public_streams_queryset,
)
from zerver.lib.topic import (
    DB_TOPIC_NAME,
    MATCH_TOPIC,
    get_resolved_topic_condition_sa,
    topic_column_sa,
    topic_match_sa,
)
from zerver.lib.topic_mutes import exclude_topic_mutes
from zerver.lib.types import Validator
from zerver.lib.utils import statsd
from zerver.lib.validator import (
    check_bool,
    check_dict,
    check_int,
    check_list,
    check_required_string,
    check_string,
    check_string_or_int,
    check_string_or_int_list,
    to_non_negative_int,
)
from zerver.models import (
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
    get_active_streams,
    get_user_by_id_in_realm_including_cross_realm,
    get_user_including_cross_realm,
)

LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000
MAX_MESSAGES_PER_FETCH = 5000


class BadNarrowOperator(JsonableError):
    code = ErrorCode.BAD_NARROW
    data_fields = ["desc"]

    def __init__(self, desc: str) -> None:
        self.desc: str = desc

    @staticmethod
    def msg_format() -> str:
        return _("Invalid narrow operator: {desc}")


ConditionTransform = Callable[[ClauseElement], ClauseElement]

OptionalNarrowListT = Optional[List[Dict[str, Any]]]

# These delimiters will not appear in rendered messages or HTML-escaped topics.
TS_START = "<ts-match>"
TS_STOP = "</ts-match>"


def ts_locs_array(
    config: "ColumnElement[Text]",
    text: "ColumnElement[Text]",
    tsquery: "ColumnElement[Any]",
) -> "ColumnElement[ARRAY[Integer]]":
    options = f"HighlightAll = TRUE, StartSel = {TS_START}, StopSel = {TS_STOP}"
    delimited = func.ts_headline(config, text, tsquery, options, type_=Text)
    part = func.unnest(
        func.string_to_array(delimited, TS_START, type_=ARRAY(Text)), type_=Text
    ).column_valued()
    part_len = func.length(part, type_=Integer) - len(TS_STOP)
    match_pos = func.sum(part_len, type_=Integer).over(rows=(None, -1)) + len(TS_STOP)
    match_len = func.strpos(part, TS_STOP, type_=Integer) - 1
    return func.array(
        select(postgresql.array([match_pos, match_len])).offset(1).scalar_subquery(),
        type_=ARRAY(Integer),
    )


# When you add a new operator to this, also update zerver/lib/narrow.py
class NarrowBuilder:
    """
    Build up a SQLAlchemy query to find messages matching a narrow.
    """

    # This class has an important security invariant:
    #
    #   None of these methods ever *add* messages to a query's result.
    #
    # That is, the `add_term` method, and its helpers the `by_*` methods,
    # are passed a Select object representing a query for messages; they may
    # call some methods on it, and then they return a resulting Select
    # object.  Things these methods may do to the queries they handle
    # include
    #  * add conditions to filter out rows (i.e., messages), with `query.where`
    #  * add columns for more information on the same message, with `query.column`
    #  * add a join for more information on the same message
    #
    # Things they may not do include
    #  * anything that would pull in additional rows, or information on
    #    other messages.

    def __init__(
        self,
        user_profile: Optional[UserProfile],
        msg_id_column: "ColumnElement[Integer]",
        realm: Realm,
        is_web_public_query: bool = False,
    ) -> None:
        self.user_profile = user_profile
        self.msg_id_column = msg_id_column
        self.realm = realm
        self.is_web_public_query = is_web_public_query

    def add_term(self, query: Select, term: Dict[str, Any]) -> Select:
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
        operator = term["operator"]
        operand = term["operand"]

        negated = term.get("negated", False)

        method_name = "by_" + operator.replace("-", "_")
        method = getattr(self, method_name, None)
        if method is None:
            raise BadNarrowOperator("unknown operator " + operator)

        if negated:
            maybe_negate = not_
        else:
            maybe_negate = lambda cond: cond

        return method(query, operand, maybe_negate)

    def by_has(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        if operand not in ["attachment", "image", "link"]:
            raise BadNarrowOperator("unknown 'has' operand " + operand)
        col_name = "has_" + operand
        cond = column(col_name, Boolean)
        return query.where(maybe_negate(cond))

    def by_in(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        # This operator does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        if operand == "home":
            conditions = exclude_muting_conditions(self.user_profile, [])
            return query.where(and_(*conditions))
        elif operand == "all":
            return query

        raise BadNarrowOperator("unknown 'in' operand " + operand)

    def by_is(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        # This operator class does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        if operand == "private":
            cond = column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "starred":
            cond = column("flags", Integer).op("&")(UserMessage.flags.starred.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "unread":
            cond = column("flags", Integer).op("&")(UserMessage.flags.read.mask) == 0
            return query.where(maybe_negate(cond))
        elif operand == "mentioned":
            cond1 = column("flags", Integer).op("&")(UserMessage.flags.mentioned.mask) != 0
            cond2 = column("flags", Integer).op("&")(UserMessage.flags.wildcard_mentioned.mask) != 0
            cond = or_(cond1, cond2)
            return query.where(maybe_negate(cond))
        elif operand == "alerted":
            cond = column("flags", Integer).op("&")(UserMessage.flags.has_alert_word.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "resolved":
            cond = get_resolved_topic_condition_sa()
            return query.where(maybe_negate(cond))
        raise BadNarrowOperator("unknown 'is' operand " + operand)

    _alphanum = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

    def _pg_re_escape(self, pattern: str) -> str:
        """
        Escape user input to place in a regex

        Python's re.escape escapes Unicode characters in a way which PostgreSQL
        fails on, '\u03bb' to '\\\u03bb'. This function will correctly escape
        them for PostgreSQL, '\u03bb' to '\\u03bb'.
        """
        s = list(pattern)
        for i, c in enumerate(s):
            if c not in self._alphanum:
                if ord(c) >= 128:
                    # convert the character to hex PostgreSQL regex will take
                    # \uXXXX
                    s[i] = f"\\u{ord(c):0>4x}"
                else:
                    s[i] = "\\" + c
        return "".join(s)

    def by_stream(
        self, query: Select, operand: Union[str, int], maybe_negate: ConditionTransform
    ) -> Select:
        try:
            # Because you can see your own message history for
            # private streams you are no longer subscribed to, we
            # need get_stream_by_narrow_operand_access_unchecked here.
            stream = get_stream_by_narrow_operand_access_unchecked(operand, self.realm)

            if self.is_web_public_query and not stream.is_web_public:
                raise BadNarrowOperator("unknown web-public stream " + str(operand))
        except Stream.DoesNotExist:
            raise BadNarrowOperator("unknown stream " + str(operand))

        if self.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to "social" to also show messages to
            # /^(un)*social(.d)*$/ (unsocial, ununsocial, social.d, ...).

            # In `ok_to_include_history`, we assume that a non-negated
            # `stream` term for a public stream will limit the query to
            # that specific stream.  So it would be a bug to hit this
            # codepath after relying on this term there.  But all streams in
            # a Zephyr realm are private, so that doesn't happen.
            assert not stream.is_public()

            m = re.search(r"^(?:un)*(.+?)(?:\.d)*$", stream.name, re.IGNORECASE)
            # Since the regex has a `.+` in it and "" is invalid as a
            # stream name, this will always match
            assert m is not None
            base_stream_name = m.group(1)

            matching_streams = get_active_streams(self.realm).filter(
                name__iregex=rf"^(un)*{self._pg_re_escape(base_stream_name)}(\.d)*$"
            )
            recipient_ids = [matching_stream.recipient_id for matching_stream in matching_streams]
            cond = column("recipient_id", Integer).in_(recipient_ids)
            return query.where(maybe_negate(cond))

        recipient = stream.recipient
        cond = column("recipient_id", Integer) == recipient.id
        return query.where(maybe_negate(cond))

    def by_streams(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        if operand == "public":
            # Get all both subscribed and non subscribed public streams
            # but exclude any private subscribed streams.
            recipient_queryset = get_public_streams_queryset(self.realm)
        elif operand == "web-public":
            recipient_queryset = get_web_public_streams_queryset(self.realm)
        else:
            raise BadNarrowOperator("unknown streams operand " + operand)

        recipient_ids = recipient_queryset.values_list("recipient_id", flat=True).order_by("id")
        cond = column("recipient_id", Integer).in_(recipient_ids)
        return query.where(maybe_negate(cond))

    def by_topic(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        if self.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to topic "foo" to also show messages to /^foo(.d)*$/
            # (foo, foo.d, foo.d.d, etc)
            m = re.search(r"^(.*?)(?:\.d)*$", operand, re.IGNORECASE)
            # Since the regex has a `.*` in it, this will always match
            assert m is not None
            base_topic = m.group(1)

            # Additionally, MIT users expect the empty instance and
            # instance "personal" to be the same.
            if base_topic in ("", "personal", '(instance "")'):
                cond: ClauseElement = or_(
                    topic_match_sa(""),
                    topic_match_sa(".d"),
                    topic_match_sa(".d.d"),
                    topic_match_sa(".d.d.d"),
                    topic_match_sa(".d.d.d.d"),
                    topic_match_sa("personal"),
                    topic_match_sa("personal.d"),
                    topic_match_sa("personal.d.d"),
                    topic_match_sa("personal.d.d.d"),
                    topic_match_sa("personal.d.d.d.d"),
                    topic_match_sa('(instance "")'),
                    topic_match_sa('(instance "").d'),
                    topic_match_sa('(instance "").d.d'),
                    topic_match_sa('(instance "").d.d.d'),
                    topic_match_sa('(instance "").d.d.d.d'),
                )
            else:
                # We limit `.d` counts, since PostgreSQL has much better
                # query planning for this than they do for a regular
                # expression (which would sometimes table scan).
                cond = or_(
                    topic_match_sa(base_topic),
                    topic_match_sa(base_topic + ".d"),
                    topic_match_sa(base_topic + ".d.d"),
                    topic_match_sa(base_topic + ".d.d.d"),
                    topic_match_sa(base_topic + ".d.d.d.d"),
                )
            return query.where(maybe_negate(cond))

        cond = topic_match_sa(operand)
        return query.where(maybe_negate(cond))

    def by_sender(
        self, query: Select, operand: Union[str, int], maybe_negate: ConditionTransform
    ) -> Select:
        try:
            if isinstance(operand, str):
                sender = get_user_including_cross_realm(operand, self.realm)
            else:
                sender = get_user_by_id_in_realm_including_cross_realm(operand, self.realm)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator("unknown user " + str(operand))

        cond = column("sender_id", Integer) == literal(sender.id)
        return query.where(maybe_negate(cond))

    def by_near(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        return query

    def by_id(
        self, query: Select, operand: Union[int, str], maybe_negate: ConditionTransform
    ) -> Select:
        if not str(operand).isdigit():
            raise BadNarrowOperator("Invalid message ID")
        cond = self.msg_id_column == literal(operand)
        return query.where(maybe_negate(cond))

    def by_pm_with(
        self, query: Select, operand: Union[str, Iterable[int]], maybe_negate: ConditionTransform
    ) -> Select:
        # This operator does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        try:
            if isinstance(operand, str):
                email_list = operand.split(",")
                user_profiles = get_user_profiles(
                    emails=email_list,
                    realm=self.realm,
                )
            else:
                """
                This is where we handle passing a list of user IDs for the narrow, which is the
                preferred/cleaner API.
                """
                user_profiles = get_user_profiles_by_ids(
                    user_ids=operand,
                    realm=self.realm,
                )

            recipient = recipient_for_user_profiles(
                user_profiles=user_profiles,
                forwarded_mirror_message=False,
                forwarder_user_profile=None,
                sender=self.user_profile,
                allow_deactivated=True,
            )
        except (JsonableError, ValidationError):
            raise BadNarrowOperator("unknown user in " + str(operand))

        # Group DM
        if recipient.type == Recipient.HUDDLE:
            cond = column("recipient_id", Integer) == recipient.id
            return query.where(maybe_negate(cond))

        # 1:1 PM
        other_participant = None

        # Find if another person is in PM
        for user in user_profiles:
            if user.id != self.user_profile.id:
                other_participant = user

        # PM with another person
        if other_participant:
            # We need bidirectional messages PM with another person.
            # But Recipient.PERSONAL objects only encode the person who
            # received the message, and not the other participant in
            # the thread (the sender), we need to do a somewhat
            # complex query to get messages between these two users
            # with either of them as the sender.
            self_recipient_id = self.user_profile.recipient_id
            cond = or_(
                and_(
                    column("sender_id", Integer) == other_participant.id,
                    column("recipient_id", Integer) == self_recipient_id,
                ),
                and_(
                    column("sender_id", Integer) == self.user_profile.id,
                    column("recipient_id", Integer) == recipient.id,
                ),
            )
            return query.where(maybe_negate(cond))

        # PM with self
        cond = and_(
            column("sender_id", Integer) == self.user_profile.id,
            column("recipient_id", Integer) == recipient.id,
        )
        return query.where(maybe_negate(cond))

    def by_group_pm_with(
        self, query: Select, operand: Union[str, int], maybe_negate: ConditionTransform
    ) -> Select:
        # This operator does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        try:
            if isinstance(operand, str):
                narrow_profile = get_user_including_cross_realm(operand, self.realm)
            else:
                narrow_profile = get_user_by_id_in_realm_including_cross_realm(operand, self.realm)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperator("unknown user " + str(operand))

        self_recipient_ids = [
            recipient_tuple["recipient_id"]
            for recipient_tuple in Subscription.objects.filter(
                user_profile=self.user_profile,
                recipient__type=Recipient.HUDDLE,
            ).values("recipient_id")
        ]
        narrow_recipient_ids = [
            recipient_tuple["recipient_id"]
            for recipient_tuple in Subscription.objects.filter(
                user_profile=narrow_profile,
                recipient__type=Recipient.HUDDLE,
            ).values("recipient_id")
        ]

        recipient_ids = set(self_recipient_ids) & set(narrow_recipient_ids)
        cond = column("recipient_id", Integer).in_(recipient_ids)
        return query.where(maybe_negate(cond))

    def by_search(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        if settings.USING_PGROONGA:
            return self._by_search_pgroonga(query, operand, maybe_negate)
        else:
            return self._by_search_tsearch(query, operand, maybe_negate)

    def _by_search_pgroonga(
        self, query: Select, operand: str, maybe_negate: ConditionTransform
    ) -> Select:
        match_positions_character = func.pgroonga_match_positions_character
        query_extract_keywords = func.pgroonga_query_extract_keywords
        operand_escaped = func.escape_html(operand, type_=Text)
        keywords = query_extract_keywords(operand_escaped)
        query = query.add_columns(
            match_positions_character(column("rendered_content", Text), keywords).label(
                "content_matches"
            ),
            match_positions_character(
                func.escape_html(topic_column_sa(), type_=Text), keywords
            ).label("topic_matches"),
        )
        condition = column("search_pgroonga", Text).op("&@~")(operand_escaped)
        return query.where(maybe_negate(condition))

    def _by_search_tsearch(
        self, query: Select, operand: str, maybe_negate: ConditionTransform
    ) -> Select:
        tsquery = func.plainto_tsquery(literal("zulip.english_us_search"), literal(operand))
        query = query.add_columns(
            ts_locs_array(
                literal("zulip.english_us_search", Text), column("rendered_content", Text), tsquery
            ).label("content_matches"),
            # We HTML-escape the topic in PostgreSQL to avoid doing a server round-trip
            ts_locs_array(
                literal("zulip.english_us_search", Text),
                func.escape_html(topic_column_sa(), type_=Text),
                tsquery,
            ).label("topic_matches"),
        )

        # Do quoted string matching.  We really want phrase
        # search here so we can ignore punctuation and do
        # stemming, but there isn't a standard phrase search
        # mechanism in PostgreSQL
        for term in re.findall(r'"[^"]+"|\S+', operand):
            if term[0] == '"' and term[-1] == '"':
                term = term[1:-1]
                term = "%" + connection.ops.prep_for_like_query(term) + "%"
                cond: ClauseElement = or_(
                    column("content", Text).ilike(term), topic_column_sa().ilike(term)
                )
                query = query.where(maybe_negate(cond))

        cond = column("search_tsvector", postgresql.TSVECTOR).op("@@")(tsquery)
        return query.where(maybe_negate(cond))


def highlight_string(text: str, locs: Iterable[Tuple[int, int]]) -> str:
    highlight_start = '<span class="highlight">'
    highlight_stop = "</span>"
    pos = 0
    result = ""
    in_tag = False

    for loc in locs:
        (offset, length) = loc

        prefix_start = pos
        prefix_end = offset
        match_start = offset
        match_end = offset + length

        prefix = text[prefix_start:prefix_end]
        match = text[match_start:match_end]

        for character in prefix + match:
            if character == "<":
                in_tag = True
            elif character == ">":
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

    result += text[pos:]
    return result


def get_search_fields(
    rendered_content: str,
    topic_name: str,
    content_matches: Iterable[Tuple[int, int]],
    topic_matches: Iterable[Tuple[int, int]],
) -> Dict[str, str]:
    return {
        "match_content": highlight_string(rendered_content, content_matches),
        MATCH_TOPIC: highlight_string(escape_html(topic_name), topic_matches),
    }


def narrow_parameter(json: str) -> OptionalNarrowListT:

    data = orjson.loads(json)
    if not isinstance(data, list):
        raise ValueError("argument is not a list")
    if len(data) == 0:
        # The "empty narrow" should be None, and not []
        return None

    def convert_term(elem: Union[Dict[str, Any], List[str]]) -> Dict[str, Any]:

        # We have to support a legacy tuple format.
        if isinstance(elem, list):
            if len(elem) != 2 or any(not isinstance(x, str) for x in elem):
                raise ValueError("element is not a string pair")
            return dict(operator=elem[0], operand=elem[1])

        if isinstance(elem, dict):
            # Make sure to sync this list to frontend also when adding a new operator.
            # that supports user IDs. Relevant code is located in static/js/message_fetch.js
            # in handle_operators_supporting_id_based_api function where you will need to update
            # operators_supporting_id, or operators_supporting_ids array.
            operators_supporting_id = ["sender", "group-pm-with", "stream"]
            operators_supporting_ids = ["pm-with"]
            operators_non_empty_operand = {"search"}

            operator = elem.get("operator", "")
            if operator in operators_supporting_id:
                operand_validator: Validator[object] = check_string_or_int
            elif operator in operators_supporting_ids:
                operand_validator = check_string_or_int_list
            elif operator in operators_non_empty_operand:
                operand_validator = check_required_string
            else:
                operand_validator = check_string

            validator = check_dict(
                required_keys=[
                    ("operator", check_string),
                    ("operand", operand_validator),
                ],
                optional_keys=[
                    ("negated", check_bool),
                ],
            )

            try:
                validator("elem", elem)
            except ValidationError as error:
                raise JsonableError(error.message)

            # whitelist the fields we care about for now
            return dict(
                operator=elem["operator"],
                operand=elem["operand"],
                negated=elem.get("negated", False),
            )

        raise ValueError("element is not a dictionary")

    return list(map(convert_term, data))


def ok_to_include_history(
    narrow: OptionalNarrowListT, user_profile: Optional[UserProfile], is_web_public_query: bool
) -> bool:
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

    # For web-public queries, we are always returning history.  The
    # analogues of the below stream access checks for whether streams
    # have is_web_public set and banning is operators in this code
    # path are done directly in NarrowBuilder.
    if is_web_public_query:
        assert user_profile is None
        return True

    assert user_profile is not None

    include_history = False
    if narrow is not None:
        for term in narrow:
            if term["operator"] == "stream" and not term.get("negated", False):
                operand: Union[str, int] = term["operand"]
                if isinstance(operand, str):
                    include_history = can_access_stream_history_by_name(user_profile, operand)
                else:
                    include_history = can_access_stream_history_by_id(user_profile, operand)
            elif (
                term["operator"] == "streams"
                and term["operand"] == "public"
                and not term.get("negated", False)
                and user_profile.can_access_public_streams()
            ):
                include_history = True
        # Disable historical messages if the user is narrowing on anything
        # that's a property on the UserMessage table.  There cannot be
        # historical messages in these cases anyway.
        for term in narrow:
            if term["operator"] == "is":
                include_history = False

    return include_history


def get_stream_from_narrow_access_unchecked(
    narrow: OptionalNarrowListT, realm: Realm
) -> Optional[Stream]:
    if narrow is not None:
        for term in narrow:
            if term["operator"] == "stream":
                return get_stream_by_narrow_operand_access_unchecked(term["operand"], realm)
    return None


def exclude_muting_conditions(
    user_profile: UserProfile, narrow: OptionalNarrowListT
) -> List[ClauseElement]:
    conditions: List[ClauseElement] = []
    stream_id = None
    try:
        # Note: It is okay here to not check access to stream
        # because we are only using the stream id to exclude data,
        # not to include results.
        stream = get_stream_from_narrow_access_unchecked(narrow, user_profile.realm)
        if stream is not None:
            stream_id = stream.id
    except Stream.DoesNotExist:
        pass

    # Stream-level muting only applies when looking at views that
    # include multiple streams, since we do want users to be able to
    # browser messages within a muted stream.
    if stream_id is None:
        rows = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            is_muted=True,
            recipient__type=Recipient.STREAM,
        ).values("recipient_id")
        muted_recipient_ids = [row["recipient_id"] for row in rows]
        if len(muted_recipient_ids) > 0:
            # Only add the condition if we have muted streams to simplify/avoid warnings.
            condition = not_(column("recipient_id", Integer).in_(muted_recipient_ids))
            conditions.append(condition)

    conditions = exclude_topic_mutes(conditions, user_profile, stream_id)

    # Muted user logic for hiding messages is implemented entirely
    # client-side. This is by design, as it allows UI to hint that
    # muted messages exist where their absence might make conversation
    # difficult to understand. As a result, we do not need to consider
    # muted users in this server-side logic for returning messages to
    # clients. (We could in theory exclude PMs from muted users, but
    # they're likely to be sufficiently rare to not be worth extra
    # logic/testing here).

    return conditions


def get_base_query_for_search(
    user_profile: Optional[UserProfile], need_message: bool, need_user_message: bool
) -> Tuple[Select, "ColumnElement[Integer]"]:
    # Handle the simple case where user_message isn't involved first.
    if not need_user_message:
        assert need_message
        query = select(column("id", Integer).label("message_id")).select_from(
            table("zerver_message")
        )
        inner_msg_id_col = literal_column("zerver_message.id", Integer)
        return (query, inner_msg_id_col)

    assert user_profile is not None
    if need_message:
        query = (
            select(column("message_id", Integer), column("flags", Integer))
            .where(column("user_profile_id", Integer) == literal(user_profile.id))
            .select_from(
                join(
                    table("zerver_usermessage"),
                    table("zerver_message"),
                    literal_column("zerver_usermessage.message_id", Integer)
                    == literal_column("zerver_message.id", Integer),
                )
            )
        )
        inner_msg_id_col = column("message_id", Integer)
        return (query, inner_msg_id_col)

    query = (
        select(column("message_id", Integer), column("flags", Integer))
        .where(column("user_profile_id", Integer) == literal(user_profile.id))
        .select_from(table("zerver_usermessage"))
    )
    inner_msg_id_col = column("message_id", Integer)
    return (query, inner_msg_id_col)


def add_narrow_conditions(
    user_profile: Optional[UserProfile],
    inner_msg_id_col: "ColumnElement[Integer]",
    query: Select,
    narrow: OptionalNarrowListT,
    is_web_public_query: bool,
    realm: Realm,
) -> Tuple[Select, bool]:
    is_search = False  # for now

    if narrow is None:
        return (query, is_search)

    # Build the query for the narrow
    builder = NarrowBuilder(user_profile, inner_msg_id_col, realm, is_web_public_query)
    search_operands = []

    # As we loop through terms, builder does most of the work to extend
    # our query, but we need to collect the search operands and handle
    # them after the loop.
    for term in narrow:
        if term["operator"] == "search":
            search_operands.append(term["operand"])
        else:
            query = builder.add_term(query, term)

    if search_operands:
        is_search = True
        query = query.add_columns(topic_column_sa(), column("rendered_content", Text))
        search_term = dict(
            operator="search",
            operand=" ".join(search_operands),
        )
        query = builder.add_term(query, search_term)

    return (query, is_search)


def find_first_unread_anchor(
    sa_conn: Connection, user_profile: Optional[UserProfile], narrow: OptionalNarrowListT
) -> int:
    # For anonymous web users, all messages are treated as read, and so
    # always return LARGER_THAN_MAX_MESSAGE_ID.
    if user_profile is None:
        return LARGER_THAN_MAX_MESSAGE_ID

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
        is_web_public_query=False,
        realm=user_profile.realm,
    )

    condition = column("flags", Integer).op("&")(UserMessage.flags.read.mask) == 0

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
        anchor = LARGER_THAN_MAX_MESSAGE_ID

    return anchor


def parse_anchor_value(anchor_val: Optional[str], use_first_unread_anchor: bool) -> Optional[int]:
    """Given the anchor and use_first_unread_anchor parameters passed by
    the client, computes what anchor value the client requested,
    handling backwards-compatibility and the various string-valued
    fields.  We encode use_first_unread_anchor as anchor=None.
    """
    if use_first_unread_anchor:
        # Backwards-compatibility: Before we added support for the
        # special string-typed anchor values, clients would pass
        # anchor=None and use_first_unread_anchor=True to indicate
        # what is now expressed as anchor="first_unread".
        return None
    if anchor_val is None:
        # Throw an exception if neither an anchor argument not
        # use_first_unread_anchor was specified.
        raise JsonableError(_("Missing 'anchor' argument."))
    if anchor_val == "oldest":
        return 0
    if anchor_val == "newest":
        return LARGER_THAN_MAX_MESSAGE_ID
    if anchor_val == "first_unread":
        return None
    try:
        # We don't use `.isnumeric()` to support negative numbers for
        # anchor.  We don't recommend it in the API (if you want the
        # very first message, use 0 or 1), but it used to be supported
        # and was used by the web app, so we need to continue
        # supporting it for backwards-compatibility
        anchor = int(anchor_val)
        if anchor < 0:
            return 0
        elif anchor > LARGER_THAN_MAX_MESSAGE_ID:
            return LARGER_THAN_MAX_MESSAGE_ID
        return anchor
    except ValueError:
        raise JsonableError(_("Invalid anchor"))


@has_request_variables
def get_messages_backend(
    request: HttpRequest,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    anchor_val: Optional[str] = REQ("anchor", default=None),
    num_before: int = REQ(converter=to_non_negative_int),
    num_after: int = REQ(converter=to_non_negative_int),
    narrow: OptionalNarrowListT = REQ("narrow", converter=narrow_parameter, default=None),
    use_first_unread_anchor_val: bool = REQ(
        "use_first_unread_anchor", json_validator=check_bool, default=False
    ),
    client_gravatar: bool = REQ(json_validator=check_bool, default=True),
    apply_markdown: bool = REQ(json_validator=check_bool, default=True),
) -> HttpResponse:
    anchor = parse_anchor_value(anchor_val, use_first_unread_anchor_val)
    if num_before + num_after > MAX_MESSAGES_PER_FETCH:
        raise JsonableError(
            _("Too many messages requested (maximum {}).").format(
                MAX_MESSAGES_PER_FETCH,
            )
        )

    realm = get_valid_realm_from_request(request)
    if not maybe_user_profile.is_authenticated:
        # If user is not authenticated, clients must include
        # `streams:web-public` in their narrow query to indicate this
        # is a web-public query.  This helps differentiate between
        # cases of web-public queries (where we should return the
        # web-public results only) and clients with buggy
        # authentication code (where we should return an auth error).
        #
        # GetOldMessagesTest.test_unauthenticated_* tests ensure
        # that we are not leaking any secure data (private messages and
        # non web-public-stream messages) via this path.
        if not realm.allow_web_public_streams_access():
            raise MissingAuthenticationError()
        if not is_web_public_narrow(narrow):
            raise MissingAuthenticationError()
        assert narrow is not None
        if not is_spectator_compatible(narrow):
            raise MissingAuthenticationError()

        # We use None to indicate unauthenticated requests as it's more
        # readable than using AnonymousUser, and the lack of Django
        # stubs means that mypy can't check AnonymousUser well.
        user_profile: Optional[UserProfile] = None
        is_web_public_query = True
    else:
        assert isinstance(maybe_user_profile, UserProfile)
        user_profile = maybe_user_profile
        assert user_profile is not None
        is_web_public_query = False

    assert realm is not None

    if (
        is_web_public_query
        or realm.email_address_visibility != Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE
    ):
        # If email addresses are only available to administrators,
        # clients cannot compute gravatars, so we force-set it to false.
        client_gravatar = False

    include_history = ok_to_include_history(narrow, user_profile, is_web_public_query)
    if include_history:
        # The initial query in this case doesn't use `zerver_usermessage`,
        # and isn't yet limited to messages the user is entitled to see!
        #
        # This is OK only because we've made sure this is a narrow that
        # will cause us to limit the query appropriately elsewhere.
        # See `ok_to_include_history` for details.
        #
        # Note that is_web_public_query=True goes here, since
        # include_history is semantically correct for is_web_public_query.
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

    query: SelectBase
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
        realm=realm,
        is_web_public_query=is_web_public_query,
    )

    if narrow is not None:
        # Add some metadata to our logging data for narrows
        verbose_operators = []
        for term in narrow:
            if term["operator"] == "is":
                verbose_operators.append("is:" + term["operand"])
            else:
                verbose_operators.append(term["operator"])
        log_data = RequestNotes.get_notes(request).log_data
        assert log_data is not None
        log_data["extra"] = "[{}]".format(",".join(verbose_operators))

    with get_sqlalchemy_connection() as sa_conn:
        if anchor is None:
            # `anchor=None` corresponds to the anchor="first_unread" parameter.
            anchor = find_first_unread_anchor(
                sa_conn,
                user_profile,
                narrow,
            )

        anchored_to_left = anchor == 0

        # Set value that will be used to short circuit the after_query
        # altogether and avoid needless conditions in the before_query.
        anchored_to_right = anchor >= LARGER_THAN_MAX_MESSAGE_ID
        if anchored_to_right:
            num_after = 0

        first_visible_message_id = get_first_visible_message_id(realm)

        query = limit_query_to_range(
            query=query,
            num_before=num_before,
            num_after=num_after,
            anchor=anchor,
            anchored_to_left=anchored_to_left,
            anchored_to_right=anchored_to_right,
            id_col=inner_msg_id_col,
            first_visible_message_id=first_visible_message_id,
        )

        main_query = query.subquery()
        query = (
            select(*main_query.c)
            .select_from(main_query)
            .order_by(column("message_id", Integer).asc())
        )
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
        first_visible_message_id=first_visible_message_id,
    )

    rows = query_info["rows"]

    # The following is a little messy, but ensures that the code paths
    # are similar regardless of the value of include_history.  The
    # 'user_messages' dictionary maps each message to the user's
    # UserMessage object for that message, which we will attach to the
    # rendered message dict before returning it.  We attempt to
    # bulk-fetch rendered message dicts from remote cache using the
    # 'messages' list.
    message_ids: List[int] = []
    user_message_flags: Dict[int, List[str]] = {}
    if is_web_public_query:
        # For spectators, we treat all historical messages as read.
        for row in rows:
            message_id = row[0]
            message_ids.append(message_id)
            user_message_flags[message_id] = ["read"]
    elif include_history:
        assert user_profile is not None
        message_ids = [row[0] for row in rows]

        # TODO: This could be done with an outer join instead of two queries
        um_rows = UserMessage.objects.filter(user_profile=user_profile, message_id__in=message_ids)
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

    search_fields: Dict[int, Dict[str, str]] = {}
    if is_search:
        for row in rows:
            message_id = row[0]
            (topic_name, rendered_content, content_matches, topic_matches) = row[-4:]

            try:
                search_fields[message_id] = get_search_fields(
                    rendered_content, topic_name, content_matches, topic_matches
                )
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
        allow_edit_history=realm.allow_edit_history,
    )

    statsd.incr("loaded_old_messages", len(message_list))

    ret = dict(
        messages=message_list,
        result="success",
        msg="",
        found_anchor=query_info["found_anchor"],
        found_oldest=query_info["found_oldest"],
        found_newest=query_info["found_newest"],
        history_limited=query_info["history_limited"],
        anchor=anchor,
    )
    return json_success(request, data=ret)


def limit_query_to_range(
    query: Select,
    num_before: int,
    num_after: int,
    anchor: int,
    anchored_to_left: bool,
    anchored_to_right: bool,
    id_col: "ColumnElement[Integer]",
    first_visible_message_id: int,
) -> SelectBase:
    """
    This code is actually generic enough that we could move it to a
    library, but our only caller for now is message search.
    """
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
        after_anchor = max(anchor, first_visible_message_id)
        before_limit = num_before
        after_limit = num_after + 1
    elif need_before_query:
        before_anchor = anchor
        before_limit = num_before
        if not anchored_to_right:
            before_limit += 1
    elif need_after_query:
        after_anchor = max(anchor, first_visible_message_id)
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
        return union_all(before_query.self_group(), after_query.self_group())
    elif need_before_query:
        return before_query
    elif need_after_query:
        return after_query
    else:
        # If we don't have either a before_query or after_query, it's because
        # some combination of num_before/num_after/anchor are zero or
        # use_first_unread_anchor logic found no unread messages.
        #
        # The most likely reason is somebody is doing an id search, so searching
        # for something like `message_id = 42` is exactly what we want.  In other
        # cases, which could possibly be buggy API clients, at least we will
        # return at most one row here.
        return query.where(id_col == anchor)


def post_process_limited_query(
    rows: Sequence[Union[Row, Sequence[Any]]],
    num_before: int,
    num_after: int,
    anchor: int,
    anchored_to_left: bool,
    anchored_to_right: bool,
    first_visible_message_id: int,
) -> Dict[str, Any]:
    # Our queries may have fetched extra rows if they added
    # "headroom" to the limits, but we want to truncate those
    # rows.
    #
    # Also, in cases where we had non-zero values of num_before or
    # num_after, we want to know found_oldest and found_newest, so
    # that the clients will know that they got complete results.

    if first_visible_message_id > 0:
        visible_rows: Sequence[Union[Row, Sequence[Any]]] = [
            r for r in rows if r[0] >= first_visible_message_id
        ]
    else:
        visible_rows = rows

    rows_limited = len(visible_rows) != len(rows)

    if anchored_to_right:
        num_after = 0
        before_rows = visible_rows[:]
        anchor_rows = []
        after_rows = []
    else:
        before_rows = [r for r in visible_rows if r[0] < anchor]
        anchor_rows = [r for r in visible_rows if r[0] == anchor]
        after_rows = [r for r in visible_rows if r[0] > anchor]

    if num_before:
        before_rows = before_rows[-1 * num_before :]

    if num_after:
        after_rows = after_rows[:num_after]

    visible_rows = [*before_rows, *anchor_rows, *after_rows]

    found_anchor = len(anchor_rows) == 1
    found_oldest = anchored_to_left or (len(before_rows) < num_before)
    found_newest = anchored_to_right or (len(after_rows) < num_after)
    # BUG: history_limited is incorrect False in the event that we had
    # to bump `anchor` up due to first_visible_message_id, and there
    # were actually older messages.  This may be a rare event in the
    # context where history_limited is relevant, because it can only
    # happen in one-sided queries with no num_before (see tests tagged
    # BUG in PostProcessTest for examples), and we don't generally do
    # those from the UI, so this might be OK for now.
    #
    # The correct fix for this probably involves e.g. making a
    # `before_query` when we increase `anchor` just to confirm whether
    # messages were hidden.
    history_limited = rows_limited and found_oldest

    return dict(
        rows=visible_rows,
        found_anchor=found_anchor,
        found_newest=found_newest,
        found_oldest=found_oldest,
        history_limited=history_limited,
    )


@has_request_variables
def messages_in_narrow_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    msg_ids: List[int] = REQ(json_validator=check_list(check_int)),
    narrow: OptionalNarrowListT = REQ(converter=narrow_parameter),
) -> HttpResponse:

    first_visible_message_id = get_first_visible_message_id(user_profile.realm)
    msg_ids = [message_id for message_id in msg_ids if message_id >= first_visible_message_id]
    # This query is limited to messages the user has access to because they
    # actually received them, as reflected in `zerver_usermessage`.
    query = (
        select(column("message_id", Integer), topic_column_sa(), column("rendered_content", Text))
        .where(
            and_(
                column("user_profile_id", Integer) == literal(user_profile.id),
                column("message_id", Integer).in_(msg_ids),
            )
        )
        .select_from(
            join(
                table("zerver_usermessage"),
                table("zerver_message"),
                literal_column("zerver_usermessage.message_id", Integer)
                == literal_column("zerver_message.id", Integer),
            )
        )
    )

    builder = NarrowBuilder(user_profile, column("message_id", Integer), user_profile.realm)
    if narrow is not None:
        for term in narrow:
            query = builder.add_term(query, term)

    search_fields = {}
    with get_sqlalchemy_connection() as sa_conn:
        for row in sa_conn.execute(query).fetchall():
            message_id = row._mapping["message_id"]
            topic_name = row._mapping[DB_TOPIC_NAME]
            rendered_content = row._mapping["rendered_content"]
            if "content_matches" in row._mapping:
                content_matches = row._mapping["content_matches"]
                topic_matches = row._mapping["topic_matches"]
            else:
                content_matches = topic_matches = []
            search_fields[str(message_id)] = get_search_fields(
                rendered_content,
                topic_name,
                content_matches,
                topic_matches,
            )

    return json_success(request, data={"messages": search_fields})
