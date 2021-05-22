# Generated by Django 3.2.2 on 2021-05-22 11:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0324_fix_deletion_cascade_behavior"),
    ]

    operations = [
        migrations.CreateModel(
            name="StreamUserGroupAccess",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
                (
                    "stream",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.stream"
                    ),
                ),
                (
                    "user_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.usergroup"
                    ),
                ),
            ],
            options={
                "unique_together": {("user_group", "stream")},
            },
        ),
    ]
