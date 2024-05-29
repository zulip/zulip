import re
from typing import Any, Dict

import boto3
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef


def fix_emoji_metadata(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    if settings.LOCAL_UPLOADS_DIR is not None:
        return

    bucket = boto3.resource(
        "s3",
        aws_access_key_id=settings.S3_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        endpoint_url=settings.S3_ENDPOINT_URL,
        config=Config(
            signature_version=None,
            s3={"addressing_style": settings.S3_ADDRESSING_STYLE},
        ),
    ).Bucket(settings.S3_AVATAR_BUCKET)

    Realm = apps.get_model("zerver", "Realm")
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    UserProfile = apps.get_model("zerver", "UserProfile")

    for realm in Realm.objects.filter(
        Exists(RealmEmoji.objects.filter(realm_id=OuterRef("id")))
    ).only("id"):
        fallback_owner = (
            UserProfile.objects.filter(realm=realm.id, is_bot=False, role=100, is_active=True)
            .order_by("id")
            .first()
        )
        assert fallback_owner is not None

        emoji_by_filename: Dict[str, Any] = {}
        for emoji in RealmEmoji.objects.filter(realm_id=realm.id).exclude(file_name=None):
            assert emoji.file_name is not None
            if emoji.author_id is None:
                emoji.author_id = fallback_owner.id
                emoji.save(update_fields=["author_id"])
            if emoji.file_name not in emoji_by_filename:
                # Slack imports may have multiple RealmEmoji rows for
                # the same file_name; we pick one arbitrarily
                emoji_by_filename[emoji.file_name] = emoji

        for obj_summary in bucket.objects.filter(Prefix=f"{realm.id}/emoji/images/"):
            match = re.match(r"^\d+/emoji/images/(.+)$", obj_summary.key)
            assert match
            emoji_filename = match.group(1)
            if emoji_filename not in emoji_by_filename:
                continue
            emoji = emoji_by_filename[emoji_filename]
            assert emoji.author_id is not None

            head = bucket.meta.client.head_object(Bucket=bucket.name, Key=obj_summary.key)
            metadata = head["Metadata"]
            changed = False
            if metadata.get("realm_id") is None:
                metadata["realm_id"] = str(realm.id)
                changed = True
            if metadata.get("user_profile_id") is None:
                metadata["user_profile_id"] = str(emoji.author_id)
                changed = True

            if not changed:
                continue

            assert not head.get("ContentDisposition")
            obj_summary.copy_from(
                ContentType=head["ContentType"],
                CopySource=f"{bucket.name}/{obj_summary.key}",
                Metadata=metadata,
                MetadataDirective="REPLACE",
            )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0508_realmuserdefault_receives_typing_notifications_and_more"),
    ]

    operations = [
        migrations.RunPython(
            fix_emoji_metadata, reverse_code=migrations.RunPython.noop, elidable=True
        )
    ]
