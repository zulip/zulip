import contextlib
import logging
import os
from collections.abc import Iterator
from typing import Any

import boto3
import botocore
import magic
import pyvips
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

IMAGE_BOMB_TOTAL_PIXELS = 90000000
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024

VALID_EMOJI_CONTENT_TYPE = frozenset(
    [
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
)

STILL_PATH_ID_TEMPLATE = "{realm_id}/emoji/images/still/{emoji_filename_without_extension}.png"


class SkipImageError(Exception):
    pass


@contextlib.contextmanager
def libvips_check_image(image_data: bytes) -> Iterator[pyvips.Image]:
    try:
        source_image = pyvips.Image.new_from_buffer(image_data, "")
    except pyvips.Error as e:
        raise SkipImageError(f"Cannot process image: {e}")

    if source_image.width * source_image.height > IMAGE_BOMB_TOTAL_PIXELS:
        raise SkipImageError(f"Image too big: {source_image.height} * {source_image.width}")

    try:
        yield source_image
    except pyvips.Error as e:
        raise SkipImageError(f"Bad image data? {e}")


def extract_first_frame(image_data: bytes) -> bytes:
    if len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES:
        raise SkipImageError(f"Image has too many bytes: {len(image_data)}")

    with libvips_check_image(image_data) as source_image:
        if source_image.get_n_pages() == 1:
            raise SkipImageError("Not animated")

        still = pyvips.Image.thumbnail_buffer(
            image_data,
            64,
            height=64,
            crop=pyvips.Interesting.CENTRE,
        ).write_to_buffer(".png")

        return still


def emoji_iterator(apps: StateApps) -> Iterator[Any]:
    Realm = apps.get_model("zerver", "Realm")
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    for realm in Realm.objects.filter(realmemoji__isnull=False).distinct().order_by("id"):
        yield from RealmEmoji.objects.filter(realm=realm, is_animated=False).order_by("id")


def generate_missing_stills_local(apps: StateApps) -> None:
    assert settings.LOCAL_AVATARS_DIR is not None
    for total_processed, emoji in enumerate(emoji_iterator(apps)):
        if total_processed % 100 == 0:
            print(f"Processed {total_processed} custom emoji")

        try:
            base_path = os.path.join(
                settings.LOCAL_AVATARS_DIR, str(emoji.realm_id), "emoji/images"
            )

            filename_no_extension = os.path.splitext(emoji.file_name)[0]
            still_path = os.path.join(
                settings.LOCAL_AVATARS_DIR,
                STILL_PATH_ID_TEMPLATE.format(
                    realm_id=emoji.realm_id,
                    emoji_filename_without_extension=filename_no_extension,
                ),
            )

            if os.path.exists(still_path):
                continue

            original_path = f"{base_path}/{emoji.file_name}.original"
            if not os.path.exists(original_path):
                original_path = f"{base_path}/{emoji.file_name}"
                if not os.path.exists(original_path):
                    raise SkipImageError("Failed to read .original file: Does not exist")

            with open(original_path, "rb") as fh:
                original_bytes = fh.read()

            content_type = magic.from_buffer(original_bytes[:1024], mime=True)

            if content_type not in VALID_EMOJI_CONTENT_TYPE:
                raise SkipImageError(f"Invalid content-type: {content_type}")

            still = extract_first_frame(original_bytes)

            os.makedirs(os.path.dirname(still_path), exist_ok=True)

            with open(still_path, "wb") as fh:
                fh.write(still)

            emoji.is_animated = True
            emoji.save(update_fields=["is_animated"])

        except SkipImageError:
            continue
        except Exception as e:
            logging.error(
                "Failed to generate still image for emoji id %d (%s): %s",
                emoji.id,
                emoji.file_name,
                e,
            )


def generate_missing_stills_s3(apps: StateApps) -> None:
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

    for total_processed, emoji in enumerate(emoji_iterator(apps)):
        if total_processed % 100 == 0:
            print(f"Processed {total_processed} custom emoji")

        try:
            base_path = f"{emoji.realm_id}/emoji/images"
            filename_no_extension = os.path.splitext(emoji.file_name)[0]

            still_path = STILL_PATH_ID_TEMPLATE.format(
                realm_id=emoji.realm_id,
                emoji_filename_without_extension=filename_no_extension,
            )

            try:
                avatar_bucket.Object(still_path).load()
                continue
            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    raise

            original_path = f"{base_path}/{emoji.file_name}.original"

            try:
                obj = avatar_bucket.Object(original_path).get()
            except botocore.exceptions.ClientError:
                original_path = f"{base_path}/{emoji.file_name}"
                obj = avatar_bucket.Object(original_path).get()

            original_bytes = obj["Body"].read()

            content_type = magic.from_buffer(original_bytes[:1024], mime=True)

            if content_type not in VALID_EMOJI_CONTENT_TYPE:
                raise SkipImageError(f"Invalid content-type: {content_type}")

            still = extract_first_frame(original_bytes)

            metadata = obj.get("Metadata", {})

            avatar_bucket.Object(still_path).put(
                Metadata=metadata,
                ContentType="image/png",
                CacheControl="public, max-age=31536000, immutable",
                Body=still,
            )

            emoji.is_animated = True
            emoji.save(update_fields=["is_animated"])

        except SkipImageError:
            continue
        except Exception as e:
            logging.error(
                "Failed to generate still image for emoji id %d (%s): %s",
                emoji.id,
                emoji.file_name,
                e,
            )


def generate_missing_stills(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    if settings.LOCAL_AVATARS_DIR is not None:
        generate_missing_stills_local(apps)
    else:
        generate_missing_stills_s3(apps)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0771_alter_realmemoji_author"),
    ]

    operations = [
        migrations.RunPython(
            generate_missing_stills, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
