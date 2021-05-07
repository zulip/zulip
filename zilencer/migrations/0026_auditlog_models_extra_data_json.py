# Generated by Django 4.0.7 on 2022-09-30 20:25

import django
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0025_alter_remotepushdevicetoken_user_id_drop_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="remoterealmauditlog",
            name="extra_data_json",
            field=models.JSONField(
                default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder
            ),
        ),
        migrations.AddField(
            model_name="remotezulipserverauditlog",
            name="extra_data_json",
            field=models.JSONField(
                default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder
            ),
        ),
    ]
