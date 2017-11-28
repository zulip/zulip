import logging
import os
import sys
from distutils.version import StrictVersion
from typing import Any, List

import pip
from pip import main, commands
from pip.commands.download import DownloadCommand as BaseDownloadCommand
from pip.exceptions import CommandError
from pip.index import FormatControl
from pip.req import RequirementSet
from pip.utils import ensure_dir, normalize_path
from pip.utils.build import BuildDirectory
from pip.utils.filesystem import check_path_owner

logger = logging.getLogger(__name__)

class DownloadCommand(BaseDownloadCommand):
    def run(self, options: Any, args: List[str]) -> RequirementSet:
        """
        This function applies the patch in the following commit:
        https://github.com/pypa/pip/pull/4529/commits/2d97891497d4511ad3426a14c1ffff4c086aca4e

        Rest of this function is copied from
        pip.commands.download.DownloadCommand.run.
        """
        options.ignore_installed = True

        if options.python_version:
            python_versions = [options.python_version]
        else:
            python_versions = None

        dist_restriction_set = any([
            options.python_version,
            options.platform,
            options.abi,
            options.implementation,
        ])
        binary_only = FormatControl(set(), set([':all:']))
        no_sdist_dependencies = (
            options.format_control != binary_only and
            not options.ignore_dependencies
        )
        if dist_restriction_set and no_sdist_dependencies:
            raise CommandError(
                "When restricting platform and interpreter constraints using "
                "--python-version, --platform, --abi, or --implementation, "
                "either --no-deps must be set, or --only-binary=:all: must be "
                "set and --no-binary must not be set (or must be set to "
                ":none:)."
            )

        options.src_dir = os.path.abspath(options.src_dir)
        options.download_dir = normalize_path(options.download_dir)

        ensure_dir(options.download_dir)

        with self._build_session(options) as session:
            finder = self._build_package_finder(
                options=options,
                session=session,
                platform=options.platform,
                python_versions=python_versions,
                abi=options.abi,
                implementation=options.implementation,
            )
            build_delete = (not (options.no_clean or options.build_dir))
            if options.cache_dir and not check_path_owner(options.cache_dir):
                logger.warning(
                    "The directory '%s' or its parent directory is not owned "
                    "by the current user and caching wheels has been "
                    "disabled. check the permissions and owner of that "
                    "directory. If executing pip with sudo, you may want "
                    "sudo's -H flag.",
                    options.cache_dir,
                )
                options.cache_dir = None

            with BuildDirectory(options.build_dir,
                                delete=build_delete) as build_dir:

                requirement_set = RequirementSet(
                    build_dir=build_dir,
                    src_dir=options.src_dir,
                    download_dir=options.download_dir,
                    ignore_installed=True,
                    ignore_dependencies=options.ignore_dependencies,
                    session=session,
                    isolated=options.isolated_mode,
                    require_hashes=options.require_hashes
                )
                self.populate_requirement_set(
                    requirement_set,
                    args,
                    options,
                    finder,
                    session,
                    self.name,
                    None
                )

                if not requirement_set.has_requirements:
                    return

                requirement_set.prepare_files(finder)

                downloaded = ' '.join([
                    req.name for req in requirement_set.successfully_downloaded
                ])
                if downloaded:
                    logger.info(
                        'Successfully downloaded %s', downloaded
                    )

                # Clean up
                if not options.no_clean:
                    requirement_set.cleanup_files()

        return requirement_set

def monkey_patch_download_command() -> None:
    commands.commands_dict[DownloadCommand.name] = DownloadCommand

if __name__ == '__main__':
    if StrictVersion(pip.__version__) > StrictVersion("9.0.1"):
        from warnings import warn
        warn("This script is deprecated. Use pip directly.")
        sys.exit(1)

    monkey_patch_download_command()
    args = ['download'] + sys.argv[1:]
    sys.exit(main(args=args))
