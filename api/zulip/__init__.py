# -*- coding: utf-8 -*-

# Copyright © 2012-2014 Zulip, Inc.
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import simplejson
import requests
import time
import traceback
import sys
import os
import optparse
import platform
import random
from distutils.version import LooseVersion

from six.moves.configparser import SafeConfigParser
from six.moves import urllib
import logging
import six
from typing import Any, Dict


__version__ = "0.2.5"

logger = logging.getLogger(__name__)

# Check that we have a recent enough version
# Older versions don't provide the 'json' attribute on responses.
assert(LooseVersion(requests.__version__) >= LooseVersion('0.12.1')) # type: ignore # https://github.com/python/mypy/issues/1165 and https://github.com/python/typeshed/pull/206
# In newer versions, the 'json' attribute is a function, not a property
requests_json_is_function = callable(requests.Response.json)

API_VERSTRING = "v1/"

class CountingBackoff(object):
    def __init__(self, maximum_retries=10, timeout_success_equivalent=None):
        self.number_of_retries = 0
        self.maximum_retries = maximum_retries
        self.timeout_success_equivalent = timeout_success_equivalent
        self.last_attempt_time = 0

    def keep_going(self):
        self._check_success_timeout()
        return self.number_of_retries < self.maximum_retries

    def succeed(self):
        self.number_of_retries = 0
        self.last_attempt_time = time.time()

    def fail(self):
        self._check_success_timeout()
        self.number_of_retries = min(self.number_of_retries + 1,
                                     self.maximum_retries)
        self.last_attempt_time = time.time()

    def _check_success_timeout(self):
        if (self.timeout_success_equivalent is not None
            and self.last_attempt_time != 0
            and time.time() - self.last_attempt_time > self.timeout_success_equivalent):
            self.number_of_retries = 0

class RandomExponentialBackoff(CountingBackoff):
    def fail(self):
        super(RandomExponentialBackoff, self).fail()
        # Exponential growth with ratio sqrt(2); compute random delay
        # between x and 2x where x is growing exponentially
        delay_scale = int(2 ** (self.number_of_retries / 2.0 - 1)) + 1
        delay = delay_scale + random.randint(1, delay_scale)
        message = "Sleeping for %ss [max %s] before retrying." % (delay, delay_scale * 2)
        try:
            logger.warning(message)
        except NameError:
            print(message)
        time.sleep(delay)

def _default_client():
    return "ZulipPython/" + __version__

def generate_option_group(parser, prefix=''):
    group = optparse.OptionGroup(parser, 'Zulip API configuration')
    group.add_option('--%ssite' % (prefix,),
                     dest="zulip_site",
                     help="Zulip server URI",
                     default=None)
    group.add_option('--%sapi-key' % (prefix,),
                     dest="zulip_api_key",
                     action='store')
    group.add_option('--%suser' % (prefix,),
                     dest='zulip_email',
                     help='Email address of the calling bot or user.')
    group.add_option('--%sconfig-file' % (prefix,),
                     action='store',
                     dest="zulip_config_file",
                     help='Location of an ini file containing the\nabove information. (default ~/.zuliprc)')
    group.add_option('-v', '--verbose',
                     action='store_true',
                     help='Provide detailed output.')
    group.add_option('--%sclient' % (prefix,),
                     action='store',
                     default=None,
                     dest="zulip_client",
                     help=optparse.SUPPRESS_HELP)
    group.add_option('--insecure',
                     action='store_true',
                     dest='insecure',
                     help='''Do not verify the server certificate.
                          The https connection will not be secure.''')
    group.add_option('--cert-bundle',
                     action='store',
                     dest='cert_bundle',
                     help='''Specify a file containing either the
                          server certificate, or a set of trusted
                          CA certificates. This will be used to
                          verify the server's identity. All
                          certificates should be PEM encoded.''')
    group.add_option('--client-cert',
                     action='store',
                     dest='client_cert',
                     help='''Specify a file containing a client
                          certificate (not needed for most deployments).''')
    group.add_option('--client-cert-key',
                     action='store',
                     dest='client_cert_key',
                     help='''Specify a file containing the client
                          certificate's key (if it is in a separate
                          file).''')
    return group

def init_from_options(options, client=None):
    if options.zulip_client is not None:
        client = options.zulip_client
    elif client is None:
        client = _default_client()
    return Client(email=options.zulip_email, api_key=options.zulip_api_key,
                  config_file=options.zulip_config_file, verbose=options.verbose,
                  site=options.zulip_site, client=client,
                  cert_bundle=options.cert_bundle, insecure=options.insecure,
                  client_cert=options.client_cert,
                  client_cert_key=options.client_cert_key)

