# Useful reading is https://zulip.readthedocs.io/en/latest/subsystems/front-end-build-process.html

import os
import shutil
from typing import Any, Dict, List, Tuple

from django.conf import settings
from django.contrib.staticfiles.storage import ManifestStaticFilesStorage
from pipeline.storage import PipelineMixin

from zerver.lib.str_utils import force_str

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
                new_file.write(force_str(header + orig_contents, encoding=settings.FILE_CHARSET))

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
        to_remove = ['templates', 'styles', 'js']

        for tree in to_remove:
            shutil.rmtree(os.path.join(root, tree))

        is_valid = lambda p: all([not p.startswith(k) for k in to_remove])

        paths = {k: v for k, v in paths.items() if is_valid(k)}
        super_class = super()
        if hasattr(super_class, 'post_process'):
            return super_class.post_process(paths, dry_run, **kwargs)  # type: ignore # https://github.com/python/mypy/issues/2956

        return []

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
                   ManifestStaticFilesStorage):
    pass
