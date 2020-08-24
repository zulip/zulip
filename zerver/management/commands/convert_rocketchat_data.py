import argparse
import os
import tempfile
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from zerver.data_import.rocketchat import do_convert_data

fallback_avatar_url = ('https://user-images.githubusercontent.com/35293767/'
                       '34953768-88f630a0-fa26-11e7-9589-020d002fcc5b.png')


class Command(BaseCommand):
    help = """Convert the Rocketchat data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        paa = parser.add_argument
        paa('--output', dest='output_dir',
            action="store", default=None,
            help='Directory to write exported data to.')
        paa('-R', '--rocketchat_dump', help="Dir with Rocketchat MongoDB dump")
        paa('-A', '--fallback_avatar', default=fallback_avatar_url,
            help="Provide URL to custom avatar. Default: {}".format(
                fallback_avatar_url))
        paa('-l', '--loglevel', help="Set log level", default="info")
        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="converted-rocketchat-data-")
        else:
            output_dir = os.path.realpath(output_dir)

        print("Converting Data ...")
        do_convert_data(output_dir, options)
