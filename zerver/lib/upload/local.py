import logging
import os
import random
import secrets
import shutil
from datetime import datetime
from typing import IO, Any, BinaryIO, Callable, Iterator, Literal, Optional, Tuple

from django.conf import settings

from zerver.lib.avatar_hash import user_avatar_path
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.upload.base import (
    MEDIUM_AVATAR_SIZE,
    ZulipUploadBackend,
    create_attachment,
    resize_avatar,
    resize_emoji,
    resize_logo,
    sanitize_name,
)
from zerver.lib.utils import assert_is_not_none
from zerver.models import Realm, RealmEmoji, UserProfile


def assert_is_local_storage_path(type: Literal["avatars", "files"], full_path: str) -> None:
    """
    Verify that we are only reading and writing files under the
    expected paths.  This is expected to be already enforced at other
    layers, via cleaning of user input, but we assert it here for
    defense in depth.
    """
    assert settings.LOCAL_UPLOADS_DIR is not None
    type_path = os.path.join(settings.LOCAL_UPLOADS_DIR, type)
    assert os.path.commonpath([type_path, full_path]) == type_path


def write_local_file(type: Literal["avatars", "files"], path: str, file_data: bytes) -> None:
    file_path = os.path.join(assert_is_not_none(settings.LOCAL_UPLOADS_DIR), type, path)
    assert_is_local_storage_path(type, file_path)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(file_data)


def read_local_file(type: Literal["avatars", "files"], path: str) -> bytes:
    file_path = os.path.join(assert_is_not_none(settings.LOCAL_UPLOADS_DIR), type, path)
    assert_is_local_storage_path(type, file_path)

    with open(file_path, "rb") as f:
        return f.read()


def delete_local_file(type: Literal["avatars", "files"], path: str) -> bool:
    file_path = os.path.join(assert_is_not_none(settings.LOCAL_UPLOADS_DIR), type, path)
    assert_is_local_storage_path(type, file_path)

    if os.path.isfile(file_path):
        # This removes the file but the empty folders still remain.
        os.remove(file_path)
        return True
    file_name = path.split("/")[-1]
    logging.warning("%s does not exist. Its entry in the database will be removed.", file_name)
    return False


