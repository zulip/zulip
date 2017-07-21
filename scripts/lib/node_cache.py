from __future__ import print_function

import os
import hashlib
from os.path import dirname, abspath

if False:
    from typing import Optional, List, IO, Tuple, Any

from scripts.lib.zulip_tools import subprocess_text_output, run

ZULIP_PATH = dirname(dirname(dirname(abspath(__file__))))
NODE_MODULES_CACHE_PATH = "/srv/zulip-npm-cache"

if 'TRAVIS' in os.environ:
    # In Travis CI, we don't have root access
    NODE_MODULES_CACHE_PATH = "/home/travis/zulip-npm-cache"

def generate_sha1sum_node_modules(npm_args=None):
    # type: (Optional[List[str]]) -> str
    sha1sum = hashlib.sha1()
    sha1sum.update(subprocess_text_output(['cat', 'package.json']).encode('utf8'))
    sha1sum.update(subprocess_text_output(['npm', '--version']).encode('utf8'))
    sha1sum.update(subprocess_text_output(['node', '--version']).encode('utf8'))
    if npm_args is not None:
        sha1sum.update(''.join(sorted(npm_args)).encode('utf8'))

    return sha1sum.hexdigest()

def setup_node_modules(production=False, stdout=None, stderr=None, copy_modules=False):
    # type: (bool, Optional[IO], Optional[IO], bool) -> None
    if production:
        npm_args = ["--production"]
    else:
        npm_args = []
    sha1sum = generate_sha1sum_node_modules(npm_args)
    target_path = os.path.join(NODE_MODULES_CACHE_PATH, sha1sum)
    cached_node_modules = os.path.join(target_path, 'node_modules')
    success_stamp = os.path.join(target_path, '.success-stamp')
    # Check if a cached version already exists
    if not os.path.exists(success_stamp):
        do_npm_install(target_path,
                       npm_args,
                       success_stamp,
                       stdout=stdout,
                       stderr=stderr,
                       copy_modules=copy_modules)

    print("Using cached node modules from %s" % (cached_node_modules,))
    cmds = [
        ['rm', '-rf', 'node_modules'],
        ["ln", "-nsf", cached_node_modules, 'node_modules'],
    ]
    for cmd in cmds:
        run(cmd, stdout=stdout, stderr=stderr)

def do_npm_install(target_path, npm_args, success_stamp, stdout=None, stderr=None,
                   copy_modules=False):
    # type: (str, List[str], str, Optional[IO], Optional[IO], bool) -> None
    cmds = [
        ["rm", "-rf", target_path],
        ['mkdir', '-p', target_path],
        ['cp', 'package.json', target_path],
    ]
    cached_node_modules = os.path.join(target_path, 'node_modules')
    if copy_modules:
        print("Cached version not found! Copying node modules.")
        cmds.append(["cp", "-rT", "prod-static/serve/node_modules", cached_node_modules])
    else:
        print("Cached version not found! Installing node modules.")
        cmds.append(['npm', 'install'] + npm_args + ['--prefix', target_path])
    cmds.append(['touch', success_stamp])

    for cmd in cmds:
        run(cmd, stdout=stdout, stderr=stderr)
