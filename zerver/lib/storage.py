# Useful reading is https://zulip.readthedocs.io/en/latest/subsystems/front-end-build-process.html

import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from pipeline.storage import PipelineMixin

class AddHeaderMixin:
    def post_process(self, paths: Dict[str, Tuple['ZulipStorage', str]], dry_run: bool=False,
                     **kwargs: Any) -> List[Tuple[str, str, bool]]:
        if dry_run:
            return []

        with open(settings.STATIC_HEADER_FILE, 'rb') as header_file:
            header = header_file.read().decode(settings.FILE_CHARSET)

        # A dictionary of path to tuples of (old_path, new_path,
        # processed).  The return value of this method is the values
        # of this dictionary
        ret_dict = {}

        for name in paths:
            storage, path = paths[name]

            if not path.startswith('min/') or not path.endswith('.css'):
                ret_dict[path] = (path, path, False)
                continue

            # Prepend the header
            with storage.open(path, 'rb') as orig_file:
                orig_contents = orig_file.read().decode(settings.FILE_CHARSET)

            storage.delete(path)

            with storage.open(path, 'w') as new_file:
                new_file.write(header + orig_contents)

            ret_dict[path] = (path, path, True)

        super_class = super()
        if hasattr(super_class, 'post_process'):
            super_ret = super_class.post_process(paths, dry_run, **kwargs)  # type: ignore # https://github.com/python/mypy/issues/2956
        else:
            super_ret = []

        # Merge super class's return value with ours
        for val in super_ret:
            old_path, new_path, processed = val
            if processed:
                ret_dict[old_path] = val

        return list(ret_dict.values())


class RemoveUnminifiedFilesMixin:
    def post_process(self, paths: Dict[str, Tuple['ZulipStorage', str]], dry_run: bool=False,
                     **kwargs: Any) -> List[Tuple[str, str, bool]]:
        if dry_run:
            return []

        root = settings.STATIC_ROOT
        to_remove = ['js']

        for tree in to_remove:
            shutil.rmtree(os.path.join(root, tree))

        is_valid = lambda p: all([not p.startswith(k) for k in to_remove])

        paths = {k: v for k, v in paths.items() if is_valid(k)}
        super_class = super()
        if hasattr(super_class, 'post_process'):
            return super_class.post_process(paths, dry_run, **kwargs)  # type: ignore # https://github.com/python/mypy/issues/2956

        return []

class IgnoreBundlesManifestStaticFilesStorage(ManifestStaticFilesStorage):
    def hashed_name(self, name: str, content: Optional[str]=None, filename: Optional[str]=None) -> str:
        ext = os.path.splitext(name)[1]
        if (name.startswith("webpack-bundles") and
                ext in ['.js', '.css', '.map']):
            # Hack to avoid renaming already-hashnamed webpack bundles
            # when minifying; this was causing every bundle to have
            # two hashes appended to its name, one by webpack and one
            # here.  We can't just skip processing of these bundles,
            # since we do need the Django storage to add these to the
            # manifest for django_webpack_loader to work.  So, we just
            # use a no-op hash function for these already-hashed
            # assets.
            return name
        if ext in ['.png', '.gif', '.jpg', '.svg']:
            # Similarly, don't hash-rename image files; we only serve
            # the original file paths (not the hashed file paths), and
            # so the only effect of hash-renaming these is to increase
            # the size of release tarballs with duplicate copies of thesex.
            #
            # One could imagine a future world in which we instead
            # used the hashed paths for these; in that case, though,
            # we should instead be removing the non-hashed paths.
            return name
        if ext in ['json', 'po', 'mo', 'mp3', 'ogg', 'html']:
            # And same story for translation files, sound files, etc.
            return name
        return super().hashed_name(name, content, filename)

if settings.PRODUCTION:
    # This is a hack to use staticfiles.json from within the
    # deployment, rather than a directory under STATIC_ROOT.  By doing
    # so, we can use a different copy of staticfiles.json for each
    # deployment, which ensures that we always use the correct static
    # assets for each deployment.
    ManifestStaticFilesStorage.manifest_name = os.path.join(settings.DEPLOY_ROOT,
                                                            "staticfiles.json")
    orig_path = ManifestStaticFilesStorage.path

    def path(self: ManifestStaticFilesStorage, name: str) -> str:
        if name == ManifestStaticFilesStorage.manifest_name:
            return name
        return orig_path(self, name)
    ManifestStaticFilesStorage.path = path

class ZulipStorage(PipelineMixin,
                   AddHeaderMixin, RemoveUnminifiedFilesMixin,
                   IgnoreBundlesManifestStaticFilesStorage):
    pass
