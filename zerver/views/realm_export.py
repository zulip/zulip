from datetime import timedelta

from analytics.models import RealmCount

from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.utils.translation import ugettext as _
from django.http import HttpResponse, HttpRequest

from zerver.decorator import require_realm_admin
from zerver.models import RealmAuditLog, UserProfile
from zerver.lib.queue import queue_json_publish
from zerver.lib.response import json_error, json_success
from zerver.lib.export import get_realm_exports_serialized
from zerver.lib.actions import do_delete_realm_export

import ujson

@require_realm_admin
def export_realm(request: HttpRequest, user: UserProfile) -> HttpResponse:
    # Currently only supports public-data-only exports.
    event_type = RealmAuditLog.REALM_EXPORTED
    event_time = timezone_now()
    realm = user.realm
    EXPORT_LIMIT = 5
    # Conservative limit on the size of message history in
    # organizations being exported; this exists to protect Zulip
    # against a possible unmonitored accidental DoS caused by trying
    # to export an organization with huge history.
    MAX_MESSAGE_HISTORY = 250000
    MAX_UPLOAD_QUOTA = 10 * 1024 * 1024 * 1024

    # Filter based upon the number of events that have occurred in the delta
    # If we are at the limit, the incoming request is rejected
    event_time_delta = event_time - timedelta(days=7)
    limit_check = RealmAuditLog.objects.filter(realm=realm,
                                               event_type=event_type,
                                               event_time__gte=event_time_delta)
    if len(limit_check) >= EXPORT_LIMIT:
        return json_error(_('Exceeded rate limit.'))

    total_messages = sum(realm_count.value for realm_count in
                         RealmCount.objects.filter(realm=user.realm,
                                                   property='messages_sent:client:day'))
    if (total_messages > MAX_MESSAGE_HISTORY or
            user.realm.currently_used_upload_space_bytes() > MAX_UPLOAD_QUOTA):
        return json_error(_('Please request a manual export from %s.') % (
            settings.ZULIP_ADMINISTRATOR,))

    row = RealmAuditLog.objects.create(realm=realm,
                                       event_type=event_type,
                                       event_time=event_time,
                                       acting_user=user)
    # Using the deferred_work queue processor to avoid
    # killing the process after 60s
    event = {'type': "realm_export",
             'time': event_time,
             'realm_id': realm.id,
             'user_profile_id': user.id,
             'id': row.id}
    queue_json_publish('deferred_work', event)
    return json_success()

@require_realm_admin
def get_realm_exports(request: HttpRequest, user: UserProfile) -> HttpResponse:
    realm_exports = get_realm_exports_serialized(user)
    return json_success({"exports": realm_exports})

@require_realm_admin
def delete_realm_export(request: HttpRequest, user: UserProfile, export_id: int) -> HttpResponse:
    try:
        audit_log_entry = RealmAuditLog.objects.get(id=export_id,
                                                    realm=user.realm,
                                                    event_type=RealmAuditLog.REALM_EXPORTED)
    except RealmAuditLog.DoesNotExist:
        return json_error(_("Invalid data export ID"))

    export_data = ujson.loads(audit_log_entry.extra_data)
    if 'deleted_timestamp' in export_data:
        return json_error(_("Export already deleted"))
    do_delete_realm_export(user, audit_log_entry)
    return json_success()
