import logging
import tempfile
import time
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.message_send import internal_send_private_message
from zerver.lib.export import (
    export_realm_wrapper,
    export_tarball_prefix,
    get_realm_exports_serialized,
)
from zerver.lib.upload import delete_export_tarball
from zerver.models import Realm, RealmAuditLog, RealmExport, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.users import get_system_bot, get_user_profile_by_id
from zerver.tornado.django_api import send_event_on_commit


def notify_realm_export(realm: Realm) -> None:
    event = dict(type="realm_export", exports=get_realm_exports_serialized(realm))
    send_event_on_commit(realm, event, realm.get_human_admin_users().values_list("id", flat=True))


@transaction.atomic(durable=True)
def do_delete_realm_export(export_row: RealmExport, acting_user: UserProfile) -> None:
    export_path = export_row.export_path
    assert export_path is not None

    delete_export_tarball(export_path)

    export_row.status = RealmExport.DELETED
    export_row.date_deleted = timezone_now()
    export_row.save(update_fields=["status", "date_deleted"])
    notify_realm_export(export_row.realm)

    RealmAuditLog.objects.create(
        acting_user=acting_user,
        realm=export_row.realm,
        event_type=AuditLogEventType.REALM_EXPORT_DELETED,
        event_time=export_row.date_deleted,
        extra_data={"realm_export_id": export_row.id},
    )


def export_realm_from_event(
    event: dict[str, Any], *, threaded: bool, logger: logging.Logger
) -> None:
    start = time.time()
    user_profile = get_user_profile_by_id(event["user_profile_id"])
    realm = user_profile.realm
    output_dir = tempfile.mkdtemp(prefix=export_tarball_prefix(realm))
    export_event = None

    if "realm_export_id" in event:
        export_row = RealmExport.objects.get(id=event["realm_export_id"])
    else:  # nocoverage
        # Handle existing events in the queue before we switched to RealmExport model.
        export_event = RealmAuditLog.objects.get(id=event["id"])
        extra_data = export_event.extra_data

        if extra_data.get("export_row_id") is not None:
            export_row = RealmExport.objects.get(id=extra_data["export_row_id"])
        else:
            export_row = RealmExport.objects.create(
                realm=realm,
                type=RealmExport.EXPORT_PUBLIC,
                acting_user=user_profile,
                status=RealmExport.REQUESTED,
                date_requested=event["time"],
            )
            export_event.extra_data = {"export_row_id": export_row.id}
            export_event.save(update_fields=["extra_data"])

    if export_row.status != RealmExport.REQUESTED:
        logger.error(
            "Marking export for realm %s as failed due to retry -- possible OOM during export?",
            realm.string_id,
        )
        export_row.status = RealmExport.FAILED
        export_row.date_failed = timezone_now()
        export_row.save(update_fields=["status", "date_failed"])
        notify_realm_export(realm)
        return

    logger.info(
        "Starting realm export for realm %s into %s, initiated by user_profile_id %s",
        realm.string_id,
        output_dir,
        user_profile.id,
    )

    try:
        export_realm_wrapper(
            export_row=export_row,
            output_dir=output_dir,
            processes=1 if threaded else 6,
            upload=True,
        )
    except Exception:
        logging.exception(
            "Data export for %s failed after %s",
            realm.string_id,
            time.time() - start,
            stack_info=True,
        )
        notify_realm_export(realm)
        return

    # We create RealmAuditLog entry in 'export_realm_wrapper'.
    # Delete the old entry created before we switched to RealmExport model.
    if export_event:  # nocoverage
        export_event.delete()

    # Send a direct message notification letting the user who
    # triggered the export know the export finished.
    with override_language(user_profile.default_language):
        content = _(
            "Your data export is complete. [View and download exports]({export_settings_link})."
        ).format(export_settings_link="/#organization/data-exports-admin")
    internal_send_private_message(
        sender=get_system_bot(settings.NOTIFICATION_BOT, realm.id),
        recipient_user=user_profile,
        content=content,
    )

    # For future frontend use, also notify administrator
    # clients that the export happened.
    notify_realm_export(realm)
    logging.info(
        "Completed data export for %s in %s",
        realm.string_id,
        time.time() - start,
    )
