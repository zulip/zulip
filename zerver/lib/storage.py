# Useful reading is:
# https://zulip.readthedocs.io/en/latest/subsystems/html-css.html#front-end-build-process

import os
from typing import Optional

from django.conf import settings
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from django.core.files.base import File
from django.core.files.storage import FileSystemStorage

if settings.DEBUG:
    from django.contrib.staticfiles.finders import find

    def static_path(path: str) -> str:
        return find(path) or "/nonexistent"

else:

    def static_path(path: str) -> str:
        return os.path.join(settings.STATIC_ROOT, path)


class IgnoreBundlesManifestStaticFilesStorage(ManifestStaticFilesStorage):
    def hashed_name(
        self, name: str, content: Optional["File[bytes]"] = None, filename: Optional[str] = None
    ) -> str:
        ext = os.path.splitext(name)[1]
        if name.startswith("webpack-bundles"):
            # Hack to avoid renaming already-hashnamed webpack bundles
            # when minifying; this was causing every bundle to have
            # two hashes appended to its name, one by webpack and one
            # here.  We can't just skip processing of these bundles,
            # since we do need the Django storage to add these to the
            # manifest for django_webpack_loader to work.  So, we just
            # use a no-op hash function for these already-hashed
            # assets.
            return name
        if name == "generated/emoji/emoji_api.json":
            # Unlike most .json files, we do want to hash this file;
            # its hashed URL is returned as part of the API.  See
            # data_url() in zerver/lib/emoji.py.
            return super().hashed_name(name, content, filename)
        if ext in [".png", ".gif", ".jpg", ".svg"]:
            # Similarly, don't hash-rename image files; we only serve
            # the original file paths (not the hashed file paths), and
            # so the only effect of hash-renaming these is to increase
            # the size of release tarballs with duplicate copies of these.
            #
            # One could imagine a future world in which we instead
            # used the hashed paths for these; in that case, though,
            # we should instead be removing the non-hashed paths.
            return name
        if ext in [".json", ".po", ".mo", ".mp3", ".ogg", ".html", ".md"]:
            # And same story for translation files, sound files, etc.
            return name
        return super().hashed_name(name, content, filename)


class ZulipStorage(IgnoreBundlesManifestStaticFilesStorage):
    # This is a hack to use staticfiles.json from within the
    # deployment, rather than a directory under STATIC_ROOT.  By doing
    # so, we can use a different copy of staticfiles.json for each
    # deployment, which ensures that we always use the correct static
    # assets for each deployment.
    def __init__(self) -> None:
        super().__init__(manifest_storage=FileSystemStorage(location=settings.DEPLOY_ROOT))
