#!/usr/bin/env python
import subprocess
import os
from os import path

from twisted.internet import reactor
from twisted.web      import proxy, server, resource

"""
Starts the app listening on localhost, for local development.

This script launches the Django and Tornado servers, then runs a reverse proxy
which serves to both of them.  After it's all up and running, browse to

    http://localhost:9991/

Note that, while runserver and runtornado have the usual auto-restarting
behavior, the reverse proxy itself does *not* automatically restart on changes
to this file.
"""

proxy_port = 9991
proxy_host = 'localhost:%d' % (proxy_port,)

os.chdir(path.join(path.dirname(__file__), '..'))

procs = []
for cmd in ['python manage.py runserver  localhost:9992',
            'python manage.py runtornado localhost:9993']:
    procs.append(subprocess.Popen(cmd, shell=True))

class Resource(resource.Resource):
    def getChild(self, name, request):
        request.requestHeaders.setRawHeaders('X-Forwarded-Host', [proxy_host])

        if request.uri in ['/json/get_updates', '/api/v1/get_messages']:
            return proxy.ReverseProxyResource('localhost', 9993, '/'+name)

        return proxy.ReverseProxyResource('localhost', 9992, '/'+name)

reactor.listenTCP(proxy_port, server.Site(Resource()), interface='127.0.0.1')

try:
    reactor.run()
finally:
    for proc in procs:
        proc.terminate()
