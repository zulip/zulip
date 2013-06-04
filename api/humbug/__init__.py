# -*- coding: utf-8 -*-

# Copyright © 2012 Humbug, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import simplejson
import requests
import time
import traceback
import urlparse
import sys
import os
import optparse
from distutils.version import LooseVersion

from ConfigParser import SafeConfigParser


__version__ = "0.1.8"

# Check that we have a recent enough version
# Older versions don't provide the 'json' attribute on responses.
assert(LooseVersion(requests.__version__) >= LooseVersion('0.12.1'))
# In newer versions, the 'json' attribute is a function, not a property
requests_json_is_function = callable(requests.Response.json)

API_VERSTRING = "/api/v1/"

def generate_option_group(parser):
    group = optparse.OptionGroup(parser, 'API configuration')
    group.add_option('--site',
                      default=None,
                      help=optparse.SUPPRESS_HELP)
    group.add_option('--api-key',
                     action='store')
    group.add_option('--user',
                     dest='email',
                     help='Email address of the calling user.')
    group.add_option('--config-file',
                     action='store',
                     help='Location of an ini file containing the above information.')
    group.add_option('-v', '--verbose',
                     action='store_true',
                     help='Provide detailed output.')

    return group

def init_from_options(options):
    return Client(email=options.email, api_key=options.api_key, config_file=options.config_file,
                  verbose=options.verbose, site=options.site)

