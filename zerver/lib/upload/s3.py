import logging
import os
import secrets
import urllib
from datetime import datetime
from mimetypes import guess_type
from typing import IO, Any, BinaryIO, Callable, Iterator, List, Literal, Optional, Tuple

import boto3
import botocore
from boto3.session import Session
from botocore.client import Config
from django.conf import settings
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.service_resource import Bucket, Object

from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.upload.base import (
    INLINE_MIME_TYPES,
    MEDIUM_AVATAR_SIZE,
    ZulipUploadBackend,
    create_attachment,
    resize_avatar,
    resize_emoji,
    resize_logo,
    sanitize_name,
)
from zerver.models import Realm, RealmEmoji, UserProfile

# Duration that the signed upload URLs that we redirect to when
# accessing uploaded files are available for clients to fetch before
# they expire.
SIGNED_UPLOAD_URL_DURATION = 60

# Performance note:
#
# For writing files to S3, the file could either be stored in RAM
# (if it is less than 2.5MiB or so) or an actual temporary file on disk.
#
# Because we set FILE_UPLOAD_MAX_MEMORY_SIZE to 0, only the latter case
# should occur in practice.
#
# This is great, because passing the pseudofile object that Django gives
# you to boto would be a pain.

# To come up with a s3 key we randomly generate a "directory". The
# "file name" is the original filename provided by the user run
# through a sanitization function.


# https://github.com/boto/botocore/issues/2644 means that the IMDS
# request _always_ pulls from the environment.  Monkey-patch the
# `should_bypass_proxies` function if we need to skip them, based
# on S3_SKIP_PROXY.
if settings.S3_SKIP_PROXY is True:  # nocoverage
    botocore.utils.should_bypass_proxies = lambda url: True


def get_bucket(bucket_name: str, session: Optional[Session] = None) -> Bucket:
    if session is None:
        session = Session(settings.S3_KEY, settings.S3_SECRET_KEY)
    bucket = session.resource(
        "s3", region_name=settings.S3_REGION, endpoint_url=settings.S3_ENDPOINT_URL
    ).Bucket(bucket_name)
    return bucket


def upload_image_to_s3(
    bucket: Bucket,
    file_name: str,
    content_type: Optional[str],
    user_profile: UserProfile,
    contents: bytes,
    storage_class: Literal[
        "GLACIER_IR",
        "INTELLIGENT_TIERING",
        "ONEZONE_IA",
        "REDUCED_REDUNDANCY",
        "STANDARD",
        "STANDARD_IA",
    ] = "STANDARD",
) -> None:
    key = bucket.Object(file_name)
    metadata = {
        "user_profile_id": str(user_profile.id),
        "realm_id": str(user_profile.realm_id),
    }

    content_disposition = ""
    if content_type is None:
        content_type = ""
    if content_type not in INLINE_MIME_TYPES:
        content_disposition = "attachment"

    key.put(
        Body=contents,
        Metadata=metadata,
        ContentType=content_type,
        ContentDisposition=content_disposition,
        StorageClass=storage_class,
    )


def get_signed_upload_url(path: str, force_download: bool = False) -> str:
    client = boto3.client(
        "s3",
        aws_access_key_id=settings.S3_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        endpoint_url=settings.S3_ENDPOINT_URL,
    )
    params = {
        "Bucket": settings.S3_AUTH_UPLOADS_BUCKET,
        "Key": path,
    }
    if force_download:
        params["ResponseContentDisposition"] = "attachment"

    return client.generate_presigned_url(
        ClientMethod="get_object",
        Params=params,
        ExpiresIn=SIGNED_UPLOAD_URL_DURATION,
        HttpMethod="GET",
    )


