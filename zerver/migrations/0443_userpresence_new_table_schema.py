import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

from zerver.lib.migrate import rename_indexes_constraints


class Migration(migrations.Migration):
    """
    First step of migrating to a new UserPresence data model. Creates a new
    table with the intended fields, into which in the next step
    data can be ported over from the current UserPresence model.
    In the last step, the old model will be replaced with the new one.
    """

    dependencies = [
        ("zerver", "0442_remove_realmfilter_url_format_string"),
    ]

    operations = [
        # Django doesn't rename indexes and constraints when renaming
        # a table (https://code.djangoproject.com/ticket/23577). This
        # means that after renaming UserPresence->UserPresenceOld the
        # UserPresenceOld indexes/constraints retain their old name
        # causing a conflict when CreateModel tries to create them for
        # the new UserPresence table.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    rename_indexes_constraints("zerver_userpresence", "zerver_userpresenceold"),
                    reverse_code=rename_indexes_constraints(
                        "zerver_userpresenceold", "zerver_userpresence"
                    ),
                )
            ],
            state_operations=[
                migrations.RenameModel(
                    old_name="UserPresence",
                    new_name="UserPresenceOld",
                ),
                migrations.RenameIndex(
                    model_name="userpresenceold",
                    old_name="zerver_userpresence_realm_id_timestamp_25f410da_idx",
                    new_name="zerver_userpresenceold_realm_id_timestamp_52ef5fd3_idx",
                ),
            ],
        ),
        migrations.CreateModel(
            name="UserPresence",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "last_connected_time",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now, null=True
                    ),
                ),
                (
                    "last_active_time",
                    models.DateTimeField(
                        db_index=True, default=django.utils.timezone.now, null=True
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.Realm"
                    ),
                ),
                (
                    "user_profile",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="userpresence",
            index=models.Index(
                fields=["realm", "last_active_time"],
                name="zerver_userpresence_realm_id_last_active_time_1c5aa9a2_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="userpresence",
            index=models.Index(
                fields=["realm", "last_connected_time"],
                name="zerver_userpresence_realm_id_last_connected_time_98d2fc9f_idx",
            ),
        ),
    ]
