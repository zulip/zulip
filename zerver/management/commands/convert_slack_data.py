
import argparse
import os
import subprocess
import tempfile
import shutil
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from zerver.lib.slack_data_to_zulip_data import do_convert_data

class Command(BaseCommand):
    help = """Convert the Slack data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('slack_data_zip', nargs='+',
                            metavar='<slack data zip>',
                            help="Zipped slack data")

        parser.add_argument('realm_name', metavar='<realm_name>',
                            type=str, help="Realm Name")

        parser.add_argument('--token', metavar='<slack_token>',
                            type=str, help='Slack legacy token of the organsation')

        parser.add_argument('--output', dest='output_dir',
                            action="store", default=None,
                            help='Directory to write exported data to.')
        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="/tmp/converted-slack-data-")
        else:
            output_dir = os.path.realpath(output_dir)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir)

        realm_name = options['realm_name']
        token = options['token']
        if realm_name is None:
            print("Enter realm name!")
            exit(1)

        if token is None:
            print("Enter slack legacy token!")
            exit(1)

        for path in options['slack_data_zip']:
            if not os.path.exists(path):
                print("Slack data directory not found: '%s'" % (path,))
                exit(1)

            print("Converting Data ...")
            do_convert_data(path, realm_name, output_dir, token)
