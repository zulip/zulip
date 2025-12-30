from typing import Annotated

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from pydantic import Json
from sqlalchemy.sql import func, select

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.exceptions import MissingAuthenticationError
from zerver.lib.narrow import (
    NarrowParameter,
    add_narrow_conditions,
    clean_narrow_for_message_fetch,
    get_base_query_for_search,
    is_spectator_compatible,
    is_web_public_narrow,
    ok_to_include_history,
    parse_anchor_value,
)
from zerver.lib.response import json_success
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def get_message_count_backend(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    *,
    narrow: Json[list[NarrowParameter] | None] = None,
    anchor_val: Annotated[str | None, ApiParamConfig("anchor")] = None,
    include_anchor: Json[bool] = True,
) -> HttpResponse:
    realm = get_valid_realm_from_request(request)

    if not maybe_user_profile.is_authenticated:
        if not realm.allow_web_public_streams_access():
            raise MissingAuthenticationError
        
        # spectactor queries are only allowed for web-public streams
        from zerver.views.message_fetch import clean_narrow_for_web_public_api
        narrow = clean_narrow_for_web_public_api(narrow)
        if not is_web_public_narrow(narrow):
            raise MissingAuthenticationError
        if not is_spectator_compatible(narrow):
            raise MissingAuthenticationError

        user_profile: UserProfile | None = None
        is_web_public_query = True
    else:
        assert isinstance(maybe_user_profile, UserProfile)
        user_profile = maybe_user_profile
        is_web_public_query = False

    narrow = clean_narrow_for_message_fetch(narrow, realm, maybe_user_profile)

    anchor = None
    if anchor_val is not None:
        anchor = parse_anchor_value(anchor_val, False)

    include_history = ok_to_include_history(narrow, user_profile, is_web_public_query)
    need_user_message = not include_history

    query, inner_msg_id_col = get_base_query_for_search(
        realm_id=realm.id,
        user_profile=user_profile,
        need_user_message=need_user_message,
    )

    query, _is_search, _is_dm_narrow = add_narrow_conditions(
        user_profile=user_profile,
        inner_msg_id_col=inner_msg_id_col,
        query=query,
        narrow=narrow,
        realm=realm,
        is_web_public_query=is_web_public_query,
    )

    if anchor is not None:
        if include_anchor:
            query = query.where(inner_msg_id_col >= anchor)
        else:
            query = query.where(inner_msg_id_col > anchor)

    # Use a subquery to count results to handle any complexity in the narrow query.
    count_query = select(func.count()).select_from(query.subquery())

    with get_sqlalchemy_connection() as sa_conn:
        count = sa_conn.execute(count_query).scalar()

    return json_success(request, data={"count": count})
