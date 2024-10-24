from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from zerver.actions.topic_settings import do_set_topic_settings
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id, can_access_stream_user_ids
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile
from zerver.models.constants import MAX_TOPIC_NAME_LENGTH


@typed_endpoint
def update_topic_settings(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stream_id: Json[int],
    topic: Annotated[str, StringConstraints(max_length=MAX_TOPIC_NAME_LENGTH)],
    is_locked: Json[bool],
) -> HttpResponse:
    if not (user_profile.role == UserProfile.ROLE_MODERATOR or user_profile.is_realm_admin):
        raise JsonableError(_("Must be an organization moderator."))

    (stream, sub) = access_stream_by_id(user_profile, stream_id)
    user_ids = can_access_stream_user_ids(stream)
    do_set_topic_settings(
        user_profile, stream_id, topic, is_topic_locked=is_locked, users_to_notify=user_ids
    )
    return json_success(request)
