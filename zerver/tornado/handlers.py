from __future__ import absolute_import
from __future__ import print_function

import sys
import tornado.web
import logging
from django import http
from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest, get_script_name
from django.core.handlers import base
from django.core.urlresolvers import set_script_prefix
from django.core import signals
from django.core import exceptions, urlresolvers
from django.http import HttpRequest, HttpResponse
from threading import Lock
from tornado.wsgi import WSGIContainer
from six.moves import urllib

from zerver.decorator import RespondAsynchronously
from zerver.lib.response import json_response
from zerver.middleware import async_request_stop, async_request_restart
from zerver.tornado.descriptors import get_descriptor_by_handler_id

from typing import Any, Callable

current_handler_id = 0
handlers = {} # type: Dict[int, AsyncDjangoHandler]

def get_handler_by_id(handler_id):
    # type: (int) -> AsyncDjangoHandler
    return handlers[handler_id]

def allocate_handler_id(handler):
    # type: (AsyncDjangoHandler) -> int
    global current_handler_id
    handlers[current_handler_id] = handler
    handler.handler_id = current_handler_id
    current_handler_id += 1
    return handler.handler_id

def clear_handler_by_id(handler_id):
    # type: (int) -> None
    del handlers[handler_id]

def handler_stats_string():
    # type: () -> str
    return "%s handlers, latest ID %s" % (len(handlers), current_handler_id)

def finish_handler(handler_id, event_queue_id, contents, apply_markdown):
    # type: (int, str, List[Dict[str, Any]], bool) -> None
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

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super(AsyncDjangoHandler, self).__init__(*args, **kwargs)

        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        self._request_middleware = None  # type: ignore # Should be List[Callable[[WSGIRequest], Any]] https://github.com/JukkaL/mypy/issues/1174
        self.initLock.acquire()
        # Check that middleware is still uninitialised.
        if self._request_middleware is None:
            self.load_middleware()
        self.initLock.release()
        self._auto_finish = False
        # Handler IDs are allocated here, and the handler ID map must
        # be cleared when the handler finishes its response
        allocate_handler_id(self)

    def __repr__(self):
        # type: () -> str
        descriptor = get_descriptor_by_handler_id(self.handler_id)
        return "AsyncDjangoHandler<%s, %s>" % (self.handler_id, descriptor)

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        environ = WSGIContainer.environ(self.request)
        environ['PATH_INFO'] = urllib.parse.unquote(environ['PATH_INFO'])
        request = WSGIRequest(environ)
        request._tornado_handler = self

        set_script_prefix(get_script_name(environ))
        signals.request_started.send(sender=self.__class__)
        try:
            response = self.get_response(request)

            if not response:
                return
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

    def head(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.get(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.get(*args, **kwargs)

    def on_connection_close(self):
        # type: () -> None
        client_descriptor = get_descriptor_by_handler_id(self.handler_id)
        if client_descriptor is not None:
            client_descriptor.disconnect_handler(client_closed=True)

    # Based on django.core.handlers.base: get_response
    def get_response(self, request):
        # type: (HttpRequest) -> HttpResponse
        "Returns an HttpResponse object for the given HttpRequest"
        try:
            try:
                # Setup default url resolver for this thread.
                urlconf = settings.ROOT_URLCONF
                urlresolvers.set_urlconf(urlconf)
                resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)

                response = None

                # Apply request middleware
                for middleware_method in self._request_middleware:
                    response = middleware_method(request)
                    if response:
                        break

                if hasattr(request, "urlconf"):
                    # Reset url resolver with a custom urlconf.
                    urlconf = request.urlconf
                    urlresolvers.set_urlconf(urlconf)
                    resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)

                ### ADDED BY ZULIP
                request._resolver = resolver
                ### END ADDED BY ZULIP

                callback, callback_args, callback_kwargs = resolver.resolve(
                    request.path_info)

                # Apply view middleware
                if response is None:
                    for middleware_method in self._view_middleware:
                        response = middleware_method(request, callback, callback_args,
                                                     callback_kwargs)
                        if response:
                            break

                ### THIS BLOCK MODIFIED BY ZULIP
                if response is None:
                    try:
                        response = callback(request, *callback_args, **callback_kwargs)
                        if response is RespondAsynchronously:
                            async_request_stop(request)
                            return None
                        clear_handler_by_id(self.handler_id)
                    except Exception as e:
                        clear_handler_by_id(self.handler_id)
                        # If the view raised an exception, run it through exception
                        # middleware, and if the exception middleware returns a
                        # response, use that. Otherwise, reraise the exception.
                        for middleware_method in self._exception_middleware:
                            response = middleware_method(request, e)
                            if response:
                                break
                        if response is None:
                            raise

                if response is None:
                    try:
                        view_name = callback.__name__
                    except AttributeError:
                        view_name = callback.__class__.__name__ + '.__call__'
                    raise ValueError("The view %s.%s returned None." %
                                     (callback.__module__, view_name))

                # If the response supports deferred rendering, apply template
                # response middleware and the render the response
                if hasattr(response, 'render') and callable(response.render):
                    for middleware_method in self._template_response_middleware:
                        response = middleware_method(request, response)
                    response = response.render()

            except http.Http404 as e:
                if settings.DEBUG:
                    from django.views import debug
                    response = debug.technical_404_response(request, e)
                else:
                    try:
                        callback, param_dict = resolver.resolve404()
                        response = callback(request, **param_dict)
                    except:
                        try:
                            response = self.handle_uncaught_exception(request, resolver,
                                                                      sys.exc_info())
                        finally:
                            signals.got_request_exception.send(sender=self.__class__,
                                                               request=request)
            except exceptions.PermissionDenied:
                logging.warning(
                    'Forbidden (Permission denied): %s', request.path,
                    extra={
                        'status_code': 403,
                        'request': request
                    })
                try:
                    callback, param_dict = resolver.resolve403()
                    response = callback(request, **param_dict)
                except:
                    try:
                        response = self.handle_uncaught_exception(request,
                                                                  resolver, sys.exc_info())
                    finally:
                        signals.got_request_exception.send(
                            sender=self.__class__, request=request)
            except SystemExit:
                # See https://code.djangoproject.com/ticket/4701
                raise
            except Exception as e:
                exc_info = sys.exc_info()
                signals.got_request_exception.send(sender=self.__class__, request=request)
                return self.handle_uncaught_exception(request, resolver, exc_info)
        finally:
            # Reset urlconf on the way out for isolation
            urlresolvers.set_urlconf(None)

        ### ZULIP CHANGE: The remainder of this function was moved
        ### into its own function, just below, so we can call it from
        ### finish().
        response = self.apply_response_middleware(request, response, resolver)

        return response

    ### Copied from get_response (above in this file)
    def apply_response_middleware(self, request, response, resolver):
        # type: (HttpRequest, HttpResponse, urlresolvers.RegexURLResolver) -> HttpResponse
        try:
            # Apply response middleware, regardless of the response
            for middleware_method in self._response_middleware:
                response = middleware_method(request, response)
            if hasattr(self, 'apply_response_fixes'):
                response = self.apply_response_fixes(request, response)
        except:  # Any exception should be gathered and handled
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

        return response

    def zulip_finish(self, response, request, apply_markdown):
        # type: (HttpResponse, HttpRequest, bool) -> None
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
        django_response = self.apply_response_middleware(request, django_response,
                                                         request._resolver)
        # Pass through the content-type from Django, as json content should be
        # served as application/json
        self.set_header("Content-Type", django_response['Content-Type'])
        self.finish(django_response.content)
