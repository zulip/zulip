#!/usr/bin/env python2
from __future__ import print_function

import optparse
import subprocess
import signal
import traceback
import sys
import os

if False: from typing import Any

# find out python version
major_version = int(subprocess.check_output(['python', '-c', 'import sys; print(sys.version_info[0])']))
if major_version != 2:
    # use twisted from its python2 venv but use django, tornado, etc. from the python3 venv.
    PATH = os.environ["PATH"]
    activate_this = "/srv/zulip-venv/bin/activate_this.py"
    if not os.path.exists(activate_this):
        activate_this = "/srv/zulip-py2-twisted-venv/bin/activate_this.py"
    exec(open(activate_this).read(), {}, dict(__file__=activate_this)) # type: ignore # https://github.com/python/mypy/issues/1577
    os.environ["PATH"] = PATH

from twisted.internet import reactor
from twisted.web      import proxy, server, resource

# Monkey-patch twisted.web.http to avoid request.finish exceptions
# https://trac.zulip.net/ticket/1728
from twisted.web.http import Request
orig_finish = Request.finish
def patched_finish(self):
    # type: (Any) -> None
    if not self._disconnected:
        orig_finish(self)
Request.finish = patched_finish

if 'posix' in os.name and os.geteuid() == 0:
    raise RuntimeError("run-dev.py should not be run as root.")

parser = optparse.OptionParser(r"""

Starts the app listening on localhost, for local development.

This script launches the Django and Tornado servers, then runs a reverse proxy
which serves to both of them.  After it's all up and running, browse to

    http://localhost:9991/

Note that, while runserver and runtornado have the usual auto-restarting
behavior, the reverse proxy itself does *not* automatically restart on changes
to this file.
""")

parser.add_option('--test',
    action='store_true', dest='test',
    help='Use the testing database and ports')

parser.add_option('--interface',
    action='store', dest='interface',
    default='127.0.0.1', help='Set the IP or hostname for the proxy to listen on')

parser.add_option('--no-clear-memcached',
    action='store_false', dest='clear_memcached',
    default=True, help='Do not clear memcached')

(options, args) = parser.parse_args()

base_port   = 9991
if options.test:
    base_port   = 9981
    settings_module = "zproject.test_settings"
else:
    settings_module = "zproject.settings"

manage_args = ['--settings=%s' % (settings_module,)]
os.environ['DJANGO_SETTINGS_MODULE'] = settings_module

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

proxy_port   = base_port
django_port  = base_port+1
tornado_port = base_port+2
webpack_port = base_port+3

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

# Clean up stale .pyc files etc.
subprocess.check_call('./tools/clean-repo')

if options.clear_memcached:
    print("Clearing memcached ...")
    subprocess.check_call('./scripts/setup/flush-memcached')

# Set up a new process group, so that we can later kill run{server,tornado}
# and all of the processes they spawn.
os.setpgrp()

# Pass --nostatic because we configure static serving ourselves in
# zulip/urls.py.
cmds = [['./tools/compile-handlebars-templates', 'forever'],
        ['python', 'manage.py', 'rundjango'] +
          manage_args + ['127.0.0.1:%d' % (django_port,)],
        ['python', '-u', 'manage.py', 'runtornado'] +
          manage_args + ['127.0.0.1:%d' % (tornado_port,)],
        ['./tools/run-dev-queue-processors'] + manage_args,
        ['env', 'PGHOST=127.0.0.1', # Force password authentication using .pgpass
         './puppet/zulip/files/postgresql/process_fts_updates']]
if options.test:
    # Webpack doesn't support 2 copies running on the same system, so
    # in order to support running the Casper tests while a Zulip
    # development server is running, we use webpack in production mode
    # for the Casper tests.
    subprocess.check_call('./tools/webpack')
else:
    cmds += [['./tools/webpack', '--watch', '--port', str(webpack_port)]]
for cmd in cmds:
    subprocess.Popen(cmd)

class Resource(resource.Resource):
    def getChild(self, name, request):
        # type: (str, server.Request) -> resource.Resource

        # Assume an HTTP 1.1 request
        proxy_host = request.requestHeaders.getRawHeaders('Host')
        request.requestHeaders.setRawHeaders('X-Forwarded-Host', proxy_host)

        if (request.uri in ['/json/get_events'] or
            request.uri.startswith('/json/events') or
            request.uri.startswith('/api/v1/events') or
            request.uri.startswith('/sockjs')):
            return proxy.ReverseProxyResource('127.0.0.1', tornado_port, '/'+name)

        elif (request.uri.startswith('/webpack') or
              request.uri.startswith('/socket.io')):
            return proxy.ReverseProxyResource('127.0.0.1', webpack_port, '/'+name)

        return proxy.ReverseProxyResource('127.0.0.1', django_port, '/'+name)

try:
    reactor.listenTCP(proxy_port, server.Site(Resource()), interface=options.interface)
    reactor.run()
except:
    # Print the traceback before we get SIGTERM and die.
    traceback.print_exc()
    raise
finally:
    # Kill everything in our process group.
    os.killpg(0, signal.SIGTERM)
