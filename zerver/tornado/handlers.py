
import logging
import sys
import urllib
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

import tornado.web
from django import http
from django.conf import settings
from django.core import exceptions, signals
from django.urls import resolvers
from django.core.exceptions import MiddlewareNotUsed
from django.core.handlers import base
from django.core.handlers.exception import convert_exception_to_response
from django.core.handlers.wsgi import WSGIRequest, get_script_name
from django.urls import set_script_prefix, set_urlconf
from django.http import HttpRequest, HttpResponse
from django.utils.module_loading import import_string
from tornado.wsgi import WSGIContainer

from zerver.decorator import RespondAsynchronously
from zerver.lib.response import json_response
from zerver.lib.types import ViewFuncT
from zerver.middleware import async_request_timer_restart, async_request_timer_stop
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
        # We call async_request_timer_restart here in case we are
        # being finished without any events (because another
        # get_events request has supplanted this request)
        handler = get_handler_by_id(handler_id)
        request = handler._request
        async_request_timer_restart(request)
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
# We mark this for nocoverage, since we only change 1 line of actual code.
class AsyncDjangoHandlerBase(tornado.web.RequestHandler, base.BaseHandler):  # nocoverage
    initLock = Lock()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        self._request_middleware = None  # type: Optional[List[Callable[[HttpRequest], HttpResponse]]]
        self.initLock.acquire()
        # Check that middleware is still uninitialised.
        if self._request_middleware is None:
            self.load_middleware()
        self.initLock.release()
        self._auto_finish = False
        # Handler IDs are allocated here, and the handler ID map must
        # be cleared when the handler finishes its response
        allocate_handler_id(self)

    def __repr__(self) -> str:
        descriptor = get_descriptor_by_handler_id(self.handler_id)
        return "AsyncDjangoHandler<%s, %s>" % (self.handler_id, descriptor)

    def load_middleware(self) -> None:
        """
        Populate middleware lists from settings.MIDDLEWARE. This is copied
        from Django. This uses settings.MIDDLEWARE setting with the old
        business logic. The middleware architecture is not compatible
        with our asynchronous handlers. The problem occurs when we return
        None from our handler. The Django middlewares throw exception
        because they can't handler None, so we can either upgrade the Django
        middlewares or just override this method to use the new setting with
        the old logic. The added advantage is that due to this our event
        system code doesn't change.
        """
        self._request_middleware = []  # type: Optional[List[Callable[[HttpRequest], HttpResponse]]]
        self._view_middleware = []  # type: List[Callable[[HttpRequest, ViewFuncT, List[str], Dict[str, Any]], Optional[HttpResponse]]]
        self._template_response_middleware = []  # type: List[Callable[[HttpRequest, HttpResponse], HttpResponse]]
        self._response_middleware = []  # type: List[Callable[[HttpRequest, HttpResponse], HttpResponse]]
        self._exception_middleware = []  # type: List[Callable[[HttpRequest, Exception], Optional[HttpResponse]]]

        handler = convert_exception_to_response(self._legacy_get_response)
        for middleware_path in settings.MIDDLEWARE:
            mw_class = import_string(middleware_path)
            try:
                mw_instance = mw_class()
            except MiddlewareNotUsed as exc:
                if settings.DEBUG:
                    if str(exc):
                        base.logger.debug('MiddlewareNotUsed(%r): %s', middleware_path, exc)
                    else:
                        base.logger.debug('MiddlewareNotUsed: %r', middleware_path)
                continue

            if hasattr(mw_instance, 'process_request'):
                self._request_middleware.append(mw_instance.process_request)
            if hasattr(mw_instance, 'process_view'):
                self._view_middleware.append(mw_instance.process_view)
            if hasattr(mw_instance, 'process_template_response'):
                self._template_response_middleware.insert(0, mw_instance.process_template_response)
            if hasattr(mw_instance, 'process_response'):
                self._response_middleware.insert(0, mw_instance.process_response)
            if hasattr(mw_instance, 'process_exception'):
                self._exception_middleware.insert(0, mw_instance.process_exception)

        # We only assign to this when initialization is complete as it is used
        # as a flag for initialization being complete.
        self._middleware_chain = handler

    def get(self, *args: Any, **kwargs: Any) -> None:
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

    # Based on django.core.handlers.base: get_response
    def get_response(self, request: HttpRequest) -> HttpResponse:
        "Returns an HttpResponse object for the given HttpRequest"
        try:
            try:
                # Setup default url resolver for this thread.
                urlconf = settings.ROOT_URLCONF
                set_urlconf(urlconf)
                resolver = resolvers.RegexURLResolver(r'^/', urlconf)

                response = None

                # Apply request middleware
                for middleware_method in self._request_middleware:
                    response = middleware_method(request)
                    if response:
                        break

                if hasattr(request, "urlconf"):
                    # Reset url resolver with a custom urlconf.
                    urlconf = request.urlconf
                    set_urlconf(urlconf)
                    resolver = resolvers.RegexURLResolver(r'^/', urlconf)

                ### ADDED BY ZULIP
                request._resolver = resolver
                ### END ADDED BY ZULIP

                callback, callback_args, callback_kwargs = resolver.resolve(
                    request.path_info)

                # Apply view middleware
                if response is None:
                    for view_middleware_method in self._view_middleware:
                        response = view_middleware_method(request, callback,
                                                          callback_args, callback_kwargs)
                        if response:
                            break

                ### THIS BLOCK MODIFIED BY ZULIP
                if response is None:
                    try:
                        response = callback(request, *callback_args, **callback_kwargs)
                        if response is RespondAsynchronously:
                            async_request_timer_stop(request)
                            return None
                        clear_handler_by_id(self.handler_id)
                    except Exception as e:
                        clear_handler_by_id(self.handler_id)
                        # If the view raised an exception, run it through exception
                        # middleware, and if the exception middleware returns a
                        # response, use that. Otherwise, reraise the exception.
                        for exception_middleware_method in self._exception_middleware:
                            response = exception_middleware_method(request, e)
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
                    for template_middleware_method in self._template_response_middleware:
                        response = template_middleware_method(request, response)
                    response = response.render()

            except http.Http404 as e:
                if settings.DEBUG:
                    from django.views import debug
                    response = debug.technical_404_response(request, e)
                else:
                    try:
                        callback, param_dict = resolver.resolve404()
                        response = callback(request, **param_dict)
                    except Exception:
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
                except Exception:
                    try:
                        response = self.handle_uncaught_exception(request,
                                                                  resolver, sys.exc_info())
                    finally:
                        signals.got_request_exception.send(
                            sender=self.__class__, request=request)
            except SystemExit:
                # See https://code.djangoproject.com/ticket/4701
                raise
            except Exception:
                exc_info = sys.exc_info()
                signals.got_request_exception.send(sender=self.__class__, request=request)
                return self.handle_uncaught_exception(request, resolver, exc_info)
        finally:
            # Reset urlconf on the way out for isolation
            set_urlconf(None)

        ### ZULIP CHANGE: The remainder of this function was moved
        ### into its own function, just below, so we can call it from
        ### finish().
        response = self.apply_response_middleware(request, response, resolver)

        return response

    ### Copied from get_response (above in this file)
    def apply_response_middleware(self, request: HttpRequest, response: HttpResponse,
                                  resolver: resolvers.RegexURLResolver) -> HttpResponse:
        try:
            # Apply response middleware, regardless of the response
            for middleware_method in self._response_middleware:
                response = middleware_method(request, response)
            if hasattr(self, 'apply_response_fixes'):
                response = self.apply_response_fixes(request, response)
        except Exception:  # Any exception should be gathered and handled
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

        return response

class AsyncDjangoHandler(AsyncDjangoHandlerBase):
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
        django_response = self.apply_response_middleware(request, django_response,
                                                         request._resolver)
        # Pass through the content-type from Django, as json content should be
        # served as application/json
        self.set_header("Content-Type", django_response['Content-Type'])
        self.finish(django_response.content)
