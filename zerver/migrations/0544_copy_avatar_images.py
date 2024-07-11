import contextlib
import hashlib
import os
from typing import Any, Optional, Union

import boto3
import pyvips
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import QuerySet

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
    return hashlib.sha256(user_key.encode()).hexdigest()[:40]


def old_hash(user_profile: Any) -> str:
    user_key = str(user_profile.id) + settings.AVATAR_SALT
    return hashlib.sha1(user_key.encode()).hexdigest()


def thumbnail_s3_avatars(users: QuerySet[Any]) -> None:
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
    for total_processed, user in enumerate(users):
        old_base = os.path.join(str(user.realm_id), old_hash(user))
        new_base = os.path.join(str(user.realm_id), new_hash(user))

        if total_processed % 100 == 0:
            print(f"Processing {total_processed}/{len(users)} user avatars")

        with contextlib.suppress(Exception):
            # Check if we've already uploaded this one; if so, continue.
            avatar_bucket.Object(new_base + ".original").load()
            continue

        try:
            old_data = avatar_bucket.Object(old_base + ".original").get()
            metadata = old_data["Metadata"]
            metadata["avatar_version"] = str(user.avatar_version)
            original_bytes = old_data["Body"].read()
        except Exception:
            print(f"Failed to fetch {old_base}")
            continue

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
            ContentType="image/png",
            CacheControl="public, max-age=31536000, immutable",
            Body=small,
        )
        medium = resize_avatar(original_bytes, MEDIUM_AVATAR_SIZE)
        if medium is None:
            print(f"Failed to medium resize {old_base}")
            continue
        avatar_bucket.Object(new_base + "-medium.png").put(
            Metadata=metadata,
            ContentType="image/png",
            CacheControl="public, max-age=31536000, immutable",
            Body=medium,
        )


def thumbnail_local_avatars(users: QuerySet[Any]) -> None:
    total_processed = 0
    assert settings.LOCAL_AVATARS_DIR is not None
    for total_processed, user in enumerate(users):
        old_base = os.path.join(settings.LOCAL_AVATARS_DIR, str(user.realm_id), old_hash(user))
        new_base = os.path.join(settings.LOCAL_AVATARS_DIR, str(user.realm_id), new_hash(user))

        if total_processed % 100 == 0:
            print(f"Processing {total_processed}/{len(users)} user avatars")

        if os.path.exists(new_base + "-medium.png"):
            # This user's avatar has already been migrated.
            continue

        with contextlib.suppress(Exception):
            # Remove the hard link, if present from a previous failed run.
            os.remove(new_base + ".original")

        # We hardlink, rather than copying, so we don't take any extra space.
        try:
            os.link(old_base + ".original", new_base + ".original")
            with open(old_base + ".original", "rb") as f:
                original_bytes = f.read()
        except Exception:
            print(f"Failed to read {old_base}.original")
            raise

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
    users = (
        UserProfile.objects.filter(avatar_source="U")
        .only("id", "realm_id", "avatar_version")
        .order_by("id")
    )
    if settings.LOCAL_AVATARS_DIR is not None:
        thumbnail_local_avatars(users)
    else:
        thumbnail_s3_avatars(users)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0543_preregistrationuser_notify_referrer_on_join"),
    ]

    operations = [migrations.RunPython(thumbnail_avatars, elidable=True)]
