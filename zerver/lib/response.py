from __future__ import absolute_import

from django.http import HttpResponse, HttpResponseNotAllowed
import ujson

from typing import Optional, Any, Dict, List
from six import text_type


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self, realm):
        # type (text_type) -> None
        HttpResponse.__init__(self)
        self["WWW-Authenticate"] = 'Basic realm="%s"' % (realm,)

def json_unauthorized(message):
    # type: (text_type) -> text_type
    resp = HttpResponseUnauthorized("zulip")
    resp.content = ujson.dumps({"result": "error",
                                "msg": message}) + "\n"
    return resp

def json_method_not_allowed(methods):
    # type: (List[text_type]) -> text_type
    resp = HttpResponseNotAllowed(methods)
    resp.content = ujson.dumps({"result": "error",
        "msg": "Method Not Allowed",
        "allowed_methods": methods})
    return resp

def json_response(res_type="success", msg="", data=None, status=200):
    # type: (text_type, text_type, Optional[Dict[str, Any]], int) -> HttpResponse
    content = {"result": res_type, "msg": msg}
    if data is not None:
        content.update(data)
    return HttpResponse(content=ujson.dumps(content) + "\n",
                        content_type='application/json', status=status)

def json_success(data=None):
    # type: (Optional[Dict[str, Any]]) -> HttpResponse
    return json_response(data=data)

def json_error(msg, data=None, status=400):
    # type: (str, Optional[Dict[str, Any]], int) -> HttpResponse
    return json_response(res_type="error", msg=msg, data=data, status=status)

def json_unhandled_exception():
    # type: () -> HttpResponse
    return json_response(res_type="error", msg="Internal server error", status=500)
