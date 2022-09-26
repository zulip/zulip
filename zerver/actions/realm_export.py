import orjson
from django.utils.timezone import now as timezone_now

from zerver.lib.export import get_realm_exports_serialized
from zerver.lib.upload import delete_export_tarball
from zerver.models import RealmAuditLog, UserProfile
from zerver.tornado.django_api import send_event


def notify_realm_export(user_profile: UserProfile) -> None:
    # In the future, we may want to send this event to all realm admins.
    event = dict(type="realm_export", exports=get_realm_exports_serialized(user_profile))
    send_event(user_profile.realm, event, [user_profile.id])


def do_delete_realm_export(user_profile: UserProfile, export: RealmAuditLog) -> None:
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
    notify_realm_export(user_profile)
