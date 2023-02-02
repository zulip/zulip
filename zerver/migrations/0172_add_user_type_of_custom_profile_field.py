# Generated by Django 1.11.11 on 2018-05-08 17:24

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0171_userprofile_dense_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customprofilefield",
            name="field_type",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (1, "Short text"),
                    (2, "Long text"),
                    (4, "Date"),
                    (5, "URL"),
                    (3, "Choice"),
                    (6, "User"),
                ],
                default=1,
            ),
        ),
    ]
