from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.hotspots import do_mark_hotspot_as_read
from zerver.decorator import human_users_only
from zerver.lib.exceptions import JsonableError
from zerver.lib.hotspots import ALL_HOTSPOTS
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile


@human_users_only
@has_request_variables
def mark_hotspot_as_read(
    request: HttpRequest, user: UserProfile, hotspot: str = REQ()
) -> HttpResponse:
    if hotspot not in ALL_HOTSPOTS:
        raise JsonableError(_("Unknown hotspot: {hotspot}").format(hotspot=hotspot))
    do_mark_hotspot_as_read(user, hotspot)
    return json_success(request)
