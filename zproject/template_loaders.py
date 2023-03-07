from pathlib import Path
from typing import List, Union

from django.template.loaders import app_directories


class TwoFactorLoader(app_directories.Loader):
    def get_dirs(self) -> List[Union[str, Path]]:
        dirs = super().get_dirs()
        # app_directories.Loader returns only a list of
        # Path objects by calling get_app_template_dirs
        two_factor_dirs: List[Union[str, Path]] = []
        for d in dirs:
            assert isinstance(d, Path)
            if d.match("two_factor/*"):
                two_factor_dirs.append(d)
        return two_factor_dirs
