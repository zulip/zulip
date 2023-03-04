from typing import Dict, List

import orjson
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def move_to_separate_table(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    AlertWord = apps.get_model("zerver", "AlertWord")

    for user_profile in UserProfile.objects.all():
        list_of_words = orjson.loads(user_profile.alert_words)

        # Remove duplicates with our case-insensitive model.
        word_dict: Dict[str, str] = {}
        for word in list_of_words:
            word_dict[word.lower()] = word

        AlertWord.objects.bulk_create(
            AlertWord(user_profile=user_profile, word=word, realm=user_profile.realm)
            for word in word_dict.values()
        )


def move_back_to_user_profile(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    AlertWord = apps.get_model("zerver", "AlertWord")
    UserProfile = apps.get_model("zerver", "UserProfile")

    user_ids_and_words = AlertWord.objects.all().values("user_profile_id", "word")
    user_ids_with_words: Dict[int, List[str]] = {}

    for id_and_word in user_ids_and_words:
        user_ids_with_words.setdefault(id_and_word["user_profile_id"], [])
        user_ids_with_words[id_and_word["user_profile_id"]].append(id_and_word["word"])

    for user_id, words in user_ids_with_words.items():
        user_profile = UserProfile.objects.get(id=user_id)
        user_profile.alert_words = orjson.dumps(words).decode()
        user_profile.save(update_fields=["alert_words"])


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0276_alertword"),
    ]

    operations = [
        migrations.RunPython(move_to_separate_table, move_back_to_user_profile, elidable=True),
    ]
