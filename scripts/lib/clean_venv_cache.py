#!/usr/bin/env python3
import argparse
import glob
import os
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ZULIP_PATH)
from scripts.lib.hash_reqs import expand_reqs, hash_deps
from scripts.lib.zulip_tools import (
    get_environment,
    get_recent_deployments,
    parse_cache_script_args,
    purge_unused_caches,
)

ENV = get_environment()
VENV_CACHE_DIR = "/srv/zulip-venv-cache"


def get_caches_in_use(threshold_days: int) -> set[str]:
    setups_to_check = {ZULIP_PATH}
    caches_in_use = set()

    def add_current_venv_cache(venv_name: str) -> None:
        CACHE_SYMLINK = os.path.join(os.path.dirname(ZULIP_PATH), venv_name)
        CURRENT_CACHE = os.path.dirname(os.path.realpath(CACHE_SYMLINK))
        caches_in_use.add(CURRENT_CACHE)

    if ENV == "prod":
        setups_to_check |= get_recent_deployments(threshold_days)
    if ENV == "dev":
        add_current_venv_cache("zulip-py3-venv")

    for path in setups_to_check:
        reqs_dir = os.path.join(path, "requirements")
        # If the target directory doesn't contain a requirements
        # directory, skip it to avoid throwing an exception trying to
        # list its requirements subdirectory.
        if not os.path.exists(reqs_dir):
            continue
        requirements_files = glob.glob(os.path.join(reqs_dir, "*.txt"))
        for requirements_file in requirements_files:
            deps = expand_reqs(requirements_file)
            hash_val = hash_deps(deps)
            caches_in_use.add(os.path.join(VENV_CACHE_DIR, hash_val))

    return caches_in_use


def main(args: argparse.Namespace) -> None:
    caches_in_use = get_caches_in_use(args.threshold_days)
    purge_unused_caches(VENV_CACHE_DIR, caches_in_use, "venv cache", args)


if __name__ == "__main__":
    args = parse_cache_script_args("This script cleans unused Zulip venv caches.")
    main(args)
