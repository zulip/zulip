from django.utils.timezone import now as timezone_now

from zerver.lib.export import get_realm_exports_serialized
from zerver.lib.upload import delete_export_tarball
from zerver.models import Realm, RealmExport
from zerver.tornado.django_api import send_event_on_commit


def notify_realm_export(realm: Realm) -> None:
    event = dict(type="realm_export", exports=get_realm_exports_serialized(realm))
    send_event_on_commit(realm, event, realm.get_human_admin_users().values_list("id", flat=True))


def do_delete_realm_export(export_row: RealmExport) -> None:
    export_path = export_row.export_path
    assert export_path is not None

    delete_export_tarball(export_path)

    export_row.status = RealmExport.DELETED
    export_row.date_deleted = timezone_now()
    export_row.save(update_fields=["status", "date_deleted"])
    notify_realm_export(export_row.realm)
