import contextlib
import hashlib
import logging
import os
import re
from typing import Any, Iterator, List, Optional, Set, Tuple

import boto3
import botocore
import pyvips
from botocore.client import Config
from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.mime_types import guess_type

# From zerver.lib.thumbnail
DEFAULT_EMOJI_SIZE = 64
IMAGE_BOMB_TOTAL_PIXELS = 90000000
MAX_EMOJI_GIF_FILE_SIZE_BYTES = 128 * 1024 * 1024  # 128 kb


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
) -> Tuple[bytes, Optional[bytes]]:
    if len(image_data) > MAX_EMOJI_GIF_FILE_SIZE_BYTES:
        raise SkipImageError(f"Image has too many bytes: {len(image_data)}")

    # Square brackets are used for providing options to libvips' save
    # operation; these should have been filtered out earlier, so we
    # assert none are found here, for safety.
    write_file_ext = os.path.splitext(emoji_file_name)[1]
    if "[" in write_file_ext:
        raise SkipImageError(f"Invalid file name: {emoji_file_name}")

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


# From zerver.lib.emoji, with minor exception changes
def get_emoji_file_name(emoji_file_name: str, emoji_id: int) -> str:
    image_ext = os.path.splitext(emoji_file_name)[1]
    if not re.match(r"\.\w+$", image_ext):
        raise SkipImageError(f"Invalid file name: {emoji_file_name}")
    # We salt this with a server-side secret so that it is not
    # enumerable by clients, and will not collide on the server.  New
    # realm imports may pass a synthetic emoji_id, which is fine as
    # long as it starts at 1, and as such later emoji cannot collide
    # unless there is a legit hash collision.
    hash_key = settings.AVATAR_SALT.encode() + b":" + str(emoji_id).encode()
    return "".join((hashlib.sha256(hash_key).hexdigest()[0:8], image_ext))


def thumbnail_local_emoji(apps: StateApps) -> None:
    assert settings.LOCAL_AVATARS_DIR is not None
    for emoji, old_file_name, new_file_name, to_delete in thumbnail_iterator(apps):
        print(f"{old_file_name} -> {new_file_name}")
        try:
            base_path = os.path.join(
                settings.LOCAL_AVATARS_DIR, str(emoji.realm_id), "emoji/images"
            )
            try:
                if os.path.exists(f"{base_path}/{new_file_name}.original"):
                    os.unlink(f"{base_path}/{new_file_name}.original")
                os.link(
                    f"{base_path}/{old_file_name}.original", f"{base_path}/{new_file_name}.original"
                )
                with open(f"{base_path}/{new_file_name}.original", "rb") as fh:
                    original_bytes = fh.read()
            except OSError as e:
                raise SkipImageError(f"Failed to read original file: {e}")

            animated, still = resize_emoji(original_bytes, new_file_name)
            try:
                with open(f"{base_path}/{new_file_name}", "wb") as fh:
                    fh.write(animated)

                if still is not None:
                    filename_no_extension = os.path.splitext(new_file_name)[0]
                    with open(f"{base_path}/still/{filename_no_extension}.png", "wb") as fh:
                        fh.write(still)
            except OSError as e:
                raise SkipImageError(f"Failed to write new file: {e}")

            emoji.file_name = new_file_name
            emoji.save(update_fields=["file_name"])

            for path in to_delete:
                with contextlib.suppress(OSError):
                    os.unlink(f"{base_path}/{path}")
        except SkipImageError as e:
            logging.error(
                "Failed to re-thumbnail %s/emoji/images/%s: %s", emoji.realm_id, emoji.file_name, e
            )


def thumbnail_s3_emoji(apps: StateApps) -> None:
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
    for emoji, old_file_name, new_file_name, to_delete in thumbnail_iterator(apps):
        print(f"{old_file_name} -> {new_file_name}")
        try:
            base_path = os.path.join(str(emoji.realm_id), "emoji/images")
            try:
                old_data = avatar_bucket.Object(f"{base_path}/{old_file_name}.original").get()
                original_bytes = old_data["Body"].read()
            except botocore.exceptions.ClientError as e:
                raise SkipImageError(f"Failed to read original file: {e}")

            metadata = old_data["Metadata"]
            # Make sure this metadata is up-to-date, while we're
            # in here; some early emoji are missing it
            metadata["realm_id"] = str(emoji.realm_id)
            if emoji.author_id:
                metadata["user_profile_id"] = str(emoji.author_id)

            avatar_bucket.Object(f"{base_path}/{new_file_name}.original").copy_from(
                CopySource=f"{settings.S3_AVATAR_BUCKET}/{base_path}/{old_file_name}.original",
                MetadataDirective="REPLACE",
                Metadata=metadata,
                ContentDisposition=old_data["ContentDisposition"],
                ContentType=old_data["ContentType"],
                CacheControl="public, max-age=31536000, immutable",
            )

            content_type = guess_type(new_file_name)[0]
            if content_type is None or not content_type.startswith("image/"):
                raise SkipImageError(f"Content is unknown or not an image: {content_type}")
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

            for path in to_delete:
                with contextlib.suppress(botocore.exceptions.ClientError):
                    avatar_bucket.Object(f"{base_path}/{path}").delete()
        except SkipImageError as e:
            logging.error(
                "Failed to re-thumbnail %s/emoji/images/%s: %s", emoji.realm_id, emoji.file_name, e
            )


def used_emoji_filenames(apps: StateApps, realm: Any) -> Set[str]:
    # We can remove the old filename for any emoji that is _not_
    # referenced in the rendered body of a message; re-rending is
    # complicated and time-consuming, and email digests exist
    # referencing the URLs regardless.
    Message = apps.get_model("zerver", "Message")
    BATCH_SIZE = 1000
    seen = set()
    min_id = 0
    while True:
        messages = Message.objects.filter(
            realm=realm,
            id__gt=min_id,
            rendered_content__contains=f"/user_avatars/{realm.id}/emoji/images/",
        )[:BATCH_SIZE]

        for message in messages:
            for match in re.findall(
                rf'/user_avatars/{realm.id}/emoji/images/([^"]+)', message.rendered_content
            ):
                seen.add(match)

        if len(messages) < BATCH_SIZE:
            break
        min_id = messages[-1].id
    return seen


def thumbnail_iterator(apps: StateApps) -> Iterator[Tuple[Any, str, str, List[str]]]:
    Realm = apps.get_model("zerver", "Realm")
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    for realm in Realm.objects.filter(realmemoji__isnull=False):
        seen_file_names = used_emoji_filenames(apps, realm)
        emoji_list = RealmEmoji.objects.filter(realm=realm)
        for emoji in emoji_list:
            old_file_name = emoji.file_name
            new_file_name = get_emoji_file_name(emoji.file_name, emoji.id)
            if old_file_name == new_file_name:
                continue

            to_delete = []
            if old_file_name not in seen_file_names:
                filename_no_extension = os.path.splitext(old_file_name)[0]
                to_delete = [
                    f"{old_file_name}.original",
                    f"{old_file_name}",
                    f"still/{filename_no_extension}.png",
                ]
            yield emoji, old_file_name, new_file_name, to_delete


def thumbnail_emoji(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    if settings.LOCAL_AVATARS_DIR is not None:
        thumbnail_local_emoji(apps)
    else:
        thumbnail_s3_emoji(apps)


class Migration(migrations.Migration):
    atomic = False
    elidable = True

    dependencies = [
        ("zerver", "0542_copy_avatar_images"),
    ]

    operations = [migrations.RunPython(thumbnail_emoji, elidable=True)]
