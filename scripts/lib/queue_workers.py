#!/usr/bin/env -S uv run --frozen --no-config --only-group=prod --preview-features=target-workspace-discovery --script  # -*-python-*-
import os

import django

from zerver.worker.queue_processors import get_active_worker_queues

os.environ["DJANGO_SETTINGS_MODULE"] = "zproject.settings"
django.setup()

if __name__ == "__main__":
    for worker in sorted(get_active_worker_queues()):
        print(worker)
