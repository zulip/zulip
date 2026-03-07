from datetime import datetime, timezone

from django.db import migrations, models


def backfill_created_at(apps: migrations.state.StateApps, schema_editor: object) -> None:
    """Backfill RealmEmoji.created_at from RealmAuditLog.

    Reads REALM_EMOJI_ADDED (226) entries in chronological order and stamps each
    matching emoji with its audit log event_time. Iterating oldest-first means
    the true original upload time wins if duplicate entries exist.

    Emoji with no audit log entry keep the epoch sentinel and are treated as
    old, receiving no new-emoji bonus.

    extra_data shape: {"added_emoji": {"id": "<str_pk>", ...}, ...}
    """
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")

    REALM_EMOJI_ADDED = 226

    for log_entry in RealmAuditLog.objects.filter(
        event_type=REALM_EMOJI_ADDED,
    ).order_by("event_time"):
        extra_data = log_entry.extra_data
        if not extra_data:
            continue
        added_emoji = extra_data.get("added_emoji")
        if not added_emoji:
            continue
        emoji_id_str = added_emoji.get("id")
        if not emoji_id_str:
            continue
        try:
            emoji_id = int(emoji_id_str)
        except (ValueError, TypeError):
            continue
        RealmEmoji.objects.filter(id=emoji_id).update(created_at=log_entry.event_time)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0768_realmauditlog_scrubbed"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmemoji",
            name="created_at",
            field=models.DateTimeField(
                # Epoch sentinel: existing rows are treated as old and get no bonus.
                # The RunPython step below overwrites this for rows with an audit log entry.
                default=datetime(1970, 1, 1, tzinfo=timezone.utc),
                db_index=True,
            ),
        ),
        migrations.RunPython(
            backfill_created_at,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
