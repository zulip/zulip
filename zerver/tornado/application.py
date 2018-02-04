
import atexit

import tornado.autoreload
import tornado.web
from django.conf import settings

from zerver.lib.queue import get_queue_client
from zerver.tornado.handlers import AsyncDjangoHandler
from zerver.tornado.socket import get_sockjs_router

def setup_tornado_rabbitmq() -> None:
    # When tornado is shut down, disconnect cleanly from rabbitmq
    if settings.USING_RABBITMQ:
        queue_client = get_queue_client()
        atexit.register(lambda: queue_client.close())
        tornado.autoreload.add_reload_hook(lambda: queue_client.close())

def create_tornado_application() -> tornado.web.Application:
    urls = (r"/notify_tornado",
            r"/json/events",
            r"/api/v1/events",
            )

    # Application is an instance of Django's standard wsgi handler.
    return tornado.web.Application(([(url, AsyncDjangoHandler) for url in urls] +
                                    get_sockjs_router().urls),
                                   debug=settings.DEBUG,
                                   autoreload=settings.AUTORELOAD,
                                   # Disable Tornado's own request logging, since we have our own
                                   log_function=lambda x: None)
