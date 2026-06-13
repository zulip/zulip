from collections import defaultdict

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

APNS_KIND = 1


def cleanup_case_mismatched_legacy_apns_tokens_bouncer(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Bouncer counterpart to zerver migration
    0800_cleanup_case_mismatched_legacy_apns_tokens.
    See that migration for context.
    """
    RemotePushDevice = apps.get_model("zilencer", "RemotePushDevice")
    RemotePushDeviceToken = apps.get_model("zilencer", "RemotePushDeviceToken")

    # Find tokens registered for E2EE through remote servers.
    # (Those registered through this server (with `remote_realm` null)
    # also appear in `Device` and are covered by zerver migration 0800.)
    e2ee_tokens_by_remote_realm: dict[int, set[str]] = defaultdict(set)
    for remote_realm_id, token in (
        RemotePushDevice.objects.filter(
            token_kind="apns",
            remote_realm__isnull=False,
        )
        .values_list("remote_realm_id", "token")
        .iterator()
    ):
        e2ee_tokens_by_remote_realm[remote_realm_id].add(token.lower())

    if not e2ee_tokens_by_remote_realm:
        return

    legacy_ids_to_delete: list[int] = []
    for legacy_id, remote_realm_id, token in (
        RemotePushDeviceToken.objects.filter(
            kind=APNS_KIND,
            remote_realm_id__in=e2ee_tokens_by_remote_realm,
        )
        .values_list("id", "remote_realm_id", "token")
        .iterator()
    ):
        if token.lower() in e2ee_tokens_by_remote_realm[remote_realm_id]:
            legacy_ids_to_delete.append(legacy_id)

    if legacy_ids_to_delete:
        RemotePushDeviceToken.objects.filter(id__in=legacy_ids_to_delete).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "zilencer",
            "0070_remove_remoterealmauditlog_zilencer_remoterealmauditlog_synced_billing_events_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            cleanup_case_mismatched_legacy_apns_tokens_bouncer,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
