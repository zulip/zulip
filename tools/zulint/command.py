# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import

import argparse

def add_default_linter_arguments(parser):
    # type: (argparse.ArgumentParser) -> None
    parser.add_argument('--modified', '-m',
                        action='store_true',
                        help='Only check modified files')
    parser.add_argument('--verbose', '-v',
                        action='store_true',
                        help='Print verbose timing output')
    parser.add_argument('targets',
                        nargs='*',
                        help='Specify directories to check')
