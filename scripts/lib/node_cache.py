import os
import hashlib
import json
import shutil

from typing import Optional, List, IO, Any
from scripts.lib.zulip_tools import subprocess_text_output, run

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ZULIP_SRV_PATH = "/srv"

if 'TRAVIS' in os.environ:
    # In Travis CI, we don't have root access
    ZULIP_SRV_PATH = "/home/travis"


NODE_MODULES_CACHE_PATH = os.path.join(ZULIP_SRV_PATH, 'zulip-npm-cache')
YARN_BIN = os.path.join(ZULIP_SRV_PATH, 'zulip-yarn/bin/yarn')
YARN_PACKAGE_JSON = os.path.join(ZULIP_SRV_PATH, 'zulip-yarn/package.json')

DEFAULT_PRODUCTION = False

def get_yarn_args(production):
    # type: (bool) -> List[str]
    if production:
        yarn_args = ["--prod"]
    else:
        yarn_args = []
    return yarn_args

def generate_sha1sum_node_modules(setup_dir=None, production=DEFAULT_PRODUCTION):
    # type: (Optional[str], bool) -> str
    if setup_dir is None:
        setup_dir = os.path.realpath(os.getcwd())
    PACKAGE_JSON_FILE_PATH = os.path.join(setup_dir, 'package.json')
    YARN_LOCK_FILE_PATH = os.path.join(setup_dir, 'yarn.lock')
    sha1sum = hashlib.sha1()
    sha1sum.update(subprocess_text_output(['cat', PACKAGE_JSON_FILE_PATH]).encode('utf8'))
    if os.path.exists(YARN_LOCK_FILE_PATH):
        # For backwards compatibility, we can't assume yarn.lock exists
        sha1sum.update(subprocess_text_output(['cat', YARN_LOCK_FILE_PATH]).encode('utf8'))
    with open(YARN_PACKAGE_JSON, "r") as f:
        yarn_version = json.loads(f.read())['version']
        sha1sum.update(yarn_version.encode("utf8"))
    sha1sum.update(subprocess_text_output(['node', '--version']).encode('utf8'))
    yarn_args = get_yarn_args(production=production)
    sha1sum.update(''.join(sorted(yarn_args)).encode('utf8'))
    return sha1sum.hexdigest()

def setup_node_modules(production=DEFAULT_PRODUCTION, stdout=None, stderr=None,
                       prefer_offline=False):
    # type: (bool, Optional[IO[Any]], Optional[IO[Any]], bool) -> None
    yarn_args = get_yarn_args(production=production)
    if prefer_offline:
        yarn_args.append("--prefer-offline")
    sha1sum = generate_sha1sum_node_modules(production=production)
    target_path = os.path.join(NODE_MODULES_CACHE_PATH, sha1sum)
    cached_node_modules = os.path.join(target_path, 'node_modules')
    success_stamp = os.path.join(target_path, '.success-stamp')
    # Check if a cached version already exists
    if not os.path.exists(success_stamp):
        do_yarn_install(target_path,
                        yarn_args,
                        success_stamp,
                        stdout=stdout,
                        stderr=stderr)

    print("Using cached node modules from %s" % (cached_node_modules,))
    if os.path.islink('node_modules'):
        os.remove('node_modules')
    elif os.path.isdir('node_modules'):
        shutil.rmtree('node_modules')
    os.symlink(cached_node_modules, 'node_modules')

def do_yarn_install(target_path, yarn_args, success_stamp, stdout=None, stderr=None):
    # type: (str, List[str], str, Optional[IO[Any]], Optional[IO[Any]]) -> None
    os.makedirs(target_path, exist_ok=True)
    shutil.copy('package.json', target_path)
    shutil.copy("yarn.lock", target_path)
    shutil.copy(".yarnrc", target_path)
    cached_node_modules = os.path.join(target_path, 'node_modules')
    print("Cached version not found! Installing node modules.")

    # Copy the existing node_modules to speed up install
    if os.path.exists("node_modules") and not os.path.exists(cached_node_modules):
        shutil.copytree("node_modules/", cached_node_modules, symlinks=True)
    if os.environ.get('CUSTOM_CA_CERTIFICATES'):
        run([YARN_BIN, "config", "set", "cafile", os.environ['CUSTOM_CA_CERTIFICATES']],
            stdout=stdout, stderr=stderr)
    run([YARN_BIN, "install", "--non-interactive", "--frozen-lockfile"] + yarn_args,
        cwd=target_path, stdout=stdout, stderr=stderr)
    with open(success_stamp, 'w'):
        pass
