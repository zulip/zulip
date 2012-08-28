import hashlib

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def remove_prefix_from_archived_streams(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Stream = apps.get_model("zerver", "Stream")
    archived_streams = Stream.objects.filter(deactivated=True)

    for archived_stream in archived_streams:
        old_prefix = "!DEACTIVATED:"
        streamID = str(archived_stream.id)
        stream_id_hash_object = hashlib.sha512(streamID.encode())
        hashed_stream_id = stream_id_hash_object.hexdigest()[0:7]
        prefix = hashed_stream_id + old_prefix
        prefix_length = len(prefix)
        old_name = archived_stream.name
        new_name = old_name
        if old_name.startswith(prefix):
            new_name = old_name[prefix_length:]

        # Check for archived streams before commit 1b6f68b.
        elif old_prefix in old_name:
            prefix_end_index = old_name.find(old_prefix) + len(old_prefix)
            new_name = old_name[prefix_end_index:]

        else:
            continue

        # Check if there's an active stream or another archived stream with the new name
        if not Stream.objects.filter(
            realm_id=archived_stream.realm_id, name__iexact=new_name
        ).exists():
            archived_stream.name = new_name
            archived_stream.save(update_fields=["name"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        (
            "zerver",
            "0616_userprofile_can_change_user_emails",
        ),
    ]

    operations = [
        migrations.RunPython(
            remove_prefix_from_archived_streams,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
