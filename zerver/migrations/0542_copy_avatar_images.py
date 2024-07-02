import hashlib
import os
from typing import Any, Iterable, Optional, Union

import boto3
import pyvips
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

IMAGE_BOMB_TOTAL_PIXELS = 90000000
DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500


def resize_avatar(
    image_data: Union[bytes, pyvips.Image],
    size: int,
) -> Optional[bytes]:
    try:
        source_image = pyvips.Image.new_from_buffer(image_data, "")
        if source_image.width * source_image.height > IMAGE_BOMB_TOTAL_PIXELS:
            return None

        return pyvips.Image.thumbnail_buffer(
            image_data,
            size,
            height=size,
            crop=pyvips.Interesting.CENTRE,
        ).write_to_buffer(".png")
    except pyvips.Error:
        return None


def new_hash(user_profile: Any) -> str:
    user_key = (
        str(user_profile.id) + ":" + str(user_profile.avatar_version) + ":" + settings.AVATAR_SALT
    )
    return hashlib.sha1(user_key.encode()).hexdigest()


def old_hash(user_profile: Any) -> str:
    user_key = str(user_profile.id) + settings.AVATAR_SALT
    return hashlib.sha1(user_key.encode()).hexdigest()


def thumbnail_s3_avatars(users: Iterable[Any]) -> None:
    avatar_bucket = boto3.resource(
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
    for user in users:
        old_base = os.path.join(str(user.realm_id), old_hash(user))
        new_base = os.path.join(str(user.realm_id), new_hash(user))

        try:
            old_data = avatar_bucket.Object(old_base + ".original").get()
            metadata = old_data["Metadata"]
            metadata["avatar_version"] = str(user.avatar_version)
            original_bytes = old_data["Body"].read()
        except Exception:
            print(f"Failed to fetch {old_base}")

        avatar_bucket.Object(new_base + ".original").copy_from(
            CopySource=f"{settings.S3_AVATAR_BUCKET}/{old_base}.original",
            MetadataDirective="REPLACE",
            Metadata=metadata,
            ContentDisposition=old_data["ContentDisposition"],
            ContentType=old_data["ContentType"],
            CacheControl="public, max-age=31536000, immutable",
        )

        small = resize_avatar(original_bytes, DEFAULT_AVATAR_SIZE)
        if small is None:
            print(f"Failed to resize {old_base}")
            continue
        avatar_bucket.Object(new_base + ".png").put(
            Metadata=metadata,
            ContentDisposition=old_data["ContentDisposition"],
            ContentType=old_data["ContentType"],
            CacheControl="public, max-age=31536000, immutable",
            Body=small,
        )
        medium = resize_avatar(original_bytes, MEDIUM_AVATAR_SIZE)
        if medium is None:
            print(f"Failed to medium resize {old_base}")
            continue
        avatar_bucket.Object(new_base + "-medium.png").put(
            Metadata=metadata,
            ContentDisposition=old_data["ContentDisposition"],
            ContentType=old_data["ContentType"],
            CacheControl="public, max-age=31536000, immutable",
            Body=medium,
        )


def thumbnail_local_avatars(users: Iterable[Any]) -> None:
    assert settings.LOCAL_AVATARS_DIR is not None
    for user in users:
        old_base = os.path.join(settings.LOCAL_AVATARS_DIR, str(user.realm_id), old_hash(user))
        new_base = os.path.join(settings.LOCAL_AVATARS_DIR, str(user.realm_id), new_hash(user))

        # We hardlink, rather than copying, so we don't take any extra space.
        try:
            os.link(old_base + ".original", new_base + ".original")
            with open(old_base + ".original", "rb") as f:
                original_bytes = f.read()
        except Exception:
            print(f"Failed to read {old_base}.original")

        small = resize_avatar(original_bytes, DEFAULT_AVATAR_SIZE)
        if small is None:
            print(f"Failed to resize {old_base}")
            continue
        with open(new_base + ".png", "wb") as f:
            f.write(small)

        medium = resize_avatar(original_bytes, MEDIUM_AVATAR_SIZE)
        if medium is None:
            print(f"Failed to medium resize {old_base}")
            continue
        with open(new_base + "-medium.png", "wb") as f:
            f.write(medium)


def thumbnail_avatars(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    users = UserProfile.objects.filter(avatar_source="U").only("id", "realm_id", "avatar_version")
    if settings.LOCAL_AVATARS_DIR is not None:
        thumbnail_local_avatars(users)
    else:
        thumbnail_s3_avatars(users)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0541_alter_realmauditlog_options"),
    ]

    operations = [migrations.RunPython(thumbnail_avatars, elidable=True)]
