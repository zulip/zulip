# Generated by Django 3.1.7 on 2021-04-07 23:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0318_remove_realm_invite_by_admins_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="stream",
            name="default_color",
            field=models.CharField(default=None, max_length=10, null=True),
        ),
    ]
