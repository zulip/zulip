#!/usr/bin/env python3
import argparse
import os
import sys

if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import Set

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ZULIP_PATH)
from scripts.lib.zulip_tools import \
    get_environment, get_recent_deployments, \
    parse_cache_script_args, purge_unused_caches

ENV = get_environment()
EMOJI_CACHE_PATH = "/srv/zulip-emoji-cache"
if ENV == "travis":
    EMOJI_CACHE_PATH = os.path.join(os.environ["HOME"], "zulip-emoji-cache")

def get_caches_in_use(threshold_days):
    # type: (int) -> Set[str]
    setups_to_check = set([ZULIP_PATH, ])
    caches_in_use = set()

    if ENV == "prod":
        setups_to_check |= get_recent_deployments(threshold_days)
    if ENV == "dev":
        CACHE_SYMLINK = os.path.join(ZULIP_PATH, "static", "generated", "emoji")
        CURRENT_CACHE = os.path.dirname(os.path.realpath(CACHE_SYMLINK))
        caches_in_use.add(CURRENT_CACHE)

    for setup_dir in setups_to_check:
        emoji_link_path = os.path.join(setup_dir, "static/generated/emoji")
        if not os.path.islink(emoji_link_path):
            # This happens for a deployment directory extracted from a
            # tarball, which just has a copy of the emoji data, not a symlink.
            continue
        # The actual cache path doesn't include the /emoji
        caches_in_use.add(os.path.dirname(os.readlink(emoji_link_path)))
    return caches_in_use

def main(args: argparse.Namespace) -> None:
    caches_in_use = get_caches_in_use(args.threshold_days)
    purge_unused_caches(
        EMOJI_CACHE_PATH, caches_in_use, "emoji cache", args)

if __name__ == "__main__":
    args = parse_cache_script_args("This script cleans unused zulip emoji caches.")
    main(args)
