
import argparse
import os
import tempfile
from typing import Any

from django.core.management.base import BaseCommand, CommandParser, CommandError

from zerver.data_import.gitter import do_convert_data

class Command(BaseCommand):
    help = """Convert the Gitter data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('gitter_data', nargs='+',
                            metavar='<gitter data>',
                            help="Gitter data in json format")

        parser.add_argument('--output', dest='output_dir',
                            action="store", default=None,
                            help='Directory to write exported data to.')

        parser.add_argument('--threads',
                            dest='threads',
                            action="store",
                            default=6,
                            help='Threads to download avatars and attachments faster')

        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="converted-gitter-data-")
        else:
            output_dir = os.path.realpath(output_dir)

        num_threads = int(options['threads'])
        if num_threads < 1:
            raise CommandError('You must have at least one thread.')

        for path in options['gitter_data']:
            if not os.path.exists(path):
                print("Gitter data file not found: '%s'" % (path,))
                exit(1)
            # TODO add json check
            print("Converting Data ...")
            do_convert_data(path, output_dir, num_threads)