class LocalUploadBackend(ZulipUploadBackend):
    def get_public_upload_root_url(self) -> str:
        return "/user_avatars/"

    def generate_message_upload_path(self, realm_id: str, uploaded_file_name: str) -> str:
        # Split into 256 subdirectories to prevent directories from getting too big
        return "/".join(
            [
                realm_id,
                format(random.randint(0, 255), "x"),
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

        path = self.generate_message_upload_path(str(target_realm.id), uploaded_file_name)

        write_local_file("files", path, file_data)
        create_attachment(uploaded_file_name, path, user_profile, target_realm, uploaded_file_size)
        return "/user_uploads/" + path

    def save_attachment_contents(self, path_id: str, filehandle: BinaryIO) -> None:
        filehandle.write(read_local_file("files", path_id))

    def delete_message_attachment(self, path_id: str) -> bool:
        return delete_local_file("files", path_id)

    def all_message_attachments(self) -> Iterator[Tuple[str, datetime]]:
        assert settings.LOCAL_UPLOADS_DIR is not None
        for dirname, _, files in os.walk(settings.LOCAL_UPLOADS_DIR + "/files"):
            for f in files:
                fullpath = os.path.join(dirname, f)
                yield (
                    os.path.relpath(fullpath, settings.LOCAL_UPLOADS_DIR + "/files"),
                    timestamp_to_datetime(os.path.getmtime(fullpath)),
                )

    def get_avatar_url(self, hash_key: str, medium: bool = False) -> str:
        medium_suffix = "-medium" if medium else ""
        return f"/user_avatars/{hash_key}{medium_suffix}.png"

    def write_avatar_images(self, file_path: str, image_data: bytes) -> None:
        write_local_file("avatars", file_path + ".original", image_data)

        resized_data = resize_avatar(image_data)
        write_local_file("avatars", file_path + ".png", resized_data)

        resized_medium = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        write_local_file("avatars", file_path + "-medium.png", resized_medium)

    def upload_avatar_image(
        self,
        user_file: IO[bytes],
        acting_user_profile: UserProfile,
        target_user_profile: UserProfile,
        content_type: Optional[str] = None,
    ) -> None:
        file_path = user_avatar_path(target_user_profile)

        image_data = user_file.read()
        self.write_avatar_images(file_path, image_data)

    def copy_avatar(self, source_profile: UserProfile, target_profile: UserProfile) -> None:
        source_file_path = user_avatar_path(source_profile)
        target_file_path = user_avatar_path(target_profile)

        image_data = read_local_file("avatars", source_file_path + ".original")
        self.write_avatar_images(target_file_path, image_data)

    def ensure_avatar_image(self, user_profile: UserProfile, is_medium: bool = False) -> None:
        file_extension = "-medium.png" if is_medium else ".png"
        file_path = user_avatar_path(user_profile)

        output_path = os.path.join(
            assert_is_not_none(settings.LOCAL_AVATARS_DIR),
            file_path + file_extension,
        )
        if os.path.isfile(output_path):
            return

        image_path = os.path.join(
            assert_is_not_none(settings.LOCAL_AVATARS_DIR),
            file_path + ".original",
        )
        with open(image_path, "rb") as f:
            image_data = f.read()
        if is_medium:
            resized_avatar = resize_avatar(image_data, MEDIUM_AVATAR_SIZE)
        else:
            resized_avatar = resize_avatar(image_data)
        write_local_file("avatars", file_path + file_extension, resized_avatar)

    def delete_avatar_image(self, user: UserProfile) -> None:
        path_id = user_avatar_path(user)

        delete_local_file("avatars", path_id + ".original")
        delete_local_file("avatars", path_id + ".png")
        delete_local_file("avatars", path_id + "-medium.png")

    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        return f"/user_avatars/{realm_id}/realm/icon.png?version={version}"

    def upload_realm_icon_image(self, icon_file: IO[bytes], user_profile: UserProfile) -> None:
        upload_path = self.realm_avatar_and_logo_path(user_profile.realm)
        image_data = icon_file.read()
        write_local_file("avatars", os.path.join(upload_path, "icon.original"), image_data)

        resized_data = resize_avatar(image_data)
        write_local_file("avatars", os.path.join(upload_path, "icon.png"), resized_data)

    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        if night:
            file_name = "night_logo.png"
        else:
            file_name = "logo.png"
        return f"/user_avatars/{realm_id}/realm/{file_name}?version={version}"

    def upload_realm_logo_image(
        self, logo_file: IO[bytes], user_profile: UserProfile, night: bool
    ) -> None:
        upload_path = self.realm_avatar_and_logo_path(user_profile.realm)
        if night:
            original_file = "night_logo.original"
            resized_file = "night_logo.png"
        else:
            original_file = "logo.original"
            resized_file = "logo.png"
        image_data = logo_file.read()
        write_local_file("avatars", os.path.join(upload_path, original_file), image_data)

        resized_data = resize_logo(image_data)
        write_local_file("avatars", os.path.join(upload_path, resized_file), resized_data)

    def get_emoji_url(self, emoji_file_name: str, realm_id: int, still: bool = False) -> str:
        if still:
            return os.path.join(
                "/user_avatars",
                RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
                    realm_id=realm_id,
                    emoji_filename_without_extension=os.path.splitext(emoji_file_name)[0],
                ),
            )
        else:
            return os.path.join(
                "/user_avatars",
                RealmEmoji.PATH_ID_TEMPLATE.format(
                    realm_id=realm_id, emoji_file_name=emoji_file_name
                ),
            )

    def upload_emoji_image(
        self, emoji_file: IO[bytes], emoji_file_name: str, user_profile: UserProfile
    ) -> bool:
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=user_profile.realm_id,
            emoji_file_name=emoji_file_name,
        )

        image_data = emoji_file.read()
        write_local_file("avatars", f"{emoji_path}.original", image_data)
        resized_image_data, is_animated, still_image_data = resize_emoji(image_data)
        write_local_file("avatars", emoji_path, resized_image_data)
        if is_animated:
            assert still_image_data is not None
            still_path = RealmEmoji.STILL_PATH_ID_TEMPLATE.format(
                realm_id=user_profile.realm_id,
                emoji_filename_without_extension=os.path.splitext(emoji_file_name)[0],
            )
            write_local_file("avatars", still_path, still_image_data)
        return is_animated

    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        # export_path has a leading `/`
        return realm.uri + export_path

    def upload_export_tarball(
        self,
        realm: Realm,
        tarball_path: str,
        percent_callback: Optional[Callable[[Any], None]] = None,
    ) -> str:
        path = os.path.join(
            "exports",
            str(realm.id),
            secrets.token_urlsafe(18),
            os.path.basename(tarball_path),
        )
        abs_path = os.path.join(assert_is_not_none(settings.LOCAL_AVATARS_DIR), path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        shutil.copy(tarball_path, abs_path)
        public_url = realm.uri + "/user_avatars/" + path
        return public_url

    def delete_export_tarball(self, export_path: str) -> Optional[str]:
        # Get the last element of a list in the form ['user_avatars', '<file_path>']
        assert export_path.startswith("/")
        file_path = export_path[1:].split("/", 1)[-1]
        if delete_local_file("avatars", file_path):
            return export_path
        return None
