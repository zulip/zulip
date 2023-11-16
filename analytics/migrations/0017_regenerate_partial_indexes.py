from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0016_unique_constraint_when_subgroup_null"),
    ]

    # If the server was installed between 7.0 and 7.4 (or main between
    # 2c20028aa451 and 7807bff52635), it contains indexes which (when
    # running 7.5 or 7807bff52635 or higher) are never used, because
    # they contain an improper cast
    # (https://code.djangoproject.com/ticket/34840).
    #
    # We regenerate the indexes here, by dropping and re-creating
    # them, so that we know that they are properly formed.
    operations = [
        migrations.RemoveConstraint(
            model_name="installationcount",
            name="unique_installation_count",
        ),
        migrations.AddConstraint(
            model_name="installationcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=False),
                fields=("property", "subgroup", "end_time"),
                name="unique_installation_count",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="installationcount",
            name="unique_installation_count_null_subgroup",
        ),
        migrations.AddConstraint(
            model_name="installationcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=True),
                fields=("property", "end_time"),
                name="unique_installation_count_null_subgroup",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="realmcount",
            name="unique_realm_count",
        ),
        migrations.AddConstraint(
            model_name="realmcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=False),
                fields=("realm", "property", "subgroup", "end_time"),
                name="unique_realm_count",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="realmcount",
            name="unique_realm_count_null_subgroup",
        ),
        migrations.AddConstraint(
            model_name="realmcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=True),
                fields=("realm", "property", "end_time"),
                name="unique_realm_count_null_subgroup",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="streamcount",
            name="unique_stream_count",
        ),
        migrations.AddConstraint(
            model_name="streamcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=False),
                fields=("stream", "property", "subgroup", "end_time"),
                name="unique_stream_count",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="streamcount",
            name="unique_stream_count_null_subgroup",
        ),
        migrations.AddConstraint(
            model_name="streamcount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=True),
                fields=("stream", "property", "end_time"),
                name="unique_stream_count_null_subgroup",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="usercount",
            name="unique_user_count",
        ),
        migrations.AddConstraint(
            model_name="usercount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=False),
                fields=("user", "property", "subgroup", "end_time"),
                name="unique_user_count",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="usercount",
            name="unique_user_count_null_subgroup",
        ),
        migrations.AddConstraint(
            model_name="usercount",
            constraint=models.UniqueConstraint(
                condition=models.Q(subgroup__isnull=True),
                fields=("user", "property", "end_time"),
                name="unique_user_count_null_subgroup",
            ),
        ),
    ]
