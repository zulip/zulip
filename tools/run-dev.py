#!/usr/bin/env python3

import argparse
import os
import pwd
import signal
import subprocess
import sys
import time
import traceback

from urllib.parse import urlunparse

# check for the venv
from lib import sanity_check
sanity_check.check_venv(__file__)

from tornado import httpclient
from tornado import httputil
from tornado import gen
from tornado import web
from tornado.ioloop import IOLoop
from tornado.websocket import WebSocketHandler, websocket_connect

from typing import Any, Callable, Generator, List, Optional

if 'posix' in os.name and os.geteuid() == 0:
    raise RuntimeError("run-dev.py should not be run as root.")

parser = argparse.ArgumentParser(description=r"""

Starts the app listening on localhost, for local development.

This script launches the Django and Tornado servers, then runs a reverse proxy
which serves to both of them.  After it's all up and running, browse to

    http://localhost:9991/

Note that, while runserver and runtornado have the usual auto-restarting
behavior, the reverse proxy itself does *not* automatically restart on changes
to this file.
""",
                                 formatter_class=argparse.RawTextHelpFormatter)

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TOOLS_DIR))
from tools.lib.test_script import (
    get_provisioning_status,
)

parser.add_argument('--test',
                    action='store_true',
                    help='Use the testing database and ports')
parser.add_argument('--minify',
                    action='store_true',
                    help='Minifies assets for testing in dev')
parser.add_argument('--interface',
                    action='store',
                    default=None, help='Set the IP or hostname for the proxy to listen on')
parser.add_argument('--no-clear-memcached',
                    action='store_false', dest='clear_memcached',
                    default=True, help='Do not clear memcached')
parser.add_argument('--force',
                    action="store_true",
                    default=False, help='Run command despite possible problems.')
parser.add_argument('--enable-tornado-logging',
                    action="store_true",
                    default=False, help='Enable access logs from tornado proxy server.')
options = parser.parse_args()

if not options.force:
    ok, msg = get_provisioning_status()
    if not ok:
        print(msg)
        print('If you really know what you are doing, use --force to run anyway.')
        sys.exit(1)

if options.interface is None:
    user_id = os.getuid()
    user_name = pwd.getpwuid(user_id).pw_name
    if user_name in ["vagrant", "zulipdev"]:
        # In the Vagrant development environment, we need to listen on
        # all ports, and it's safe to do so, because Vagrant is only
        # exposing certain guest ports (by default just 9991) to the
        # host.  The same argument applies to the remote development
        # servers using username "zulipdev".
        options.interface = None
    else:
        # Otherwise, only listen to requests on localhost for security.
        options.interface = "127.0.0.1"
elif options.interface == "":
    options.interface = None

runserver_args = []  # type: List[str]
base_port = 9991
if options.test:
    base_port = 9981
    settings_module = "zproject.test_settings"
    # Don't auto-reload when running casper tests
    runserver_args = ['--noreload']
else:
    settings_module = "zproject.settings"

manage_args = ['--settings=%s' % (settings_module,)]
os.environ['DJANGO_SETTINGS_MODULE'] = settings_module

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from scripts.lib.zulip_tools import WARNING, ENDC

proxy_port = base_port
django_port = base_port + 1
tornado_port = base_port + 2
webpack_port = base_port + 3
thumbor_port = base_port + 4

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

# Clean up stale .pyc files etc.
subprocess.check_call('./tools/clean-repo')

if options.clear_memcached:
    print("Clearing memcached ...")
    subprocess.check_call('./scripts/setup/flush-memcached')

# Set up a new process group, so that we can later kill run{server,tornado}
# and all of the processes they spawn.
os.setpgrp()

# Save pid of parent process to the pid file. It can be used later by
# tools/stop-run-dev to kill the server without having to find the
# terminal in question.

if options.test:
    pid_file_path = os.path.join(os.path.join(os.getcwd(), 'var/casper/run_dev.pid'))
else:
    pid_file_path = os.path.join(os.path.join(os.getcwd(), 'var/run/run_dev.pid'))

# Required for compatibility python versions.
if not os.path.exists(os.path.dirname(pid_file_path)):
    os.makedirs(os.path.dirname(pid_file_path))
pid_file = open(pid_file_path, 'w+')
pid_file.write(str(os.getpgrp()) + "\n")
pid_file.close()

