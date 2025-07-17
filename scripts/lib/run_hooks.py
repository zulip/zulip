#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.lib.zulip_tools import (
    DEPLOYMENTS_DIR,
    assert_running_as_root,
    get_deploy_root,
    get_zulip_pwent,
    parse_version_from,
    su_to_zulip,
)

assert_running_as_root()

# Updates to the below choices to add a new hook type should
# adjust puppet's `app_frontend_base.pp` as well.
parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=["pre-deploy", "post-deploy"], help="")
parser.add_argument("--from-git", action="store_true", help="Upgrading from git")
args = parser.parse_args()

from version import ZULIP_MERGE_BASE as NEW_ZULIP_MERGE_BASE
from version import ZULIP_VERSION as NEW_ZULIP_VERSION

deploy_path = get_deploy_root()

if args.kind == "post-deploy":
    old_dir_name = "last"
else:
    old_dir_name = "current"
old_version = parse_version_from(DEPLOYMENTS_DIR + "/" + old_dir_name)
old_merge_base = parse_version_from(DEPLOYMENTS_DIR + "/" + old_dir_name, merge_base=True)

path = f"/etc/zulip/hooks/{args.kind}.d"
if not os.path.exists(path):
    sys.exit(0)

# Pass in, via environment variables, the old/new "version
# string" (which is a `git describe` output)
env = os.environ.copy()
env["ZULIP_OLD_VERSION"] = old_version
env["ZULIP_NEW_VERSION"] = NEW_ZULIP_VERSION

# preexec_fn=su_to_zulip normally handles this, but our explicit
# env overrides that
env["HOME"] = get_zulip_pwent().pw_dir


def resolve_version_string(version: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", version], cwd=deploy_path, preexec_fn=su_to_zulip, text=True
    ).strip()


if args.from_git:
    # If we have a git repo, we also resolve those `git describe`
    # values to full commit hashes, as well as provide the
    # merge-base of the old/new commits with mainline.
    env["ZULIP_OLD_COMMIT"] = resolve_version_string(old_version)
    env["ZULIP_NEW_COMMIT"] = resolve_version_string(NEW_ZULIP_VERSION)
    env["ZULIP_OLD_MERGE_BASE_COMMIT"] = resolve_version_string(old_merge_base)
    env["ZULIP_NEW_MERGE_BASE_COMMIT"] = resolve_version_string(NEW_ZULIP_MERGE_BASE)

failures = []
for script_name in sorted(f for f in os.listdir(path) if f.endswith(".hook")):
    result = subprocess.run(
        [os.path.join(path, script_name)],
        check=False,
        cwd=deploy_path,
        preexec_fn=su_to_zulip,
        env=env,
    )
    if result.returncode != 0:
        # Pre-deploy hooks abort on the first failure; post-deploy
        # hooks are best-effort and a failure of one does not abort
        # the rest of them.
        if args.kind == "pre-deploy":
            sys.exit(1)
        failures.append(script_name)

if failures:
    print("Failed hooks:")
    for failed_script in failures:
        print(f"  {failed_script}")
