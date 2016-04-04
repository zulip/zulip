from __future__ import absolute_import
from __future__ import print_function

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

import glob
import logging
import os
import shutil
import tempfile
import ujson

from zerver.lib.export import export_usermessages_batch

class Command(BaseCommand):
    help = """UserMessage fetching helper for export.py"""

    def add_arguments(self, parser):
        parser.add_argument('--path',
                            dest='path',
                            action="store",
                            default=None,
                            help='Path to find messages.json archives')
        parser.add_argument('--thread',
                            dest='thread',
                            action="store",
                            default=None,
                            help='Thread ID')

    def handle(self, *args, **options):
        logging.info("Starting UserMessage batch thread %s" % (options['thread'],))
        files = set(glob.glob(os.path.join(options['path'], 'messages-*.json.partial')))
        for partial_path in files:
            locked_path = partial_path.replace(".json.partial", ".json.locked")
            output_path = partial_path.replace(".json.partial", ".json")
            try:
                shutil.move(partial_path, locked_path)
            except Exception:
                # Already claimed by another process
                continue
            logging.info("Thread %s processing %s" % (options['thread'], output_path))
            try:
                export_usermessages_batch(locked_path, output_path)
            except Exception:
                # Put the item back in the free pool when we fail
                shutil.move(locked_path, partial_path)
                raise