class Client(object):
    def __init__(self, email=None, api_key=None, config_file=None,
                 verbose=False, retry_on_errors=True,
                 site=None, client="API: Python"):
        if None in (api_key, email):
            if config_file is None:
                config_file = os.path.join(os.environ["HOME"], ".humbugrc")
            if not os.path.exists(config_file):
                raise RuntimeError("api_key or email not specified and %s does not exist"
                                   % (config_file,))
            config = SafeConfigParser()
            with file(config_file, 'r') as f:
                config.readfp(f, config_file)
            if api_key is None:
                api_key = config.get("api", "key")
            if email is None:
                email = config.get("api", "email")
            if site is None and config.has_option("api", "site"):
                site = config.get("api", "site")

        self.api_key = api_key
        self.email = email
        self.verbose = verbose
        if site is not None:
            self.base_url = site
        else:
            self.base_url = "https://humbughq.com"
        self.retry_on_errors = retry_on_errors
        self.client_name = client

    def do_api_query(self, orig_request, url, method="POST", longpolling = False):
        request = {}
        request["client"] = self.client_name

        for (key, val) in orig_request.iteritems():
            if not (isinstance(val, str) or isinstance(val, unicode)):
                request[key] = simplejson.dumps(val)
            else:
                request[key] = val

        query_state = {
            'had_error_retry': False,
            'request': request,
            'failures': 0,
        }

        def error_retry(error_string):
            if not self.retry_on_errors or query_state["failures"] >= 10:
                return False
            if self.verbose:
                if not query_state["had_error_retry"]:
                    sys.stdout.write("humbug API(%s): connection error%s -- retrying." % \
                            (url.split(API_VERSTRING, 2)[1], error_string,))
                    query_state["had_error_retry"] = True
                else:
                    sys.stdout.write(".")
                sys.stdout.flush()
            query_state["request"]["dont_block"] = simplejson.dumps(True)
            time.sleep(1)
            query_state["failures"] += 1
            return True

        def end_error_retry(succeeded):
            if query_state["had_error_retry"] and self.verbose:
                if succeeded:
                    print "Success!"
                else:
                    print "Failed!"

        while True:
            try:
                if method == "GET":
                    kwarg = "params"
                else:
                    kwarg = "data"
                kwargs = {kwarg: query_state["request"]}
                res = requests.request(
                        method,
                        urlparse.urljoin(self.base_url, url),
                        auth=requests.auth.HTTPBasicAuth(self.email,
                                                         self.api_key),
                        verify=True, timeout=90,
                        **kwargs)

                # On 50x errors, try again after a short sleep
                if str(res.status_code).startswith('5'):
                    if error_retry(" (server %s)" % (res.status_code,)):
                        continue
                    # Otherwise fall through and process the python-requests error normally
            except (requests.exceptions.Timeout, requests.exceptions.SSLError) as e:
                # Timeouts are either a Timeout or an SSLError; we
                # want the later exception handlers to deal with any
                # non-timeout other SSLErrors
                if (isinstance(e, requests.exceptions.SSLError) and
                    str(e) != "The read operation timed out"):
                    raise
                if longpolling:
                    # When longpolling, we expect the timeout to fire,
                    # and the correct response is to just retry
                    continue
                else:
                    end_error_retry(False)
                    return {'msg': "Connection error:\n%s" % traceback.format_exc(),
                            "result": "connection-error"}
            except requests.exceptions.ConnectionError:
                if error_retry(""):
                    continue
                end_error_retry(False)
                return {'msg': "Connection error:\n%s" % traceback.format_exc(),
                        "result": "connection-error"}
            except Exception:
                # We'll split this out into more cases as we encounter new bugs.
                return {'msg': "Unexpected error:\n%s" % traceback.format_exc(),
                        "result": "unexpected-error"}

            if requests_json_is_function:
                json_result = res.json()
            else:
                json_result = res.json
            if json_result is not None:
                end_error_retry(True)
                return json_result
            end_error_retry(False)
            return {'msg': res.text, "result": "http-error",
                    "status_code": res.status_code}

    @classmethod
    def _register(cls, name, url=None, make_request=(lambda request={}: request),
            method="POST", **query_kwargs):
        if url is None:
            url = name
        def call(self, *args, **kwargs):
            request = make_request(*args, **kwargs)
            return self.do_api_query(request, API_VERSTRING + url, method=method, **query_kwargs)
        call.func_name = name
        setattr(cls, name, call)

    def call_on_each_event(self, callback, event_types=None):
        def do_register():
            while True:
                if event_types is None:
                    res = self.register()
                else:
                    res = self.register(event_types=event_types)

                if 'error' in res.get('result'):
                    if self.verbose:
                        print "Server returned error:\n%s" % res['msg']
                    time.sleep(1)
                else:
                    return (res['queue_id'], res['last_event_id'])

        queue_id = None
        while True:
            if queue_id is None:
                (queue_id, last_event_id) = do_register()

            res = self.get_events(queue_id=queue_id, last_event_id=last_event_id)
            if 'error' in res.get('result'):
                if res["result"] == "http-error":
                    if self.verbose:
                        print "HTTP error fetching events -- probably a server restart"
                elif res["result"] == "connection-error":
                    if self.verbose:
                        print "Connection error fetching events -- probably server is temporarily down?"
                else:
                    if self.verbose:
                        print "Server returned error:\n%s" % res["msg"]
                    if res["msg"].startswith("Bad event queue id:"):
                        # Our event queue went away, probably because
                        # we were asleep or the server restarted
                        # abnormally.  We may have missed some
                        # events while the network was down or
                        # something, but there's not really anything
                        # we can do about it other than resuming
                        # getting new ones.
                        #
                        # Reset queue_id to register a new event queue.
                        queue_id = None
                # TODO: Make this back off once it's more reliable
                time.sleep(1)
                continue

            for event in res['events']:
                last_event_id = max(last_event_id, int(event['id']))
                callback(event)

    def call_on_each_message(self, callback):
        def event_callback(event):
            if event['type'] == 'message':
                callback(event['message'])

        self.call_on_each_event(event_callback, ['message'])

def _mk_subs(streams):
    return {'subscriptions': streams}

def _mk_rm_subs(streams):
    return {'delete': streams}

def _mk_events(event_types=None):
    if event_types is None:
        return dict()
    return dict(event_types=event_types)

Client._register('send_message', url='messages', make_request=(lambda request: request))
Client._register('update_message', method='PATCH', url='messages', make_request=(lambda request: request))
Client._register('get_messages', method='GET', url='messages/latest', longpolling=True)
Client._register('get_events', url='events', method='GET', longpolling=True, make_request=(lambda **kwargs: kwargs))
Client._register('register', make_request=_mk_events)
Client._register('get_profile', method='GET', url='users/me')
Client._register('get_public_streams', method='GET', url='streams')
Client._register('get_members', method='GET', url='users')
Client._register('list_subscriptions', method='GET', url='users/me/subscriptions')
Client._register('add_subscriptions', url='users/me/subscriptions',    make_request=_mk_subs)
Client._register('remove_subscriptions', method='PATCH', url='users/me/subscriptions', make_request=_mk_rm_subs)
