from __future__ import absolute_import

import datetime
import time
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now
from django.utils.translation import ugettext as _

from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import get_status_dict, update_user_presence
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_bool
from zerver.models import UserActivity, UserPresence, UserProfile

def get_status_list(requesting_user_profile):
    # type: (UserProfile) -> Dict[str, Any]
    return {'presences': get_status_dict(requesting_user_profile),
            'server_timestamp': time.time()}

@has_request_variables
def update_active_status_backend(request, user_profile, status=REQ(),
                                 new_user_input=REQ(validator=check_bool, default=False)):
    # type: (HttpRequest, UserProfile, str, bool) -> HttpResponse
    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError(_("Invalid presence status: %s") % (status,))
    else:
        update_user_presence(user_profile, request.client, now(), status_val,
                             new_user_input)

    ret = get_status_list(user_profile)
    if user_profile.realm.is_zephyr_mirror_realm:
        # Presence is disabled in zephyr mirroring realms
        try:
            activity = UserActivity.objects.get(user_profile = user_profile,
                                                query="get_events_backend",
                                                client__name="zephyr_mirror")

            ret['zephyr_mirror_active'] = \
                (activity.last_visit.replace(tzinfo=None) >
                 datetime.datetime.utcnow() - datetime.timedelta(minutes=5))
        except UserActivity.DoesNotExist:
            ret['zephyr_mirror_active'] = False

    return json_success(ret)

@authenticated_json_post_view
def json_get_active_statuses(request, user_profile):
    # type: (HttpRequest, UserProfile) -> HttpResponse
    return json_success(get_status_list(user_profile))
