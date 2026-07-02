from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.actions.direct_message_groups import do_set_direct_message_group_pin
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def update_dm_conversation_pin(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_ids: Json[list[int]],
    pinned: Json[bool],
) -> HttpResponse:
    do_set_direct_message_group_pin(user_profile, user_ids, pinned=pinned)
    return json_success(request)
