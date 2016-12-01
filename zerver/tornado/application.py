from __future__ import absolute_import
from __future__ import print_function

from django.conf import settings

from zerver.tornado.handlers import AsyncDjangoHandler
from zerver.tornado.socket import get_sockjs_router

import tornado.web

def create_tornado_application():
    # type: () -> tornado.web.Application
    urls = (r"/notify_tornado",
            r"/json/events",
            r"/api/v1/events",
            )

    # Application is an instance of Django's standard wsgi handler.
    return tornado.web.Application([(url, AsyncDjangoHandler) for url in urls]
                                   + get_sockjs_router().urls,
                                   debug=settings.DEBUG,
                                   # Disable Tornado's own request logging, since we have our own
                                   log_function=lambda x: None)
