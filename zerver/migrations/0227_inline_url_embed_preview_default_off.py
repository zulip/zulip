# Generated by Django 1.11.20 on 2019-05-31 02:33

from django.db import migrations, models
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def disable_realm_inline_url_embed_preview(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    realms = Realm.objects.filter(inline_url_embed_preview=True)
    realms.update(inline_url_embed_preview=False)


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0226_archived_submessage_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realm',
            name='inline_url_embed_preview',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(disable_realm_inline_url_embed_preview,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),

    ]
