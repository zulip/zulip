# Generated by Django 1.10.5 on 2017-03-31 05:51
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0071_rename_realmalias_to_realmdomain'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realmauditlog',
            name='event_time',
            field=models.DateTimeField(db_index=True),
        ),
    ]
