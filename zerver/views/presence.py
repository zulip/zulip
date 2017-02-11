from __future__ import absolute_import

import datetime
import time
from typing import Any, Text

from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.utils.translation import ugettext as _

from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import get_status_dict, update_user_presence
from zerver.lib.request import has_request_variables, REQ, JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_bool
from zerver.models import UserActivity, UserPresence, UserProfile, \
    get_user_profile_by_email

def get_status_list(requesting_user_profile):
    # type: (UserProfile) -> Dict[str, Any]
    return {'presences': get_status_dict(requesting_user_profile),
            'server_timestamp': time.time()}

def get_presence_backend(request, user_profile, email):
    # type: (HttpRequest, UserProfile, Text) -> HttpResponse
    try:
        target = get_user_profile_by_email(email)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))
    if target.realm != user_profile.realm:
        return json_error(_('No such user'))
    if not target.is_active:
        return json_error(_('No such user'))
    if target.is_bot:
        return json_error(_('No presence for bot users'))

    presence_dict = UserPresence.get_status_dict_by_user(target)
    if len(presence_dict) == 0:
        return json_error(_('No presence data for %s' % (target.email,)))

    # For initial version, we just include the status and timestamp keys
    result = dict(presence=presence_dict[target.email])
    for val in result['presence'].values():
        del val['client']
        del val['pushable']
    return json_success(result)

@has_request_variables
def update_active_status_backend(request, user_profile, status=REQ(),
                                 new_user_input=REQ(validator=check_bool, default=False)):
    # type: (HttpRequest, UserProfile, str, bool) -> HttpResponse
    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError(_("Invalid status: %s") % (status,))
    else:
        update_user_presence(user_profile, request.client, timezone.now(),
                             status_val, new_user_input)

    ret = get_status_list(user_profile)
    if user_profile.realm.is_zephyr_mirror_realm:
        # In zephyr mirroring realms, users can't see the presence of other
        # users, but each user **is** interested in whether their mirror bot
        # (running as their user) has been active.
        try:
            activity = UserActivity.objects.get(user_profile = user_profile,
                                                query="get_events_backend",
                                                client__name="zephyr_mirror")

            ret['zephyr_mirror_active'] = \
                (activity.last_visit > timezone.now() - datetime.timedelta(minutes=5))
        except UserActivity.DoesNotExist:
            ret['zephyr_mirror_active'] = False

    return json_success(ret)
