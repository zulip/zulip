from datetime import timedelta

from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from django.http import HttpResponse, HttpRequest

from zerver.decorator import require_realm_admin
from zerver.models import RealmAuditLog, UserProfile
from zerver.lib.queue import queue_json_publish
from zerver.lib.response import json_error, json_success

@require_realm_admin
def public_only_realm_export(request: HttpRequest, user: UserProfile) -> HttpResponse:
    event_type = RealmAuditLog.REALM_EXPORTED
    event_time = timezone_now()
    realm = user.realm
    time_delta_limit = 5
    event_time_delta = event_time - timedelta(days=7)

    # Filter based upon the number of events that have occurred in the delta
    # If we are at the limit, the incoming request is rejected
    limit_check = RealmAuditLog.objects.filter(realm=realm,
                                               event_type=event_type,
                                               event_time__gte=event_time_delta)
    if len(limit_check) >= time_delta_limit:
        return json_error(_('Exceeded rate limit.'))

    # Using the deferred_work queue processor to avoid killing the process after 60s
    event = {'type': event_type,
             'time': event_time,
             'realm_id': realm.id,
             'user_profile_id': user.id}
    queue_json_publish('deferred_work', event)

    RealmAuditLog.objects.create(realm=realm,
                                 event_type=event_type,
                                 event_time=event_time)

    return json_success()
