# Generated by Django 3.2.8 on 2021-11-22 18:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0370_auto_20211122_1727'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usertopic',
            name='muted_datetime',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='usertopic',
            name='remind_datetime',
            field=models.DateTimeField(null=True),
        ),
    ]
