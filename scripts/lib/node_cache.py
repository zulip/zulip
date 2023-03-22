import os

from scripts.lib.zulip_tools import get_deploy_root, run

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

    pnpm_command = ["/usr/local/bin/pnpm", "install", "--frozen-lockfile"]
    if production:
        pnpm_command += ["--prod"]

    deploy_root = get_deploy_root()
    with open("/proc/self/mounts") as mounts:
        for line in mounts:
            fields = line.split()
            if fields[1] == deploy_root and fields[2] in ("fuse.grpcfuse", "fakeowner"):
                print("Working around https://github.com/pnpm/pnpm/issues/5803")
                pnpm_command += ["--package-import-method=copy"]

    run(pnpm_command)
