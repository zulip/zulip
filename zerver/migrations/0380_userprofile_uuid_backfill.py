import uuid

from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_user_profile_uuid(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")

    max_id = UserProfile.objects.aggregate(models.Max("id"))["id__max"]
    if max_id is None:
        # Nothing to do if there are no users yet.
        return

    BATCH_SIZE = 10000
    lower_bound = 0

    while lower_bound < max_id:
        user_profiles_to_update = []
        for user_profile in UserProfile.objects.filter(
            id__gt=lower_bound, id__lte=lower_bound + BATCH_SIZE, uuid=None
        ).only("id", "uuid"):
            user_profile.uuid = uuid.uuid4()
            user_profiles_to_update.append(user_profile)
        lower_bound += BATCH_SIZE

        UserProfile.objects.bulk_update(user_profiles_to_update, ["uuid"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0379_userprofile_uuid"),
    ]

    operations = [
        migrations.RunPython(backfill_user_profile_uuid, reverse_code=migrations.RunPython.noop),
    ]
