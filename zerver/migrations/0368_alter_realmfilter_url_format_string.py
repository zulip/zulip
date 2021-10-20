# Generated by Django 3.2.8 on 2021-10-20 23:42

from django.db import migrations, models

from zerver.models import filter_format_validator


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0367_scimclient"),
    ]

    operations = [
        migrations.AlterField(
            model_name="realmfilter",
            name="url_format_string",
            field=models.TextField(validators=[filter_format_validator]),
        ),
    ]
