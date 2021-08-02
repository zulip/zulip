#!/usr/bin/env python3
import argparse
import os
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ZULIP_PATH)

from scripts.lib.zulip_tools import may_be_perform_purging, parse_cache_script_args

YARN_CACHE_PATH = os.path.expanduser("~/.cache/yarn/")
CURRENT_VERSION = "v6"


def remove_unused_versions_dir(args: argparse.Namespace) -> None:
    """Deletes cache data from obsolete Yarn versions.

    Yarn does not provide an interface for removing obsolete data from
    ~/.cache/yarn for packages that you haven't installed in years; but one
    can always remove the cache entirely.
    """
    current_version_dir = os.path.join(YARN_CACHE_PATH, CURRENT_VERSION)
    try:
        dirs_to_purge = {
            os.path.join(YARN_CACHE_PATH, directory)
            for directory in os.listdir(YARN_CACHE_PATH)
            if directory != CURRENT_VERSION
        }
    except FileNotFoundError:
        return

    no_headings = getattr(args, "no_headings", False)
    may_be_perform_purging(
        dirs_to_purge,
        {current_version_dir},
        "yarn cache",
        args.dry_run,
        args.verbose,
        no_headings,
    )


def main(args: argparse.Namespace) -> None:
    remove_unused_versions_dir(args)


if __name__ == "__main__":
    args = parse_cache_script_args("This script cleans redundant Zulip yarn caches.")
    main(args)
