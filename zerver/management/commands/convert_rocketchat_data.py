import argparse
import os
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.data_import.rocketchat import do_convert_data


class Command(BaseCommand):
    help = """Convert the Rocketchat data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        dir_help = "Directory containing all the `bson` files from mongodb dump of rocketchat."
        parser.add_argument(
            "rocketchat_data_dir", metavar="<rocketchat data directory>", help=dir_help
        )

        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write converted data to."
        )

        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            raise CommandError("You need to specify --output <output directory>")

        if os.path.exists(output_dir) and not os.path.isdir(output_dir):
            raise CommandError(output_dir + " is not a directory")

        os.makedirs(output_dir, exist_ok=True)

        if os.listdir(output_dir):
            raise CommandError("Output directory should be empty!")
        output_dir = os.path.realpath(output_dir)

        data_dir = options["rocketchat_data_dir"]
        if not os.path.exists(data_dir):
            raise CommandError(f"Directory not found: '{data_dir}'")
        data_dir = os.path.realpath(data_dir)

        print("Converting Data ...")
        do_convert_data(rocketchat_data_dir=data_dir, output_dir=output_dir)
