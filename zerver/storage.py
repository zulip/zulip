from __future__ import absolute_import

import os
import shutil
from typing import List, Any, Tuple

from django.conf import settings
from django.contrib.staticfiles.storage import CachedFilesMixin, StaticFilesStorage
from pipeline.storage import PipelineMixin

class AddHeaderMixin(object):
    def post_process(self, paths, dry_run=False, **kwargs):
        # type: (Dict[str, Tuple[ZulipStorage, str]], bool, **Any) -> List[Tuple[str, str, bool]]
        if dry_run:
            return []

        with open(settings.STATIC_HEADER_FILE) as header_file:
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
            with storage.open(path) as orig_file:
                orig_contents = orig_file.read().decode(settings.FILE_CHARSET)

            storage.delete(path)

            with storage.open(path, 'w') as new_file:
                new_file.write(header + orig_contents)

            ret_dict[path] = (path, path, True)

        super_class = super(AddHeaderMixin, self) # type: ignore # https://github.com/JukkaL/mypy/issues/857
        if hasattr(super_class, 'post_process'):
            super_ret = super_class.post_process(paths, dry_run, **kwargs)
        else:
            super_ret = []

        # Merge super class's return value with ours
        for val in super_ret:
            old_path, new_path, processed = val
            if processed:
                ret_dict[old_path] = val

        return list(ret_dict.values())


class RemoveUnminifiedFilesMixin(object):
    def post_process(self, paths, dry_run=False, **kwargs):
        # type: (Dict[str, Tuple[ZulipStorage, str]], bool, **Any) -> List[Tuple[str, str, bool]]
        if dry_run:
            return []

        root = settings.STATIC_ROOT
        to_remove = ['templates', 'styles', 'js']

        for tree in to_remove:
            shutil.rmtree(os.path.join(root, tree))

        is_valid = lambda p: all([not p.startswith(k) for k in to_remove])

        paths = {k: v for k, v in paths.items() if is_valid(k)}
        super_class = super(RemoveUnminifiedFilesMixin, self)  # type: ignore # https://github.com/JukkaL/mypy/issues/857
        if hasattr(super_class, 'post_process'):
            return super_class.post_process(paths, dry_run, **kwargs)

        return []


class ZulipStorage(PipelineMixin,
        AddHeaderMixin, RemoveUnminifiedFilesMixin,
        CachedFilesMixin, StaticFilesStorage):
    pass
