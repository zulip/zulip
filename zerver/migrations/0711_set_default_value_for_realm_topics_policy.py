from enum import Enum

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


class RealmTopicsPolicyEnum(Enum):
    allow_empty_topic = 2
    disable_empty_topic = 3


def set_default_value_for_realm_topics_policy(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")

    Realm.objects.filter(topics_policy=None, mandatory_topics=True).update(
        topics_policy=RealmTopicsPolicyEnum.disable_empty_topic.value
    )

    Realm.objects.filter(topics_policy=None, mandatory_topics=False).update(
        topics_policy=RealmTopicsPolicyEnum.allow_empty_topic.value
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0710_realm_topics_policy"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_realm_topics_policy,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
