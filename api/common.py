#!/usr/bin/python
import simplejson
import requests
import time
import traceback

# Check that we have a recent enough version
assert(requests.__version__ > '0.12')

class HumbugAPI():
    def __init__(self, email, api_key, verbose=False, site="https://app.humbughq.com"):
        self.api_key = api_key
        self.email = email
        self.verbose = verbose
        self.base_url = site

    def do_api_query(self, request, url):
        request["email"] = self.email
        request["api-key"] = self.api_key
        while True:
            try:
                res = requests.post(self.base_url + url,
                                    data=request,
                                    verify=True,
                                    auth=requests.auth.HTTPDigestAuth('tabbott',
                                                                      'xxxxxxxxxxxxxxxxx'))
                if res.status_code == requests.codes.service_unavailable:
                    # On 503 errors, try again after a short sleep
                    time.sleep(0.5)
                    continue
            except requests.exceptions.ConnectionError:
                return {'msg': "Connection error:\n%s" % traceback.format_exc(),
                        "result": "connection-error"}
            except Exception:
                # we'll split this out into more cases as we encounter new bugs.
                return {'msg': "Unexpected error:\n%s" % traceback.format_exc(),
                        "result": "unexpected-error"}

            if res.json is not None:
                return res.json
            return {'msg': res.text, "result": "http-error",
                    "status_code": res.status_code}

    def send_message(self, request):
        return self.do_api_query(request, "/api/v1/send_message")

    def get_messages(self, request = {}):
        return self.do_api_query(request, "/api/v1/get_messages")

    def get_public_streams(self, request = {}):
        return self.do_api_query(request, "/api/v1/get_public_streams")

    def get_subscriptions(self, request = {}):
        return self.do_api_query(request, "/api/v1/get_subscriptions")

    def subscribe(self, streams):
        request = {}
        request["streams"] = simplejson.dumps(streams)
        return self.do_api_query(request, "/api/v1/subscribe")

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
                        print "Unexpected error -- probably a server restart"
                    elif res["result"] == "connection-error":
                        print "Connection error -- probably server is temporarily down?"
                    else:
                        print "Server returned error:\n%s" % res["msg"]
                # TODO: Make this back off once it's more reliable
                time.sleep(1)
                continue
            for message in sorted(res['messages'], key=lambda x: int(x["id"])):
                max_message_id = max(max_message_id, int(message["id"]))
                callback(message)
