from datetime import timedelta
from typing import Annotated

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json

from analytics.models import RealmCount
from zerver.actions.realm_export import do_delete_realm_export, notify_realm_export
from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.export import (
    check_export_with_consent_is_usable,
    check_public_export_is_usable,
    get_realm_exports_serialized,
)
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.response import json_success
from zerver.lib.send_email import FromAddress
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.typed_endpoint_validators import check_int_in_validator
from zerver.models import RealmExport, UserProfile


@transaction.atomic(durable=True)
@require_realm_admin
@typed_endpoint
def export_realm(
    request: HttpRequest,
    user: UserProfile,
    *,
    export_type: Json[
        Annotated[
            int,
            check_int_in_validator(
                [RealmExport.EXPORT_PUBLIC, RealmExport.EXPORT_FULL_WITH_CONSENT]
            ),
        ]
    ] = RealmExport.EXPORT_PUBLIC,
) -> HttpResponse:
    realm = user.realm
    EXPORT_LIMIT = 5

    # Exporting organizations with a huge amount of history can
    # potentially consume a lot of disk or otherwise have accidental
    # DoS risk; for that reason, we require large exports to be done
    # manually on the command line.
    #
    # It's very possible that higher limits would be completely safe.
    MAX_MESSAGE_HISTORY = 250000
    MAX_UPLOAD_QUOTA = 20 * 1024 * 1024 * 1024

    # Filter based upon the number of events that have occurred in the delta
    # If we are at the limit, the incoming request is rejected
    event_time_delta = timezone_now() - timedelta(days=7)
    limit_check = RealmExport.objects.filter(
        realm=realm, date_requested__gte=event_time_delta
    ).count()
    if limit_check >= EXPORT_LIMIT:
        raise JsonableError(_("Exceeded rate limit."))

    # The RealmCount analytics table lets us efficiently get an estimate
    # for the number of messages in an organization. It won't match the
    # actual number of messages in the export, because this measures the
    # number of messages that went to DMs / Group DMs / public or private
    # channels at the time they were sent.
    # Thus, messages that were deleted or moved between channels and
    # private messages for which the users didn't consent for export will be
    # treated differently for this check vs. in the export code.
    realm_count_query = RealmCount.objects.filter(
        realm=realm, property="messages_sent:message_type:day"
    )
    if export_type == RealmExport.EXPORT_PUBLIC:
        realm_count_query.filter(subgroup="public_stream")
    exportable_messages_estimate = sum(realm_count.value for realm_count in realm_count_query)

    if (
        exportable_messages_estimate > MAX_MESSAGE_HISTORY
        or user.realm.currently_used_upload_space_bytes() > MAX_UPLOAD_QUOTA
    ):
        raise JsonableError(
            _("Please request a manual export from {email}.").format(
                email=FromAddress.SUPPORT,
            )
        )

    if (
        export_type == RealmExport.EXPORT_FULL_WITH_CONSENT
        and not check_export_with_consent_is_usable(realm)
    ):
        raise JsonableError(
            _(
                "Make sure at least one Organization Owner is consenting to the export "
                "or contact {email} for help."
            ).format(email=FromAddress.SUPPORT)
        )
    elif export_type == RealmExport.EXPORT_PUBLIC and not check_public_export_is_usable(realm):
        raise JsonableError(
            _(
                "Make sure at least one Organization Owner allows other "
                "Administrators to see their email address "
                "or contact {email} for help"
            ).format(email=FromAddress.SUPPORT)
        )

    row = RealmExport.objects.create(
        realm=realm,
        type=export_type,
        acting_user=user,
        status=RealmExport.REQUESTED,
        date_requested=timezone_now(),
    )

    # Allow for UI updates on a pending export
    notify_realm_export(realm)

    # Using the deferred_work queue processor to avoid
    # killing the process after 60s
    event = {
        "type": "realm_export",
        "user_profile_id": user.id,
        "realm_export_id": row.id,
    }
    queue_event_on_commit("deferred_work", event)
    return json_success(request, data={"id": row.id})


@require_realm_admin
def get_realm_exports(request: HttpRequest, user: UserProfile) -> HttpResponse:
    realm_exports = get_realm_exports_serialized(user.realm)
    return json_success(request, data={"exports": realm_exports})


@require_realm_admin
def delete_realm_export(request: HttpRequest, user: UserProfile, export_id: int) -> HttpResponse:
    try:
        export_row = RealmExport.objects.get(realm_id=user.realm_id, id=export_id)
    except RealmExport.DoesNotExist:
        raise JsonableError(_("Invalid data export ID"))

    if export_row.status == RealmExport.DELETED:
        raise JsonableError(_("Export already deleted"))
    if export_row.status == RealmExport.FAILED:
        raise JsonableError(_("Export failed, nothing to delete"))
    if export_row.status in [RealmExport.REQUESTED, RealmExport.STARTED]:
        raise JsonableError(_("Export still in progress"))
    do_delete_realm_export(export_row, user)
    return json_success(request)


@require_realm_admin
def get_users_export_consents(request: HttpRequest, user: UserProfile) -> HttpResponse:
    rows = UserProfile.objects.filter(realm=user.realm, is_active=True, is_bot=False).values(
        "id", "allow_private_data_export"
    )
    export_consents = [
        {"user_id": row["id"], "consented": row["allow_private_data_export"]} for row in rows
    ]
    return json_success(request, data={"export_consents": export_consents})
