from typing import Dict, Iterable, List, Optional, Tuple, Union

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import connection, transaction
from django.http import HttpRequest, HttpResponse
from django.utils.html import escape as escape_html
from django.utils.translation import gettext as _
from sqlalchemy.sql import and_, column, join, literal, literal_column, select, table
from sqlalchemy.types import Integer, Text

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.exceptions import JsonableError, MissingAuthenticationError
from zerver.lib.message import get_first_visible_message_id, messages_for_ids
from zerver.lib.narrow import (
    OptionalNarrowListT,
    add_narrow_conditions,
    fetch_messages,
    is_spectator_compatible,
    is_web_public_narrow,
    narrow_parameter,
    parse_anchor_value,
)
from zerver.lib.request import REQ, RequestNotes, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.topic import DB_TOPIC_NAME, MATCH_TOPIC
from zerver.lib.topic_sqlalchemy import topic_column_sa
from zerver.lib.validator import check_bool, check_int, check_list, to_non_negative_int
from zerver.models import UserMessage, UserProfile

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


def clean_narrow_for_web_public_api(narrow: OptionalNarrowListT) -> OptionalNarrowListT:
    if narrow is None:
        return None

    # Remove {'operator': 'in', 'operand': 'home', 'negated': False} from narrow.
    # This is to allow spectators to access all messages. The narrow should still pass
    # is_web_public_narrow check after this change.
    return [
        term
        for term in narrow
        if not (term["operator"] == "in" and term["operand"] == "home" and not term["negated"])
    ]


@has_request_variables
def get_messages_backend(
    request: HttpRequest,
    maybe_user_profile: Union[UserProfile, AnonymousUser],
    anchor_val: Optional[str] = REQ("anchor", default=None),
    include_anchor: bool = REQ(json_validator=check_bool, default=True),
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
            _("Too many messages requested (maximum {max_messages}).").format(
                max_messages=MAX_MESSAGES_PER_FETCH,
            )
        )
    if num_before > 0 and num_after > 0 and not include_anchor:
        raise JsonableError(_("The anchor can only be excluded at an end of the range"))

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
        # that we are not leaking any secure data (direct messages and
        # non-web-public stream messages) via this path.
        if not realm.allow_web_public_streams_access():
            raise MissingAuthenticationError
        narrow = clean_narrow_for_web_public_api(narrow)
        if not is_web_public_narrow(narrow):
            raise MissingAuthenticationError
        assert narrow is not None
        if not is_spectator_compatible(narrow):
            raise MissingAuthenticationError

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

    if is_web_public_query:
        # client_gravatar here is just the user-requested value. "finalize_payload" function
        # is responsible for sending avatar_url based on each individual sender's
        # email_address_visibility setting.
        client_gravatar = False

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

    with transaction.atomic(durable=True):
        # We're about to perform a search, and then get results from
        # it; this is done across multiple queries.  To prevent race
        # conditions, we want the messages returned to be consistent
        # with the version of the messages that was searched, to
        # prevent changes which happened between them from leaking to
        # clients who should not be able to see the new values, and
        # when messages are deleted in between.  We set up
        # repeatable-read isolation for this transaction, so that we
        # prevent both phantom reads and non-repeatable reads.
        #
        # In a read-only repeatable-read transaction, it is not
        # possible to encounter deadlocks or need retries due to
        # serialization errors.
        #
        # You can only set the isolation level before any queries in
        # the transaction, meaning it must be the top-most
        # transaction, which durable=True establishes.  Except in
        # tests, where durable=True is a lie, because there is an
        # outer transaction for each test.  We thus skip this command
        # in tests, since it would fail.
        if not settings.TEST_SUITE:  # nocoverage
            cursor = connection.cursor()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        query_info = fetch_messages(
            narrow=narrow,
            user_profile=user_profile,
            realm=realm,
            is_web_public_query=is_web_public_query,
            anchor=anchor,
            include_anchor=include_anchor,
            num_before=num_before,
            num_after=num_after,
        )

        anchor = query_info.anchor
        include_history = query_info.include_history
        is_search = query_info.is_search
        rows = query_info.rows

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
            um_rows = UserMessage.objects.filter(
                user_profile=user_profile, message_id__in=message_ids
            )
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
            user_profile=user_profile,
            realm=realm,
        )

    ret = dict(
        messages=message_list,
        result="success",
        msg="",
        found_anchor=query_info.found_anchor,
        found_oldest=query_info.found_oldest,
        found_newest=query_info.found_newest,
        history_limited=query_info.history_limited,
        anchor=anchor,
    )
    return json_success(request, data=ret)


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
        select(column("message_id", Integer))
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

    inner_msg_id_col = column("message_id", Integer)
    query, is_search = add_narrow_conditions(
        user_profile=user_profile,
        inner_msg_id_col=inner_msg_id_col,
        query=query,
        narrow=narrow,
        is_web_public_query=False,
        realm=user_profile.realm,
    )

    if not is_search:
        # `add_narrow_conditions` adds the following columns only if narrow has search operands.
        query = query.add_columns(topic_column_sa(), column("rendered_content", Text))

    search_fields = {}
    with get_sqlalchemy_connection() as sa_conn:
        for row in sa_conn.execute(query).mappings():
            message_id = row["message_id"]
            topic_name: str = row[DB_TOPIC_NAME]
            rendered_content: str = row["rendered_content"]
            content_matches = row.get("content_matches", [])
            topic_matches = row.get("topic_matches", [])
            search_fields[str(message_id)] = get_search_fields(
                rendered_content,
                topic_name,
                content_matches,
                topic_matches,
            )

    return json_success(request, data={"messages": search_fields})
