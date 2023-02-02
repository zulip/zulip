# Generated by Django 3.2.12 on 2022-03-23 03:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0384_alter_realm_not_null"),
    ]

    operations = [
        migrations.AlterField(
            model_name="archivedattachment",
            name="is_realm_public",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name="archivedattachment",
            name="is_web_public",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name="attachment",
            name="is_realm_public",
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name="attachment",
            name="is_web_public",
            field=models.BooleanField(default=False, null=True),
        ),
    ]
