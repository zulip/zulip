import os

from scripts.lib.zulip_tools import run

DEFAULT_PRODUCTION = False


def setup_node_modules(production: bool = DEFAULT_PRODUCTION) -> None:
    if os.path.islink("node_modules"):
        os.unlink("node_modules")

    skip = False

    try:
        with open("node_modules/.pnpm/lock.yaml") as a, open("pnpm-lock.yaml") as b:
            if a.read() == b.read():
                skip = True
    except FileNotFoundError:
        pass

    # We need this check when switching between branches without `help-beta`
    # package. `node_modules` will be removed when working on a non `help-beta`
    # branch, but if `node_modules/.pnpm/lock.yaml` has not been updated by that
    # branch, we will end up in a situation where we might not have `node_modules`
    # even when we run the provision command.
    if not os.path.exists("help-beta/node_modules"):
        skip = False

    if not skip:
        run(
            [
                "/usr/local/bin/corepack",
                "pnpm",
                "install",
                "--frozen-lockfile",
                "--prefer-offline",
                *(["--prod"] if production else []),
            ],
        )
