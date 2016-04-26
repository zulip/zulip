from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt

from zerver.lib.response import json_success, json_error
from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji

from zerver.lib.rest import rest_dispatch as _rest_dispatch
rest_dispatch = csrf_exempt((lambda request, *args, **kwargs: _rest_dispatch(request, globals(), *args, **kwargs)))


def list_emoji(request, user_profile):
    return json_success({'emoji': user_profile.realm.get_emoji()})

def upload_emoji(request, user_profile):
    emoji_name = request.POST.get('name', None)
    emoji_url = request.POST.get('url', None)
    try:
        check_add_realm_emoji(user_profile.realm, emoji_name, emoji_url)
    except ValidationError as e:
        return json_error(e.message_dict)
    return json_success()

def delete_emoji(request, user_profile, emoji_name):
    do_remove_realm_emoji(user_profile.realm, emoji_name)
    return json_success({})
