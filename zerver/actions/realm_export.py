from typing import Optional

from django.utils.timezone import now as timezone_now

from zerver.lib.export import notify_realm_export
from zerver.lib.upload import delete_export_tarball
from zerver.models import Realm, RealmExport, UserProfile


def do_create_realm_export(
    realm: Realm,
    is_public: bool = True,
    acting_user: Optional[UserProfile] = None,
    consent_message_id: Optional[int] = None,
) -> RealmExport:
    if is_public:
        assert consent_message_id is None
        type = RealmExport.EXPORT_PUBLIC
    elif consent_message_id is not None:
        type = RealmExport.EXPORT_WITH_CONSENT
    else:
        type = RealmExport.EXPORT_WITHOUT_CONSENT

    export = RealmExport.objects.create(
        realm=realm,
        type=type,
        consent_message_id=consent_message_id,
        acting_user=acting_user,
    )

    # We create the RealmAuditLog entry when we actually start doing
    # the export, in zerver.lib.export.export_realm_wrapper

    notify_realm_export(realm)
    return export


def do_delete_realm_export(export: RealmExport) -> None:
    if export.export_path:
        # Allow removal even if the export failed.
        delete_export_tarball(export.export_path)
    export.date_deleted = timezone_now()
    export.save(update_fields=["date_deleted"])
    notify_realm_export(export.realm)
