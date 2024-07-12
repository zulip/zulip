import contextlib
import hashlib
import os
from typing import Any

import boto3
import pyvips
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import QuerySet
from django.utils.timezone import now as timezone_now

IMAGE_BOMB_TOTAL_PIXELS = 90000000
DEFAULT_AVATAR_SIZE = 100
MEDIUM_AVATAR_SIZE = 500


def resize_avatar(
    image_data: bytes | pyvips.Image,
    size: int,
) -> bytes | None:
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


def do_remove_avatar(user_profile: Any, apps: StateApps) -> None:
    avatar_source = "G"  # UserProfile.AVATAR_FROM_GRAVATAR
    user_profile.avatar_source = avatar_source
    user_profile.avatar_version += 1
    user_profile.save(update_fields=["avatar_source", "avatar_version"])
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    RealmAuditLog.objects.create(
        realm_id=user_profile.realm_id,
        modified_user_id=user_profile.id,
        event_type=123,  # RealmAuditLog.USER_AVATAR_SOURCE_CHANGED,
        extra_data={"avatar_source": avatar_source},
        event_time=timezone_now(),
        acting_user=None,
    )


class SkipImageError(Exception):
    def __init__(self, message: str, user: Any) -> None:
        super().__init__(message)
        self.user = user


# Just the image types from zerver.lib.upload.INLINE_MIME_TYPES
INLINE_IMAGE_MIME_TYPES = [
    "image/apng",
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    # To avoid cross-site scripting attacks, DO NOT add types such
    # as image/svg+xml.
]


def thumbnail_s3_avatars(users: QuerySet[Any], apps: StateApps) -> None:
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
        try:
            old_base = os.path.join(str(user.realm_id), old_hash(user))
            new_base = os.path.join(str(user.realm_id), new_hash(user))

            if total_processed % 100 == 0:
                print(f"Processing {total_processed}/{len(users)} user avatars")

            with contextlib.suppress(ClientError):
                # Check if we've already uploaded this one; if so, continue.
                avatar_bucket.Object(new_base + ".original").load()
                continue

            try:
                old_data = avatar_bucket.Object(old_base + ".original").get()
                metadata = old_data["Metadata"]
                metadata["avatar_version"] = str(user.avatar_version)
                original_bytes = old_data["Body"].read()
            except ClientError:
                raise SkipImageError(f"Failed to fetch {old_base}", user)

            # INLINE_IMAGE_MIME_TYPES changing (e.g. adding
            # "image/avif") means this may not match the old
            # content-disposition.
            inline_type = old_data["ContentType"] in INLINE_IMAGE_MIME_TYPES
            extra_params = {}
            if not inline_type:
                extra_params["ContentDisposition"] = "attachment"

            avatar_bucket.Object(new_base + ".original").copy_from(
                CopySource=f"{settings.S3_AVATAR_BUCKET}/{old_base}.original",
                MetadataDirective="REPLACE",
                Metadata=metadata,
                ContentType=old_data["ContentType"],
                CacheControl="public, max-age=31536000, immutable",
                **extra_params,  # type: ignore[arg-type] # The dynamic kwargs here confuse mypy.
            )

            small = resize_avatar(original_bytes, DEFAULT_AVATAR_SIZE)
            if small is None:
                raise SkipImageError(f"Failed to resize {old_base}", user)
            avatar_bucket.Object(new_base + ".png").put(
                Metadata=metadata,
                ContentType="image/png",
                CacheControl="public, max-age=31536000, immutable",
                Body=small,
            )
            medium = resize_avatar(original_bytes, MEDIUM_AVATAR_SIZE)
            if medium is None:
                raise SkipImageError(f"Failed to medium resize {old_base}", user)
            avatar_bucket.Object(new_base + "-medium.png").put(
                Metadata=metadata,
                ContentType="image/png",
                CacheControl="public, max-age=31536000, immutable",
                Body=medium,
            )
        except SkipImageError as e:
            print(f"{e!s} for {e.user}; reverting to gravatar")
            do_remove_avatar(e.user, apps)


def thumbnail_local_avatars(users: QuerySet[Any], apps: StateApps) -> None:
    total_processed = 0
    assert settings.LOCAL_AVATARS_DIR is not None
    for total_processed, user in enumerate(users):
        try:
            old_base = os.path.join(settings.LOCAL_AVATARS_DIR, str(user.realm_id), old_hash(user))
            new_base = os.path.join(settings.LOCAL_AVATARS_DIR, str(user.realm_id), new_hash(user))

            if total_processed % 100 == 0:
                print(f"Processing {total_processed}/{len(users)} user avatars")

            if os.path.exists(new_base + "-medium.png"):
                # This user's avatar has already been migrated.
                continue

            with contextlib.suppress(FileNotFoundError):
                # Remove the hard link, if present from a previous failed run.
                os.remove(new_base + ".original")

            # We hardlink, rather than copying, so we don't take any extra space.
            try:
                os.link(old_base + ".original", new_base + ".original")
                with open(old_base + ".original", "rb") as f:
                    original_bytes = f.read()
            except OSError:
                raise SkipImageError(f"Failed to read {old_base}", user)

            small = resize_avatar(original_bytes, DEFAULT_AVATAR_SIZE)
            if small is None:
                raise SkipImageError(f"Failed to resize {old_base}", user)
            with open(new_base + ".png", "wb") as f:
                f.write(small)

            medium = resize_avatar(original_bytes, MEDIUM_AVATAR_SIZE)
            if medium is None:
                raise SkipImageError(f"Failed to medium resize {old_base}", user)
            with open(new_base + "-medium.png", "wb") as f:
                f.write(medium)
        except SkipImageError as e:
            print(f"{e!s} for {e.user}; reverting to gravatar")
            do_remove_avatar(e.user, apps)


def thumbnail_avatars(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    users = (
        UserProfile.objects.filter(avatar_source="U")
        .only("id", "realm_id", "avatar_version")
        .order_by("id")
    )
    if settings.LOCAL_AVATARS_DIR is not None:
        thumbnail_local_avatars(users, apps)
    else:
        thumbnail_s3_avatars(users, apps)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0543_preregistrationuser_notify_referrer_on_join"),
    ]

    operations = [migrations.RunPython(thumbnail_avatars, elidable=True)]
