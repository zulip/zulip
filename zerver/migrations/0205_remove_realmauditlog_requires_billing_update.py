# Generated by Django 1.11.18 on 2019-02-02 02:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0204_remove_realm_billing_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="realmauditlog",
            name="requires_billing_update",
        ),
    ]
