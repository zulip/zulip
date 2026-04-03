import tornado.web
from django.conf import settings
from django.core.handlers.base import BaseHandler
from tornado import autoreload

from zerver.lib.queue import TornadoQueueClient
from zerver.tornado.handlers import AsyncDjangoHandler


def setup_tornado_rabbitmq(queue_client: TornadoQueueClient) -> None:  # nocoverage
    # When tornado is shut down, disconnect cleanly from RabbitMQ
    autoreload.add_reload_hook(queue_client.close)


def create_tornado_application(*, autoreload: bool = False) -> tornado.web.Application:
    django_handler = BaseHandler()
    django_handler.load_middleware()

    return tornado.web.Application(
        [(tornado.routing.AnyMatches(), AsyncDjangoHandler, dict(django_handler=django_handler))],
        debug=settings.DEBUG,
        autoreload=autoreload,
        # Disable Tornado's own request logging, since we have our own
        log_function=lambda x: None,
    )
