from __future__ import absolute_import

from django.http import HttpResponse, HttpResponseNotAllowed
from django.conf import settings
import django.shortcuts
import simplejson

class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self, realm):
        HttpResponse.__init__(self)
        self["WWW-Authenticate"] = 'Basic realm="%s"' % realm

def json_method_not_allowed(methods):
    resp = HttpResponseNotAllowed(methods)
    resp.content = simplejson.dumps({"result": "error",
        "msg": "Method Not Allowed",
        "allowed_methods": methods})
    return resp

def json_response(res_type="success", msg="", data={}, status=200):
    content = {"result": res_type, "msg": msg}
    content.update(data)
    return HttpResponse(content=simplejson.dumps(content),
                        mimetype='application/json', status=status)

def json_success(data={}):
    return json_response(data=data)

def json_error(msg, data={}, status=400):
    return json_response(res_type="error", msg=msg, data=data, status=status)

# We wrap render_to_response so that we can always add some data to
# the template context dictionary.  In particular, we add the
# mixpanel token (which varies based on whether we're deployed or
# not) because the mixpanel code is included in base.html.
def render_to_response(template, *args, **kwargs):
    if args:
        dictionary = args[0]
    else:
        try:
            dictionary = kwargs['dictionary']
        except KeyError:
            dictionary = {}
            kwargs['dictionary'] = dictionary

    dictionary['mixpanel_token'] = settings.MIXPANEL_TOKEN
    return django.shortcuts.render_to_response(template, *args, **kwargs)
