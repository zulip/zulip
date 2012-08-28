from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings
import os
import sys
import tornado.web
 
class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--noreload', action='store_false',
            dest='auto_reload', default=True,
            help="Configures tornado to not auto-reload (for prod use)."),
        make_option('--nokeepalive', action='store_true',
            dest='no_keep_alive', default=False,
            help="Tells Tornado to NOT keep alive http connections."),
        make_option('--noxheaders', action='store_false',
            dest='xheaders', default=True,
            help="Tells Tornado to NOT override remote IP with X-Real-IP."),
    )
    help = "Starts a Tornado Web server wrapping Django."
    args = '[optional port number or ipaddr:port]\n  (use multiple ports to start multiple servers)'

    def handle(self, *addrport, **options):
        # setup unbuffered I/O
        sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
        sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)
 
        if len(addrport) == 0:
            self.run_one(**options)
        elif len(addrport) == 1:
            self.run_one(addrport[0], **options)
        else:
            from multiprocessing import Process

            plist = []
            for ap in addrport:
                p = Process(target=self.run_one, args=(ap,), kwargs=options)
                p.start()
                plist.append(p)

            while plist:
                if plist[0].exitcode is None:
                    plist.pop(0)
                else:
                    plist[0].join()
            

    def run_one(self, addrport, **options):
        import django
        from django.core.handlers.wsgi import WSGIHandler
        from tornado import httpserver, wsgi, ioloop, web

        if not addrport:
            addr = ''
            port = '8000'
        else:
            try:
                addr, port = addrport.split(':')
            except ValueError:
                addr, port = '', addrport
        if not addr:
            addr = '127.0.0.1'
 
        if not port.isdigit():
            raise CommandError("%r is not a valid port number." % port)
 
        auto_reload = options.get('auto_reload', False)
        xheaders = options.get('xheaders', True)
        no_keep_alive = options.get('no_keep_alive', False)
        quit_command = 'CTRL-C'

        if settings.DEBUG:
            import logging
            logger = logging.getLogger()
            logger.setLevel(logging.INFO)
 
        def inner_run():
            from django.conf import settings
            from django.utils import translation
            translation.activate(settings.LANGUAGE_CODE)

            print "Validating Django models.py..."
            self.validate(display_num_errors=True)
            print "\nDjango version %s" % (django.get_version())
            print "Tornado server is running at http://%s:%s/" % (addr, port)
            print "Quit the server with %s." % quit_command
            
            from tornado.web import FallbackHandler, StaticFileHandler
            django_app = wsgi.WSGIContainer(WSGIHandler())

            try:
                # Application is an instance of Django's standard wsgi handler.
                application = web.Application([(r"/get_updates_longpoll", AsyncDjangoHandler),
                                               (r".*", FallbackHandler, dict(fallback=django_app)),
                                               ])

                # start tornado web server in single-threaded mode
                http_server = httpserver.HTTPServer(application,
                                                    xheaders=xheaders,
                                                    no_keep_alive=no_keep_alive)
                http_server.listen(int(port), address=addr)

                ioloop.IOLoop.instance().start()
            except KeyboardInterrupt:
                sys.exit(0)
 
        if auto_reload:
            from tornado import autoreload
            autoreload.start()

        inner_run()

#
#  Modify the base Tornado handler for Django
#
from threading import Lock
from django.core.handlers import base
from django.core.urlresolvers import set_script_prefix
from django.core import signals

