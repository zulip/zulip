from django.http import HttpRequest, HttpResponse
from django.core.exceptions import ValidationError

from zerver.models import UserProfile

from zerver.lib.response import json_success, json_error
from zerver.lib.actions import check_add_realm_emoji, do_remove_realm_emoji

from six import text_type

def list_emoji(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return json_success({'emoji': user_profile.realm.get_emoji()})

def upload_emoji(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    emoji_name = request.POST.get('name', None)
    emoji_url = request.POST.get('url', None)
    try:
        check_add_realm_emoji(user_profile.realm, emoji_name, emoji_url)
    except ValidationError as e:
        return json_error(e.messages[0])
    return json_success()

def delete_emoji(request, user_profile, emoji_name):
    # type: (HttpRequest, UserProfile, text_type) -> HttpResponse
    do_remove_realm_emoji(user_profile.realm, emoji_name)
    return json_success({})
