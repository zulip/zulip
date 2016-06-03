from __future__ import absolute_import
from typing import Any

from django.http import HttpResponse, HttpResponseNotAllowed
import ujson

class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self, realm):
        HttpResponse.__init__(self)
        self["WWW-Authenticate"] = 'Basic realm="%s"' % (realm,)

def json_unauthorized(message):
    # type: (str) ->  HttpResponseUnauthorized
    resp = HttpResponseUnauthorized("zulip")
    resp.content = ujson.dumps({"result": "error",
                                "msg": message}) + "\n"
    return resp

def json_method_not_allowed(methods):
    # type: (List[str]) ->  HttpResponseNotAllowed
    resp = HttpResponseNotAllowed(methods)
    resp.content = ujson.dumps({"result": "error",
        "msg": "Method Not Allowed",
        "allowed_methods": methods})
    return resp

def json_response(res_type="success", msg="", data={}, status=200):
    # type: (str, str, Dict[Any, Any], int) -> HttpResponse
    content = {"result": res_type, "msg": msg}
    content.update(data)
    return HttpResponse(content=ujson.dumps(content) + "\n",
                        content_type='application/json', status=status)

def json_success(data={}):
    # type: (Dict[Any, Any]) -> HttpResponse
    return json_response(data=data)

def json_error(msg, data={}, status=400):
    # type: (str, Dict[Any, Any], int) -> HttpResponse
    return json_response(res_type="error", msg=msg, data=data, status=status)

def json_unhandled_exception():
    # type: () -> HttpResponse
    return json_response(res_type="error", msg="Internal server error", status=500)
