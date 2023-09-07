from typing import Any, Dict, Iterator, List, Mapping, Optional

import orjson
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

from zerver.lib.exceptions import JsonableError, UnauthorizedError


class MutableJsonResponse(HttpResponse):
    def __init__(
        self,
        data: Dict[str, Any],
        *,
        content_type: str,
        status: int,
    ) -> None:
        # Mirror the behavior of Django's TemplateResponse and pass an
        # empty string for the initial content value. Because that will
        # set _needs_serialization to False, we initialize it to True
        # after the call to super __init__.
        super().__init__("", content_type=content_type, status=status)
        self._data = data
        self._needs_serialization = True

    def get_data(self) -> Dict[str, Any]:
        """Get data for this MutableJsonResponse. Calling this method
        after the response's content has already been serialized
        will mean the next time the response's content is accessed
        it will be reserialized because the caller may have mutated
        the data."""
        self._needs_serialization = True
        return self._data

    # This always returns bytes, but in Django's HttpResponse the return
    # value can be bytes, an iterable of bytes or some other object. Any
    # is used here to encompass all of those return values.
    # See https://github.com/typeddjango/django-stubs/commit/799b41fe47cfe2e56be33eee8cfbaf89a9853a8e
    # and https://github.com/python/mypy/issues/3004.
    @property
    def content(self) -> Any:
        """Get content for the response. If the content hasn't been
        overridden by the property setter, it will be the response data
        serialized lazily to JSON."""
        if self._needs_serialization:
            # Because we don't pass a default handler, OPT_PASSTHROUGH_DATETIME
            # actually causes orjson to raise a TypeError on datetime objects. This
            # helps us avoid relying on the particular serialization used by orjson.
            self.content = orjson.dumps(
                self._data,
                option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_PASSTHROUGH_DATETIME,
            )
        return super().content

    # There are two ways this might be called. The first is in the getter when
    # the response data is being serialized into JSON. The second is when it
    # is called from some other part of the code. This happens for instance in
    # the parent class constructor. In this case, the new content overrides the
    # serialized JSON.
    @content.setter
    def content(self, value: Any) -> None:
        """Set the content for the response."""
        assert isinstance(HttpResponse.content, property)
        assert HttpResponse.content.fset is not None
        HttpResponse.content.fset(self, value)
        self._needs_serialization = False

    # The superclass HttpResponse defines an iterator that doesn't access the content
    # property, so in order to not break the implementation of the superclass with
    # our lazy content generation, we override the iterator to access `self.content`
    # through our getter.
    def __iter__(self) -> Iterator[bytes]:
        return iter([self.content])


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
) -> MutableJsonResponse:
    content = {"result": res_type, "msg": msg}
    content.update(data)

    return MutableJsonResponse(
        data=content,
        content_type="application/json",
        status=status,
    )


def json_success(request: HttpRequest, data: Mapping[str, Any] = {}) -> MutableJsonResponse:
    return json_response(data=data)


def json_response_from_error(exception: JsonableError) -> MutableJsonResponse:
    """
    This should only be needed in middleware; in app code, just raise.

    When app code raises a JsonableError, the JsonErrorHandler
    middleware takes care of transforming it into a response by
    calling this function.
    """
    response_type = "error"
    if 200 <= exception.http_status_code < 300:
        response_type = "success"
    response = json_response(
        response_type, msg=exception.msg, data=exception.data, status=exception.http_status_code
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
