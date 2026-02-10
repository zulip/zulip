import argparse
import os
import tempfile
from typing import Any

from django.conf import settings
from django.core.management.base import CommandError, CommandParser
from typing_extensions import override

from zerver.data_import.microsoft_teams import do_convert_directory
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Convert the Microsoft Teams data into Zulip data format."""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "microsoft_teams_data_path",
            nargs="+",
            metavar="<Microsoft Teams data path>",
            help="Zipped Microsoft Teams data or directory",
        )

        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write exported data to."
        )

        parser.add_argument(
            "--token",
            metavar="<microsoft_graph_api_token>",
            help="Microsoft Graph API token, see https://learn.microsoft.com/en-us/graph/auth-v2-service?tabs=http",
        )

        parser.add_argument(
            "--threads",
            default=settings.DEFAULT_DATA_EXPORT_IMPORT_PARALLELISM,
            help="Threads to use in exporting UserMessage objects in parallel",
        )

        parser.formatter_class = argparse.RawTextHelpFormatter

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="converted-ms-teams-data-")
        else:
            output_dir = os.path.realpath(output_dir)

        token = options["token"]
        if token is None:
            raise CommandError("Enter Microsoft Graph API token!")

        num_threads = int(options["threads"])
        if num_threads < 1:
            raise CommandError("You must have at least one thread.")

        for path in options["microsoft_teams_data_path"]:
            if not os.path.exists(path):
                raise CommandError(f"Microsoft Teams data file or directory not found: '{path}'")

            print("Converting data ...")
            if os.path.isdir(path):
                print(path)
                do_convert_directory(
                    path,
                    output_dir,
                    token,
                    threads=num_threads,
                )
            elif os.path.isfile(path) and path.endswith(".zip"):
                raise ValueError(
                    "Importing .zip Microsoft Teams data is not yet supported, please try again with the extracted data."
                )
            else:
                raise ValueError(f"Don't know how to import Microsoft Teams data from {path}")
