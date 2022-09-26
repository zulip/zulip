#!/usr/bin/env python3
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
from scripts.lib.setup_path import setup_path

setup_path()

os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"

import django

django.setup()
from zerver.worker.queue_processors import get_active_worker_queues

if __name__ == "__main__":
    for worker in sorted(get_active_worker_queues()):
        print(worker)
