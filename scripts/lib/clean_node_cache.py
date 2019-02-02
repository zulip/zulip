#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

if False:
    # See https://zulip.readthedocs.io/en/latest/testing/mypy.html#mypy-in-production-scripts
    from typing import Set

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ZULIP_PATH)
from scripts.lib.zulip_tools import \
    get_environment, get_recent_deployments, parse_cache_script_args, \
    purge_unused_caches

ENV = get_environment()
NODE_MODULES_CACHE_PATH = "/srv/zulip-npm-cache"
if ENV == "travis":
    NODE_MODULES_CACHE_PATH = os.path.join(os.environ["HOME"], "zulip-npm-cache")
    try:
        subprocess.check_output(["/home/travis/zulip-yarn/bin/yarn", '--version'])
    except OSError:
        print('yarn not found. Most probably we are running static-analysis and '
              'hence yarn is not installed. Exiting without cleaning npm cache.')
        sys.exit(0)

def get_caches_in_use(threshold_days):
    # type: (int) -> Set[str]
    setups_to_check = set([ZULIP_PATH, ])
    caches_in_use = set()

    if ENV == "prod":
        setups_to_check |= get_recent_deployments(threshold_days)
    if ENV == "dev":
        # In dev always include the currently active cache in order
        # not to break current installation in case dependencies
        # are updated with bumping the provision version.
        CURRENT_CACHE = os.path.dirname(os.path.realpath(os.path.join(ZULIP_PATH, "node_modules")))
        caches_in_use.add(CURRENT_CACHE)

    for setup_dir in setups_to_check:
        node_modules_link_path = os.path.join(setup_dir, "node_modules")
        if not os.path.islink(node_modules_link_path):
            # If 'package.json' file doesn't exist then no node_modules
            # cache is associated with this setup.
            continue
        # The actual cache path doesn't include the /node_modules
        caches_in_use.add(os.path.dirname(os.readlink(node_modules_link_path)))

    return caches_in_use

def main(args: argparse.Namespace) -> None:
    caches_in_use = get_caches_in_use(args.threshold_days)
    purge_unused_caches(
        NODE_MODULES_CACHE_PATH, caches_in_use, "node modules cache", args)

if __name__ == "__main__":
    args = parse_cache_script_args("This script cleans unused zulip npm caches.")
    main(args)
