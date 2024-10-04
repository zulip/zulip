from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.lib.export import get_realm_exports_serialized
from zerver.lib.upload import delete_export_tarball
from zerver.models import Realm, RealmAuditLog, RealmExport, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
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
