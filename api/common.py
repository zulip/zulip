#!/usr/bin/python
import simplejson
import requests
import time
import traceback

# TODO: Drop verify=False once we have real certificates
# Or switch to specifying a testing cert manually

class HumbugAPI():
    def __init__(self, email, api_key, verbose=False, site="https://app.humbughq.com"):
        self.api_key = api_key
        self.email = email
        self.verbose = verbose
        self.base_url = site

    def send_message(self, submit_hash):
        submit_hash["email"] = self.email
        submit_hash["api-key"] = self.api_key
        try:
            res = requests.post(self.base_url + "/api/v1/send_message",
                                data=submit_hash,
                                verify=False,
                                auth=requests.auth.HTTPDigestAuth('tabbott', 'xxxxxxxxxxxxxxxxx'))
            # TODO: Add some sort of automated retry for certain errors
        except requests.exceptions.ConnectionError:
            return {'msg': "Connection error\n%s" % traceback.format_exc(),
                    "result": "connection-error"}
        if res.json is not None:
            return res.json
        return {'msg': res.text, "result": "unexpected-error",
                "status_code": res.status_code}

    def get_messages(self, options = {}):
        options["email"] = self.email
        options["api-key"] = self.api_key
        try:
            res = requests.post(self.base_url + "/api/v1/get_messages",
                                data=options,
                                verify=False,
                                auth=requests.auth.HTTPDigestAuth('tabbott', 'xxxxxxxxxxxxxxxxx'))
        except requests.exceptions.ConnectionError:
            return {'msg': "Connection error\n%s" % traceback.format_exc(),
                    "result": "connection-error"}
        if res.json is not None:
            return res.json
        return {'msg': res.text, "result": "unexpected-error",
                "status_code": res.status_code}

    def call_on_each_message(self, callback, options = {}):
        max_message_id = None
        while True:
            if max_message_id is not None:
                options["first"] = "0"
                options["last"] = str(max_message_id)
            res = self.get_messages(options)
            if 'error' in res.get('result'):
                if self.verbose:
                    if res["result"] == "unexpected-error":
                        print "Unexpected error -- probably a server restart"
                    elif res["result"] == "connection-error":
                        print "Connection error -- probably server is down?"
                    else:
                        print "Server returned error:\n%s" % res["msg"]
                # TODO: Make this back off once it's more reliable
                time.sleep(1)
                continue
            for message in sorted(res['messages'], key=lambda x: x["id"]):
                max_message_id = max(max_message_id, message["id"])
                callback(message)