def get_default_config_filename():
    config_file = os.path.join(os.environ["HOME"], ".zuliprc")
    if (not os.path.exists(config_file) and
        os.path.exists(os.path.join(os.environ["HOME"], ".humbugrc"))):
        raise RuntimeError("The Zulip API configuration file is now ~/.zuliprc; please run:\n\n"
                           "  mv ~/.humbugrc ~/.zuliprc\n")
    return config_file

class Client(object):
    def __init__(self, email=None, api_key=None, config_file=None,
                 verbose=False, retry_on_errors=True,
                 site=None, client=None,
                 cert_bundle=None, insecure=None,
                 client_cert=None, client_cert_key=None):
        if client is None:
            client = _default_client()

        if config_file is None:
            config_file = get_default_config_filename()
        if os.path.exists(config_file):
            config = SafeConfigParser()
            with open(config_file, 'r') as f:
                config.readfp(f, config_file)
            if api_key is None:
                api_key = config.get("api", "key")
            if email is None:
                email = config.get("api", "email")
            if site is None and config.has_option("api", "site"):
                site = config.get("api", "site")
            if client_cert is None and config.has_option("api", "client_cert"):
                client_cert = config.get("api", "client_cert")
            if client_cert_key is None and config.has_option("api", "client_cert_key"):
                client_cert_key = config.get("api", "client_cert_key")
            if cert_bundle is None and config.has_option("api", "cert_bundle"):
                cert_bundle = config.get("api", "cert_bundle")
            if insecure is None and config.has_option("api", "insecure"):
                # Be quite strict about what is accepted so that users don't
                # disable security unintentionally.
                insecure_setting = config.get("api", "insecure").lower()
                if insecure_setting == "true":
                    insecure = True
                elif insecure_setting == "false":
                    insecure = False
                else:
                    raise RuntimeError("insecure is set to '%s', it must be 'true' or 'false' if it is used in %s"
                                       % (insecure_setting, config_file))
        elif None in (api_key, email):
            raise RuntimeError("api_key or email not specified and %s does not exist"
                               % (config_file,))

        self.api_key = api_key
        self.email = email
        self.verbose = verbose
        if site is not None:
            if not site.startswith("http"):
                site = "https://" + site
            # Remove trailing "/"s from site to simplify the below logic for adding "/api"
            site = site.rstrip("/")
            self.base_url = site
        else:
            self.base_url = "https://api.zulip.com"

        if self.base_url != "https://api.zulip.com" and not self.base_url.endswith("/api"):
            self.base_url += "/api"
        self.base_url += "/"
        self.retry_on_errors = retry_on_errors
        self.client_name = client

        if insecure:
            self.tls_verification=False
        elif cert_bundle is not None:
            if not os.path.isfile(cert_bundle):
                raise RuntimeError("tls bundle '%s' does not exist"
                                   %(cert_bundle,))
            self.tls_verification=cert_bundle
        else:
            # Default behavior: verify against system CA certificates
            self.tls_verification=True

        if client_cert is None:
            if client_cert_key is not None:
                raise RuntimeError("client cert key '%s' specified, but no client cert public part provided"
                                   %(client_cert_key,))
        else: # we have a client cert
            if not os.path.isfile(client_cert):
                raise RuntimeError("client cert '%s' does not exist"
                                   %(client_cert,))
            if client_cert_key is not None:
                if not os.path.isfile(client_cert_key):
                    raise RuntimeError("client cert key '%s' does not exist"
                                       %(client_cert_key,))
        self.client_cert = client_cert
        self.client_cert_key = client_cert_key

    def get_user_agent(self):
        vendor = ''
        vendor_version = ''
        try:
            vendor = platform.system()
            vendor_version = platform.release()
        except IOError:
            # If the calling process is handling SIGCHLD, platform.system() can
            # fail with an IOError.  See http://bugs.python.org/issue9127
            pass

        if vendor == "Linux":
            vendor, vendor_version, dummy = platform.linux_distribution()
        elif vendor == "Windows":
            vendor_version = platform.win32_ver()[1]
        elif vendor == "Darwin":
            vendor_version = platform.mac_ver()[0]

        return "{client_name} ({vendor}; {vendor_version})".format(
                client_name=self.client_name,
                vendor=vendor,
                vendor_version=vendor_version,
                )

    def do_api_query(self, orig_request, url, method="POST", longpolling = False):
        request = {}

        for (key, val) in six.iteritems(orig_request):
            if isinstance(val, str) or isinstance(val, six.text_type):
                request[key] = val
            else:
                request[key] = simplejson.dumps(val)

        query_state = {
            'had_error_retry': False,
            'request': request,
            'failures': 0,
        } # type: Dict[str, Any]

        def error_retry(error_string):
            if not self.retry_on_errors or query_state["failures"] >= 10:
                return False
            if self.verbose:
                if not query_state["had_error_retry"]:
                    sys.stdout.write("zulip API(%s): connection error%s -- retrying." % \
                            (url.split(API_VERSTRING, 2)[0], error_string,))
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
                    print("Success!")
                else:
                    print("Failed!")

        while True:
            try:
                if method == "GET":
                    kwarg = "params"
                else:
                    kwarg = "data"
                kwargs = {kwarg: query_state["request"]}

                # Build a client cert object for requests
                if self.client_cert_key is not None:
                    client_cert = (self.client_cert, self.client_cert_key)
                else:
                    client_cert = self.client_cert

                res = requests.request(
                        method,
                        urllib.parse.urljoin(self.base_url, url),
                        auth=requests.auth.HTTPBasicAuth(self.email,
                                                         self.api_key),
                        verify=self.tls_verification,
                        cert=client_cert,
                        timeout=90,
                        headers={"User-agent": self.get_user_agent()},
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

            try:
                if requests_json_is_function:
                    json_result = res.json()
                else:
                    json_result = res.json
            except Exception:
                json_result = None

            if json_result is not None:
                end_error_retry(True)
                return json_result
            end_error_retry(False)
            return {'msg': "Unexpected error from the server", "result": "http-error",
                    "status_code": res.status_code}

    @classmethod
    def _register(cls, name, url=None, make_request=None,
                  method="POST", computed_url=None, **query_kwargs):
        if url is None:
            url = name
        if make_request is None:
            def make_request(request=None):
                if request is None:
                    request = {}
                return request
        def call(self, *args, **kwargs):
            request = make_request(*args, **kwargs)
            if computed_url is not None:
                req_url = computed_url(request)
            else:
                req_url = url
            return self.do_api_query(request, API_VERSTRING + req_url, method=method, **query_kwargs)
        call.__name__ = name
        setattr(cls, name, call)

    def call_on_each_event(self, callback, event_types=None, narrow=None):
        if narrow is None:
            narrow = []
        def do_register():
            while True:
                if event_types is None:
                    res = self.register()
                else:
                    res = self.register(event_types=event_types, narrow=narrow)

                if 'error' in res.get('result'):
                    if self.verbose:
                        print("Server returned error:\n%s" % res['msg'])
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
                        print("HTTP error fetching events -- probably a server restart")
                elif res["result"] == "connection-error":
                    if self.verbose:
                        print("Connection error fetching events -- probably server is temporarily down?")
                else:
                    if self.verbose:
                        print("Server returned error:\n%s" % res["msg"])
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

def _mk_subs(streams, **kwargs):
    result = kwargs
    result['subscriptions'] = streams
    return result

def _mk_rm_subs(streams):
    return {'delete': streams}

def _mk_deregister(queue_id):
    return {'queue_id': queue_id}

def _mk_events(event_types=None, narrow=None):
    if event_types is None:
        return dict()
    if narrow is None:
        narrow = []
    return dict(event_types=event_types, narrow=narrow)

def _kwargs_to_dict(**kwargs):
    return kwargs

class ZulipStream(object):
    """
    A Zulip stream-like object
    """

    def __init__(self, type, to, subject, **kwargs):
        self.client = Client(**kwargs)
        self.type = type
        self.to = to
        self.subject = subject

    def write(self, content):
        message = {"type": self.type,
                   "to": self.to,
                   "subject": self.subject,
                   "content": content}
        self.client.send_message(message)

    def flush(self):
        pass

Client._register('send_message', url='messages', make_request=(lambda request: request))
Client._register('update_message', method='PATCH', url='messages', make_request=(lambda request: request))
Client._register('get_messages', method='GET', url='messages/latest', longpolling=True)
Client._register('get_events', url='events', method='GET', longpolling=True, make_request=(lambda **kwargs: kwargs))
Client._register('register', make_request=_mk_events)
Client._register('export', method='GET', url='export')
Client._register('deregister', url="events", method="DELETE", make_request=_mk_deregister)
Client._register('get_profile', method='GET', url='users/me')
Client._register('get_streams', method='GET', url='streams', make_request=_kwargs_to_dict)
Client._register('get_members', method='GET', url='users')
Client._register('list_subscriptions', method='GET', url='users/me/subscriptions')
Client._register('add_subscriptions', url='users/me/subscriptions', make_request=_mk_subs)
Client._register('remove_subscriptions', method='PATCH', url='users/me/subscriptions', make_request=_mk_rm_subs)
Client._register('get_subscribers', method='GET',
                 computed_url=lambda request: 'streams/%s/members' % (urllib.parse.quote(request['stream'], safe=''),),
                 make_request=_kwargs_to_dict)
Client._register('render_message', method='GET', url='messages/render')
Client._register('create_user', method='POST', url='users')
