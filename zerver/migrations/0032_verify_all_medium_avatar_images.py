import hashlib
from unittest.mock import patch

from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.upload import upload_backend
from zerver.models import UserProfile


# We hackishly patch this function in order to revert it to the state
# it had when this migration was first written.  This is a balance
# between copying in a historical version of hundreds of lines of code
# from zerver.lib.upload (which would pretty annoying, but would be a
# pain) and just using the current version, which doesn't work
# since we rearranged the avatars in Zulip 1.6.
def patched_user_avatar_path(user_profile: UserProfile) -> str:
    email = user_profile.email
    user_key = email.lower() + settings.AVATAR_SALT
    return hashlib.sha1(user_key.encode()).hexdigest()


@patch("zerver.lib.upload.s3.user_avatar_path", patched_user_avatar_path)
@patch("zerver.lib.upload.local.user_avatar_path", patched_user_avatar_path)
def verify_medium_avatar_image(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    user_profile_model = apps.get_model("zerver", "UserProfile")
    for user_profile in user_profile_model.objects.filter(avatar_source="U"):
        upload_backend.ensure_avatar_image(user_profile, is_medium=True)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0031_remove_system_avatar_source"),
    ]

    operations = [
        migrations.RunPython(verify_medium_avatar_image, elidable=True),
    ]
