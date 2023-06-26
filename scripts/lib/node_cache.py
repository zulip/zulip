import os

from scripts.lib.zulip_tools import run

DEFAULT_PRODUCTION = False


def setup_node_modules(production: bool = DEFAULT_PRODUCTION) -> None:
    if os.path.islink("node_modules"):
        os.unlink("node_modules")

    try:
        with open("node_modules/.pnpm/lock.yaml") as a, open("pnpm-lock.yaml") as b:
            if a.read() == b.read():
                return
    except FileNotFoundError:
        pass

    run(
        [
            "/usr/local/bin/pnpm",
            "install",
            "--frozen-lockfile",
            "--prefer-offline",
            *(["--prod"] if production else []),
        ]
    )
