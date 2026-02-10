import contextlib
import hashlib
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

from zerver.lib.mime_types import guess_extension

# From zerver.lib.thumbnail
DEFAULT_EMOJI_SIZE = 64
IMAGE_BOMB_TOTAL_PIXELS = 90000000
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024  # 128 kb

# This is the intersection of INLINE_MIME_TYPES and THUMBNAIL_ACCEPT_IMAGE_TYPES
VALID_EMOJI_CONTENT_TYPE = frozenset(
    [
        "image/avif",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]
)


class SkipImageError(Exception):
    pass


# From zerver.lib.thumbnail, with minor exception changes
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


# From zerver.lib.thumbnail, with minor exception changes
def resize_emoji(
    image_data: bytes, emoji_file_name: str, size: int = DEFAULT_EMOJI_SIZE
) -> tuple[bytes, bytes | None]:
    if len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES:
        raise SkipImageError(f"Image has too many bytes: {len(image_data)}")

    # Square brackets are used for providing options to libvips' save
    # operation; the extension on the filename comes from reversing
    # the content-type, which removes most of the attacker control of
    # this string, but assert it has no bracketed pieces for safety.
    write_file_ext = os.path.splitext(emoji_file_name)[1]
    assert "[" not in write_file_ext

    # This function returns two values:
    # 1) Emoji image data.
    # 2) If it is animated, the still image data i.e. first frame of gif.
    with libvips_check_image(image_data) as source_image:
        if source_image.get_n_pages() == 1:
            return (
                pyvips.Image.thumbnail_buffer(
                    image_data,
                    size,
                    height=size,
                    crop=pyvips.Interesting.CENTRE,
                ).write_to_buffer(write_file_ext),
                None,
            )
        first_still = pyvips.Image.thumbnail_buffer(
            image_data,
            size,
            height=size,
            crop=pyvips.Interesting.CENTRE,
        ).write_to_buffer(".png")

        animated = pyvips.Image.thumbnail_buffer(
            image_data,
            size,
            height=size,
            # This is passed to the loader, and means "load all
            # frames", instead of the default of just the first
            option_string="n=-1",
        )
        if animated.width != animated.get("page-height"):
            # If the image is non-square, we have to iterate the
            # frames to add padding to make it so
            if not animated.hasalpha():
                animated = animated.addalpha()
            frames = [
                frame.gravity(
                    pyvips.CompassDirection.CENTRE,
                    size,
                    size,
                    extend=pyvips.Extend.BACKGROUND,
                    background=[0, 0, 0, 0],
                )
                for frame in animated.pagesplit()
            ]
            animated = frames[0].pagejoin(frames[1:])
        return (animated.write_to_buffer(write_file_ext), first_still)


# From zerver.lib.emoji
def get_emoji_file_name(content_type: str, emoji_id: int) -> str:
    image_ext = guess_extension(content_type, strict=False)
    # The only callsite of this pre-limits the content_type to a
    # reasonable set that we know have extensions.
    assert image_ext is not None

    # We salt this with a server-side secret so that it is not
    # enumerable by clients, and will not collide on the server.  New
    # realm imports may pass a synthetic emoji_id, which is fine as
    # long as it starts at 1, and as such later emoji cannot collide
    # unless there is a legit hash collision.
    #
    # We truncate the hash at 8 characters, as this is enough entropy
    # to make collisions vanishingly unlikely.  In the event of a
    # collusion, the id will advance and a manual retry will succeed.
    hash_key = settings.AVATAR_SALT.encode() + b":" + str(emoji_id).encode()
    return "".join((hashlib.sha256(hash_key).hexdigest()[0:8], image_ext))


