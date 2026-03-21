from typing import Annotated, Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from zerver.actions.presence import update_user_presence
from zerver.actions.user_status import do_update_user_status
from zerver.decorator import human_users_only
from zerver.lib.exceptions import JsonableError
from zerver.lib.presence import get_presence_for_user, get_presence_response
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.typed_endpoint import ApiParamConfig, PathOnly, typed_endpoint
from zerver.lib.user_status import check_update_user_status, get_user_status
from zerver.lib.users import access_user_by_id, check_can_access_user
from zerver.models import UserPresence, UserProfile
from zerver.models.users import get_active_user, get_active_user_profile_by_id_in_realm


@typed_endpoint
def get_presence_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    user_id_or_email: PathOnly[str],
    *,
    slim_presence: Json[bool] = False,
) -> HttpResponse:
    # This endpoint is available for API use by bots and other clients.
    # It's most useful for embedding presence data in external sites.

    try:
        try:
            user_id = int(user_id_or_email)
            target = get_active_user_profile_by_id_in_realm(user_id, user_profile.realm)
        except ValueError:
            email = user_id_or_email
            target = get_active_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such user"))

    # Check bot_type here, rather than is_bot, because that matches
    # authenticated_json_view's check of .is_incoming_webhook; the
    # narrow user cache can hence be optimized to only have the
    # nullable bot_type, as long as this check matches.
    if target.bot_type is not None:
        raise JsonableError(_("Presence is not supported for bot users."))

    if settings.CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE and not check_can_access_user(
        target, user_profile
    ):
        raise JsonableError(_("Insufficient permission"))

    presence_dict = get_presence_for_user(target.id, slim_presence)
    if len(presence_dict) == 0:
        raise JsonableError(
            _("No presence data for {user_id_or_email}").format(user_id_or_email=user_id_or_email)
        )

    if slim_presence:
        # Modern format: data is keyed by user_id, contains active_timestamp/idle_timestamp
        result = dict(presence=presence_dict[str(target.id)])
    else:
        # Legacy format: data is keyed by email, requires additional processing
        result = dict(presence=presence_dict[target.email])
        aggregated_info = result["presence"]["aggregated"]
        aggr_status_duration = datetime_to_timestamp(timezone_now()) - aggregated_info["timestamp"]
        if aggr_status_duration > settings.OFFLINE_THRESHOLD_SECS:
            aggregated_info["status"] = "offline"
        for val in result["presence"].values():
            val.pop("client", None)
            val.pop("pushable", None)

    return json_success(request, data=result)


def get_status_backend(
    request: HttpRequest, user_profile: UserProfile, user_id: int
) -> HttpResponse:
    target_user = access_user_by_id(user_profile, user_id, allow_bots=False, for_admin=False)
    return json_success(request, data={"status": get_user_status(target_user)})


@human_users_only
@typed_endpoint
def update_user_status_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    away: Json[bool] | None = None,
    emoji_code: str | None = None,
    emoji_name: str | None = None,
    # TODO: emoji_type is the more appropriate name for this parameter, but changing
    # that requires nontrivial work on the API documentation, since it's not clear
    # that the reactions endpoint would prefer such a change.
    emoji_type: Annotated[str | None, ApiParamConfig("reaction_type")] = None,
    status_text: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=60)
    ] = None,
) -> HttpResponse:
    user_status = check_update_user_status(
        user_profile.realm,
        away=away,
        status_text=status_text,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        emoji_type=emoji_type,
    )

    client = RequestNotes.get_notes(request).client
    assert client is not None
    do_update_user_status(
        user_profile=user_profile,
        away=away,
        status_text=user_status.status_text,
        client_id=client.id,
        emoji_name=user_status.emoji_name,
        emoji_code=user_status.emoji_code,
        reaction_type=user_status.reaction_type,
    )

    return json_success(request)


@typed_endpoint
def update_user_status_admin(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_id: PathOnly[Json[int]],
    status_text: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=60)
    ] = None,
    emoji_name: str | None = None,
    emoji_code: str | None = None,
    emoji_type: Annotated[str | None, ApiParamConfig("reaction_type")] = None,
) -> HttpResponse:
    target_user = access_user_by_id(user_profile, user_id, allow_bots=False, for_admin=True)

    user_status = check_update_user_status(
        target_user.realm,
        status_text=status_text,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        emoji_type=emoji_type,
    )

    client = RequestNotes.get_notes(request).client
    assert client is not None
    do_update_user_status(
        user_profile=target_user,
        away=None,
        status_text=user_status.status_text,
        client_id=client.id,
        emoji_name=user_status.emoji_name,
        emoji_code=user_status.emoji_code,
        reaction_type=user_status.reaction_type,
    )

    return json_success(request)


@human_users_only
@typed_endpoint
def update_active_status_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    history_limit_days: Json[int] | None = None,
    last_update_id: Json[int] | None = None,
    new_user_input: Json[bool] = False,
    ping_only: Json[bool] = False,
    slim_presence: Json[bool] = False,
    status: str,
) -> HttpResponse:
    if last_update_id is not None:
        # This param being submitted by the client, means they want to use
        # the modern API.
        slim_presence = True

    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError(_("Invalid status: {status}").format(status=status))

    client = RequestNotes.get_notes(request).client
    assert client is not None
    update_user_presence(user_profile, client, timezone_now(), status_val, new_user_input)

    if ping_only:
        ret: dict[str, Any] = {}
    else:
        ret = get_presence_response(
            user_profile,
            slim_presence,
            last_update_id_fetched_by_client=last_update_id,
            history_limit_days=history_limit_days,
        )

    return json_success(request, data=ret)


def get_statuses_for_realm(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # This isn't used by the web app; it's available for API use by
    # bots and other clients.  We may want to add slim_presence
    # support for it (or just migrate its API wholesale) later.
    data = get_presence_response(user_profile, slim_presence=False)

    # We're not interested in the last_update_id field in this context.
    data.pop("presence_last_update_id", None)
    return json_success(request, data=data)
