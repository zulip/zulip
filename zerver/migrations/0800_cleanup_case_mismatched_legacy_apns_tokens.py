import hashlib
from collections import defaultdict

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

APNS_KIND = 1


def compute_token_id_int(token: str) -> int:
    # Equivalent to zerver.lib.push_registration.compute_token_id_int,
    # inlined to avoid importing live code from a migration.
    hash_bytes = hashlib.sha256(token.encode()).digest()
    return int.from_bytes(hash_bytes[0:8], byteorder="big", signed=True)


def cleanup_case_mismatched_legacy_apns_tokens(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """One-time cleanup for legacy PushDeviceToken APNs rows that
    `cleanup_legacy_push_device_token` left behind because it compared
    tokens case-sensitively prior to the previous commit.
    """
    Device = apps.get_model("zerver", "Device")
    PushDeviceToken = apps.get_model("zerver", "PushDeviceToken")

    e2ee_apns_token_ids_by_user: dict[int, set[int]] = defaultdict(set)
    for user_id, push_token_id in (
        Device.objects.filter(
            push_token_kind="apns",
            push_token_id__isnull=False,
        )
        .values_list("user_id", "push_token_id")
        .iterator()
    ):
        e2ee_apns_token_ids_by_user[user_id].add(push_token_id)

    if not e2ee_apns_token_ids_by_user:
        return

    legacy_ids_to_delete: list[int] = []
    for legacy_id, user_id, token in (
        PushDeviceToken.objects.filter(
            kind=APNS_KIND,
            user_id__in=e2ee_apns_token_ids_by_user,
        )
        .values_list("id", "user_id", "token")
        .iterator()
    ):
        e2ee_token_ids = e2ee_apns_token_ids_by_user[user_id]
        candidate_hashes = {
            compute_token_id_int(token),
            compute_token_id_int(token.lower()),
            compute_token_id_int(token.upper()),
        }
        if not candidate_hashes.isdisjoint(e2ee_token_ids):
            legacy_ids_to_delete.append(legacy_id)

    if legacy_ids_to_delete:
        PushDeviceToken.objects.filter(id__in=legacy_ids_to_delete).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0799_remove_realm_emoji_from_audit_log_extra_data"),
    ]

    operations = [
        migrations.RunPython(
            cleanup_case_mismatched_legacy_apns_tokens,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
