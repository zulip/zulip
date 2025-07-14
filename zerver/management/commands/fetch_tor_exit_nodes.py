import os
from argparse import ArgumentParser
from typing import Any

import orjson
from django.conf import settings
from typing_extensions import override
from urllib3.util import Retry

from zerver.lib.management import ZulipBaseCommand, abort_cron_during_deploy
from zerver.lib.outgoing_http import OutgoingSession


class TorDataSession(OutgoingSession):
    def __init__(self, max_retries: int) -> None:
        Retry.DEFAULT_BACKOFF_MAX = 64
        retry = Retry(
            total=max_retries,
            backoff_factor=2.0,
            status_forcelist={  # Retry on these
                429,  # The formal rate-limiting response code
                500,  # Server error
                502,  # Bad gateway
                503,  # Service unavailable
            },
        )
        super().__init__(role="tor_data", timeout=3, max_retries=retry)


class Command(ZulipBaseCommand):
    help = """Fetch the list of TOR exit nodes, and write the list of IP addresses
to a file for access from Django for rate-limiting purposes.

Does nothing unless RATE_LIMIT_TOR_TOGETHER is enabled.
"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--max-retries",
            type=int,
            default=10,
            help="Number of times to retry fetching data from TOR",
        )

    @override
    @abort_cron_during_deploy
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.RATE_LIMIT_TOR_TOGETHER:
            return

        session = TorDataSession(max_retries=options["max_retries"])
        response = session.get("https://check.torproject.org/exit-addresses")
        response.raise_for_status()

        # Format:
        #     ExitNode 4273E6D162ED2717A1CF4207A254004CD3F5307B
        #     Published 2021-11-02 11:01:07
        #     LastStatus 2021-11-02 23:00:00
        #     ExitAddress 176.10.99.200 2021-11-02 23:17:02
        exit_nodes: set[str] = set()
        for line in response.text.splitlines():
            if line.startswith("ExitAddress "):
                exit_nodes.add(line.split()[1])

        # Write to a tmpfile to ensure we can't read a partially-written file
        with open(settings.TOR_EXIT_NODE_FILE_PATH + ".tmp", "wb") as f:
            f.write(orjson.dumps(list(exit_nodes)))

        # Do an atomic rename into place
        os.rename(
            settings.TOR_EXIT_NODE_FILE_PATH + ".tmp",
            settings.TOR_EXIT_NODE_FILE_PATH,
        )
