#!/usr/bin/env python
import optparse
import subprocess
import signal
import traceback
import os
from os import path

from twisted.internet import reactor
from twisted.web      import proxy, server, resource

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

(options, args) = parser.parse_args()

base_port   = 9991
manage_args = ''
if options.test:
    base_port   = 9981
    manage_args = '--settings=humbug.test_settings'

proxy_port   = base_port
django_port  = base_port+1
tornado_port = base_port+2
proxy_host = 'localhost:%d' % (proxy_port,)

os.chdir(path.join(path.dirname(__file__), '..'))

# Set up a new process group, so that we can later kill run{server,tornado}
# and all of the processes they spawn.
os.setpgrp()

# Pass --nostatic because we configure static serving ourselves in
# humbug/urls.py.
for cmd in ['python manage.py runserver --nostatic %s localhost:%d'
                % (manage_args, django_port),
            'python manage.py runtornado %s localhost:%d'
                % (manage_args, tornado_port)]:
    subprocess.Popen(cmd, shell=True)

class Resource(resource.Resource):
    def getChild(self, name, request):
        request.requestHeaders.setRawHeaders('X-Forwarded-Host', [proxy_host])

        if request.uri in ['/json/get_updates', '/api/v1/get_messages']:
            return proxy.ReverseProxyResource('localhost', tornado_port, '/'+name)

        return proxy.ReverseProxyResource('localhost', django_port, '/'+name)

try:
    reactor.listenTCP(proxy_port, server.Site(Resource()), interface='127.0.0.1')
    reactor.run()
except:
    # Print the traceback before we get SIGTERM and die.
    traceback.print_exc()
    raise
finally:
    # Kill everything in our process group.
    os.killpg(0, signal.SIGTERM)
