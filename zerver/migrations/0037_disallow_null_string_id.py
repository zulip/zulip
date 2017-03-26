# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from six.moves import range

from django.db.utils import IntegrityError

from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db import migrations, models

def set_string_id_using_domain(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    Realm = apps.get_model('zerver', 'Realm')
    for realm in Realm.objects.all():
        if not realm.string_id:
            prefix = realm.domain.split('.')[0]
            try:
                realm.string_id = prefix
                realm.save(update_fields=["string_id"])
                continue
            except IntegrityError:
                pass
            for i in range(1, 100):
                try:
                    realm.string_id = prefix + str(i)
                    realm.save(update_fields=["string_id"])
                    continue
                except IntegrityError:
                    pass
            raise RuntimeError("Unable to find a good string_id for realm %s" % (realm,))

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0036_rename_subdomain_to_string_id'),
    ]

    operations = [
        migrations.RunPython(set_string_id_using_domain),

        migrations.AlterField(
            model_name='realm',
            name='string_id',
            field=models.CharField(unique=True, max_length=40),
        ),
    ]
