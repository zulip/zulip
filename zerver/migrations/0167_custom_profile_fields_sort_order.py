# Generated by Django 1.11.11 on 2018-04-08 15:49

from django.db import migrations, models
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F


def migrate_set_order_value(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    CustomProfileField = apps.get_model('zerver', 'CustomProfileField')
    CustomProfileField.objects.all().update(order=F('id'))

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0166_add_url_to_profile_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='customprofilefield',
            name='order',
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(migrate_set_order_value,
                             reverse_code=migrations.RunPython.noop),
    ]
