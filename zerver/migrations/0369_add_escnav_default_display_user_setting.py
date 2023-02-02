# Generated by Django 3.2.8 on 2021-10-25 12:12

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0368_alter_realmfilter_url_format_string"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="escape_navigates_to_default_view",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="escape_navigates_to_default_view",
            field=models.BooleanField(default=True),
        ),
    ]
