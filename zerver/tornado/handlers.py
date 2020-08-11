import logging
import urllib
from typing import Any, Dict, List

import tornado.web
from django import http
from django.core import signals
from django.core.handlers import base
from django.core.handlers.wsgi import WSGIRequest, get_script_name
from django.http import HttpRequest, HttpResponse
from django.urls import set_script_prefix
from tornado.wsgi import WSGIContainer

from zerver.lib.response import json_response
from zerver.middleware import async_request_timer_restart, async_request_timer_stop
from zerver.tornado.descriptors import get_descriptor_by_handler_id

current_handler_id = 0
handlers: Dict[int, 'AsyncDjangoHandler'] = {}

# Copied from django.core.handlers.base
logger = logging.getLogger('django.request')

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
    return f"{len(handlers)} handlers, latest ID {current_handler_id}"

def finish_handler(handler_id: int, event_queue_id: str,
                   contents: List[Dict[str, Any]], apply_markdown: bool) -> None:
    err_msg = f"Got error finishing handler for queue {event_queue_id}"
    try:
        # We call async_request_timer_restart here in case we are
        # being finished without any events (because another
        # get_events request has supplanted this request)
        handler = get_handler_by_id(handler_id)
        request = handler._request
        async_request_timer_restart(request)
        if len(contents) != 1:
            request._log_data['extra'] = f"[{event_queue_id}/1]"
        else:
            request._log_data['extra'] = "[{}/1/{}]".format(event_queue_id, contents[0]["type"])

        handler.zulip_finish(dict(result='success', msg='',
                                  events=contents,
                                  queue_id=event_queue_id),
                             request, apply_markdown=apply_markdown)
    except OSError as e:
        if str(e) != 'Stream is closed':
            logging.exception(err_msg, stack_info=True)
    except AssertionError as e:
        if str(e) != 'Request closed':
            logging.exception(err_msg, stack_info=True)
    except Exception:
        logging.exception(err_msg, stack_info=True)


