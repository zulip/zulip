import logging
import os
import random
import secrets
import shutil
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import IO, Any, Literal

import pyvips
from django.conf import settings
from typing_extensions import override

from zerver.lib.mime_types import guess_type
from zerver.lib.thumbnail import resize_logo, resize_realm_icon
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.lib.upload.base import StreamingSourceWithSize, ZulipUploadBackend
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


def read_local_file(type: Literal["avatars", "files"], path: str) -> Iterator[bytes]:
    file_path = os.path.join(assert_is_not_none(settings.LOCAL_UPLOADS_DIR), type, path)
    assert_is_local_storage_path(type, file_path)

    with open(file_path, "rb") as f:
        yield from iter(lambda: f.read(4 * 1024 * 1024), b"")


def delete_local_file(type: Literal["avatars", "files"], path: str) -> bool:
    file_path = os.path.join(assert_is_not_none(settings.LOCAL_UPLOADS_DIR), type, path)
    assert_is_local_storage_path(type, file_path)

    if os.path.isfile(file_path):
        os.remove(file_path)

        # Remove as many directories up the tree as are now empty
        directory = os.path.dirname(file_path)
        while directory != settings.LOCAL_UPLOADS_DIR:
            try:
                os.rmdir(directory)
                directory = os.path.dirname(directory)
            except OSError:
                break
        return True
    file_name = path.split("/")[-1]
    logging.warning("%s does not exist. Its entry in the database will be removed.", file_name)
    return False


class LocalUploadBackend(ZulipUploadBackend):
    @override
    def get_public_upload_root_url(self) -> str:
        return "/user_avatars/"

    @override
    def generate_message_upload_path(self, realm_id: str, sanitized_file_name: str) -> str:
        # Split into 256 subdirectories to prevent directories from getting too big
        return "/".join(
            [
                realm_id,
                format(random.randint(0, 255), "x"),
                secrets.token_urlsafe(18),
                sanitized_file_name,
            ]
        )

    @override
    def upload_message_attachment(
        self,
        path_id: str,
        filename: str,
        content_type: str,
        file_data: bytes,
        user_profile: UserProfile | None,
    ) -> None:
        write_local_file("files", path_id, file_data)

    @override
    def save_attachment_contents(self, path_id: str, filehandle: IO[bytes]) -> None:
        for chunk in read_local_file("files", path_id):
            filehandle.write(chunk)

    @override
    def attachment_vips_source(self, path_id: str) -> StreamingSourceWithSize:
        file_path = os.path.join(assert_is_not_none(settings.LOCAL_UPLOADS_DIR), "files", path_id)
        assert_is_local_storage_path("files", file_path)
        source = pyvips.Source.new_from_file(file_path)
        return StreamingSourceWithSize(size=os.path.getsize(file_path), source=source)

    @override
    def delete_message_attachment(self, path_id: str) -> bool:
        return delete_local_file("files", path_id)

    @override
    def all_message_attachments(
        self,
        include_thumbnails: bool = False,
        prefix: str = "",
    ) -> Iterator[tuple[str, datetime]]:
        assert settings.LOCAL_UPLOADS_DIR is not None
        top = settings.LOCAL_UPLOADS_DIR + "/files"
        start = top
        if prefix != "":
            start += f"/{prefix}"
        for dirname, subdirnames, files in os.walk(start):
            if not include_thumbnails and dirname == top and "thumbnail" in subdirnames:
                subdirnames.remove("thumbnail")
            for f in files:
                fullpath = os.path.join(dirname, f)
                yield (
                    os.path.relpath(fullpath, top),
                    timestamp_to_datetime(os.path.getmtime(fullpath)),
                )

    @override
    def get_avatar_url(self, hash_key: str, medium: bool = False) -> str:
        return "/user_avatars/" + self.get_avatar_path(hash_key, medium)

    @override
    def get_avatar_contents(self, file_path: str) -> tuple[bytes, str]:
        image_data = b"".join(read_local_file("avatars", file_path + ".original"))
        content_type = guess_type(file_path)[0]
        return image_data, content_type or "application/octet-stream"

    @override
    def upload_single_avatar_image(
        self,
        file_path: str,
        *,
        user_profile: UserProfile,
        image_data: bytes,
        content_type: str | None,
        future: bool = True,
    ) -> None:
        write_local_file("avatars", file_path, image_data)

    @override
    def delete_avatar_image(self, path_id: str) -> None:
        delete_local_file("avatars", path_id + ".original")
        delete_local_file("avatars", self.get_avatar_path(path_id, True))
        delete_local_file("avatars", self.get_avatar_path(path_id, False))

    @override
    def get_realm_icon_url(self, realm_id: int, version: int) -> str:
        return f"/user_avatars/{realm_id}/realm/icon.png?version={version}"

    @override
    def upload_realm_icon_image(
        self, icon_file: IO[bytes], user_profile: UserProfile, content_type: str
    ) -> None:
        upload_path = self.realm_avatar_and_logo_path(user_profile.realm)
        image_data = icon_file.read()
        write_local_file("avatars", os.path.join(upload_path, "icon.original"), image_data)

        resized_data = resize_realm_icon(image_data)
        write_local_file("avatars", os.path.join(upload_path, "icon.png"), resized_data)

    @override
    def get_realm_logo_url(self, realm_id: int, version: int, night: bool) -> str:
        if night:
            file_name = "night_logo.png"
        else:
            file_name = "logo.png"
        return f"/user_avatars/{realm_id}/realm/{file_name}?version={version}"

    @override
    def upload_realm_logo_image(
        self, logo_file: IO[bytes], user_profile: UserProfile, night: bool, content_type: str
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

    @override
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

    @override
    def upload_single_emoji_image(
        self, path: str, content_type: str | None, user_profile: UserProfile, image_data: bytes
    ) -> None:
        write_local_file("avatars", path, image_data)

    @override
    def get_export_tarball_url(self, realm: Realm, export_path: str) -> str:
        # export_path has a leading `/`
        return realm.url + export_path

    @override
    def upload_export_tarball(
        self,
        realm: Realm,
        tarball_path: str,
        percent_callback: Callable[[Any], None] | None = None,
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
        return self.get_export_tarball_url(realm, "/user_avatars/" + path)

    @override
    def delete_export_tarball(self, export_path: str) -> str | None:
        # Get the last element of a list in the form ['user_avatars', '<file_path>']
        assert export_path.startswith("/")
        file_path = export_path.removeprefix("/").split("/", 1)[-1]
        if delete_local_file("avatars", file_path):
            return export_path
        return None
