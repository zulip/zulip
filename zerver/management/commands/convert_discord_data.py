import argparse
import os
import tempfile
from typing import Any

from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.data_import.discord import do_convert_directory
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Convert the Discord data into Zulip data format."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "discord_data_path",
            nargs="+",
            metavar="<Discord data path>",
            help="Directory containing a DiscordChatExporter JSON export",
        )

        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write exported data to."
        )

        parser.add_argument(
            "--token",
            metavar="<Discord bot token>",
            help="Discord bot token.",
        )

        parser.formatter_class = argparse.RawTextHelpFormatter

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="converted-discord-data-")
        else:
            output_dir = os.path.realpath(output_dir)

        token = options["token"]
        if token is None:
            raise CommandError("Enter Discord bot token!")

        for path in options["discord_data_path"]:
            if not os.path.exists(path):
                raise CommandError(f"Discord data file or directory not found: '{path}'")

            print("Converting data ...")
            if os.path.isdir(path):
                do_convert_directory(path, output_dir, token)
            elif os.path.isfile(path) and path.endswith(".zip"):
                raise ValueError(
                    "Importing .zip Discord data is not yet supported, please try again with the extracted data."
                )
            else:
                raise ValueError(f"Don't know how to import Discord data from {path}")
