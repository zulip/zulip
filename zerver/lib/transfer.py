import logging
import os
from glob import glob

import magic
from django.conf import settings

from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.mime_types import guess_type
from zerver.lib.parallel import run_parallel
from zerver.lib.thumbnail import BadImageError
from zerver.lib.upload import upload_emoji_image, write_avatar_images
from zerver.lib.upload.s3 import S3UploadBackend, upload_content_to_s3
from zerver.models import Attachment, RealmEmoji, UserProfile

s3backend = S3UploadBackend()
mime_magic = magic.Magic(mime=True)


def transfer_uploads_to_s3(processes: int) -> None:
    # TODO: Eventually, we'll want to add realm icon and logo
    transfer_avatars_to_s3(processes)
    transfer_message_files_to_s3(processes)
    transfer_emoji_to_s3(processes)


def _transfer_avatar_to_s3(user: UserProfile) -> None:
    avatar_path = user_avatar_path(user)
    assert settings.LOCAL_UPLOADS_DIR is not None
    assert settings.LOCAL_AVATARS_DIR is not None
    file_path = os.path.join(settings.LOCAL_AVATARS_DIR, avatar_path)
    try:
        with open(file_path + ".original", "rb") as f:
            # We call write_avatar_images directly to walk around the
            # content-type checking in upload_avatar_image.  We don't
            # know the original file format, and we don't need to know
            # it because we never serve them directly.
            write_avatar_images(
                user_avatar_path(user, future=False),
                user,
                f.read(),
                content_type="application/octet-stream",
                backend=s3backend,
                future=False,
            )
            logging.info("Uploaded avatar for %s in realm %s", user.id, user.realm.name)
    except FileNotFoundError:
        pass


def transfer_avatars_to_s3(processes: int) -> None:
    run_parallel(_transfer_avatar_to_s3, UserProfile.objects.all(), processes)


def _transfer_message_files_to_s3(attachment: Attachment) -> None:
    assert settings.LOCAL_UPLOADS_DIR is not None
    assert settings.LOCAL_FILES_DIR is not None
    file_path = os.path.join(settings.LOCAL_FILES_DIR, attachment.path_id)
    try:
        with open(file_path, "rb") as f:
            guessed_type = guess_type(attachment.file_name)[0]
            upload_content_to_s3(
                s3backend.uploads_bucket,
                attachment.path_id,
                guessed_type,
                attachment.owner,
                f.read(),
                storage_class=settings.S3_UPLOADS_STORAGE_CLASS,
            )
            logging.info("Uploaded message file in path %s", file_path)
        thumbnail_dir = os.path.join(settings.LOCAL_FILES_DIR, "thumbnail", attachment.path_id)
        if os.path.isdir(thumbnail_dir):
            thumbnails = 0
            for thumbnail_path in glob(os.path.join(thumbnail_dir, "*")):
                with open(thumbnail_path, "rb") as f:
                    # This relies on the thumbnails having guessable
                    # content-type from their path, in order to avoid
                    # having to fetch the ImageAttachment inside the
                    # ProcessPoolExecutor.  We also have no clean way
                    # to prefetch those rows via select_related in the
                    # outer query, as they match on `path_id`, which
                    # is not supported as a foreign key.
                    guessed_type = guess_type(thumbnail_path)[0]
                    upload_content_to_s3(
                        s3backend.uploads_bucket,
                        os.path.join(
                            "thumbnail", attachment.path_id, os.path.basename(thumbnail_path)
                        ),
                        guessed_type,
                        None,
                        f.read(),
                        storage_class=settings.S3_UPLOADS_STORAGE_CLASS,
                    )
                thumbnails += 1
            logging.info(
                "Uploaded %d thumbnails into %s",
                thumbnails,
                os.path.join("thumbnail", attachment.path_id),
            )
    except FileNotFoundError:  # nocoverage
        pass


def transfer_message_files_to_s3(processes: int) -> None:
    run_parallel(_transfer_message_files_to_s3, Attachment.objects.all(), processes)


def _transfer_emoji_to_s3(realm_emoji: RealmEmoji) -> None:
    if not realm_emoji.file_name:
        return  # nocoverage
    emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
        realm_id=realm_emoji.realm.id,
        emoji_file_name=realm_emoji.file_name,
    )
    assert settings.LOCAL_UPLOADS_DIR is not None
    assert settings.LOCAL_AVATARS_DIR is not None
    content_type = guess_type(emoji_path)[0]
    emoji_path = os.path.join(settings.LOCAL_AVATARS_DIR, emoji_path) + ".original"
    if content_type is None:  # nocoverage
        # This should not be possible after zerver/migrations/0553_copy_emoji_images.py
        logging.error("Emoji %d has no recognizable file extension", realm_emoji.id)
        return
    try:
        with open(emoji_path, "rb") as f:
            upload_emoji_image(
                f, realm_emoji.file_name, realm_emoji.author, content_type, backend=s3backend
            )
            logging.info("Uploaded emoji file in path %s", emoji_path)
    except FileNotFoundError:  # nocoverage
        logging.error("Emoji %d could not be loaded from local disk", realm_emoji.id)
    except BadImageError as e:  # nocoverage
        # This should not be possible after zerver/migrations/0553_copy_emoji_images.py
        logging.error("Emoji %d is invalid: %s", realm_emoji.id, e)


def transfer_emoji_to_s3(processes: int) -> None:
    run_parallel(_transfer_emoji_to_s3, RealmEmoji.objects.filter(), processes)
