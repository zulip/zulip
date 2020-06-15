import datetime
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _

from zerver.decorator import human_users_only
from zerver.lib.actions import do_update_user_status, update_user_presence
from zerver.lib.presence import get_presence_for_user, get_presence_response
from zerver.lib.request import REQ, JsonableError, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.validator import check_bool, check_capped_string
from zerver.models import UserActivity, UserPresence, UserProfile, get_active_user


def get_presence_backend(request: HttpRequest, user_profile: UserProfile,
                         email: str) -> HttpResponse:
    # This isn't used by the webapp; it's available for API use by
    # bots and other clients.  We may want to add slim_presence
    # support for it (or just migrate its API wholesale) later.
    try:
        target = get_active_user(email, user_profile.realm)
    except UserProfile.DoesNotExist:
        return json_error(_('No such user'))
    if target.is_bot:
        return json_error(_('Presence is not supported for bot users.'))

    presence_dict = get_presence_for_user(target.id)
    if len(presence_dict) == 0:
        return json_error(_('No presence data for {email}').format(email=email))

    # For initial version, we just include the status and timestamp keys
    result = dict(presence=presence_dict[target.email])
    aggregated_info = result['presence']['aggregated']
    aggr_status_duration = datetime_to_timestamp(timezone_now()) - aggregated_info['timestamp']
    if aggr_status_duration > settings.OFFLINE_THRESHOLD_SECS:
        aggregated_info['status'] = 'offline'
    for val in result['presence'].values():
        val.pop('client', None)
        val.pop('pushable', None)
    return json_success(result)

@human_users_only
@has_request_variables
def update_user_status_backend(request: HttpRequest,
                               user_profile: UserProfile,
                               away: Optional[bool]=REQ(validator=check_bool, default=None),
                               status_text: Optional[str]=REQ(str_validator=check_capped_string(60),
                                                              default=None),
                               ) -> HttpResponse:

    if status_text is not None:
        status_text = status_text.strip()

    if (away is None) and (status_text is None):
        return json_error(_('Client did not pass any new values.'))

    do_update_user_status(
        user_profile=user_profile,
        away=away,
        status_text=status_text,
        client_id=request.client.id,
    )

    return json_success()

@human_users_only
@has_request_variables
def update_active_status_backend(request: HttpRequest, user_profile: UserProfile,
                                 status: str=REQ(),
                                 ping_only: bool=REQ(validator=check_bool, default=False),
                                 new_user_input: bool=REQ(validator=check_bool, default=False),
                                 slim_presence: bool=REQ(validator=check_bool, default=False),
                                 ) -> HttpResponse:
    status_val = UserPresence.status_from_string(status)
    if status_val is None:
        raise JsonableError(_("Invalid status: {}").format(status))
    elif user_profile.presence_enabled:
        update_user_presence(user_profile, request.client, timezone_now(),
                             status_val, new_user_input)

    if ping_only:
        ret: Dict[str, Any] = {}
    else:
        ret = get_presence_response(user_profile, slim_presence)

    if user_profile.realm.is_zephyr_mirror_realm:
        # In zephyr mirroring realms, users can't see the presence of other
        # users, but each user **is** interested in whether their mirror bot
        # (running as their user) has been active.
        try:
            activity = UserActivity.objects.get(user_profile = user_profile,
                                                query="get_events",
                                                client__name="zephyr_mirror")

            ret['zephyr_mirror_active'] = \
                (activity.last_visit > timezone_now() - datetime.timedelta(minutes=5))
        except UserActivity.DoesNotExist:
            ret['zephyr_mirror_active'] = False

    return json_success(ret)

def get_statuses_for_realm(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    # This isn't used by the webapp; it's available for API use by
    # bots and other clients.  We may want to add slim_presence
    # support for it (or just migrate its API wholesale) later.
    return json_success(get_presence_response(user_profile, slim_presence=False))
