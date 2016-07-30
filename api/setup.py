#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
if False: from typing import Any, Generator, List, Tuple

import os
import sys

import itertools

def version():
    # type: () -> str
    version_py = os.path.join(os.path.dirname(__file__), "zulip", "__init__.py")
    with open(version_py) as in_handle:
        version_line = next(itertools.dropwhile(lambda x: not x.startswith("__version__"),
                                           in_handle))
    version = version_line.split('=')[-1].strip().replace('"', '')
    return version

def recur_expand(target_root, dir):
    # type: (Any, Any) -> Generator[Tuple[str, List[str]], None, None]
    for root, _, files in os.walk(dir):
        paths = [os.path.join(root, f) for f in files]
        if len(paths):
            yield os.path.join(target_root, root), paths

# We should be installable with either setuptools or distutils.
package_info = dict(
    name='zulip',
    version=version(),
    description='Bindings for the Zulip message API',
    author='Zulip, Inc.',
    author_email='zulip-devel@googlegroups.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Communications :: Chat',
    ],
    url='https://www.zulip.com/dist/api/',
    packages=['zulip'],
    data_files=[('share/zulip/examples', ["examples/zuliprc", "examples/send-message", "examples/subscribe",
                                           "examples/get-public-streams", "examples/unsubscribe",
                                           "examples/list-members", "examples/list-subscriptions",
                                           "examples/print-messages", "examples/recent-messages"])] + \
        list(recur_expand('share/zulip', 'integrations/')),
    scripts=["bin/zulip-send"],
) # type: Dict[str, Any]

setuptools_info = dict(
    install_requires=['requests>=0.12.1',
                      'simplejson',
                      'six',
                      'typing',
    ],
)

try:
    from setuptools import setup
    package_info.update(setuptools_info)
except ImportError:
    from distutils.core import setup
    from distutils.version import LooseVersion
    # Manual dependency check
    try:
        import simplejson
    except ImportError:
        print("simplejson is not installed", file=sys.stderr)
        sys.exit(1)
    try:
        import requests
        assert(LooseVersion(requests.__version__) >= LooseVersion('0.12.1')) # type: ignore # https://github.com/JukkaL/mypy/issues/1165
    except (ImportError, AssertionError):
        print("requests >=0.12.1 is not installed", file=sys.stderr)
        sys.exit(1)


setup(**package_info)
