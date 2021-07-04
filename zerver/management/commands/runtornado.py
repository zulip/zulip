import asyncio
import logging
import sys
from typing import Any, Callable
from urllib.parse import SplitResult

from zerver.tornado.ioloop_logging import CustomEventLoopPolicy

asyncio.set_event_loop_policy(CustomEventLoopPolicy())

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from tornado import ioloop
from tornado.log import app_log

settings.RUNNING_INSIDE_TORNADO = True

from zerver.lib.debug import interactive_debug_listen
from zerver.tornado.application import create_tornado_application, setup_tornado_rabbitmq
from zerver.tornado.autoreload import start as zulip_autoreload_start
from zerver.tornado.event_queue import (
    add_client_gc_hook,
    get_wrapped_process_notification,
    missedmessage_hook,
    setup_event_queue,
)
from zerver.tornado.sharding import notify_tornado_queue_name

if settings.USING_RABBITMQ:
    from zerver.lib.queue import TornadoQueueClient, get_queue_client


def handle_callback_exception(callback: Callable[..., Any]) -> None:
    logging.exception("Exception in callback", stack_info=True)
    app_log.error("Exception in callback %r", callback, exc_info=True)


class Command(BaseCommand):
    help = "Starts a Tornado Web server wrapping Django."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "addrport",
            nargs="?",
            help="[optional port number or ipaddr:port]\n "
            "(use multiple ports to start multiple servers)",
        )

    def handle(self, addrport: str, **options: bool) -> None:
        interactive_debug_listen()

        import django
        from tornado import httpserver

        if addrport.isdigit():
            addr, port = "", int(addrport)
        else:
            r = SplitResult("", addrport, "", "", "")
            if r.port is None:
                raise CommandError(f"{addrport!r} does not have a valid port number.")
            addr, port = r.hostname or "", r.port

        if not addr:
            addr = "127.0.0.1"

        if settings.DEBUG:
            logging.basicConfig(
                level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s"
            )

        def inner_run() -> None:
            from django.conf import settings
            from django.utils import translation

            translation.activate(settings.LANGUAGE_CODE)

            # We pass display_num_errors=False, since Django will
            # likely display similar output anyway.
            self.check(display_num_errors=False)
            print(f"Tornado server (re)started on port {port}")

            if settings.USING_RABBITMQ:
                queue_client = get_queue_client()
                assert isinstance(queue_client, TornadoQueueClient)
                # Process notifications received via RabbitMQ
                queue_name = notify_tornado_queue_name(port)
                queue_client.start_json_consumer(
                    queue_name, get_wrapped_process_notification(queue_name)
                )

            try:
                # Application is an instance of Django's standard wsgi handler.
                application = create_tornado_application()
                if settings.AUTORELOAD:
                    zulip_autoreload_start()

                # start tornado web server in single-threaded mode
                http_server = httpserver.HTTPServer(application, xheaders=True)
                http_server.listen(port, address=addr)

                from zerver.tornado.ioloop_logging import logging_data

                logging_data["port"] = str(port)
                setup_event_queue(port)
                add_client_gc_hook(missedmessage_hook)
                setup_tornado_rabbitmq()

                instance = ioloop.IOLoop.current()

                if django.conf.settings.DEBUG:
                    instance.asyncio_loop.slow_callback_duration = 5
                    instance.asyncio_loop.set_debug(True)
                instance.start()
            except KeyboardInterrupt:
                sys.exit(0)

        inner_run()
