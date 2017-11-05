
from django.http import HttpResponse, HttpResponseNotAllowed
import ujson

from typing import Optional, Any, Dict, List, Text
from zerver.lib.exceptions import JsonableError

class HttpResponseUnauthorized(HttpResponse):
    status_code = 401

    def __init__(self, realm: Text, www_authenticate: Optional[Text]=None) -> None:
        HttpResponse.__init__(self)
        if www_authenticate is None:
            self["WWW-Authenticate"] = 'Basic realm="%s"' % (realm,)
        elif www_authenticate == "session":
            self["WWW-Authenticate"] = 'Session realm="%s"' % (realm,)
        else:
            raise AssertionError("Invalid www_authenticate value!")

def json_unauthorized(message: Text, www_authenticate: Optional[Text]=None) -> HttpResponse:
    resp = HttpResponseUnauthorized("zulip", www_authenticate=www_authenticate)
    resp.content = (ujson.dumps({"result": "error",
                                 "msg": message}) + "\n").encode()
    return resp

def json_method_not_allowed(methods: List[Text]) -> HttpResponseNotAllowed:
    resp = HttpResponseNotAllowed(methods)
    resp.content = ujson.dumps({"result": "error",
                                "msg": "Method Not Allowed",
                                "allowed_methods": methods}).encode()
    return resp

def json_response(res_type: Text="success",
                  msg: Text="",
                  data: Optional[Dict[str, Any]]=None,
                  status: int=200) -> HttpResponse:
    content = {"result": res_type, "msg": msg}
    if data is not None:
        content.update(data)
    return HttpResponse(content=ujson.dumps(content) + "\n",
                        content_type='application/json', status=status)

def json_success(data: Optional[Dict[str, Any]]=None) -> HttpResponse:
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

def json_error(msg: Text, data: Optional[Dict[str, Any]]=None, status: int=400) -> HttpResponse:
    return json_response(res_type="error", msg=msg, data=data, status=status)
