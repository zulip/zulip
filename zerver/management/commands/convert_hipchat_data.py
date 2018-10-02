import argparse
import os
import subprocess
import tempfile
import shutil
from typing import Any

'''
Example usage for testing purposes:

Move the data:
    rm -Rf /tmp/hipchat*
    mkdir /tmp/hipchat
    ./manage.py convert_hipchat_data ~/hipchat-31028-2018-08-08_23-23-22.tar --output /tmp/hipchat
    ./manage.py import --destroy-rebuild-database hipchat /tmp/hipchat


Test out the realm:
    ./tools/run-dev.py
    go to browser and use your dev url
'''

from django.core.management.base import BaseCommand, CommandParser, CommandError

from zerver.data_import.hipchat import do_convert_data

class Command(BaseCommand):
    help = """Convert the Hipchat data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('hipchat_tar', nargs='+',
                            metavar='<hipchat data tarfile>',
                            help="tar of Hipchat data")

        parser.add_argument('--output', dest='output_dir',
                            action="store",
                            help='Directory to write exported data to.')

        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]

        if output_dir is None:
            print("You need to specify --output <output directory>")
            exit(1)

        if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            print(output_dir + " is not a directory")
            exit(1)

        if os.listdir(output_dir):
            print('Output directory should be empty!')
            exit(1)

        output_dir = os.path.realpath(output_dir)

        for path in options['hipchat_tar']:
            if not os.path.exists(path):
                print("Tar file not found: '%s'" % (path,))
                exit(1)

            print("Converting Data ...")
            do_convert_data(path, output_dir)
