import orjson
from django.utils.timezone import now as timezone_now

from zerver.lib.export import get_realm_exports_serialized
from zerver.lib.upload import delete_export_tarball
from zerver.models import Realm, RealmAuditLog
from zerver.tornado.django_api import send_event_on_commit


def notify_realm_export(realm: Realm) -> None:
    event = dict(type="realm_export", exports=get_realm_exports_serialized(realm))
    send_event_on_commit(realm, event, realm.get_human_admin_users().values_list("id", flat=True))


def do_delete_realm_export(export: RealmAuditLog) -> None:
    # Give mypy a hint so it knows `orjson.loads`
    # isn't being passed an `Optional[str]`.
    export_extra_data = export.extra_data
    assert export_extra_data is not None
    export_data = orjson.loads(export_extra_data)
    export_path = export_data.get("export_path")

    if export_path:
        # Allow removal even if the export failed.
        delete_export_tarball(export_path)

    export_data.update(deleted_timestamp=timezone_now().timestamp())
    export.extra_data = orjson.dumps(export_data).decode()
    export.save(update_fields=["extra_data"])
    notify_realm_export(export.realm)
