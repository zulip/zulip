#!/usr/bin/env python
# -*- coding: utf-8 -*-

import humbug

import glob
import os
from distutils.core import setup

def recur_expand(target_root, dir):
  for root, _, files in os.walk(dir):
    paths = [os.path.join(root, f) for f in files]
    if len(paths):
      yield os.path.join(target_root, root), paths

setup(name='humbug',
      version=humbug.__version__,
      description='Bindings for the Humbug message API',
      author='Humbug, Inc.',
      author_email='humbug@humbughq.com',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Topic :: Communications :: Chat',
      ],
      url='https://humbughq.com/dist/api/',
      packages=['humbug'],
      data_files=[('share/humbug/examples', ["examples/humbugrc", "examples/send-message"])] + \
          list(recur_expand('share/humbug', 'integrations/')) + \
          [('share/humbug/demos',
            [os.path.join("demos", relpath) for relpath in
            os.listdir("demos")])],
      scripts=["bin/humbug-send"],
     )
