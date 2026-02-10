# Migration to rename 'recent_topics' to 'recent' in web_home_view field

from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max, Min


def rename_recent_topics_to_recent(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    BATCH_SIZE = 10000
    UserProfile = apps.get_model("zerver", "UserProfile")
    RealmUserDefault = apps.get_model("zerver", "RealmUserDefault")

    # Migrate UserProfile records
    applicable_user_rows = UserProfile.objects.filter(web_home_view="recent_topics")
    max_id = applicable_user_rows.aggregate(Max("id"))["id__max"]
    lower_bound = applicable_user_rows.aggregate(Min("id"))["id__min"]

    if max_id is not None and lower_bound is not None:
        while lower_bound <= max_id:
            upper_bound = lower_bound + BATCH_SIZE - 1
            print(f"Processing UserProfile batch {lower_bound} to {upper_bound}")
            with transaction.atomic():
                UserProfile.objects.filter(
                    id__gte=lower_bound,
                    id__lte=upper_bound,
                    web_home_view="recent_topics",
                ).update(web_home_view="recent")
            lower_bound = upper_bound + 1

    # Migrate RealmUserDefault records (small table, no batching needed)
    RealmUserDefault.objects.filter(web_home_view="recent_topics").update(web_home_view="recent")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0773_rename_giphy_rating_realm_gif_rating_policy"),
    ]

    operations = [
        migrations.RunPython(
            rename_recent_topics_to_recent,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
