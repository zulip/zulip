#!/usr/bin/env python
# -*- coding: utf-8 -*-

import zulip

import os
from distutils.core import setup

def recur_expand(target_root, dir):
  for root, _, files in os.walk(dir):
    paths = [os.path.join(root, f) for f in files]
    if len(paths):
      yield os.path.join(target_root, root), paths

setup(name='zulip',
      version=zulip.__version__,
      description='Bindings for the Zulip message API',
      author='Zulip, Inc.',
      author_email='zulip@zulip.com',
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
                                             "examples/print-messages"])] + \
          list(recur_expand('share/zulip', 'integrations/')),
      scripts=["bin/zulip-send"],
     )
