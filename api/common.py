#!/usr/bin/python
# Copyright (C) 2012 Humbug, Inc.
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import simplejson
import requests
import time
import traceback
import urlparse
import sys
import os

# Check that we have a recent enough version
# Older versions don't provide the 'json' attribute on responses.
assert(requests.__version__ > '0.12')

class HumbugAPI(object):
    def __init__(self, email, api_key=None, api_key_file=None,
                 verbose=False, retry_on_errors=True,
                 site="https://humbughq.com", client="API"):
        if api_key is None:
            if api_key_file is None:
                api_key_file = os.path.join(os.environ["HOME"], ".humbug-api-key")
            if not os.path.exists(api_key_file):
                raise RuntimeError("api_key not specified and %s does not exist"
                                   % (api_key_file,))
            with file(api_key_file, 'r') as f:
                api_key = f.read().strip()

        self.api_key = api_key
        self.email = email
        self.verbose = verbose
        self.base_url = site
        self.retry_on_errors = retry_on_errors
        self.client_name = client

    def do_api_query(self, request, url, longpolling = False):
        had_error_retry = False
        request["email"] = self.email
        request["api-key"] = self.api_key
        request["client"] = self.client_name

        for (key, val) in request.iteritems():
            if not (isinstance(val, str) or isinstance(val, unicode)):
                request[key] = simplejson.dumps(val)

        request["failures"] = 0

        while True:
            try:
                res = requests.post(urlparse.urljoin(self.base_url, url), data=request,
                                    verify=True, timeout=55)

                # On 50x errors, try again after a short sleep
                if str(res.status_code).startswith('5') and self.retry_on_errors:
                    if self.verbose:
                        if not had_error_retry:
                            sys.stdout.write("connection error %s -- retrying." % (res.status_code,))
                            had_error_retry = True
                            request["failures"] += 1
                        else:
                            sys.stdout.write(".")
                        sys.stdout.flush()
                    time.sleep(1)
                    continue
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
                    return {'msg': "Connection error:\n%s" % traceback.format_exc(),
                            "result": "connection-error"}
            except requests.exceptions.ConnectionError:
                if self.retry_on_errors:
                    if self.verbose:
                        if not had_error_retry:
                            sys.stdout.write("connection error -- retrying.")
                            had_error_retry = True
                            request["failures"] += 1
                        else:
                            sys.stdout.write(".")
                        sys.stdout.flush()
                    time.sleep(1)
                    continue
                return {'msg': "Connection error:\n%s" % traceback.format_exc(),
                        "result": "connection-error"}
            except Exception:
                # We'll split this out into more cases as we encounter new bugs.
                return {'msg': "Unexpected error:\n%s" % traceback.format_exc(),
                        "result": "unexpected-error"}

            if self.verbose and had_error_retry:
                print "Success!"
            if res.json is not None:
                return res.json
            return {'msg': res.text, "result": "http-error",
                    "status_code": res.status_code}

    @classmethod
    def _register(cls, name, url=None, make_request=(lambda request={}: request), **query_kwargs):
        if url is None:
            url = name
        def call(self, *args, **kwargs):
            request = make_request(*args, **kwargs)
            return self.do_api_query(request, '/api/v1/' + url, **query_kwargs)
        call.func_name = name
        setattr(cls, name, call)

    def call_on_each_message(self, callback, options = {}):
        max_message_id = None
        while True:
            if max_message_id is not None:
                options["first"] = "0"
                options["last"] = str(max_message_id)
            res = self.get_messages(options)
            if 'error' in res.get('result'):
                if self.verbose:
                    if res["result"] == "http-error":
                        print "HTTP error fetching messages -- probably a server restart"
                    elif res["result"] == "connection-error":
                        print "Connection error fetching messages -- probably server is temporarily down?"
                    else:
                        print "Server returned error:\n%s" % res["msg"]
                # TODO: Make this back off once it's more reliable
                time.sleep(1)
                continue
            for message in sorted(res['messages'], key=lambda x: int(x["id"])):
                max_message_id = max(max_message_id, int(message["id"]))
                callback(message)

def _mk_subs(streams):
    return {'subscriptions': streams}

HumbugAPI._register('send_message', make_request=(lambda request: request))
HumbugAPI._register('get_messages', longpolling=True)
HumbugAPI._register('get_profile')
HumbugAPI._register('get_public_streams')
HumbugAPI._register('list_subscriptions',   url='subscriptions/list')
HumbugAPI._register('add_subscriptions',    url='subscriptions/add',    make_request=_mk_subs)
HumbugAPI._register('remove_subscriptions', url='subscriptions/remove', make_request=_mk_subs)
