#!/usr/bin/env python

from __future__ import print_function
import argparse
import os
import sys
from os.path import dirname, abspath

BASE_DIR = dirname(dirname(dirname(abspath(__file__))))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import

os.environ['DJANGO_SETTINGS_MODULE'] = 'zproject.settings'

import django
django.setup()
from zerver.worker.queue_processors import get_active_worker_queues

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--queue-type', action='store', dest='queue_type', default=None,
                        help="Specify which types of queues to list")
    args = parser.parse_args()

    for worker in sorted(get_active_worker_queues(args.queue_type)):
        print(worker)