def thumbnail_local_emoji(apps: StateApps) -> None:
    assert settings.LOCAL_AVATARS_DIR is not None
    for total_processed, emoji in enumerate(thumbnail_iterator(apps)):
        if total_processed % 100 == 0:
            print(f"Processed {total_processed} custom emoji")

        old_file_name = emoji.file_name
        try:
            base_path = os.path.join(
                settings.LOCAL_AVATARS_DIR, str(emoji.realm_id), "emoji/images"
            )
            copy_from_path = f"{base_path}/{old_file_name}.original"
            if not os.path.exists(copy_from_path) and os.path.exists(
                f"{base_path}/{old_file_name}"
            ):
                # Imports currently don't write ".original" files, so check without that
                copy_from_path = f"{base_path}/{old_file_name}"
                if not os.path.exists(copy_from_path):
                    raise SkipImageError("Failed to read .original file: Does not exist")

            with open(copy_from_path, "rb") as fh:
                original_bytes = fh.read()

            # We used to accept any bytes which pillow could
            # thumbnail, with any filename, and would use the
            # guessed-from-filename content-type when serving the
            # emoji.  Examine the bytes of the image to verify that it
            # is an image of reasonable type, and then derive the real
            # filename extension (which we will still use for deriving
            # content-type at serving time) from that.  This ensures
            # that the contents are a valid image, and that we put the
            # right content-type on it when served -- the filename
            # used for the initial upload becomes completely
            # irrelevant.
            content_type = magic.from_buffer(original_bytes[:1024], mime=True)

            if content_type not in VALID_EMOJI_CONTENT_TYPE:
                raise SkipImageError(f"Invalid content-type: {content_type}")

            new_file_name = get_emoji_file_name(content_type, emoji.id)
            if old_file_name == new_file_name:
                continue

            print(f"{base_path}/{old_file_name} -> {base_path}/{new_file_name}")
            try:
                if os.path.exists(f"{base_path}/{new_file_name}.original"):
                    os.unlink(f"{base_path}/{new_file_name}.original")
                os.link(copy_from_path, f"{base_path}/{new_file_name}.original")
            except OSError as e:
                raise SkipImageError(f"Failed to update .original file: {e}")

            animated, still = resize_emoji(original_bytes, new_file_name)
            try:
                with open(f"{base_path}/{new_file_name}", "wb") as fh:
                    fh.write(animated)

                if still is not None:
                    os.makedirs(f"{base_path}/still", exist_ok=True)
                    filename_no_extension = os.path.splitext(new_file_name)[0]
                    with open(f"{base_path}/still/{filename_no_extension}.png", "wb") as fh:
                        fh.write(still)
            except OSError as e:
                raise SkipImageError(f"Failed to write new file: {e}")

            emoji.file_name = new_file_name
            emoji.save(update_fields=["file_name"])
        except SkipImageError as e:
            logging.warning(
                "Failed to re-thumbnail emoji id %d with %s/emoji/images/%s: %s",
                emoji.id,
                emoji.realm_id,
                emoji.file_name,
                e,
            )
            new_file_name = get_emoji_file_name("image/png", emoji.id)
            try:
                with (
                    open(f"{settings.DEPLOY_ROOT}/static/images/bad-emoji.png", "rb") as f,
                    open(f"{base_path}/{new_file_name}", "wb") as new_f,
                ):
                    new_f.write(f.read())
                emoji.deactivated = True
                emoji.is_animated = False
                emoji.file_name = new_file_name
                emoji.save(update_fields=["file_name", "is_animated", "deactivated"])
            except Exception as e:
                logging.error("Failed to deactivate and replace with known-good image: %s", e)


