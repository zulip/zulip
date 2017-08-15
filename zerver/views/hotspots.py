from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _, ugettext as err_

from zerver.decorator import has_request_variables, REQ, human_users_only
from zerver.lib.actions import do_mark_hotspot_as_read
from zerver.lib.hotspots import ALL_HOTSPOTS
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_string
from zerver.models import UserProfile

@human_users_only
@has_request_variables
def mark_hotspot_as_read(request, user, hotspot=REQ(validator=check_string)):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if hotspot not in ALL_HOTSPOTS:
        return json_error(err_('Unknown hotspot: %s') % (hotspot,))
    do_mark_hotspot_as_read(user, hotspot)
    return json_success()
