import os
import ssl
from typing import Any
from urllib.parse import SplitResult

from django.core.management.base import BaseCommand, CommandParser
from typing_extensions import override

from zerver.lib.email_mirror_server import run_smtp_server


class Command(BaseCommand):
    help = """SMTP server to ingest incoming emails"""

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--listen", help="[Port, or address:port, to bind HTTP server to]", default="0.0.0.0:25"
        )
        parser.add_argument(
            "--user",
            help="User to drop privileges to, if started as root.",
            type=str,
            required=(os.geteuid() == 0),
        )
        parser.add_argument(
            "--group",
            help="Group to drop privileges to, if started as root.",
            type=str,
            required=(os.geteuid() == 0),
        )
        tls_cert: str | None = None
        tls_key: str | None = None
        if os.access("/etc/ssl/certs/zulip.combined-chain.crt", os.R_OK) and os.access(
            "/etc/ssl/private/zulip.key", os.R_OK
        ):
            tls_cert = "/etc/ssl/certs/zulip.combined-chain.crt"
            tls_key = "/etc/ssl/private/zulip.key"
        elif os.access("/etc/ssl/certs/ssl-cert-snakeoil.pem", os.R_OK) and os.access(
            "/etc/ssl/private/ssl-cert-snakeoil.key", os.R_OK
        ):
            tls_cert = "/etc/ssl/certs/ssl-cert-snakeoil.pem"
            tls_key = "/etc/ssl/private/ssl-cert-snakeoil.key"
        parser.add_argument(
            "--tls-cert",
            help="Path to TLS certificate chain file",
            type=str,
            default=tls_cert,
        )
        parser.add_argument(
            "--tls-key",
            help="Path to TLS private key file",
            type=str,
            default=tls_key,
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        listen = options["listen"]
        if listen.isdigit():
            host, port = "0.0.0.0", int(listen)  # noqa: S104
        else:
            r = SplitResult("", listen, "", "", "")
            if r.port is None:
                raise RuntimeError(f"{listen!r} does not have a valid port number.")
            host, port = r.hostname or "0.0.0.0", r.port  # noqa: S104
        if options["tls_cert"] and options["tls_key"]:
            tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            tls_context.load_cert_chain(options["tls_cert"], options["tls_key"])
        else:
            tls_context = None

        run_smtp_server(options["user"], options["group"], host, port, tls_context)
