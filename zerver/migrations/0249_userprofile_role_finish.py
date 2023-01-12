# Generated by Django 1.11.24 on 2019-10-03 23:40

from django.db import migrations, models

# The values at the time of this migration
ROLE_MEMBER = 400


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0248_userprofile_role_start"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userprofile",
            name="is_guest",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="is_realm_admin",
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.PositiveSmallIntegerField(db_index=True, default=ROLE_MEMBER),
        ),
    ]
