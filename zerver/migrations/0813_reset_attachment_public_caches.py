from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max, Model

BATCH_SIZE = 10000


def reset_attachment_public_caches(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Resets the Attachment.is_*_public caches that are currently True.

    Before the accompanying fixes, these caches were not reset when a
    message referencing an attachment was deleted or edited to no
    longer reference it, and third-party data imports marked every
    attachment as realm-public. Either could leave a True value for an
    attachment that is no longer (or never was) in a public channel.

    A null value means the cache is recomputed from the messages
    containing the attachment the next time it is accessed. False
    values are left alone, since they cannot grant access.
    """
    Attachment = apps.get_model("zerver", "Attachment")
    ArchivedAttachment = apps.get_model("zerver", "ArchivedAttachment")

    def reset_caches(attachment_model: type[Model]) -> None:
        max_id = attachment_model._default_manager.aggregate(Max("id"))["id__max"]
        if max_id is None:
            return

        lower_bound = 0
        while lower_bound < max_id:
            batch = attachment_model._default_manager.filter(
                id__gt=lower_bound, id__lte=lower_bound + BATCH_SIZE
            )
            batch.filter(is_realm_public=True).update(is_realm_public=None)
            batch.filter(is_web_public=True).update(is_web_public=None)
            lower_bound += BATCH_SIZE

    reset_caches(Attachment)
    reset_caches(ArchivedAttachment)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0812_delete_inaccessible_user_topics"),
    ]

    operations = [
        migrations.RunPython(
            reset_attachment_public_caches,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
