# Generated by Django 1.11.18 on 2019-03-03 13:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0208_add_realm_night_logo_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='stream',
            name='first_message_id',
            field=models.IntegerField(db_index=True, null=True),
        ),
    ]
