#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime, timedelta

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ZULIP_PATH)

from scripts.lib.zulip_tools import may_be_perform_purging, parse_cache_script_args

YARN_CACHE_PATH = os.path.expanduser("~/.cache/yarn/")
CURRENT_VERSION_DIR = os.path.join(YARN_CACHE_PATH, "v6")
STAMP_PATH = os.path.join(YARN_CACHE_PATH, "yarn_cache_deleted")


def remove_unused_versions_dir(args: argparse.Namespace) -> None:
    """Deletes cache data from obsolete Yarn versions.

    Yarn does not provide an interface for removing obsolete data from
    ~/.cache/yarn for packages that you haven't installed in years.
    """
    dirs_to_keep = {CURRENT_VERSION_DIR, STAMP_PATH}
    try:
        dirs_to_purge = set(
            [
                os.path.join(YARN_CACHE_PATH, directory)
                for directory in os.listdir(YARN_CACHE_PATH)
                if os.path.join(YARN_CACHE_PATH, directory) not in dirs_to_keep
            ]
        )
    except FileNotFoundError:
        return

    may_be_perform_purging(
        dirs_to_purge,
        dirs_to_keep,
        "yarn cache",
        args.dry_run,
        args.verbose,
        args.no_headings,
    )


def remove_current_version_dir(args: argparse.Namespace) -> None:
    """
    Deletes cache data from the current Yarn version if it's
    older than `date_cutoff`.

    Yarn cache over time grows larger and larger, sadly it doesn't
    have any feature to auto-prune its caches.

    We try to avoid its large size by deleting it after some time.
    """
    stamp_path = os.path.join(YARN_CACHE_PATH, "yarn_cache_deleted")
    is_stamp_file_exists = os.path.exists(stamp_path)
    date_cutoff = datetime.now() - timedelta(days=180)

    # Not removing the current cache directory because it's not older than date_cutoff.
    if is_stamp_file_exists and datetime.fromtimestamp(os.path.getmtime(stamp_path)) > date_cutoff:
        if args.verbose:
            print(
                f"Avoid removing the active yarn cache as it's older than {(datetime.now() - date_cutoff).days} days."
            )
        return

    dirs_to_purge = {CURRENT_VERSION_DIR}
    if is_stamp_file_exists:
        dirs_to_purge.add(stamp_path)

    may_be_perform_purging(
        dirs_to_purge,
        set(),
        "yarn cache",
        args.dry_run,
        args.verbose,
        args.no_headings,
    )

    # Create a stamp file as it does not exist or is deleted.
    if args.verbose:
        print("Creating a stamp file to keep track of when yarn cache was deleted.")
    if not args.dry_run:
        os.mknod(stamp_path)


def main(args: argparse.Namespace) -> None:
    remove_unused_versions_dir(args)
    remove_current_version_dir(args)


if __name__ == "__main__":
    args = parse_cache_script_args("This script cleans redundant Zulip yarn caches.")
    main(args)
