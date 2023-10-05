import argparse
import os
from typing import Any

"""
Example usage for testing purposes. For testing data see the mattermost_fixtures
in zerver/tests/.

    ./manage.py convert_mattermost_data mattermost_fixtures --output mm_export
    ./manage.py import --destroy-rebuild-database mattermost mm_export/gryffindor

Test out the realm:
    ./tools/run-dev
    go to browser and use your dev url
"""

from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.data_import.mattermost import do_convert_data


class Command(BaseCommand):
    """Convert the mattermost data into Zulip data format."""
    help = """Convert the mattermost data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        """
        Add command-line arguments to the command parser.

        Args:
            parser (CommandParser): The parser object to which the arguments should be added.
        """
        dir_help = (
            "Directory containing exported JSON file and exported_emoji (optional) directory."
        )
        parser.add_argument(
            "mattermost_data_dir", metavar="<mattermost data directory>", help=dir_help
        )

        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write converted data to."
        )

        parser.add_argument(
            "--mask",
            dest="masking_content",
            action="store_true",
            help="Mask the content for privacy during QA.",
        )

        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Handle the command.

        Args:
            *args: Variable length argument list.
            **options: Arbitrary keyword arguments.

        Raises:
            CommandError: If the 'output_dir' parameter is not specified or is not a
            directory, or if the 'output_dir' is not empty, or if the
            'mattermost_data_dir' directory is not found.
        """
        output_dir = options["output_dir"]
        if output_dir is None:
            raise CommandError("You need to specify --output <output directory>")

        if os.path.exists(output_dir) and not os.path.isdir(output_dir):
            raise CommandError(output_dir + " is not a directory")

        os.makedirs(output_dir, exist_ok=True)

        if os.listdir(output_dir):
            raise CommandError("Output directory should be empty!")
        output_dir = os.path.realpath(output_dir)

        data_dir = options["mattermost_data_dir"]
        if not os.path.exists(data_dir):
            raise CommandError(f"Directory not found: '{data_dir}'")
        data_dir = os.path.realpath(data_dir)

        print("Converting data ...")
        do_convert_data(
            mattermost_data_dir=data_dir,
            output_dir=output_dir,
            masking_content=options.get("masking_content", False),
        )
