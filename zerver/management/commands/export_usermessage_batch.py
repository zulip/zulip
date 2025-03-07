import glob
import logging
import os
from argparse import ArgumentParser
from typing import Any

import orjson
from typing_extensions import override

from zerver.lib.export import export_usermessages_batch
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """UserMessage fetching helper for export.py"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--path", help="Path to find messages.json archives")
        parser.add_argument("--thread", help="Thread ID")
        parser.add_argument(
            "--export-full-with-consent",
            action="store_true",
            help="Whether to export private data of users who consented",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        logging.info("Starting UserMessage batch thread %s", options["thread"])
        path = options["path"]
        files = set(glob.glob(os.path.join(path, "messages-*.json.partial")))

        export_full_with_consent = options["export_full_with_consent"]
        consented_user_ids = None
        if export_full_with_consent:
            consented_user_ids_path = os.path.join(path, "consented_user_ids.json")
            assert os.path.exists(consented_user_ids_path)

            with open(consented_user_ids_path, "rb") as f:
                consented_user_ids = set(orjson.loads(f.read()))

        for partial_path in files:
            locked_path = partial_path.replace(".json.partial", ".json.locked")
            output_path = partial_path.replace(".json.partial", ".json")
            try:
                os.rename(partial_path, locked_path)
            except FileNotFoundError:
                # Already claimed by another process
                continue
            logging.info("Thread %s processing %s", options["thread"], output_path)
            try:
                export_usermessages_batch(
                    locked_path,
                    output_path,
                    export_full_with_consent,
                    consented_user_ids=consented_user_ids,
                )
            except BaseException:
                # Put the item back in the free pool when we fail
                os.rename(locked_path, partial_path)
                raise
