from __future__ import print_function

import os
import hashlib
from os.path import dirname, abspath

if False:
    from typing import Optional, List, IO, Tuple

from scripts.lib.zulip_tools import subprocess_text_output, run

ZULIP_PATH = dirname(dirname(dirname(abspath(__file__))))
NPM_CACHE_PATH = "/srv/zulip-npm-cache"

if 'TRAVIS' in os.environ:
    # In Travis CI, we don't have root access
    NPM_CACHE_PATH = "/home/travis/zulip-npm-cache"

def setup_node_modules(npm_args=None, stdout=None, stderr=None, copy_modules=False):
    # type: (Optional[List[str]], Optional[IO], Optional[IO], Optional[bool]) -> None
    sha1sum = hashlib.sha1()
    sha1sum.update(subprocess_text_output(['cat', 'package.json']).encode('utf8'))
    sha1sum.update(subprocess_text_output(['npm', '--version']).encode('utf8'))
    sha1sum.update(subprocess_text_output(['node', '--version']).encode('utf8'))
    if npm_args is not None:
        sha1sum.update(''.join(sorted(npm_args)).encode('utf8'))

    npm_cache = os.path.join(NPM_CACHE_PATH, sha1sum.hexdigest())
    cached_node_modules = os.path.join(npm_cache, 'node_modules')
    success_stamp = os.path.join(cached_node_modules, '.success-stamp')
    # Check if a cached version already exists
    if not os.path.exists(success_stamp):
        do_npm_install(npm_cache,
                       npm_args or [],
                       stdout=stdout,
                       stderr=stderr,
                       success_stamp=success_stamp,
                       copy_modules=copy_modules)

    print("Using cached node modules from %s" % (cached_node_modules,))
    cmds = [
        ['rm', '-rf', 'node_modules'],
        ["ln", "-nsf", cached_node_modules, 'node_modules'],
    ]
    for cmd in cmds:
        run(cmd, stdout=stdout, stderr=stderr)

def do_npm_install(target_path, npm_args, stdout=None, stderr=None, copy_modules=False,
                   success_stamp=None):
    # type: (str, List[str], Optional[IO], Optional[IO], Optional[bool], Optional[str]) -> None
    cmds = [
        ["rm", "-rf", target_path],
        ['mkdir', '-p', target_path],
        ['cp', 'package.json', target_path],
    ]
    if copy_modules:
        print("Cached version not found! Copying node modules.")
        cmds.append(["cp", "-rT", "prod-static/serve/node_modules",
                     os.path.join(target_path, "node_modules")])
    else:
        print("Cached version not found! Installing node modules.")
        cmds.append(['npm', 'install'] + npm_args + ['--prefix', target_path])
    cmds.append(['touch', success_stamp])

    for cmd in cmds:
        run(cmd, stdout=stdout, stderr=stderr)
