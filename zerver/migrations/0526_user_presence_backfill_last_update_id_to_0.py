from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_user_presence_last_update_id(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    UserPresence = apps.get_model("zerver", "UserPresence")

    max_id = UserPresence.objects.aggregate(models.Max("id"))["id__max"]
    if max_id is None:
        # Nothing to do if there are no rows yet.
        return

    BATCH_SIZE = 10000
    lower_bound = 0

    # Add a slop factor to make it likely we run past the end in case
    # of new rows created while we run. The next step will fail to
    # remove the null possibility if we race, so this is safe.
    max_id += BATCH_SIZE / 2

    while lower_bound < max_id:
        UserPresence.objects.filter(
            id__gt=lower_bound, id__lte=lower_bound + BATCH_SIZE, last_update_id=None
        ).update(last_update_id=0)
        lower_bound += BATCH_SIZE


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0525_userpresence_last_update_id"),
    ]

    operations = [
        migrations.RunPython(
            backfill_user_presence_last_update_id,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
        migrations.AlterField(
            model_name="userpresence",
            name="last_update_id",
            field=models.PositiveBigIntegerField(db_index=True, default=0),
        ),
        AddIndexConcurrently(
            model_name="userpresence",
            index=models.Index(
                fields=["realm", "last_update_id"],
                name="zerver_userpresence_realm_last_update_id_idx",
            ),
        ),
    ]