# Pass --nostatic because we configure static serving ourselves in
# zulip/urls.py.
cmds = [['./tools/compile-handlebars-templates', 'forever'],
        ['./manage.py', 'runserver'] +
        manage_args + runserver_args + ['127.0.0.1:%d' % (django_port,)],
        ['env', 'PYTHONUNBUFFERED=1', './manage.py', 'runtornado'] +
        manage_args + ['127.0.0.1:%d' % (tornado_port,)],
        ['./tools/run-dev-queue-processors'] + manage_args,
        ['env', 'PGHOST=127.0.0.1',  # Force password authentication using .pgpass
         './puppet/zulip/files/postgresql/process_fts_updates'],
        ['./manage.py', 'deliver_scheduled_messages'],
        ['/srv/zulip-thumbor-venv/bin/thumbor', '-c', './zthumbor/thumbor.conf',
         '-p', '%s' % (thumbor_port,)]]
if options.test:
    # Webpack doesn't support 2 copies running on the same system, so
    # in order to support running the Casper tests while a Zulip
    # development server is running, we use webpack in production mode
    # for the Casper tests.
    subprocess.check_call('./tools/webpack')
else:
    webpack_cmd = ['./tools/webpack', '--watch', '--port', str(webpack_port)]
    if options.minify:
        webpack_cmd.append('--minify')
    if options.interface:
        webpack_cmd += ["--host", options.interface]
    else:
        webpack_cmd += ["--host", "0.0.0.0"]
    cmds.append(webpack_cmd)
for cmd in cmds:
    subprocess.Popen(cmd)


def transform_url(protocol, path, query, target_port, target_host):
    # type: (str, str, str, int, str) -> str
    # generate url with target host
    host = ":".join((target_host, str(target_port)))
    # Here we are going to rewrite the path a bit so that it is in parity with
    # what we will have for production
    if path.startswith('/thumbor'):
        path = path[len('/thumbor'):]
    newpath = urlunparse((protocol, host, path, '', query, ''))
    return newpath


@gen.engine
def fetch_request(url, callback, **kwargs):
    # type: (str, Any, **Any) -> Generator[Callable[..., Any], Any, None]
    # use large timeouts to handle polling requests
    req = httpclient.HTTPRequest(url, connect_timeout=240.0, request_timeout=240.0, **kwargs)
    client = httpclient.AsyncHTTPClient()
    # wait for response
    response = yield gen.Task(client.fetch, req)
    callback(response)


