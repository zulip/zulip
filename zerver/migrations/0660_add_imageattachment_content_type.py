from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef, Subquery


def populate_content_type(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    ImageAttachment = apps.get_model("zerver", "ImageAttachment")
    Attachment = apps.get_model("zerver", "Attachment")

    batch_size = 1000
    min_id = 0
    while True:
        # Update content_types from corresponding Attachments in bulk
        rows_updated = ImageAttachment.objects.filter(
            id__gt=min_id, id__lte=min_id + batch_size
        ).update(
            content_type=Subquery(
                Attachment.objects.filter(path_id=OuterRef("path_id")).values("content_type")
            ),
        )

        if not rows_updated:
            break

        min_id += batch_size
        print(f"Processed ImageAttachments through id {min_id}")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0659_remove_realm_bot_creation_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="imageattachment",
            name="content_type",
            field=models.TextField(null=True),
        ),
        migrations.RunPython(
            populate_content_type,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
