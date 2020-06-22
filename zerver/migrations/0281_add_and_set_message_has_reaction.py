from django.db import migrations, models
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def set_has_reaction_in_messages(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Message = apps.get_model("zerver", "Message")
    Reaction = apps.get_model("zerver", "Reaction")
    message = Message.objects.all()

    for e in message:
        if not e.has_reaction and Reaction.objects.filter(message=e).exists():
            e.has_reaction = True
            e.save(update_fields=["has_reaction"])


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0280_userprofile_presence_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='archivedmessage',
            name='has_reaction',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='message',
            name='has_reaction',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(
            set_has_reaction_in_messages,
            reverse_code=migrations.RunPython.noop,
            elidable=True
        ),
    ]
