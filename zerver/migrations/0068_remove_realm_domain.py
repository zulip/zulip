# Generated by Django 1.10.5 on 2017-03-13 23:32
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0067_archived_models"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="realm",
            name="domain",
        ),
    ]
