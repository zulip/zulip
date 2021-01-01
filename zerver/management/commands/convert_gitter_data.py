import argparse
import os
import tempfile
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.data_import.gitter import do_convert_data


class Command(BaseCommand):
    help = """Convert the Gitter data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('gitter_data', nargs='+',
                            metavar='<gitter data>',
                            help="Gitter data in json format")

        parser.add_argument('--output', dest='output_dir',
                            help='Directory to write exported data to.')

        parser.add_argument('--threads',
                            default=settings.DEFAULT_DATA_EXPORT_IMPORT_PARALLELISM,
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
                raise CommandError(f"Gitter data file not found: '{path}'")
            # TODO add json check
            print("Converting data ...")
            do_convert_data(path, output_dir, num_threads)
