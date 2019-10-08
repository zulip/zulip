from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from zerver.lib.bot_storage import (
    get_bot_storage,
    set_bot_storage,
    remove_bot_storage,
    get_keys_in_bot_storage,
    is_key_in_bot_storage,
    StateError,
)
from zerver.decorator import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_dict, check_list, check_string
from zerver.models import UserProfile

from typing import Dict, List, Optional

@has_request_variables
def update_storage(request: HttpRequest, user_profile: UserProfile,
                   storage: Dict[str, str]=REQ(validator=check_dict([]))) -> HttpResponse:
    try:
        set_bot_storage(user_profile, list(storage.items()))
    except StateError as e:
        return json_error(str(e))
    return json_success()

@has_request_variables
def get_storage(
        request: HttpRequest,
        user_profile: UserProfile,
        keys: Optional[List[str]]=REQ(validator=check_list(check_string), default=None)
) -> HttpResponse:
    keys = keys or get_keys_in_bot_storage(user_profile)
    try:
        storage = {key: get_bot_storage(user_profile, key) for key in keys}
    except StateError as e:
        return json_error(str(e))
    return json_success({'storage': storage})

@has_request_variables
def remove_storage(
        request: HttpRequest,
        user_profile: UserProfile,
        keys: Optional[List[str]]=REQ(validator=check_list(check_string), default=None)
) -> HttpResponse:
    keys = keys or get_keys_in_bot_storage(user_profile)
    try:
        remove_bot_storage(user_profile, keys)
    except StateError as e:
        return json_error(str(e))
    return json_success()
