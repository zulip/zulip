# Generated by Django 3.1.7 on 2021-03-14 14:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0322_realm_create_audit_log_backfill"),
    ]

    operations = [
        migrations.AddField(
            model_name="preregistrationuser",
            name="user_avatar_url",
            field=models.TextField(null=True),
        ),
    ]