class BaseWebsocketHandler(WebSocketHandler):
    # target server ip
    target_host = '127.0.0.1'  # type: str
    # target server port
    target_port = None  # type: int

    def __init__(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        super().__init__(*args, **kwargs)
        # define client for target websocket server
        self.client = None  # type: Any

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> Optional[Callable[..., Any]]
        # use get method from WebsocketHandler
        return super().get(*args, **kwargs)

    def open(self):
        # type: () -> None
        # setup connection with target websocket server
        websocket_url = "ws://{host}:{port}{uri}".format(
            host=self.target_host,
            port=self.target_port,
            uri=self.request.uri
        )
        request = httpclient.HTTPRequest(websocket_url)
        request.headers = self._add_request_headers(['sec-websocket-extensions'])
        websocket_connect(request, callback=self.open_callback,
                          on_message_callback=self.on_client_message)

    def open_callback(self, future):
        # type: (Any) -> None
        # callback on connect with target websocket server
        self.client = future.result()

    def on_client_message(self, message):
        # type: (str) -> None
        if not message:
            # if message empty -> target websocket server close connection
            return self.close()
        if self.ws_connection:
            # send message to client if connection exists
            self.write_message(message, False)

    def on_message(self, message, binary=False):
        # type: (str, bool) -> Optional[Callable[..., Any]]
        if not self.client:
            # close websocket proxy connection if no connection with target websocket server
            return self.close()
        self.client.write_message(message, binary)
        return None

    def check_origin(self, origin):
        # type: (str) -> bool
        return True

    def _add_request_headers(self, exclude_lower_headers_list=None):
        # type: (Optional[List[str]]) -> httputil.HTTPHeaders
        exclude_lower_headers_list = exclude_lower_headers_list or []
        headers = httputil.HTTPHeaders()
        for header, v in self.request.headers.get_all():
            if header.lower() not in exclude_lower_headers_list:
                headers.add(header, v)
        return headers


class CombineHandler(BaseWebsocketHandler):

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> Optional[Callable[..., Any]]
        if self.request.headers.get("Upgrade", "").lower() == 'websocket':
            return super().get(*args, **kwargs)
        return None

    def head(self):
        # type: () -> None
        pass

    def post(self):
        # type: () -> None
        pass

    def put(self):
        # type: () -> None
        pass

    def patch(self):
        # type: () -> None
        pass

    def options(self):
        # type: () -> None
        pass

    def delete(self):
        # type: () -> None
        pass

    def handle_response(self, response):
        # type: (Any) -> None
        if response.error and not isinstance(response.error, httpclient.HTTPError):
            self.set_status(500)
            self.write('Internal server error:\n' + str(response.error))
        else:
            self.set_status(response.code, response.reason)
            self._headers = httputil.HTTPHeaders()  # clear tornado default header

            for header, v in response.headers.get_all():
                if header != 'Content-Length':
                    # some header appear multiple times, eg 'Set-Cookie'
                    self.add_header(header, v)
            if response.body:
                # rewrite Content-Length Header by the response
                self.set_header('Content-Length', len(response.body))
                self.write(response.body)
        self.finish()

    @web.asynchronous
    def prepare(self):
        # type: () -> None
        if 'X-REAL-IP' not in self.request.headers:
            self.request.headers['X-REAL-IP'] = self.request.remote_ip
        if self.request.headers.get("Upgrade", "").lower() == 'websocket':
            return super().prepare()
        url = transform_url(
            self.request.protocol,
            self.request.path,
            self.request.query,
            self.target_port,
            self.target_host,
        )
        try:
            fetch_request(
                url=url,
                callback=self.handle_response,
                method=self.request.method,
                headers=self._add_request_headers(["upgrade-insecure-requests"]),
                follow_redirects=False,
                body=getattr(self.request, 'body'),
                allow_nonstandard_methods=True
            )
        except httpclient.HTTPError as e:
            if hasattr(e, 'response') and e.response:
                self.handle_response(e.response)
            else:
                self.set_status(500)
                self.write('Internal server error:\n' + str(e))
                self.finish()


class WebPackHandler(CombineHandler):
    target_port = webpack_port


class DjangoHandler(CombineHandler):
    target_port = django_port


class TornadoHandler(CombineHandler):
    target_port = tornado_port


class ThumborHandler(CombineHandler):
    target_port = thumbor_port


class Application(web.Application):
    def __init__(self, enable_logging=False):
        # type: (bool) -> None
        handlers = [
            (r"/json/events.*", TornadoHandler),
            (r"/api/v1/events.*", TornadoHandler),
            (r"/webpack.*", WebPackHandler),
            (r"/sockjs.*", TornadoHandler),
            (r"/thumbor.*", ThumborHandler),
            (r"/.*", DjangoHandler)
        ]
        super().__init__(handlers, enable_logging=enable_logging)

    def log_request(self, handler):
        # type: (BaseWebsocketHandler) -> None
        if self.settings['enable_logging']:
            super().log_request(handler)


def on_shutdown():
    # type: () -> None
    IOLoop.instance().stop()


def shutdown_handler(*args, **kwargs):
    # type: (*Any, **Any) -> None
    io_loop = IOLoop.instance()
    if io_loop._callbacks:
        io_loop.call_later(1, shutdown_handler)
    else:
        io_loop.stop()

# log which services/ports will be started
print("Starting Zulip services on ports: web proxy: {},".format(proxy_port),
      "Django: {}, Tornado: {}, Thumbor: {}".format(django_port, tornado_port, thumbor_port),
      end='')
if options.test:
    print("")  # no webpack for --test
else:
    print(", webpack: {}".format(webpack_port))

print("".join((WARNING,
               "Note: only port {} is exposed to the host in a Vagrant environment.".format(
                   proxy_port), ENDC)))

try:
    app = Application(enable_logging=options.enable_tornado_logging)
    app.listen(proxy_port, address=options.interface)
    ioloop = IOLoop.instance()
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, shutdown_handler)
    ioloop.start()
except Exception:
    # Print the traceback before we get SIGTERM and die.
    traceback.print_exc()
    raise
finally:
    # Kill everything in our process group.
    os.killpg(0, signal.SIGTERM)
    # Remove pid file when development server closed correctly.
    os.remove(pid_file_path)
