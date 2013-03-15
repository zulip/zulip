#!/usr/bin/env python
# -*- coding: utf-8 -*-

import humbug

import glob
import os
from distutils.core import setup

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
          [(os.path.join('share/humbug/', relpath),
            glob.glob(os.path.join(relpath, '*'))) for relpath in
           glob.glob("integrations/*")] + \
          [('share/humbug/demos',
            [os.path.join("demos", relpath) for relpath in
            os.listdir("demos")])],
      scripts=["bin/humbug-send"],
     )
