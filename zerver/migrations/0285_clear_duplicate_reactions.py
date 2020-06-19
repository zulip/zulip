from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Count


def clear_duplicate_reactions(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    Reaction = apps.get_model('zerver', 'Reaction')

    duplicate_reactions = Reaction.objects.all().values(
        "user_profile_id", "message_id", "reaction_type", "emoji_code").annotate(
            Count('id')).filter(id__count__gt=1)
    for duplicate_reaction in duplicate_reactions:
        duplicate_reaction.pop('id__count')
        to_cleanup = Reaction.objects.filter(**duplicate_reaction)[1:]
        for reaction in to_cleanup:
            reaction.delete()

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0284_convert_realm_admins_to_realm_owners'),
    ]

    operations = [
        migrations.RunPython(clear_duplicate_reactions,
                             reverse_code=migrations.RunPython.noop,
                             elidable=True),
    ]
