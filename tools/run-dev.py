#!/usr/bin/env python
import optparse
import subprocess
import signal
import traceback
import sys
import os

from twisted.internet import reactor
from twisted.web      import proxy, server, resource

# Monkey-patch twisted.web.http to avoid request.finish exceptions
# https://trac.zulip.net/ticket/1728
from twisted.web.http import Request
orig_finish = Request.finish
def patched_finish(self):
    if self._disconnected:
        return
    return orig_finish(self)
Request.finish = patched_finish

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

(options, args) = parser.parse_args()

base_port   = 9991
manage_args = ''
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

os.chdir(os.path.join(os.path.dirname(__file__), '..'))

# Clean up stale .pyc files etc.
subprocess.check_call('./tools/clean-repo')

# Set up a new process group, so that we can later kill run{server,tornado}
# and all of the processes they spawn.
os.setpgrp()

# Pass --nostatic because we configure static serving ourselves in
# zulip/urls.py.
cmds = [['./tools/compile-handlebars-templates', 'forever'],
        ['python', 'manage.py', 'runserver', '--nostatic'] +
          manage_args + ['localhost:%d' % (django_port,)],
        ['python', 'manage.py', 'runtornado'] +
          manage_args + ['localhost:%d' % (tornado_port,)],
        ['./tools/run-dev-queue-processors'] + manage_args,
        ['env', 'PGHOST=localhost', # Force password authentication using .pgpass
         './puppet/zulip/files/postgresql/process_fts_updates']]

for cmd in cmds:
    subprocess.Popen(cmd)

class Resource(resource.Resource):
    def getChild(self, name, request):
        # Assume an HTTP 1.1 request
        proxy_host = request.requestHeaders.getRawHeaders('Host')
        request.requestHeaders.setRawHeaders('X-Forwarded-Host', proxy_host)

        if (request.uri in ['/json/get_events'] or
            request.uri.startswith('/json/events') or
            request.uri.startswith('/api/v1/events') or
            request.uri.startswith('/sockjs')):
            return proxy.ReverseProxyResource('localhost', tornado_port, '/'+name)

        return proxy.ReverseProxyResource('localhost', django_port, '/'+name)

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
