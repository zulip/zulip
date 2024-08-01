from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.lib.bot_storage import (
    StateError,
    get_bot_storage,
    get_keys_in_bot_storage,
    remove_bot_storage,
    set_bot_storage,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def update_storage(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    storage: Json[dict[str, str]],
) -> HttpResponse:
    try:
        set_bot_storage(user_profile, list(storage.items()))
    except StateError as e:  # nocoverage
        raise JsonableError(str(e))
    return json_success(request)


@typed_endpoint
def get_storage(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    keys: Json[list[str] | None] = None,
) -> HttpResponse:
    if keys is None:
        keys = get_keys_in_bot_storage(user_profile)
    try:
        storage = {key: get_bot_storage(user_profile, key) for key in keys}
    except StateError as e:
        raise JsonableError(str(e))
    return json_success(request, data={"storage": storage})


@typed_endpoint
def remove_storage(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    keys: Json[list[str] | None] = None,
) -> HttpResponse:
    if keys is None:
        keys = get_keys_in_bot_storage(user_profile)
    try:
        remove_bot_storage(user_profile, keys)
    except StateError as e:
        raise JsonableError(str(e))
    return json_success(request)
