import re
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
)

import orjson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils.translation import gettext as _
from pydantic import BaseModel, model_validator
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Row
from sqlalchemy.sql import (
    ClauseElement,
    ColumnElement,
    Select,
    and_,
    column,
    false,
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
from typing_extensions import TypeAlias, override

from zerver.lib.addressee import get_user_profiles, get_user_profiles_by_ids
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.message import get_first_visible_message_id
from zerver.lib.narrow_predicate import channel_operators, channels_operators
from zerver.lib.recipient_users import recipient_for_user_profiles
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.streams import (
    can_access_stream_history_by_id,
    can_access_stream_history_by_name,
    get_public_streams_queryset,
    get_stream_by_narrow_operand_access_unchecked,
    get_web_public_streams_queryset,
)
from zerver.lib.topic_sqlalchemy import (
    get_resolved_topic_condition_sa,
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
from zerver.models import Huddle, Realm, Recipient, Stream, Subscription, UserMessage, UserProfile
from zerver.models.streams import get_active_streams
from zerver.models.users import (
    get_user_by_id_in_realm_including_cross_realm,
    get_user_including_cross_realm,
)


class NarrowParameter(BaseModel):
    operator: str
    operand: Any
    negated: bool = False

    @model_validator(mode="before")
    @classmethod
    def convert_term(cls, elem: Union[Dict[str, Any], List[str]]) -> Dict[str, Any]:
        # We have to support a legacy tuple format.
        if isinstance(elem, list):
            if len(elem) != 2 or any(not isinstance(x, str) for x in elem):
                raise ValueError("element is not a string pair")
            return dict(operator=elem[0], operand=elem[1])

        elif isinstance(elem, dict):
            if "operand" not in elem or elem["operand"] is None:
                raise ValueError("operand is missing")

            if "operator" not in elem or elem["operator"] is None:
                raise ValueError("operator is missing")
            return elem
        else:
            raise ValueError("dict or list required")

    @model_validator(mode="after")
    def validate_terms(self) -> "NarrowParameter":
        # Make sure to sync this list to frontend also when adding a new operator that
        # supports integer IDs. Relevant code is located in web/src/message_fetch.js
        # in handle_operators_supporting_id_based_api function where you will need to
        # update operators_supporting_id, or operators_supporting_ids array.
        operators_supporting_id = [
            *channel_operators,
            "id",
            "sender",
            "group-pm-with",
            "dm-including",
        ]
        operators_supporting_ids = ["pm-with", "dm"]
        operators_non_empty_operand = {"search"}

        operator = self.operator
        if operator in operators_supporting_id:
            operand_validator: Validator[object] = check_string_or_int
        elif operator in operators_supporting_ids:
            operand_validator = check_string_or_int_list
        elif operator in operators_non_empty_operand:
            operand_validator = check_required_string
        else:
            operand_validator = check_string

        try:
            self.operand = operand_validator("operand", self.operand)
            self.operator = check_string("operator", self.operator)
            if self.negated is not None:
                self.negated = check_bool("negated", self.negated)
        except ValidationError as error:
            raise JsonableError(error.message)

        # whitelist the fields we care about for now
        return self


def is_spectator_compatible(narrow: Iterable[Dict[str, Any]]) -> bool:
    # This implementation should agree with is_spectator_compatible in hash_parser.ts.
    supported_operators = [
        *channel_operators,
        *channels_operators,
        "topic",
        "sender",
        "has",
        "search",
        "near",
        "id",
    ]
    for element in narrow:
        operator = element["operator"]
        if "operand" not in element:
            return False
        if operator not in supported_operators:
            return False
    return True


def is_web_public_narrow(narrow: Optional[Iterable[Dict[str, Any]]]) -> bool:
    if narrow is None:
        return False

    return any(
        # Web-public queries are only allowed for limited types of narrows.
        # term == {'operator': 'channels', 'operand': 'web-public', 'negated': False}
        # or term == {'operator': 'streams', 'operand': 'web-public', 'negated': False}
        term["operator"] in channels_operators
        and term["operand"] == "web-public"
        and term["negated"] is False
        for term in narrow
    )


LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000


class BadNarrowOperatorError(JsonableError):
    code = ErrorCode.BAD_NARROW
    data_fields = ["desc"]

    def __init__(self, desc: str) -> None:
        self.desc: str = desc

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Invalid narrow operator: {desc}")


ConditionTransform: TypeAlias = Callable[[ClauseElement], ClauseElement]

OptionalNarrowListT: TypeAlias = Optional[List[Dict[str, Any]]]

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
        msg_id_column: ColumnElement[Integer],
        realm: Realm,
        is_web_public_query: bool = False,
    ) -> None:
        self.user_profile = user_profile
        self.msg_id_column = msg_id_column
        self.realm = realm
        self.is_web_public_query = is_web_public_query
        self.by_method_map = {
            "has": self.by_has,
            "in": self.by_in,
            "is": self.by_is,
            "channel": self.by_channel,
            # "stream" is a legacy alias for "channel"
            "stream": self.by_channel,
            "channels": self.by_channels,
            # "streams" is a legacy alias for "channels"
            "streams": self.by_channels,
            "topic": self.by_topic,
            "sender": self.by_sender,
            "near": self.by_near,
            "id": self.by_id,
            "search": self.by_search,
            "dm": self.by_dm,
            # "pm-with:" is a legacy alias for "dm:"
            "pm-with": self.by_dm,
            "dm-including": self.by_dm_including,
            # "group-pm-with:" was deprecated by the addition of "dm-including:"
            "group-pm-with": self.by_group_pm_with,
            # TODO/compatibility: Prior to commit a9b3a9c, the server implementation
            # for documented search operators with dashes, also implicitly supported
            # clients sending those same operators with underscores. We can remove
            # support for the below operators when support for the associated dashed
            # operator is removed.
            "pm_with": self.by_dm,
            "group_pm_with": self.by_group_pm_with,
        }
        self.is_channel_narrow = False
        self.is_dm_narrow = False

    def check_not_both_channel_and_dm_narrow(
        self, is_dm_narrow: bool = False, is_channel_narrow: bool = False
    ) -> None:
        if is_dm_narrow:
            self.is_dm_narrow = True
        if is_channel_narrow:
            self.is_channel_narrow = True
        if self.is_channel_narrow and self.is_dm_narrow:
            raise BadNarrowOperatorError(
                "No message can be both a channel message and direct message"
            )

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

        operator = term["operator"]
        operand = term["operand"]

        negated = term.get("negated", False)

        if operator in self.by_method_map:
            method = self.by_method_map[operator]
        else:
            raise BadNarrowOperatorError("unknown operator " + operator)

        if negated:
            maybe_negate: ConditionTransform = not_
        else:
            maybe_negate = lambda cond: cond

        return method(query, operand, maybe_negate)

    def by_has(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        if operand not in ["attachment", "image", "link", "reaction"]:
            raise BadNarrowOperatorError("unknown 'has' operand " + operand)

        if operand == "reaction":
            if self.msg_id_column.name == "message_id":
                # If the initial query uses `zerver_usermessage`
                check_col = literal_column("zerver_usermessage.message_id", Integer)
            else:
                # If the initial query doesn't use `zerver_usermessage`
                check_col = literal_column("zerver_message.id", Integer)
            exists_cond = (
                select([1])
                .select_from(table("zerver_reaction"))
                .where(check_col == literal_column("zerver_reaction.message_id", Integer))
                .exists()
            )
            return query.where(maybe_negate(exists_cond))

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

        raise BadNarrowOperatorError("unknown 'in' operand " + operand)

    def by_is(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        # This operator class does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        if operand in ["dm", "private"]:
            # "is:private" is a legacy alias for "is:dm"
            self.check_not_both_channel_and_dm_narrow(is_dm_narrow=True)
            cond = column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "starred":
            cond = column("flags", Integer).op("&")(UserMessage.flags.starred.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "unread":
            cond = column("flags", Integer).op("&")(UserMessage.flags.read.mask) == 0
            return query.where(maybe_negate(cond))
        elif operand == "mentioned":
            mention_flags_mask = (
                UserMessage.flags.mentioned.mask
                | UserMessage.flags.stream_wildcard_mentioned.mask
                | UserMessage.flags.topic_wildcard_mentioned.mask
                | UserMessage.flags.group_mentioned.mask
            )
            cond = column("flags", Integer).op("&")(mention_flags_mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "alerted":
            cond = column("flags", Integer).op("&")(UserMessage.flags.has_alert_word.mask) != 0
            return query.where(maybe_negate(cond))
        elif operand == "resolved":
            cond = get_resolved_topic_condition_sa()
            return query.where(maybe_negate(cond))
        raise BadNarrowOperatorError("unknown 'is' operand " + operand)

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

    def by_channel(
        self, query: Select, operand: Union[str, int], maybe_negate: ConditionTransform
    ) -> Select:
        self.check_not_both_channel_and_dm_narrow(is_channel_narrow=True)

        try:
            # Because you can see your own message history for
            # private channels you are no longer subscribed to, we
            # need get_stream_by_narrow_operand_access_unchecked here.
            channel = get_stream_by_narrow_operand_access_unchecked(operand, self.realm)

            if self.is_web_public_query and not channel.is_web_public:
                raise BadNarrowOperatorError("unknown web-public channel " + str(operand))
        except Stream.DoesNotExist:
            raise BadNarrowOperatorError("unknown channel " + str(operand))

        if self.realm.is_zephyr_mirror_realm:
            # MIT users expect narrowing to "social" to also show messages to
            # /^(un)*social(.d)*$/ (unsocial, ununsocial, social.d, ...).

            # In `ok_to_include_history`, we assume that a non-negated
            # `channel` term for a public channel will limit the query to
            # that specific channel. So it would be a bug to hit this
            # codepath after relying on this term there. But all channels in
            # a Zephyr realm are private, so that doesn't happen.
            assert not channel.is_public()

            m = re.search(r"^(?:un)*(.+?)(?:\.d)*$", channel.name, re.IGNORECASE)
            # Since the regex has a `.+` in it and "" is invalid as a
            # channel name, this will always match
            assert m is not None
            base_channel_name = m.group(1)

            matching_channels = get_active_streams(self.realm).filter(
                name__iregex=rf"^(un)*{self._pg_re_escape(base_channel_name)}(\.d)*$"
            )
            recipient_ids = [
                matching_channel.recipient_id for matching_channel in matching_channels
            ]
            cond = column("recipient_id", Integer).in_(recipient_ids)
            return query.where(maybe_negate(cond))

        recipient_id = channel.recipient_id
        assert recipient_id is not None
        cond = column("recipient_id", Integer) == recipient_id
        return query.where(maybe_negate(cond))

    def by_channels(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        self.check_not_both_channel_and_dm_narrow(is_channel_narrow=True)

        if operand == "public":
            # Get all both subscribed and non-subscribed public channels
            # but exclude any private subscribed channels.
            recipient_queryset = get_public_streams_queryset(self.realm)
        elif operand == "web-public":
            recipient_queryset = get_web_public_streams_queryset(self.realm)
        else:
            raise BadNarrowOperatorError("unknown channels operand " + operand)

        recipient_ids = recipient_queryset.values_list("recipient_id", flat=True).order_by("id")
        cond = column("recipient_id", Integer).in_(recipient_ids)
        return query.where(maybe_negate(cond))

    def by_topic(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        self.check_not_both_channel_and_dm_narrow(is_channel_narrow=True)

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
            raise BadNarrowOperatorError("unknown user " + str(operand))

        cond = column("sender_id", Integer) == literal(sender.id)
        return query.where(maybe_negate(cond))

    def by_near(self, query: Select, operand: str, maybe_negate: ConditionTransform) -> Select:
        return query

    def by_id(
        self, query: Select, operand: Union[int, str], maybe_negate: ConditionTransform
    ) -> Select:
        if not str(operand).isdigit():
            raise BadNarrowOperatorError("Invalid message ID")
        cond = self.msg_id_column == literal(operand)
        return query.where(maybe_negate(cond))

    def by_dm(
        self, query: Select, operand: Union[str, Iterable[int]], maybe_negate: ConditionTransform
    ) -> Select:
        # This operator does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        self.check_not_both_channel_and_dm_narrow(is_dm_narrow=True)

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
                create=False,
            )
        except (JsonableError, ValidationError):
            raise BadNarrowOperatorError("unknown user in " + str(operand))
        except Huddle.DoesNotExist:
            # Group DM where huddle doesn't exist
            return query.where(maybe_negate(false()))

        # Group direct message
        if recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
            cond = column("recipient_id", Integer) == recipient.id
            return query.where(maybe_negate(cond))

        # 1:1 direct message
        other_participant = None

        # Find if another person is in direct message
        for user in user_profiles:
            if user.id != self.user_profile.id:
                other_participant = user

        # Direct message with another person
        if other_participant:
            # We need bidirectional direct messages with another person.
            # But Recipient.PERSONAL objects only encode the person who
            # received the message, and not the other participant in
            # the thread (the sender), we need to do a somewhat
            # complex query to get messages between these two users
            # with either of them as the sender.
            self_recipient_id = self.user_profile.recipient_id
            cond = and_(
                column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0,
                column("realm_id", Integer) == self.realm.id,
                or_(
                    and_(
                        column("sender_id", Integer) == other_participant.id,
                        column("recipient_id", Integer) == self_recipient_id,
                    ),
                    and_(
                        column("sender_id", Integer) == self.user_profile.id,
                        column("recipient_id", Integer) == recipient.id,
                    ),
                ),
            )
            return query.where(maybe_negate(cond))

        # Direct message with self
        cond = and_(
            column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0,
            column("realm_id", Integer) == self.realm.id,
            column("sender_id", Integer) == self.user_profile.id,
            column("recipient_id", Integer) == recipient.id,
        )
        return query.where(maybe_negate(cond))

    def _get_huddle_recipients(self, other_user: UserProfile) -> Set[int]:
        self_recipient_ids = [
            recipient_tuple["recipient_id"]
            for recipient_tuple in Subscription.objects.filter(
                user_profile=self.user_profile,
                recipient__type=Recipient.DIRECT_MESSAGE_GROUP,
            ).values("recipient_id")
        ]
        narrow_recipient_ids = [
            recipient_tuple["recipient_id"]
            for recipient_tuple in Subscription.objects.filter(
                user_profile=other_user,
                recipient__type=Recipient.DIRECT_MESSAGE_GROUP,
            ).values("recipient_id")
        ]

        return set(self_recipient_ids) & set(narrow_recipient_ids)

    def by_dm_including(
        self, query: Select, operand: Union[str, int], maybe_negate: ConditionTransform
    ) -> Select:
        # This operator does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        self.check_not_both_channel_and_dm_narrow(is_dm_narrow=True)

        try:
            if isinstance(operand, str):
                narrow_user_profile = get_user_including_cross_realm(operand, self.realm)
            else:
                narrow_user_profile = get_user_by_id_in_realm_including_cross_realm(
                    operand, self.realm
                )
        except UserProfile.DoesNotExist:
            raise BadNarrowOperatorError("unknown user " + str(operand))

        # "dm-including" when combined with the user's own ID/email as the operand
        # should return all group and 1:1 direct messages (including direct messages
        # with self), so the simplest query to get these messages is the same as "is:dm".
        if narrow_user_profile.id == self.user_profile.id:
            cond = column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0
            return query.where(maybe_negate(cond))

        # all direct messages including another person (group and 1:1)
        huddle_recipient_ids = self._get_huddle_recipients(narrow_user_profile)

        self_recipient_id = self.user_profile.recipient_id
        # See note above in `by_dm` about needing bidirectional messages
        # for direct messages with another person.
        cond = and_(
            column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0,
            column("realm_id", Integer) == self.realm.id,
            or_(
                and_(
                    column("sender_id", Integer) == narrow_user_profile.id,
                    column("recipient_id", Integer) == self_recipient_id,
                ),
                and_(
                    column("sender_id", Integer) == self.user_profile.id,
                    column("recipient_id", Integer) == narrow_user_profile.recipient_id,
                ),
                and_(
                    column("recipient_id", Integer).in_(huddle_recipient_ids),
                ),
            ),
        )
        return query.where(maybe_negate(cond))

    def by_group_pm_with(
        self, query: Select, operand: Union[str, int], maybe_negate: ConditionTransform
    ) -> Select:
        # This operator does not support is_web_public_query.
        assert not self.is_web_public_query
        assert self.user_profile is not None

        self.check_not_both_channel_and_dm_narrow(is_dm_narrow=True)

        try:
            if isinstance(operand, str):
                narrow_profile = get_user_including_cross_realm(operand, self.realm)
            else:
                narrow_profile = get_user_by_id_in_realm_including_cross_realm(operand, self.realm)
        except UserProfile.DoesNotExist:
            raise BadNarrowOperatorError("unknown user " + str(operand))

        recipient_ids = self._get_huddle_recipients(narrow_profile)
        cond = and_(
            column("flags", Integer).op("&")(UserMessage.flags.is_private.mask) != 0,
            column("realm_id", Integer) == self.realm.id,
            column("recipient_id", Integer).in_(recipient_ids),
        )
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
            # Make sure to sync this list to frontend also when adding a new operator that
            # supports integer IDs. Relevant code is located in web/src/message_fetch.js
            # in handle_operators_supporting_id_based_api function where you will need to
            # update operators_supporting_id, or operators_supporting_ids array.
            operators_supporting_id = [
                *channel_operators,
                "id",
                "sender",
                "group-pm-with",
                "dm-including",
            ]
            operators_supporting_ids = ["pm-with", "dm"]
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
    # reading a public channel that might include messages that
    # were sent while the user was not subscribed, but which they are
    # allowed to see.  We have to be very careful about constructing
    # queries in those situations, so this function should return True
    # only if we are 100% sure that we're gonna add a clause to the
    # query that narrows to a particular public channel on the user's realm.
    # If we screw this up, then we can get into a nasty situation of
    # polluting our narrow results with messages from other realms.

    # For web-public queries, we are always returning history.  The
    # analogues of the below channel access checks for whether channels
    # have is_web_public set and banning is operators in this code
    # path are done directly in NarrowBuilder.
    if is_web_public_query:
        assert user_profile is None
        return True

    assert user_profile is not None

    include_history = False
    if narrow is not None:
        for term in narrow:
            if term["operator"] in channel_operators and not term.get("negated", False):
                operand: Union[str, int] = term["operand"]
                if isinstance(operand, str):
                    include_history = can_access_stream_history_by_name(user_profile, operand)
                else:
                    include_history = can_access_stream_history_by_id(user_profile, operand)
            elif (
                term["operator"] in channels_operators
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


def get_channel_from_narrow_access_unchecked(
    narrow: OptionalNarrowListT, realm: Realm
) -> Optional[Stream]:
    if narrow is not None:
        for term in narrow:
            if term["operator"] in channel_operators:
                return get_stream_by_narrow_operand_access_unchecked(term["operand"], realm)
    return None


def exclude_muting_conditions(
    user_profile: UserProfile, narrow: OptionalNarrowListT
) -> List[ClauseElement]:
    conditions: List[ClauseElement] = []
    channel_id = None
    try:
        # Note: It is okay here to not check access to channel
        # because we are only using the channel ID to exclude data,
        # not to include results.
        channel = get_channel_from_narrow_access_unchecked(narrow, user_profile.realm)
        if channel is not None:
            channel_id = channel.id
    except Stream.DoesNotExist:
        pass

    # Channel-level muting only applies when looking at views that
    # include multiple channels, since we do want users to be able to
    # browser messages within a muted channel.
    if channel_id is None:
        rows = Subscription.objects.filter(
            user_profile=user_profile,
            active=True,
            is_muted=True,
            recipient__type=Recipient.STREAM,
        ).values("recipient_id")
        muted_recipient_ids = [row["recipient_id"] for row in rows]
        if len(muted_recipient_ids) > 0:
            # Only add the condition if we have muted channels to simplify/avoid warnings.
            condition = not_(column("recipient_id", Integer).in_(muted_recipient_ids))
            conditions.append(condition)

    conditions = exclude_topic_mutes(conditions, user_profile, channel_id)

    # Muted user logic for hiding messages is implemented entirely
    # client-side. This is by design, as it allows UI to hint that
    # muted messages exist where their absence might make conversation
    # difficult to understand. As a result, we do not need to consider
    # muted users in this server-side logic for returning messages to
    # clients. (We could in theory exclude direct messages from muted
    # users, but they're likely to be sufficiently rare to not be worth
    # extra logic/testing here).

    return conditions


def get_base_query_for_search(
    realm_id: int, user_profile: Optional[UserProfile], need_message: bool, need_user_message: bool
) -> Tuple[Select, ColumnElement[Integer]]:
    # Handle the simple case where user_message isn't involved first.
    if not need_user_message:
        assert need_message
        query = (
            select(column("id", Integer).label("message_id"))
            .select_from(table("zerver_message"))
            .where(column("realm_id", Integer) == literal(realm_id))
        )

        inner_msg_id_col = literal_column("zerver_message.id", Integer)
        return (query, inner_msg_id_col)

    assert user_profile is not None
    if need_message:
        query = (
            select(column("message_id", Integer), column("flags", Integer))
            # We don't limit by realm_id despite the join to
            # zerver_messages, since the user_profile_id limit in
            # usermessage is more selective, and the query planner
            # can't know about that cross-table correlation.
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
        realm_id=user_profile.realm_id,
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


def limit_query_to_range(
    query: Select,
    num_before: int,
    num_after: int,
    anchor: int,
    include_anchor: bool,
    anchored_to_left: bool,
    anchored_to_right: bool,
    id_col: ColumnElement[Integer],
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
    # num_before = number of rows < anchor
    # num_after = number of rows > anchor
    #
    # But we may also want the row where id == anchor (if it exists),
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
        before_anchor = anchor - (not include_anchor)
        before_limit = num_before
        if not anchored_to_right:
            before_limit += include_anchor
    elif need_after_query:
        after_anchor = max(anchor + (not include_anchor), first_visible_message_id)
        after_limit = num_after + include_anchor

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


MessageRowT = TypeVar("MessageRowT", bound=Sequence[Any])


@dataclass
class LimitedMessages(Generic[MessageRowT]):
    rows: List[MessageRowT]
    found_anchor: bool
    found_newest: bool
    found_oldest: bool
    history_limited: bool


def post_process_limited_query(
    rows: Sequence[MessageRowT],
    num_before: int,
    num_after: int,
    anchor: int,
    anchored_to_left: bool,
    anchored_to_right: bool,
    first_visible_message_id: int,
) -> LimitedMessages[MessageRowT]:
    # Our queries may have fetched extra rows if they added
    # "headroom" to the limits, but we want to truncate those
    # rows.
    #
    # Also, in cases where we had non-zero values of num_before or
    # num_after, we want to know found_oldest and found_newest, so
    # that the clients will know that they got complete results.

    if first_visible_message_id > 0:
        visible_rows: Sequence[MessageRowT] = [r for r in rows if r[0] >= first_visible_message_id]
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

    limited_rows = [*before_rows, *anchor_rows, *after_rows]

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

    return LimitedMessages(
        rows=limited_rows,
        found_anchor=found_anchor,
        found_newest=found_newest,
        found_oldest=found_oldest,
        history_limited=history_limited,
    )


@dataclass
class FetchedMessages(LimitedMessages[Row]):
    anchor: int
    include_history: bool
    is_search: bool


def fetch_messages(
    *,
    narrow: OptionalNarrowListT,
    user_profile: Optional[UserProfile],
    realm: Realm,
    is_web_public_query: bool,
    anchor: Optional[int],
    include_anchor: bool,
    num_before: int,
    num_after: int,
) -> FetchedMessages:
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
        realm_id=realm.id,
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
            include_anchor=include_anchor,
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

    return FetchedMessages(
        rows=query_info.rows,
        found_anchor=query_info.found_anchor,
        found_newest=query_info.found_newest,
        found_oldest=query_info.found_oldest,
        history_limited=query_info.history_limited,
        anchor=anchor,
        include_history=include_history,
        is_search=is_search,
    )
