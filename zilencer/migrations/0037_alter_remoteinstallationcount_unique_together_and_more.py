from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Count, Min


def clear_duplicate_counts(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Clean up duplicated RemoteRealmCount and RemoteInstallationCount rows.

    This is the equivalent of analytics' 0015_clear_duplicate_counts
    migration -- but it also has additional duplicates if there are
    multiple servers submitting information with the same UUID.

    We drop the behaviour of rolling up and updating the value to the
    sum, since the active_users_log:is_bot:day field has a subgroup
    (and is thus not affected by the bug), and the few cases for
    `invites_sent::day` seem more likely to be re-submissions of the
    same data, not duplicates to roll up.

    We must do this step before switching the non-unique indexes to be
    unique, as there are currently violations.

    """
    count_tables = dict(
        realm=apps.get_model("zilencer", "RemoteRealmCount"),
        installation=apps.get_model("zilencer", "RemoteInstallationCount"),
    )

    for name, count_table in count_tables.items():
        value = ["realm_id", "server_id", "property", "end_time"]
        if name == "installation":
            value = ["server_id", "property", "end_time"]
        duplicated_rows = (
            count_table.objects.filter(subgroup=None)
            .values(*value)
            .annotate(Count("id"), Min("id"))
            .filter(id__count__gt=1)
        )

        for duplicated_row in duplicated_rows:
            duplicated_row.pop("id__count")
            first_id = duplicated_row.pop("id__min")
            count_table.objects.filter(**duplicated_row, id__gt=first_id).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0036_remotezulipserver_last_version"),
    ]

    operations = [
        migrations.RunPython(
            clear_duplicate_counts, reverse_code=migrations.RunPython.noop, elidable=True
        ),
        migrations.AddConstraint(
            model_name="remoteinstallationcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("subgroup__isnull", False)),
                fields=("server", "property", "subgroup", "end_time"),
                name="unique_remote_installation_count",
            ),
        ),
        migrations.AddConstraint(
            model_name="remoteinstallationcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("subgroup__isnull", True)),
                fields=("server", "property", "end_time"),
                name="unique_remote_installation_count_null_subgroup",
            ),
        ),
        migrations.AddConstraint(
            model_name="remoterealmcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("subgroup__isnull", False)),
                fields=("server", "realm_id", "property", "subgroup", "end_time"),
                name="unique_remote_realm_installation_count",
            ),
        ),
        migrations.AddConstraint(
            model_name="remoterealmcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("subgroup__isnull", True)),
                fields=("server", "realm_id", "property", "end_time"),
                name="unique_remote_realm_installation_count_null_subgroup",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="remoteinstallationcount",
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name="remoterealmcount",
            unique_together=set(),
        ),
    ]
