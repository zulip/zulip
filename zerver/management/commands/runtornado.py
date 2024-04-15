import asyncio
import logging
import signal
from contextlib import AsyncExitStack
from typing import Any
from urllib.parse import SplitResult

from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser
from tornado.platform.asyncio import AsyncIOMainLoop
from typing_extensions import override

settings.RUNNING_INSIDE_TORNADO = True
if settings.PRODUCTION:
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

from zerver.lib.async_utils import NoAutoCreateEventLoopPolicy
from zerver.lib.debug import interactive_debug_listen
from zerver.tornado.application import create_tornado_application, setup_tornado_rabbitmq
from zerver.tornado.descriptors import set_current_port
from zerver.tornado.event_queue import (
    add_client_gc_hook,
    dump_event_queues,
    get_wrapped_process_notification,
    missedmessage_hook,
    setup_event_queue,
)
from zerver.tornado.sharding import notify_tornado_queue_name

if settings.USING_RABBITMQ:
    from zerver.lib.queue import TornadoQueueClient, set_queue_client

asyncio.set_event_loop_policy(NoAutoCreateEventLoopPolicy())


class Command(BaseCommand):
    help = "Starts a Tornado Web server wrapping Django."

    @override
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--autoreload", action="store_true", help="Enable Tornado autoreload")
        parser.add_argument(
            "--immediate-reloads",
            action="store_true",
            help="Tell web app clients to immediately reload after Tornado starts",
        )
        parser.add_argument(
            "addrport",
            help="[port number or ipaddr:port]",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        interactive_debug_listen()
        addrport = options["addrport"]
        assert isinstance(addrport, str)

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

        async def inner_run() -> None:
            from django.utils import translation

            AsyncIOMainLoop().install()
            loop = asyncio.get_running_loop()
            stop_fut = loop.create_future()

            def stop() -> None:
                if not stop_fut.done():
                    stop_fut.set_result(None)

            def add_signal_handlers() -> None:
                loop.add_signal_handler(signal.SIGINT, stop)
                loop.add_signal_handler(signal.SIGTERM, stop)

            def remove_signal_handlers() -> None:
                loop.remove_signal_handler(signal.SIGINT)
                loop.remove_signal_handler(signal.SIGTERM)

            async with AsyncExitStack() as stack:
                stack.push_async_callback(
                    sync_to_async(remove_signal_handlers, thread_sensitive=True)
                )
                await sync_to_async(add_signal_handlers, thread_sensitive=True)()

                set_current_port(port)
                translation.activate(settings.LANGUAGE_CODE)

                if settings.CUSTOM_DEVELOPMENT_SETTINGS:
                    print("Using custom settings from zproject/custom_dev_settings.py.")

                # We pass display_num_errors=False, since Django will
                # likely display similar output anyway.
                if not options["skip_checks"]:
                    self.check(display_num_errors=False)
                print(f"Tornado server (re)started on port {port}")

                if settings.USING_RABBITMQ:
                    queue_client = TornadoQueueClient()
                    set_queue_client(queue_client)
                    # Process notifications received via RabbitMQ
                    queue_name = notify_tornado_queue_name(port)
                    stack.callback(queue_client.close)
                    queue_client.start_json_consumer(
                        queue_name, get_wrapped_process_notification(queue_name)
                    )

                # Application is an instance of Django's standard wsgi handler.
                application = create_tornado_application(autoreload=options["autoreload"])

                # start tornado web server in single-threaded mode
                http_server = httpserver.HTTPServer(application, xheaders=True)
                stack.push_async_callback(http_server.close_all_connections)
                stack.callback(http_server.stop)
                http_server.listen(port, address=addr)

                from zerver.tornado.ioloop_logging import logging_data

                logging_data["port"] = str(port)
                send_reloads = options.get("immediate_reloads", False)
                await setup_event_queue(http_server, port, send_reloads)
                stack.callback(dump_event_queues, port)
                add_client_gc_hook(missedmessage_hook)
                if settings.USING_RABBITMQ:
                    setup_tornado_rabbitmq(queue_client)

                await stop_fut

        async_to_sync(inner_run, force_new_loop=True)()
