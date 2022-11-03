import os
import re
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils.translation import gettext as _
from sqlalchemy.dialects import postgresql
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
)
from sqlalchemy.types import ARRAY, Boolean, Integer, Text

from zerver.lib.addressee import get_user_profiles, get_user_profiles_by_ids
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.recipient_users import recipient_for_user_profiles
from zerver.lib.streams import (
    get_public_streams_queryset,
    get_stream_by_narrow_operand_access_unchecked,
    get_web_public_streams_queryset,
)
from zerver.lib.topic import (
    RESOLVED_TOPIC_PREFIX,
    get_resolved_topic_condition_sa,
    get_topic_from_message_info,
    topic_column_sa,
    topic_match_sa,
)
from zerver.lib.types import Validator
from zerver.lib.user_topics import exclude_topic_mutes
from zerver.lib.validator import (
    check_bool,
    check_dict,
    check_required_string,
    check_string,
    check_string_or_int,
    check_string_or_int_list,
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

stop_words_list: Optional[List[str]] = None


def read_stop_words() -> List[str]:
    global stop_words_list
    if stop_words_list is None:
        file_path = os.path.join(
            settings.DEPLOY_ROOT, "puppet/zulip/files/postgresql/zulip_english.stop"
        )
        with open(file_path) as f:
            stop_words_list = f.read().splitlines()

    return stop_words_list


def check_supported_events_narrow_filter(narrow: Iterable[Sequence[str]]) -> None:
    for element in narrow:
        operator = element[0]
        if operator not in ["stream", "topic", "sender", "is"]:
            raise JsonableError(_("Operator {} not supported.").format(operator))


def is_spectator_compatible(narrow: Iterable[Dict[str, Any]]) -> bool:
    # This implementation should agree with the similar function in static/js/hash_util.js.
    for element in narrow:
        operator = element["operator"]
        if "operand" not in element:
            return False
        if operator not in ["streams", "stream", "topic", "sender", "has", "search", "near", "id"]:
            return False
    return True


def is_web_public_narrow(narrow: Optional[Iterable[Dict[str, Any]]]) -> bool:
    if narrow is None:
        return False

    for term in narrow:
        # Web-public queries are only allowed for limited types of narrows.
        # term == {'operator': 'streams', 'operand': 'web-public', 'negated': False}
        if (
            term["operator"] == "streams"
            and term["operand"] == "web-public"
            and term["negated"] is False
        ):
            return True

    return False


def build_narrow_filter(narrow: Collection[Sequence[str]]) -> Callable[[Mapping[str, Any]], bool]:
    """Changes to this function should come with corresponding changes to
    BuildNarrowFilterTest."""
    check_supported_events_narrow_filter(narrow)

    def narrow_filter(event: Mapping[str, Any]) -> bool:
        message = event["message"]
        flags = event["flags"]
        for element in narrow:
            operator = element[0]
            operand = element[1]
            if operator == "stream":
                if message["type"] != "stream":
                    return False
                if operand.lower() != message["display_recipient"].lower():
                    return False
            elif operator == "topic":
                if message["type"] != "stream":
                    return False
                topic_name = get_topic_from_message_info(message)
                if operand.lower() != topic_name.lower():
                    return False
            elif operator == "sender":
                if operand.lower() != message["sender_email"].lower():
                    return False
            elif operator == "is" and operand == "private":
                if message["type"] != "private":
                    return False
            elif operator == "is" and operand in ["starred"]:
                if operand not in flags:
                    return False
            elif operator == "is" and operand == "unread":
                if "read" in flags:
                    return False
            elif operator == "is" and operand in ["alerted", "mentioned"]:
                if "mentioned" not in flags:
                    return False
            elif operator == "is" and operand == "resolved":
                if message["type"] != "stream":
                    return False
                topic_name = get_topic_from_message_info(message)
                if not topic_name.startswith(RESOLVED_TOPIC_PREFIX):
                    return False

        return True

    return narrow_filter


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
    config: ColumnElement[Text],
    text: ColumnElement[Text],
    tsquery: ColumnElement[Any],
) -> ColumnElement[ARRAY[Integer]]:
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


class NarrowBuilder:
    """Build up a SQLAlchemy query to find messages matching a narrow."""

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
        msg_id_column: ColumnElement[Integer],
        realm: Realm,
        is_web_public_query: bool = False,
    ) -> None:
        self.user_profile = user_profile
        self.msg_id_column = msg_id_column
        self.realm = realm
        self.is_web_public_query = is_web_public_query

    def add_term(self, query: Select, term: Dict[str, Any]) -> Select:
        """Extend the given query to one narrowed by the given term, and return
        the result.

        This method satisfies an important security property: the
        returned query never includes a message that the given query
        didn't.  In particular, if the given query will only find
        messages that a given user can legitimately see, then so will
        the returned query.
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
        """Escape user input to place in a regex.

        Python's re.escape escapes Unicode characters in a way which
        PostgreSQL fails on, '\u03bb' to '\\\u03bb'. This function will
        correctly escape them for PostgreSQL, '\u03bb' to '\\u03bb'.
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
        assert recipient is not None
        cond = column("recipient_id", Integer) == recipient.id
        return query.where(maybe_negate(cond))

    def by_streams(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        if operand == "public":
            # Get all both subscribed and non-subscribed public streams
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
                """This is where we handle passing a list of user IDs for the
                narrow, which is the preferred/cleaner API."""
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


def narrow_parameter(var_name: str, json: str) -> OptionalNarrowListT:
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
) -> Tuple[Select, ColumnElement[Integer]]:
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
    inner_msg_id_col: ColumnElement[Integer],
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
