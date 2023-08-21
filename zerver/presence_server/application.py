import tornado.web
from django.conf import settings
from django.core.handlers.base import BaseHandler
from tornado import autoreload

from zerver.lib.queue import TornadoQueueClient

from .handlers import AsyncDjangoHandler


def setup_tornado_rabbitmq(queue_client: TornadoQueueClient) -> None:  # nocoverage
    # When tornado is shut down, disconnect cleanly from RabbitMQ
    autoreload.add_reload_hook(lambda: queue_client.close())


def create_tornado_application() -> tornado.web.Application:
    django_handler = BaseHandler()
    django_handler.load_middleware()

    urls = (
        "/api/v1/presence_events/internal",
        r"/json/presence_events",
    )

    return tornado.web.Application(
        [(url, AsyncDjangoHandler, dict(django_handler=django_handler)) for url in urls],
        debug=settings.DEBUG,
        autoreload=False,
        # Disable Tornado's own request logging, since we have our own
        log_function=lambda x: None,
    )
