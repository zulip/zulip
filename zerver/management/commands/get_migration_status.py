import argparse
import os
from typing import Any

from django.db import DEFAULT_DB_ALIAS
from typing_extensions import override

from scripts.lib.zulip_tools import get_dev_uuid_var_path
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.migration_status import get_migration_status


class Command(ZulipBaseCommand):
    help = "Get status of migrations."

    @override
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "app_label", nargs="?", help="App label of an application to synchronize the state."
        )

        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help='Nominates a database to synchronize. Defaults to the "default" database.',
        )

        parser.add_argument("--output", help="Path to store the status to (default to stdout).")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        result = get_migration_status(**options)
        if options["output"] is not None:
            uuid_var_path = get_dev_uuid_var_path()
            path = os.path.join(uuid_var_path, options["output"])
            with open(path, "w") as f:
                f.write(result)
        else:
            self.stdout.write(result)
