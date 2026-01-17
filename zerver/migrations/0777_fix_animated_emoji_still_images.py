import contextlib
import logging
import os
from collections.abc import Iterator
from typing import Any

import boto3
import botocore
import pyvips
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

DEFAULT_EMOJI_SIZE = 64
IMAGE_BOMB_TOTAL_PIXELS = 90000000


class SkipImageError(Exception):
    pass


# From zerver.lib.thumbnail, with minor exception changes
@contextlib.contextmanager
def libvips_check_image(image_data: bytes) -> Iterator[pyvips.Image]:
    try:
        source_image = pyvips.Image.new_from_buffer(image_data, "")
    except pyvips.Error as e:
        raise SkipImageError(f"Cannot process image: {e}")

    if (
        source_image.width * source_image.height * source_image.get_n_pages()
        > IMAGE_BOMB_TOTAL_PIXELS
    ):
        raise SkipImageError("Image size exceeds limit.")

    try:
        yield source_image
    except pyvips.Error as e:
        raise SkipImageError(f"Bad image data? {e}")


def extract_still_from_animated(
    emoji: Any, image_data: bytes, maybe_skip: bool = False, size: int = DEFAULT_EMOJI_SIZE
) -> bytes | None:
    # Decide whether we need to (re)generate the still frame:
    #
    # 1. If the still_frame is not square, we must always pad and regenerate,
    #    even if a still already exists.
    #
    # 2. If maybe_skip is True, we have the original file available and the
    #    emoji is already marked animated. In this case, a correct still was
    #    previously generated and the image is already square, so we can skip
    #    regeneration(We always try to load the original file, but in the
    #    unlikely case that it isn’t available, we load the resized file instead).
    #
    # 3. If emoji.is_animated is False, we always generate a still.
    #
    # 4. If we don't have the original file (maybe_skip is False), we always
    #    regenerate since we can't trust any previously generated still.
    with libvips_check_image(image_data) as source_image:
        # if the image data is not animated then we don't need to generate still
        if source_image.get_n_pages() == 1:
            return None

        if source_image.width == source_image.height and maybe_skip and emoji.is_animated:
            return None

    still_frame = pyvips.Image.thumbnail_buffer(
        image_data,
        size,
        height=size,
    )

    if still_frame.width != still_frame.height:
        if not still_frame.hasalpha():
            still_frame = still_frame.addalpha()
        still_frame = still_frame.gravity(
            pyvips.CompassDirection.CENTRE,
            size,
            size,
            extend=pyvips.Extend.BACKGROUND,
            background=[0, 0, 0, 0],
        )

    return still_frame.write_to_buffer(".png")


def fix_still_images_local(apps: StateApps) -> None:
    assert settings.LOCAL_AVATARS_DIR is not None

    RealmEmoji = apps.get_model("zerver", "RealmEmoji")

    ids_to_mark_animated: list[int] = []

    for total_processed, emoji in enumerate(RealmEmoji.objects.all().iterator()):
        if total_processed % 100 == 0:
            print(f"Processed {total_processed} realm emoji")

        base_path = os.path.join(settings.LOCAL_AVATARS_DIR, str(emoji.realm_id), "emoji/images")
        original_path = f"{base_path}/{emoji.file_name}.original"

        try:
            still_bytes: bytes | None = None
            maybe_skip = True
            if not os.path.exists(original_path):
                maybe_skip = False
                original_path = f"{base_path}/{emoji.file_name}"
                if not os.path.exists(original_path):
                    raise SkipImageError("Emoji file does not exist")

            with open(original_path, "rb") as fh:
                original_bytes = fh.read()

            still_bytes = extract_still_from_animated(emoji, original_bytes, maybe_skip)

            if still_bytes is None:
                continue

            if not emoji.is_animated:
                ids_to_mark_animated.append(emoji.id)

            still_dir = f"{base_path}/still"
            os.makedirs(still_dir, exist_ok=True)

            filename_no_extension = os.path.splitext(emoji.file_name)[0]
            still_path = f"{still_dir}/{filename_no_extension}.png"

            with open(still_path, "wb") as fh:
                fh.write(still_bytes)

        except SkipImageError as e:
            logging.warning(
                "Failed to regenerate still image for emoji id %d (%s): %s",
                emoji.id,
                emoji.file_name,
                e,
            )

    if ids_to_mark_animated:
        RealmEmoji.objects.filter(id__in=ids_to_mark_animated).update(is_animated=True)


def fix_still_images_s3(apps: StateApps) -> None:
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

    RealmEmoji = apps.get_model("zerver", "RealmEmoji")

    ids_to_mark_animated: list[int] = []

    for total_processed, emoji in enumerate(RealmEmoji.objects.all().iterator()):
        if total_processed % 100 == 0:
            print(f"Processed {total_processed} realm emoji")

        base_path = os.path.join(str(emoji.realm_id), "emoji/images")
        original_path = f"{base_path}/{emoji.file_name}.original"

        try:
            still_bytes: bytes | None = None
            maybe_skip = True
            try:
                obj = avatar_bucket.Object(original_path).get()
            except botocore.exceptions.ClientError:
                try:
                    maybe_skip = False
                    original_path = f"{base_path}/{emoji.file_name}"
                    obj = avatar_bucket.Object(original_path).get()
                except botocore.exceptions.ClientError as e:
                    raise SkipImageError(f"Failed to read original file: {e}")

            original_bytes = obj["Body"].read()

            still_bytes = extract_still_from_animated(emoji, original_bytes, maybe_skip)

            if still_bytes is None:
                continue

            if not emoji.is_animated:
                ids_to_mark_animated.append(emoji.id)

            filename_no_extension = os.path.splitext(emoji.file_name)[0]
            still_key = f"{base_path}/still/{filename_no_extension}.png"

            metadata = obj.get("Metadata", {})
            avatar_bucket.Object(still_key).put(
                Metadata=metadata,
                ContentType="image/png",
                CacheControl="public, max-age=31536000, immutable",
                Body=still_bytes,
            )

        except SkipImageError as e:
            logging.warning(
                "Failed to regenerate still image for emoji id %d (%s): %s",
                emoji.id,
                emoji.file_name,
                e,
            )

    if ids_to_mark_animated:
        RealmEmoji.objects.filter(id__in=ids_to_mark_animated).update(is_animated=True)


def fix_still_images(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    if settings.LOCAL_AVATARS_DIR is not None:
        fix_still_images_local(apps)
    else:
        fix_still_images_s3(apps)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.RunPython(
            fix_still_images, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
