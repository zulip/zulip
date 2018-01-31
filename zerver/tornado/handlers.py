
import logging
import sys
import urllib
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import tornado.web
from django.urls import get_resolver, set_urlconf
from django import http
from django.conf import settings
from django.core import exceptions, signals
from django.core.exceptions import MiddlewareNotUsed
from django.core.handlers import base
from django.core.handlers.exception import response_for_exception
from django.core.handlers.wsgi import WSGIRequest, get_script_name
from django.urls import set_script_prefix, set_urlconf
from django.http import HttpRequest, HttpResponse
from django.utils.module_loading import import_string
from tornado.wsgi import WSGIContainer

from zerver.decorator import RespondAsynchronously
from zerver.lib.response import json_response
from zerver.middleware import async_request_restart, AsyncResponse
from zerver.tornado.descriptors import get_descriptor_by_handler_id

current_handler_id = 0
handlers = {}  # type: Dict[int, 'AsyncDjangoHandler']

def get_handler_by_id(handler_id: int) -> 'AsyncDjangoHandler':
    return handlers[handler_id]

def allocate_handler_id(handler: 'AsyncDjangoHandler') -> int:
    global current_handler_id
    handlers[current_handler_id] = handler
    handler.handler_id = current_handler_id
    current_handler_id += 1
    return handler.handler_id

def clear_handler_by_id(handler_id: int) -> None:
    del handlers[handler_id]

def handler_stats_string() -> str:
    return "%s handlers, latest ID %s" % (len(handlers), current_handler_id)

def finish_handler(handler_id: int, event_queue_id: str,
                   contents: List[Dict[str, Any]], apply_markdown: bool) -> None:
    err_msg = "Got error finishing handler for queue %s" % (event_queue_id,)
    try:
        # We call async_request_restart here in case we are
        # being finished without any events (because another
        # get_events request has supplanted this request)
        handler = get_handler_by_id(handler_id)
        request = handler._request
        async_request_restart(request)
        if len(contents) != 1:
            request._log_data['extra'] = "[%s/1]" % (event_queue_id,)
        else:
            request._log_data['extra'] = "[%s/1/%s]" % (event_queue_id, contents[0]["type"])

        handler.zulip_finish(dict(result='success', msg='',
                                  events=contents,
                                  queue_id=event_queue_id),
                             request, apply_markdown=apply_markdown)
    except IOError as e:
        if str(e) != 'Stream is closed':
            logging.exception(err_msg)
    except AssertionError as e:
        if str(e) != 'Request closed':
            logging.exception(err_msg)
    except Exception:
        logging.exception(err_msg)


# Modified version of the base Tornado handler for Django
class AsyncDjangoHandler(tornado.web.RequestHandler, base.BaseHandler):
    initLock = Lock()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.deferred_middlewares = []
        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        self._middleware_chain = None  # type: Optional[Callable[[HttpRequest], HttpResponse]]
        self.initLock.acquire()
        # Check that middleware is still uninitialised.
        if self._middleware_chain is None:
            self.load_middleware()
        self.initLock.release()
        self._auto_finish = False
        # Handler IDs are allocated here, and the handler ID map must
        # be cleared when the handler finishes its response
        allocate_handler_id(self)

    def __repr__(self) -> str:
        descriptor = get_descriptor_by_handler_id(self.handler_id)
        return "AsyncDjangoHandler<%s, %s>" % (self.handler_id, descriptor)

    def get(self, *args: Any, **kwargs: Any) -> None:
        environ = WSGIContainer.environ(self.request)
        environ['PATH_INFO'] = urllib.parse.unquote(environ['PATH_INFO'])
        request = WSGIRequest(environ)
        request._tornado_handler = self

        set_script_prefix(get_script_name(environ))
        signals.request_started.send(sender=self.__class__)
        try:
            response = self.get_response(request)
            if isinstance(response, AsyncResponse):
                return None
        finally:
            signals.request_finished.send(sender=self.__class__)

        self.set_status(response.status_code)
        for h in response.items():
            self.set_header(h[0], h[1])

        if not hasattr(self, "_new_cookies"):
            self._new_cookies = []  # type: List[http.cookie.SimpleCookie]
        self._new_cookies.append(response.cookies)

        self.write(response.content)
        self.finish()

    def head(self, *args: Any, **kwargs: Any) -> None:
        self.get(*args, **kwargs)

    def post(self, *args: Any, **kwargs: Any) -> None:
        self.get(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        self.get(*args, **kwargs)

    def on_connection_close(self) -> None:
        client_descriptor = get_descriptor_by_handler_id(self.handler_id)
        if client_descriptor is not None:
            client_descriptor.disconnect_handler(client_closed=True)

    def apply_response_middleware(self, request: HttpRequest,
                                  response: HttpResponse) -> HttpResponse:
        try:
            # Apply response middleware, regardless of the response
            for middleware_method in self.deferred_middlewares:
                response = middleware_method(request, response)
        except Exception as exc:  # Any exception should be gathered and handled
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response = response_for_exception(request, exc)

        return response

    def zulip_finish(self, response: Dict[str, Any], request: HttpRequest,
                     apply_markdown: bool) -> None:
        # Make sure that Markdown rendering really happened, if requested.
        # This is a security issue because it's where we escape HTML.
        # c.f. ticket #64
        #
        # apply_markdown=True is the fail-safe default.
        if response['result'] == 'success' and 'messages' in response and apply_markdown:
            for msg in response['messages']:
                if msg['content_type'] != 'text/html':
                    self.set_status(500)
                    self.finish('Internal error: bad message format')
        if response['result'] == 'error':
            self.set_status(400)

        # Call the Django response middleware on our object so that
        # e.g. our own logging code can run; but don't actually use
        # the headers from that since sending those to Tornado seems
        # tricky; instead just send the (already json-rendered)
        # content on to Tornado
        django_response = json_response(res_type=response['result'],
                                        data=response, status=self.get_status())
        django_response = self.apply_response_middleware(request, django_response)
        # Pass through the content-type from Django, as json content should be
        # served as application/json
        self.set_header("Content-Type", django_response['Content-Type'])
        self.finish(django_response.content)
