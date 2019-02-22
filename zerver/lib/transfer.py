import os
import logging

from django.conf import settings
from django.db import connection
from mimetypes import guess_type

from zerver.models import UserProfile, Attachment, RealmEmoji
from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.upload import S3UploadBackend, upload_image_to_s3
from zerver.lib.parallel import run_parallel

s3backend = S3UploadBackend()

def transfer_uploads_to_s3(processes: int) -> None:
    # TODO: Eventually, we'll want to add realm icon and logo
    transfer_avatars_to_s3(processes)
    transfer_message_files_to_s3(processes)
    transfer_emoji_to_s3(processes)

def transfer_avatars_to_s3(processes: int) -> None:
    def _transfer_avatar_to_s3(user: UserProfile) -> int:
        avatar_path = user_avatar_path(user)
        file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", avatar_path) + ".original"
        try:
            with open(file_path, 'rb') as f:
                s3backend.upload_avatar_image(f, user, user)
                logging.info("Uploaded avatar for {} in realm {}".format(user.email, user.realm.name))
        except FileNotFoundError:
            pass
        return 0

    users = list(UserProfile.objects.all())
    if processes == 1:
        for user in users:
            _transfer_avatar_to_s3(user)
    else:  # nocoverage
        output = []
        connection.close()
        for (status, job) in run_parallel(_transfer_avatar_to_s3, users, processes):
            output.append(job)

def transfer_message_files_to_s3(processes: int) -> None:
    def _transfer_message_files_to_s3(attachment: Attachment) -> int:
        file_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "files", attachment.path_id)
        try:
            with open(file_path, 'rb') as f:
                bucket_name = settings.S3_AUTH_UPLOADS_BUCKET
                guessed_type = guess_type(attachment.file_name)[0]
                upload_image_to_s3(bucket_name, attachment.path_id, guessed_type, attachment.owner, f.read())
                logging.info("Uploaded message file in path {}".format(file_path))
        except FileNotFoundError:  # nocoverage
            pass
        return 0

    attachments = list(Attachment.objects.all())
    if processes == 1:
        for attachment in attachments:
            _transfer_message_files_to_s3(attachment)
    else:  # nocoverage
        output = []
        connection.close()
        for status, job in run_parallel(_transfer_message_files_to_s3, attachments, processes):
            output.append(job)

def transfer_emoji_to_s3(processes: int) -> None:
    def _transfer_emoji_to_s3(realm_emoji: RealmEmoji) -> int:
        if not realm_emoji.file_name or not realm_emoji.author:
            return 0  # nocoverage
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=realm_emoji.realm.id,
            emoji_file_name=realm_emoji.file_name
        )
        emoji_path = os.path.join(settings.LOCAL_UPLOADS_DIR, "avatars", emoji_path) + ".original"
        try:
            with open(emoji_path, 'rb') as f:
                s3backend.upload_emoji_image(f, realm_emoji.file_name, realm_emoji.author)
                logging.info("Uploaded emoji file in path {}".format(emoji_path))
        except FileNotFoundError:  # nocoverage
            pass
        return 0

    realm_emojis = list(RealmEmoji.objects.filter())
    if processes == 1:
        for realm_emoji in realm_emojis:
            _transfer_emoji_to_s3(realm_emoji)
    else:  # nocoverage
        output = []
        connection.close()
        for status, job in run_parallel(_transfer_emoji_to_s3, realm_emojis, processes):
            output.append(job)