class AsyncDjangoHandler(tornado.web.RequestHandler, base.BaseHandler):
    initLock = Lock()

    def __init__(self, *args, **kwargs):
        super(AsyncDjangoHandler, self).__init__(*args, **kwargs)

        # Set up middleware if needed. We couldn't do this earlier, because
        # settings weren't available.
        self._request_middleware = None
        self.initLock.acquire()
        # Check that middleware is still uninitialised.
        if self._request_middleware is None:
            self.load_middleware()
        self.initLock.release()
        self._auto_finish = False

    def prepare(func):
        """Patches the Cookie header in the Tornado request to fulfull                                                       
        Django's strict string-type cookie policy"""
        def inner_func(self,**kwargs):
            if u'Cookie' in self.request.headers:
                raw_cookie = self.request.headers[u'Cookie']
                if isinstance(raw_cookie, unicode):
                    if hasattr(escape, "native_str"):
                        self.request.headers[u'Cookie'] = escape.native_str(raw_cookie)
                    else:
                        print "Method 'native_str' in module 'escape' not found."
                        self.request.headers[u'Cookie'] = str(raw_cookie)
            return func(self)
        return inner_func

    def get(self):
        from tornado.wsgi import HTTPRequest, WSGIContainer
        from django.core.handlers.wsgi import WSGIRequest, STATUS_CODE_TEXT
        import urllib

        environ  = WSGIContainer.environ(self.request)
        environ['PATH_INFO'] = urllib.unquote(environ['PATH_INFO'])
        request  = WSGIRequest(environ)
        request._tornado_handler     = self

        set_script_prefix(base.get_script_name(environ))
        signals.request_started.send(sender=self.__class__)
        try:
            response = self.get_response(request)

            if not response:
                return 

            # Apply response middleware
            for middleware_method in self._response_middleware:
                response = middleware_method(request, response)
            response = self.apply_response_fixes(request, response)
        finally:
            signals.request_finished.send(sender=self.__class__)

        status_text = STATUS_CODE_TEXT.get(response.status_code, "UNKNOWN")
        status = '%s (%s)' % (response.status_code, status_text)

        self.set_status(response.status_code)
        for h in response.items():
            self.set_header(h[0], h[1])

        if not hasattr(self, "_new_cookies"):
            self._new_cookies = []
        self._new_cookies.append(response.cookies)

        self.write(response.content)
        self.finish()
    

    def head(self):
        self.get()

    def post(self):
        self.get()

    # Based on django.core.handlers.base: get_response
    def get_response(self, request):
        "Returns an HttpResponse object for the given HttpRequest"
        from django import http
        from django.core import exceptions, urlresolvers
        from django.conf import settings

        try:
            try:
                # Setup default url resolver for this thread.
                urlconf = settings.ROOT_URLCONF
                urlresolvers.set_urlconf(urlconf)
                resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)

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

                callback, callback_args, callback_kwargs = resolver.resolve(
                        request.path_info)

                # Apply view middleware
                for middleware_method in self._view_middleware:
                    response = middleware_method(request, callback, callback_args, callback_kwargs)
                    if response:
                        break

                from ...decorator import TornadoAsyncException

                try:
                    response = callback(request, *callback_args, **callback_kwargs)
                except TornadoAsyncException, e:
                    # TODO: Maybe add debugging output here
                    return
                except Exception, e:
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
                        view_name = callback.func_name
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


            except http.Http404, e:
                if settings.DEBUG:
                    from django.views import debug
                    response = debug.technical_404_response(request, e)
                else:
                    try:
                        callback, param_dict = resolver.resolve404()
                        response = callback(request, **param_dict)
                    except:
                        try:
                            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())
                        finally:
                            receivers = signals.got_request_exception.send(sender=self.__class__, request=request)
            except exceptions.PermissionDenied:
                logger.warning(
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
            except Exception, e:
                exc_info = sys.exc_info()
                receivers = signals.got_request_exception.send(sender=self.__class__, request=request)
                return self.handle_uncaught_exception(request, resolver, exc_info)
        finally:
            # Reset urlconf on the way out for isolation
            urlresolvers.set_urlconf(None)

        try:
            # Apply response middleware, regardless of the response                             
            for middleware_method in self._response_middleware:
                response = middleware_method(request, response)
            response = self.apply_response_fixes(request, response)
        except: # Any exception should be gathered and handled                                  
            signals.got_request_exception.send(sender=self.__class__, request=request)
            response = self.handle_uncaught_exception(request, resolver, sys.exc_info())

        return response
