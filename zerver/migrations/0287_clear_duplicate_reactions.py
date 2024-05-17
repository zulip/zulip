from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Count


def clear_duplicate_reactions(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Zulip's data model for reactions has enforced via code,
    nontransactionally, that they can only react with one emoji_code
    for a given reaction_type.  This fixes any that were stored in the
    database via a race; the next migration will add the appropriate
    database-level unique constraint.
    """
    Reaction = apps.get_model("zerver", "Reaction")

    duplicate_reactions = (
        Reaction.objects.all()
        .values("user_profile_id", "message_id", "reaction_type", "emoji_code")
        .annotate(Count("id"))
        .filter(id__count__gt=1)
    )
    for duplicate_reaction in duplicate_reactions:
        duplicate_reaction.pop("id__count")
        to_cleanup = Reaction.objects.filter(**duplicate_reaction)[1:]
        for reaction in to_cleanup:
            reaction.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0286_merge_0260_0285"),
    ]

    operations = [
        migrations.RunPython(
            clear_duplicate_reactions, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
