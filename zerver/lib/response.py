from typing import Any, List, Mapping, Optional

import ujson
from django.http import HttpResponse, HttpResponseNotAllowed
from django.utils.translation import ugettext as _

from zerver.lib.exceptions import JsonableError


class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self, realm: str, www_authenticate: Optional[str]=None) -> None:
        HttpResponse.__init__(self)
        if www_authenticate is None:
            self["WWW-Authenticate"] = f'Basic realm="{realm}"'
        elif www_authenticate == "session":
            self["WWW-Authenticate"] = f'Session realm="{realm}"'
        else:
            raise AssertionError("Invalid www_authenticate value!")

def json_unauthorized(message: Optional[str]=None,
                      www_authenticate: Optional[str]=None) -> HttpResponse:
    if message is None:
        message = _("Not logged in: API authentication or user session required")
    resp = HttpResponseUnauthorized("zulip", www_authenticate=www_authenticate)
    resp.content = (ujson.dumps({"result": "error",
                                 "msg": message}) + "\n").encode()
    return resp

def json_method_not_allowed(methods: List[str]) -> HttpResponseNotAllowed:
    resp = HttpResponseNotAllowed(methods)
    resp.content = ujson.dumps({"result": "error",
                                "msg": "Method Not Allowed",
                                "allowed_methods": methods}).encode()
    return resp

def json_response(res_type: str="success",
                  msg: str="",
                  data: Mapping[str, Any]={},
                  status: int=200) -> HttpResponse:
    content = {"result": res_type, "msg": msg}
    content.update(data)
    return HttpResponse(content=ujson.dumps(content) + "\n",
                        content_type='application/json', status=status)

def json_success(data: Mapping[str, Any]={}) -> HttpResponse:
    return json_response(data=data)

def json_response_from_error(exception: JsonableError) -> HttpResponse:
    '''
    This should only be needed in middleware; in app code, just raise.

    When app code raises a JsonableError, the JsonErrorHandler
    middleware takes care of transforming it into a response by
    calling this function.
    '''
    return json_response('error',
                         msg=exception.msg,
                         data=exception.data,
                         status=exception.http_status_code)

def json_error(msg: str, data: Mapping[str, Any]={}, status: int=400) -> HttpResponse:
    return json_response(res_type="error", msg=msg, data=data, status=status)
