import argparse
import os
import tempfile
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.data_import.slack import do_convert_data


class Command(BaseCommand):
    """Convert the Slack data into Zulip data format."""
    help = """Convert the Slack data into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "slack_data_path",
            nargs="+",
            metavar="<Slack data path>",
            help="Zipped Slack data or directory",
        )

        parser.add_argument(
            "--token", metavar="<slack_token>", help="Bot user OAuth token, starting xoxb-"
        )

        parser.add_argument(
            "--output", dest="output_dir", help="Directory to write exported data to."
        )

        parser.add_argument(
            "--threads",
            default=settings.DEFAULT_DATA_EXPORT_IMPORT_PARALLELISM,
            help="Threads to use in exporting UserMessage objects in parallel",
        )

        parser.add_argument(
            "--no-convert-slack-threads",
            action="store_true",
            help="If specified, do not convert Slack threads to separate Zulip topics",
        )

        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Handle function for converting Slack data.

        Args:
            *args: Additional arguments.
            **options: Additional keyword arguments.

        Raises:
            CommandError: If the `output_dir` is not provided or the `token` is not
            provided, or the `num_threads` is less than 1, or a `slack_data_path`
            does not exist.
        """
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="converted-slack-data-")
        else:
            output_dir = os.path.realpath(output_dir)

        token = options["token"]
        if token is None:
            raise CommandError("Enter Slack legacy token!")

        num_threads = int(options["threads"])
        if num_threads < 1:
            raise CommandError("You must have at least one thread.")

        for path in options["slack_data_path"]:
            if not os.path.exists(path):
                raise CommandError(f"Slack data directory not found: '{path}'")

            print("Converting data ...")
            convert_slack_threads = not options["no_convert_slack_threads"]
            do_convert_data(
                path,
                output_dir,
                token,
                threads=num_threads,
                convert_slack_threads=convert_slack_threads,
            )