class S3UploadBackend(ZulipUploadBackend):
    def __init__(self) -> None:
        self.session = Session(settings.S3_KEY, settings.S3_SECRET_KEY)
        self.avatar_bucket = get_bucket(settings.S3_AVATAR_BUCKET, self.session)
        self.uploads_bucket = get_bucket(settings.S3_AUTH_UPLOADS_BUCKET, self.session)

        self._boto_client: Optional[S3Client] = None
        self.public_upload_url_base = self.construct_public_upload_url_base()

    def get_boto_client(self) -> S3Client:
        """
        Creating the client takes a long time so we need to cache it.
        """
        if self._boto_client is None:
            config = Config(signature_version=botocore.UNSIGNED)
            self._boto_client = self.session.client(
                "s3",
                region_name=settings.S3_REGION,
                endpoint_url=settings.S3_ENDPOINT_URL,
                config=config,
            )
        return self._boto_client

    def delete_file_from_s3(self, path_id: str, bucket: Bucket) -> bool:
        key = bucket.Object(path_id)

        try:
            key.load()
        except botocore.exceptions.ClientError:
            file_name = path_id.split("/")[-1]
            logging.warning(
                "%s does not exist. Its entry in the database will be removed.", file_name
            )
            return False
        key.delete()
        return True

    def construct_public_upload_url_base(self) -> str:
        # Return the pattern for public URL for a key in the S3 Avatar bucket.
        # For Amazon S3 itself, this will return the following:
        #     f"https://{self.avatar_bucket.name}.{network_location}/{key}"
        #
        # However, we need this function to properly handle S3 style
        # file upload backends that Zulip supports, which can have a
        # different URL format. Configuring no signature and providing
        # no access key makes `generate_presigned_url` just return the
        # normal public URL for a key.
        #
        # It unfortunately takes 2ms per query to call
        # generate_presigned_url, even with our cached boto
        # client. Since we need to potentially compute hundreds of
        # avatar URLs in single `GET /messages` request, we instead
        # back-compute the URL pattern here.

        DUMMY_KEY = "dummy_key_ignored"
        foo_url = self.get_boto_client().generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": self.avatar_bucket.name,
                "Key": DUMMY_KEY,
            },
            ExpiresIn=0,
        )
        split_url = urllib.parse.urlsplit(foo_url)
        assert split_url.path.endswith(f"/{DUMMY_KEY}")

        return urllib.parse.urlunsplit(
            (split_url.scheme, split_url.netloc, split_url.path[: -len(DUMMY_KEY)], "", "")
        )

    def get_public_upload_root_url(self) -> str:
        return self.public_upload_url_base

    def get_public_upload_url(
        self,
        key: str,
    ) -> str:
        assert not key.startswith("/")
        return urllib.parse.urljoin(self.public_upload_url_base, key)

    def generate_message_upload_path(self, realm_id: str, uploaded_file_name: str) -> str:
        return "/".join(
            [
                realm_id,
                secrets.token_urlsafe(18),
                sanitize_name(uploaded_file_name),
            ]
        )

    def upload_message_attachment(
        self,
        uploaded_file_name: str,
        uploaded_file_size: int,
        content_type: Optional[str],
        file_data: bytes,
        user_profile: UserProfile,
        target_realm: Optional[Realm] = None,
    ) -> str:
        if target_realm is None:
            target_realm = user_profile.realm
        s3_file_name = self.generate_message_upload_path(str(target_realm.id), uploaded_file_name)
        url = f"/user_uploads/{s3_file_name}"

        upload_image_to_s3(
            self.uploads_bucket,
            s3_file_name,
            content_type,
            user_profile,
            file_data,
            settings.S3_UPLOADS_STORAGE_CLASS,
        )

        create_attachment(
            uploaded_file_name, s3_file_name, user_profile, target_realm, uploaded_file_size
        )
        return url

    def save_attachment_contents(self, path_id: str, filehandle: BinaryIO) -> None:
        for chunk in self.uploads_bucket.Object(path_id).get()["Body"]:
            filehandle.write(chunk)

    def delete_message_attachment(self, path_id: str) -> bool:
        return self.delete_file_from_s3(path_id, self.uploads_bucket)

    def delete_message_attachments(self, path_ids: List[str]) -> None:
        self.uploads_bucket.delete_objects(
            Delete={"Objects": [{"Key": path_id} for path_id in path_ids]}
        )

    def all_message_attachments(self) -> Iterator[Tuple[str, datetime]]:
        client = self.session.client(
            "s3", region_name=settings.S3_REGION, endpoint_url=settings.S3_ENDPOINT_URL
        )
        paginator = client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=self.uploads_bucket.name)

        for page in page_iterator:
            if page["KeyCount"] > 0:
                for item in page["Contents"]:
                    yield (
                        item["Key"],
                        item["LastModified"],
                    )

    def write_avatar_images(
        self,
        s3_file_name: str,
        target_user_profile: UserProfile,
        image_data: bytes,
        content_type: Optional[str],
    ) -> None:
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".original",
            content_type,
            target_user_profile,
            image_data,
        )

        # custom 500px wide version
        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + "-medium.png",
            "image/png",
            target_user_profile,
            resized_medium,
        )

        resized_data = resize_avatar(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name,
            "image/png",
            target_user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_avatar_key(self, file_name: str) -> Object:
        key = self.avatar_bucket.Object(file_name)
        return key

    def get_avatar_url(self, hash_key: str, medium: bool = False) -> str:
        medium_suffix = "-medium.png" if medium else ""
        return self.get_public_upload_url(f"{hash_key}{medium_suffix}")

    def upload_avatar_image(
        self,
        user_file: IO[bytes],
        acting_user_profile: UserProfile,
        target_user_profile: UserProfile,
        content_type: Optional[str] = None,
    ) -> None:
        if content_type is None:
            content_type = guess_type(user_file.name)[0]
        s3_file_name = user_avatar_path(target_user_profile)

        image_data = user_file.read()
        self.write_avatar_images(s3_file_name, target_user_profile, image_data, content_type)

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        s3_source_file_name = user_avatar_path(source_profile)
        s3_target_file_name = user_avatar_path(target_profile)

        key = self.get_avatar_key(s3_source_file_name + ".original")
        image_data = key.get()["Body"].read()
        content_type = key.content_type

        self.write_avatar_images(s3_target_file_name, target_profile, image_data, content_type)

    def ensure_avatar_image(self, user_profile: UserProfile, is_medium: bool = False) -> None:
        # BUG: The else case should be user_avatar_path(user_profile) + ".png".
        # See #12852 for details on this bug and how to migrate it.
        file_extension = "-medium.png" if is_medium else ""
        file_path = user_avatar_path(user_profile)
        s3_file_name = file_path

        key = self.avatar_bucket.Object(file_path + ".original")
        image_data = key.get()["Body"].read()

        if is_medium:
            resized_avatar = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        else:
            resized_avatar = resize_avatar(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + file_extension,
            "image/png",
            user_profile,
            resized_avatar,
        )

    def delete_avatar_image(self, user: UserProfile) -> None:
        path_id = user_avatar_path(user)

        self.delete_file_from_s3(path_id + ".original", self.avatar_bucket)
        self.delete_file_from_s3(path_id + "-medium.png", self.avatar_bucket)
        self.delete_file_from_s3(path_id, self.avatar_bucket)

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        public_url = self.get_public_upload_url(f"{realm_id}/realm/icon.png")
        return public_url + f"?version={version}"

    def upload_realm_icon_image(self, icon_file: IO[bytes], user_profile: UserProfile) -> None:
        content_type = guess_type(icon_file.name)[0]
        s3_file_name = os.path.join(self.realm_avatar_and_logo_path(user_profile.realm), "icon")

        image_data = icon_file.read()
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".original",
            content_type,
            user_profile,
            image_data,
        )

        resized_data = resize_avatar(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".png",
            "image/png",
            user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        if not night:
            file_name = "logo.png"
        else:
            file_name = "night_logo.png"
        public_url = self.get_public_upload_url(f"{realm_id}/realm/{file_name}")
        return public_url + f"?version={version}"

    def upload_realm_logo_image(
        self, logo_file: IO[bytes], user_profile: UserProfile, night: bool
    ) -> None:
        content_type = guess_type(logo_file.name)[0]
        if night:
            basename = "night_logo"
        else:
            basename = "logo"
        s3_file_name = os.path.join(self.realm_avatar_and_logo_path(user_profile.realm), basename)

        image_data = logo_file.read()
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".original",
            content_type,
            user_profile,
            image_data,
        )

        resized_data = resize_logo(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            s3_file_name + ".png",
            "image/png",
            user_profile,
            resized_data,
        )
        # See avatar_url in avatar.py for URL.  (That code also handles the case
        # that users use gravatar.)

    def get_emoji_url(self, emoji_file_name: str, realm_id: int, still: bool = False) -> str:
        if still:
            emoji_path = RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
                realm_id=realm_id,
                emoji_filename_without_extension=os.path.splitext(emoji_file_name)[0],
            )
            return self.get_public_upload_url(emoji_path)
        else:
            emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
                realm_id=realm_id, emoji_file_name=emoji_file_name
            )
            return self.get_public_upload_url(emoji_path)

    def upload_emoji_image(
        self, emoji_file: IO[bytes], emoji_file_name: str, user_profile: UserProfile
    ) -> bool:
        content_type = guess_type(emoji_file_name)[0]
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=emoji_file_name,
        )

        image_data = emoji_file.read()
        upload_image_to_s3(
            self.avatar_bucket,
            f"{emoji_path}.original",
            content_type,
            user_profile,
            image_data,
        )

        resized_image_data, is_animated, still_image_data = resize_emoji(image_data)
        upload_image_to_s3(
            self.avatar_bucket,
            emoji_path,
            content_type,
            user_profile,
            resized_image_data,
        )
        if is_animated:
            still_path = RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
                realm_id=user_profile.realm_id,
                emoji_filename_without_extension=os.path.splitext(emoji_file_name)[0],
            )
            assert still_image_data is not None
            upload_image_to_s3(
                self.avatar_bucket,
                still_path,
                "image/png",
                user_profile,
                still_image_data,
            )

        return is_animated

    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        # export_path has a leading /
        return self.get_public_upload_url(export_path[1:])

    def upload_export_tarball(
        self,
        realm: Optional[Realm],
        tarball_path: str,
        percent_callback: Optional[Callable[[Any], None]] = None,
    ) -> str:
        # We use the avatar bucket, because it's world-readable.
        key = self.avatar_bucket.Object(
            os.path.join("exports", secrets.token_hex(16), os.path.basename(tarball_path))
        )

        if percent_callback is None:
            key.upload_file(Filename=tarball_path)
        else:
            key.upload_file(Filename=tarball_path, Callback=percent_callback)

        public_url = self.get_public_upload_url(key.key)
        return public_url

    def delete_export_tarball(self, export_path: str) -> Optional[str]:
        assert export_path.startswith("/")
        path_id = export_path[1:]
        if self.delete_file_from_s3(path_id, self.avatar_bucket):
            return export_path
        return None
