from collections import defaultdict
from typing import Any, Dict

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def realm_emoji_name_to_id(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Reaction = apps.get_model("zerver", "Reaction")
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    realm_emoji_by_realm_id: Dict[int, Dict[str, Any]] = defaultdict(dict)
    for realm_emoji in RealmEmoji.objects.all():
        realm_emoji_by_realm_id[realm_emoji.realm_id][realm_emoji.name] = {
            "id": str(realm_emoji.id),
            "name": realm_emoji.name,
            "deactivated": realm_emoji.deactivated,
        }
    for reaction in Reaction.objects.filter(reaction_type="realm_emoji"):
        realm_id = reaction.user_profile.realm_id
        emoji_name = reaction.emoji_name
        realm_emoji = realm_emoji_by_realm_id.get(realm_id, {}).get(emoji_name)
        if realm_emoji is None:
            # Realm emoji used in this reaction has been deleted so this
            # reaction should also be deleted. We don't need to reverse
            # this step in migration reversal code.
            print(
                f"Reaction for ({emoji_name}, {reaction.message_id}) refers to deleted custom emoji {reaction.user_profile_id}; deleting"
            )
            reaction.delete()
        else:
            reaction.emoji_code = realm_emoji["id"]
            reaction.save()


def reversal(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Reaction = apps.get_model("zerver", "Reaction")
    for reaction in Reaction.objects.filter(reaction_type="realm_emoji"):
        reaction.emoji_code = reaction.emoji_name
        reaction.save()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0144_remove_realm_create_generic_bot_by_admins_only"),
    ]

    operations = [
        migrations.RunPython(realm_emoji_name_to_id, reverse_code=reversal, elidable=True),
    ]
