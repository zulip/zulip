from collections.abc import Iterator, Sequence

import tornado.web
from django.conf import settings
from django.core.handlers.base import BaseHandler
from django.urls import URLPattern, URLResolver
from tornado import autoreload

from zerver.lib.queue import TornadoQueueClient
from zerver.tornado.handlers import AsyncDjangoHandler
from zproject.tornado_urls import urlpatterns as tornado_urlpatterns


def extract_all_url_patterns(
    url_patterns: Sequence[object], base_pattern: str = "/"
) -> Iterator[str]:
    for pattern in url_patterns:
        if isinstance(pattern, URLPattern):
            yield base_pattern + str(pattern.pattern)
        elif isinstance(pattern, URLResolver):
            yield from extract_all_url_patterns(
                pattern.url_patterns, base_pattern + str(pattern.pattern)
            )


def setup_tornado_rabbitmq(queue_client: TornadoQueueClient) -> None:  # nocoverage
    # When tornado is shut down, disconnect cleanly from RabbitMQ
    autoreload.add_reload_hook(queue_client.close)


def create_tornado_application(*, autoreload: bool = False) -> tornado.web.Application:
    django_handler = BaseHandler()
    django_handler.load_middleware()

    return tornado.web.Application(
        [
            (url, AsyncDjangoHandler, dict(django_handler=django_handler))
            for url in extract_all_url_patterns(tornado_urlpatterns)
        ],
        debug=settings.DEBUG,
        autoreload=autoreload,
        # Disable Tornado's own request logging, since we have our own
        log_function=lambda x: None,
    )
