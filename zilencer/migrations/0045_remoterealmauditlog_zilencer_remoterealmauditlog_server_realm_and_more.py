# Generated by Django 4.2.7 on 2023-12-05 19:33

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0044_remoterealmbillinguser"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="remoterealmauditlog",
            index=models.Index(
                condition=models.Q(("remote_realm__isnull", True)),
                fields=["server", "realm_id"],
                name="zilencer_remoterealmauditlog_server_realm",
            ),
        ),
        migrations.AddIndex(
            model_name="remoterealmauditlog",
            index=models.Index(
                condition=models.Q(("remote_realm__isnull", True)),
                fields=["server"],
                name="zilencer_remoterealmauditlog_server",
            ),
        ),
        migrations.AddIndex(
            model_name="remoterealmcount",
            index=models.Index(
                condition=models.Q(("remote_realm__isnull", True)),
                fields=["server", "realm_id"],
                name="zilencer_remoterealmcount_server_realm",
            ),
        ),
        migrations.AddIndex(
            model_name="remoterealmcount",
            index=models.Index(
                condition=models.Q(("remote_realm__isnull", True)),
                fields=["server"],
                name="zilencer_remoterealmcount_server",
            ),
        ),
    ]
