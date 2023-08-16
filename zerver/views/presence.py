import datetime
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints
from typing_extensions import Annotated

from zerver.actions.presence import update_user_presence
from zerver.actions.user_status import do_update_user_status
from zerver.decorator import human_users_only
from zerver.lib.emoji import check_emoji_request, get_emoji_data
from zerver.lib.exceptions import JsonableError
from zerver.lib.presence import get_presence_for_user, get_presence_response
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.models import (
    UserActivity,
    UserPresence,
    UserProfile,
    UserStatus,
    get_active_user,
    get_active_user_profile_by_id_in_realm,
)


def get_presence_backend(
    request: HttpRequest, user_profile: UserProfile, user_id_or_email: str
) -> HttpResponse:
    # This isn't used by the web app; it's available for API use by
    # bots and other clients.  We may want to add slim_presence
    # support for it (or just migrate its API wholesale) later.

    try:
        try:
            user_id = int(user_id_or_email)
            target = get_active_user_profile_by_id_in_realm(user_id, user_profile.realm)
        except ValueError:
            email = user_id_or_email
            target = get_active_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("No such user"))

    if target.is_bot:
        raise JsonableError(_("Presence is not supported for bot users."))

    presence_dict = get_presence_for_user(target.id)
    if len(presence_dict) == 0:
        raise JsonableError(
            _("No presence data for {user_id_or_email}").format(user_id_or_email=user_id_or_email)
        )

    # For initial version, we just include the status and timestamp keys
    result = dict(presence=presence_dict[target.email])
    aggregated_info = result["presence"]["aggregated"]
    aggr_status_duration = datetime_to_timestamp(timezone_now()) - aggregated_info["timestamp"]
    if aggr_status_duration > settings.OFFLINE_THRESHOLD_SECS:
        aggregated_info["status"] = "offline"
    for val in result["presence"].values():
        val.pop("client", None)
        val.pop("pushable", None)
    return json_success(request, data=result)


@human_users_only
@typed_endpoint
def update_user_status_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    away: Optional[Json[bool]] = None,
    status_text: Annotated[
        Optional[str], StringConstraints(strip_whitespace=True, max_length=60)
    ] = None,
    emoji_name: Optional[str] = None,
    emoji_code: Optional[str] = None,
    # TODO: emoji_type is the more appropriate name for this parameter, but changing
    # that requires nontrivial work on the API documentation, since it's not clear
    # that the reactions endpoint would prefer such a change.
    emoji_type: Annotated[Optional[str], ApiParamConfig("reaction_type")] = None,
) -> HttpResponse:
    if status_text is not None:
        status_text = status_text.strip()

    if (away is None) and (status_text is None) and (emoji_name is None):
        raise JsonableError(_("Client did not pass any new values."))

    if emoji_name == "":
        # Reset the emoji_code and reaction_type if emoji_name is empty.
        # This should clear the user's configured emoji.
        emoji_code = ""
        emoji_type = UserStatus.UNICODE_EMOJI

    elif emoji_name is not None:
        if emoji_code is None or emoji_type is None:
            emoji_data = get_emoji_data(user_profile.realm_id, emoji_name)
            if emoji_code is None:
                # The emoji_code argument is only required for rare corner
                # cases discussed in the long block comment below.  For simple
                # API clients, we allow specifying just the name, and just
                # look up the code using the current name->code mapping.
                emoji_code = emoji_data.emoji_code

            if emoji_type is None:
                emoji_type = emoji_data.reaction_type

    elif emoji_type or emoji_code:
        raise JsonableError(
            _("Client must pass emoji_name if they pass either emoji_code or reaction_type.")
        )

    # If we're asking to set an emoji (not clear it ("") or not adjust
    # it (None)), we need to verify the emoji is valid.
    if emoji_name not in ["", None]:
        assert emoji_name is not None
        assert emoji_code is not None
        assert emoji_type is not None
        check_emoji_request(user_profile.realm, emoji_name, emoji_code, emoji_type)

    client = RequestNotes.get_notes(request).client
    assert client is not None
    do_update_user_status(
        user_profile=user_profile,
        away=away,
        status_text=status_text,
        client_id=client.id,
        emoji_name=emoji_name,
        emoji_code=emoji_code,
        reaction_type=emoji_type,
    )

    return json_success(request)


@human_users_only
@typed_endpoint
def update_active_status_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    status: str,
    ping_only: Json[bool] = False,
    new_user_input: Json[bool] = False,
    slim_presence: Json[bool] = False,
) -> HttpResponse:
    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError(_("Invalid status: {status}").format(status=status))
    elif user_profile.presence_enabled:
        client = RequestNotes.get_notes(request).client
        assert client is not None
        update_user_presence(user_profile, client, timezone_now(), status_val, new_user_input)

    if ping_only:
        ret: Dict[str, Any] = {}
    else:
        ret = get_presence_response(user_profile, slim_presence)

    if user_profile.realm.is_zephyr_mirror_realm:
        # In zephyr mirroring realms, users can't see the presence of other
        # users, but each user **is** interested in whether their mirror bot
        # (running as their user) has been active.
        try:
            activity = UserActivity.objects.get(
                user_profile=user_profile, query="get_events", client__name="zephyr_mirror"
            )

            ret["zephyr_mirror_active"] = activity.last_visit > timezone_now() - datetime.timedelta(
                minutes=5
            )
        except UserActivity.DoesNotExist:
            ret["zephyr_mirror_active"] = False

    return json_success(request, data=ret)


def get_statuses_for_realm(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # This isn't used by the web app; it's available for API use by
    # bots and other clients.  We may want to add slim_presence
    # support for it (or just migrate its API wholesale) later.
    return json_success(request, data=get_presence_response(user_profile, slim_presence=False))
