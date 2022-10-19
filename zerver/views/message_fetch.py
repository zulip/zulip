from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.utils.html import escape as escape_html
from django.utils.translation import gettext as _
from sqlalchemy.engine import Connection, Row
from sqlalchemy.sql import (
    ColumnElement,
    Select,
    and_,
    column,
    join,
    literal,
    literal_column,
    select,
    table,
    union_all,
)
from sqlalchemy.sql.selectable import SelectBase
from sqlalchemy.types import Integer, Text

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.exceptions import JsonableError, MissingAuthenticationError
from zerver.lib.message import get_first_visible_message_id, messages_for_ids
from zerver.lib.narrow import (
    NarrowBuilder,
    OptionalNarrowListT,
    add_narrow_conditions,
    exclude_muting_conditions,
    get_base_query_for_search,
    is_spectator_compatible,
    is_web_public_narrow,
    narrow_parameter,
    ok_to_include_history,
)
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.topic import DB_TOPIC_NAME, MATCH_TOPIC, topic_column_sa
from zerver.lib.utils import statsd
from zerver.lib.validator import check_bool, check_int, check_list, to_non_negative_int
from zerver.models import Realm, UserMessage, UserProfile

LARGER_THAN_MAX_MESSAGE_ID = 10000000000000000
MAX_MESSAGES_PER_FETCH = 5000


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
        # non-web-public stream messages) via this path.
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
            search_fields[message_id] = get_search_fields(
                rendered_content, topic_name, content_matches, topic_matches
            )

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
