from django.db import connection, migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef
from psycopg2.sql import SQL, Identifier


def delete_unattached_imageattachments(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")
    Attachment = apps.get_model("zerver", "Attachment")
    ImageAttachment = apps.get_model("zerver", "ImageAttachment")

    table = ImageAttachment._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute(SQL("SELECT MIN(id), MAX(id) FROM {}").format(Identifier(table)))
        (min_id, max_id) = cursor.fetchone()
        if min_id is None:
            return

        q = ImageAttachment.objects.alias(
            has_attachment=Exists(Attachment.objects.filter(path_id=OuterRef("path_id"))),
            has_archived_attachment=Exists(
                ArchivedAttachment.objects.filter(path_id=OuterRef("path_id"))
            ),
        ).filter(
            has_attachment=False,
            has_archived_attachment=False,
        )
        # The majority of these rows will have attachment rows still,
        # so we will only be deleting a small number of
        # image_attachment rows per batch; the lookups for attachment
        # and archived_attachment are both by unique path_id, so this
        # query will still be fast.
        batch_size = 10000
        while min_id <= max_id:
            lower = min_id
            upper = min_id + batch_size
            q.filter(id__gte=lower, id__lt=upper).delete()
            min_id = upper
            if min_id > max_id:
                cursor.execute(SQL("SELECT MAX(id) FROM {}").format(Identifier(table)))
                (max_id,) = cursor.fetchone()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0771_alter_realmemoji_author"),
    ]

    operations = [
        migrations.RunPython(
            delete_unattached_imageattachments,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
