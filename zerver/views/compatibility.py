from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.lib.compatibility import find_mobile_os, version_lt
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.user_agent import parse_user_agent

# Zulip Mobile release 16.2.96 was made 2018-08-22.  It fixed a
# bug in our Android code that causes spammy, obviously-broken
# notifications once the "remove_push_notification" feature is
# enabled on the user's Zulip server.
android_min_app_version = "16.2.96"


def check_global_compatibility(request: HttpRequest) -> HttpResponse:
    if "User-Agent" not in request.headers:
        raise JsonableError(_("User-Agent header missing from request"))

    # This string should not be tagged for translation, since old
    # clients are checking for an extra string.
    legacy_compatibility_error_message = "Client is too old"
    user_agent = parse_user_agent(request.headers["User-Agent"])
    if user_agent["name"] == "ZulipInvalid":
        raise JsonableError(legacy_compatibility_error_message)
    if user_agent["name"] == "ZulipMobile":
        user_os = find_mobile_os(request.headers["User-Agent"])
        if user_os == "android" and version_lt(user_agent["version"], android_min_app_version):
            raise JsonableError(legacy_compatibility_error_message)
    return json_success(request)
