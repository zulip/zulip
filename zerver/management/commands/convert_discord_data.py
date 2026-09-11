import argparse
import os
from typing import Any

from typing_extensions import override

"""
Convert a DiscordChatExporter export directory into Zulip's data format.

Usage:
    ./manage.py convert_discord_data <discord_data_dir> --output <output_dir>
    ./manage.py import <subdomain> <output_dir>
"""

from django.core.management.base import CommandError, CommandParser

from zerver.data_import.discord import do_convert_data
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Convert DiscordChatExporter data into Zulip data format."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        dir_help = "Directory containing DiscordChatExporter JSON files and _media/ directory."
        parser.add_argument("discord_data_dir", metavar="<discord data directory>", help=dir_help)

        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write converted data to."
        )

        parser.formatter_class = argparse.RawTextHelpFormatter

    @override
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

        data_dir = options["discord_data_dir"]
        if not os.path.exists(data_dir):
            raise CommandError(f"Directory not found: '{data_dir}'")
        data_dir = os.path.realpath(data_dir)

        print("Converting Discord data ...")
        do_convert_data(
            discord_data_dir=data_dir,
            output_dir=output_dir,
        )
