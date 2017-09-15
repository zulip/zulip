# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

from mock import patch
from zerver.lib.utils import make_safe_digest
from zerver.lib.upload import upload_backend
from zerver.models import UserProfile
from typing import Text
import hashlib

# We hackishly patch this function in order to revert it to the state
# it had when this migration was first written.  This is a balance
# between copying in a historical version of hundreds of lines of code
# from zerver.lib.upload (which would pretty annoying, but would be a
# pain) and just using the current version, which doesn't work
# since we rearranged the avatars in Zulip 1.6.
def patched_user_avatar_path(user_profile):
    # type: (UserProfile) -> Text
    email = user_profile.email
    user_key = email.lower() + settings.AVATAR_SALT
    return make_safe_digest(user_key, hashlib.sha1)

@patch('zerver.lib.upload.user_avatar_path', patched_user_avatar_path)
def verify_medium_avatar_image(apps, schema_editor):
    # type: (StateApps, DatabaseSchemaEditor) -> None
    user_profile_model = apps.get_model('zerver', 'UserProfile')
    for user_profile in user_profile_model.objects.filter(avatar_source=u"U"):
        upload_backend.ensure_medium_avatar_image(user_profile)


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0031_remove_system_avatar_source'),
    ]

    operations = [
        migrations.RunPython(verify_medium_avatar_image)
    ]
