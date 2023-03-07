import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from urllib.request import urlopen

import yaml

from .zulip_tools import parse_os_release, run

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZULIP_SRV_PATH = "/srv"

PUPPET_MODULES_CACHE_PATH = os.path.join(ZULIP_SRV_PATH, "zulip-puppet-cache")
PUPPET_DEPS_FILE_PATH = os.path.join(ZULIP_PATH, "puppet/deps.yaml")
PUPPET_THIRDPARTY = os.path.join(PUPPET_MODULES_CACHE_PATH, "current")


def generate_sha1sum_puppet_modules() -> str:
    data = {}
    with open(PUPPET_DEPS_FILE_PATH) as fb:
        data["deps.yaml"] = fb.read().strip()
    data["puppet-version"] = subprocess.check_output(
        # This is 10x faster than `puppet --version`
        ["ruby", "-r", "puppet/version", "-e", "puts Puppet.version"],
        text=True,
    ).strip()

    sha1sum = hashlib.sha1()
    sha1sum.update(json.dumps(data, sort_keys=True).encode())
    return sha1sum.hexdigest()


def setup_puppet_modules() -> None:
    sha1sum = generate_sha1sum_puppet_modules()
    target_path = os.path.join(PUPPET_MODULES_CACHE_PATH, sha1sum)
    success_stamp = os.path.join(target_path, ".success-stamp")
    # Check if a cached version already exists
    if not os.path.exists(success_stamp):
        do_puppet_module_install(target_path, success_stamp)

    if os.path.islink(PUPPET_THIRDPARTY):
        os.remove(PUPPET_THIRDPARTY)
    elif os.path.isdir(PUPPET_THIRDPARTY):
        shutil.rmtree(PUPPET_THIRDPARTY)
    os.symlink(target_path, PUPPET_THIRDPARTY)


def do_puppet_module_install(
    target_path: str,
    success_stamp: str,
) -> None:
    os.makedirs(target_path, exist_ok=True)
    with open(PUPPET_DEPS_FILE_PATH) as yaml_file:
        deps = yaml.safe_load(yaml_file)
    for module, metadata in deps.items():
        install_puppet_module(target_path, module, metadata["version"], metadata["sha256sum"])
    with open(success_stamp, "w"):
        pass


def install_puppet_module(
    target_path: str, module: str, version: str, expected_sha256sum: str
) -> None:
    with urlopen(f"https://forgeapi.puppet.com/v3/releases/{module}-{version}") as forge_resp:
        forge_data = json.load(forge_resp)

    forge_sha256sum = forge_data["file_sha256"]
    if forge_sha256sum != expected_sha256sum:
        raise Exception(
            f"Forge API returned unexpected SHA256 sum for {module}-{version}: "
            f"expected {expected_sha256sum}, got {forge_sha256sum}"
        )

    with tempfile.NamedTemporaryFile(
        prefix=f"zulip-puppet-{module}-{version}-",
        suffix=".tar.gz",
    ) as tarball:
        with urlopen("https://forgeapi.puppet.com" + forge_data["file_uri"]) as tarball_resp:
            tarball_content = tarball_resp.read()
            local_sha256sum = hashlib.sha256(tarball_content).hexdigest()
            if local_sha256sum != expected_sha256sum:
                raise Exception(
                    f"Downloaded file had unexpected SHA256 sum for {module}-{version}: "
                    f"expected {expected_sha256sum}, got {forge_sha256sum}"
                )
            tarball.write(tarball_content)
            tarball.flush()

        # This is to suppress Puppet warnings with ruby 2.7.
        distro_info = parse_os_release()
        puppet_env = os.environ.copy()
        if (distro_info["ID"], distro_info["VERSION_ID"]) in [("ubuntu", "20.04")]:
            puppet_env["RUBYOPT"] = "-W0"
        run(
            [
                "puppet",
                "module",
                "--modulepath",
                target_path,
                "install",
                tarball.name,
                "--ignore-dependencies",
            ],
            env=puppet_env,
        )
