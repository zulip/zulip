from typing import Any, List, Mapping, Optional

import orjson
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

from zerver.lib.exceptions import JsonableError, UnauthorizedError


def json_unauthorized(
    message: Optional[str] = None, www_authenticate: Optional[str] = None
) -> HttpResponse:
    return json_response_from_error(
        UnauthorizedError(msg=message, www_authenticate=www_authenticate)
    )


def json_method_not_allowed(methods: List[str]) -> HttpResponseNotAllowed:
    resp = HttpResponseNotAllowed(methods)
    resp.content = orjson.dumps(
        {"result": "error", "msg": "Method Not Allowed", "allowed_methods": methods}
    )
    return resp


def json_response(
    res_type: str = "success", msg: str = "", data: Mapping[str, Any] = {}, status: int = 200
) -> HttpResponse:
    content = {"result": res_type, "msg": msg}
    content.update(data)

    # Because we don't pass a default handler, OPT_PASSTHROUGH_DATETIME
    # actually causes orjson to raise a TypeError on datetime objects. This
    # helps us avoid relying on the particular serialization used by orjson.
    return HttpResponse(
        content=orjson.dumps(
            content,
            option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_PASSTHROUGH_DATETIME,
        ),
        content_type="application/json",
        status=status,
    )


def json_success(request: HttpRequest, data: Mapping[str, Any] = {}) -> HttpResponse:
    return json_response(data=data)


def json_response_from_error(exception: JsonableError) -> HttpResponse:
    """
    This should only be needed in middleware; in app code, just raise.

    When app code raises a JsonableError, the JsonErrorHandler
    middleware takes care of transforming it into a response by
    calling this function.
    """
    response = json_response(
        "error", msg=exception.msg, data=exception.data, status=exception.http_status_code
    )

    for header, value in exception.extra_headers.items():
        response[header] = value

    return response


class AsynchronousResponse(HttpResponse):
    """
    This response is just a sentinel to be discarded by Tornado and replaced
    with a real response later; see zulip_finish.
    """

    status_code = 399