class AsyncDjangoHandler(tornado.web.RequestHandler, base.BaseHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Copied from the django.core.handlers.wsgi __init__() method.
        self.load_middleware()

        # Prevent Tornado from automatically finishing the request
        self._auto_finish = False

        # Handler IDs are allocated here, and the handler ID map must
        # be cleared when the handler finishes its response
        allocate_handler_id(self)

    def __repr__(self) -> str:
        descriptor = get_descriptor_by_handler_id(self.handler_id)
        return f"AsyncDjangoHandler<{self.handler_id}, {descriptor}>"

    def convert_tornado_request_to_django_request(self) -> HttpRequest:
        # This takes the WSGI environment that Tornado received (which
        # fully describes the HTTP request that was sent to Tornado)
        # and pass it to Django's WSGIRequest to generate a Django
        # HttpRequest object with the original Tornado request's HTTP
        # headers, parameters, etc.
        environ = WSGIContainer.environ(self.request)
        environ['PATH_INFO'] = urllib.parse.unquote(environ['PATH_INFO'])

        # Django WSGIRequest setup code that should match logic from
        # Django's WSGIHandler.__call__ before the call to
        # `get_response()`.
        set_script_prefix(get_script_name(environ))
        signals.request_started.send(sender=self.__class__)
        request = WSGIRequest(environ)

        # Provide a way for application code to access this handler
        # given the HttpRequest object.
        request._tornado_handler = self

        return request

    def write_django_response_as_tornado_response(self, response: HttpResponse) -> None:
        # This takes a Django HttpResponse and copies its HTTP status
        # code, headers, cookies, and content onto this
        # tornado.web.RequestHandler (which is how Tornado prepares a
        # response to write).

        # Copy the HTTP status code.
        self.set_status(response.status_code)

        # Copy the HTTP headers (iterating through a Django
        # HttpResponse is the way to access its headers as key/value pairs)
        for h in response.items():
            self.set_header(h[0], h[1])

        # Copy any cookies
        if not hasattr(self, "_new_cookies"):
            self._new_cookies: List[http.cookie.SimpleCookie[str]] = []
        self._new_cookies.append(response.cookies)

        # Copy the response content
        self.write(response.content)

        # Close the connection.
        self.finish()

    def get(self, *args: Any, **kwargs: Any) -> None:
        request = self.convert_tornado_request_to_django_request()

        try:
            response = self.get_response(request)

            if hasattr(response, "asynchronous"):
                # For asynchronous requests, this is where we exit
                # without returning the HttpResponse that Django
                # generated back to the user in order to long-poll the
                # connection.  We save some timers here in order to
                # support accurate accounting of the total resources
                # consumed by the request when it eventually returns a
                # response and is logged.
                async_request_timer_stop(request)
                return
        finally:
            # Tell Django that we're done processing this request on
            # the Django side; this triggers cleanup work like
            # resetting the urlconf and any cache/database
            # connections.
            signals.request_finished.send(sender=self.__class__)

        # For normal/synchronous requests that don't end up
        # long-polling, we fall through to here and just need to write
        # the HTTP response that Django prepared for us via Tornado.

        # Mark this handler ID as finished for Zulip's own tracking.
        clear_handler_by_id(self.handler_id)

        self.write_django_response_as_tornado_response(response)

    def head(self, *args: Any, **kwargs: Any) -> None:
        self.get(*args, **kwargs)

    def post(self, *args: Any, **kwargs: Any) -> None:
        self.get(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> None:
        self.get(*args, **kwargs)

    def on_connection_close(self) -> None:
        # Register a Tornado handler that runs when client-side
        # connections are closed to notify the events system.
        #
        # TODO: Theoretically, this code should run when you Ctrl-C
        # curl to cause it to break a `GET /events` connection, but
        # that seems to no longer run this code.  Investigate what's up.
        client_descriptor = get_descriptor_by_handler_id(self.handler_id)
        if client_descriptor is not None:
            client_descriptor.disconnect_handler(client_closed=True)

    def zulip_finish(self, result_dict: Dict[str, Any], old_request: HttpRequest,
                     apply_markdown: bool) -> None:
        # Function called when we want to break a long-polled
        # get_events request and return a response to the client.

        # Marshall the response data from result_dict.
        if result_dict['result'] == 'success' and 'messages' in result_dict and apply_markdown:
            for msg in result_dict['messages']:
                if msg['content_type'] != 'text/html':
                    self.set_status(500)
                    self.finish('Internal error: bad message format')
        if result_dict['result'] == 'error':
            self.set_status(400)

        # The `result` dictionary contains the data we want to return
        # to the client.  We want to do so in a proper Tornado HTTP
        # response after running the Django response middleware (which
        # does things like log the request, add rate-limit headers,
        # etc.).  The Django middleware API expects to receive a fresh
        # HttpRequest object, and so to minimize hacks, our strategy
        # is to create a duplicate Django HttpRequest object, tagged
        # to automatically return our data in its response, and call
        # Django's main self.get_response() handler to generate an
        # HttpResponse with all Django middleware run.
        request = self.convert_tornado_request_to_django_request()

        # Add to this new HttpRequest logging data from the processing of
        # the original request; we will need these for logging.
        #
        # TODO: Design a cleaner way to manage these attributes,
        # perhaps via creating a ZulipHttpRequest class that contains
        # these attributes with a copy method.
        request._log_data = old_request._log_data
        if hasattr(request, "_rate_limit"):
            request._rate_limit = old_request._rate_limit
        if hasattr(request, "_requestor_for_logs"):
            request._requestor_for_logs = old_request._requestor_for_logs
        request.user = old_request.user
        request.client = old_request.client

        # The saved_response attribute, if present, causes
        # rest_dispatch to return the response immediately before
        # doing any work.  This arrangement allows Django's full
        # request/middleware system to run unmodified while avoiding
        # running expensive things like Zulip's authentication code a
        # second time.
        request.saved_response = json_response(res_type=result_dict['result'],
                                               data=result_dict, status=self.get_status())

        try:
            response = self.get_response(request)
        finally:
            # Tell Django we're done processing this request
            #
            # TODO: Investigate whether this (and other call points in
            # this file) should be using response.close() instead.
            signals.request_finished.send(sender=self.__class__)

        self.write_django_response_as_tornado_response(response)