def thumbnail_s3(apps: StateApps) -> None:
    total_processed = 0
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
    for total_processed, emoji in enumerate(thumbnail_iterator(apps)):
        if total_processed % 100 == 0:
            print(f"Processed {total_processed} custom emoji")

        old_file_name = emoji.file_name
        try:
            base_path = os.path.join(str(emoji.realm_id), "emoji/images")
            copy_from_path = f"{base_path}/{old_file_name}.original"
            try:
                old_data = avatar_bucket.Object(copy_from_path).get()
                original_bytes = old_data["Body"].read()
            except botocore.exceptions.ClientError:
                # Imports currently don't write ".original" files, so check without that
                try:
                    copy_from_path = f"{base_path}/{old_file_name}"
                    old_data = avatar_bucket.Object(f"{base_path}/{old_file_name}").get()
                except botocore.exceptions.ClientError as e:
                    raise SkipImageError(f"Failed to read .original file: {e}")
                original_bytes = old_data["Body"].read()

            # We used to accept any bytes which pillow could
            # thumbnail, with any filename, and would store the
            # guessed-from-filename content-type in S3, to be used
            # when serving the emoji.  Examine the bytes of the image
            # to verify that it is an image of reasonable type, and
            # then both store that content-type in S3 (for later
            # serving), as well as using it to derive the right
            # filename extension (for clarity).
            content_type = magic.from_buffer(original_bytes[:1024], mime=True)

            if content_type not in VALID_EMOJI_CONTENT_TYPE:
                raise SkipImageError(f"Invalid content-type: {content_type}")

            metadata = old_data["Metadata"]
            # Make sure this metadata is up-to-date, while we're
            # in here; some early emoji are missing it
            metadata["realm_id"] = str(emoji.realm_id)
            if emoji.author_id:
                metadata["user_profile_id"] = str(emoji.author_id)

            new_file_name = get_emoji_file_name(content_type, emoji.id)
            if old_file_name == new_file_name:
                continue

            print(f"{base_path}/{old_file_name} -> {base_path}/{new_file_name}")
            avatar_bucket.Object(f"{base_path}/{new_file_name}.original").copy_from(
                CopySource=f"{settings.S3_AVATAR_BUCKET}/{copy_from_path}",
                MetadataDirective="REPLACE",
                Metadata=metadata,
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )

            animated, still = resize_emoji(original_bytes, new_file_name)
            try:
                avatar_bucket.Object(f"{base_path}/{new_file_name}").put(
                    Metadata=metadata,
                    ContentType=content_type,
                    CacheControl="public, max-age=31536000, immutable",
                    Body=animated,
                )
                if still is not None:
                    filename_no_extension = os.path.splitext(new_file_name)[0]
                    avatar_bucket.Object(f"{base_path}/still/{filename_no_extension}.png").put(
                        Metadata=metadata,
                        ContentType="image/png",
                        CacheControl="public, max-age=31536000, immutable",
                        Body=still,
                    )
            except botocore.exceptions.ClientError as e:
                raise SkipImageError(f"Failed to upload new file: {e}")

            emoji.file_name = new_file_name
            emoji.save(update_fields=["file_name"])
        except SkipImageError as e:
            logging.warning(
                "Failed to re-thumbnail emoji id %d with %s/emoji/images/%s: %s",
                emoji.id,
                emoji.realm_id,
                emoji.file_name,
                e,
            )
            new_file_name = get_emoji_file_name("image/png", emoji.id)
            try:
                with open(f"{settings.DEPLOY_ROOT}/static/images/bad-emoji.png", "rb") as f:
                    avatar_bucket.Object(f"{base_path}/{new_file_name}").put(
                        Metadata={
                            "user_profile_id": str(emoji.author_id),
                            "realm_id": str(emoji.realm_id),
                        },
                        ContentType="image/png",
                        CacheControl="public, max-age=31536000, immutable",
                        Body=f.read(),
                    )
                emoji.deactivated = True
                emoji.is_animated = False
                emoji.file_name = new_file_name
                emoji.save(update_fields=["file_name", "is_animated", "deactivated"])
            except Exception as e:
                logging.error("Failed to deactivate and replace with known-good image: %s", e)


def thumbnail_iterator(apps: StateApps) -> Iterator[Any]:
    Realm = apps.get_model("zerver", "Realm")
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    for realm in Realm.objects.filter(realmemoji__isnull=False).distinct().order_by("id"):
        yield from RealmEmoji.objects.filter(realm=realm).order_by("id")


def thumbnail_emoji(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    if settings.LOCAL_AVATARS_DIR is not None:
        thumbnail_local_emoji(apps)
    else:
        thumbnail_s3(apps)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0552_remove_realm_private_message_policy"),
    ]

    operations = [migrations.RunPython(thumbnail_emoji, elidable=True)]
