from collections.abc import Iterator, Mapping
from typing import Any

import orjson
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from typing_extensions import override

from zerver.lib.exceptions import JsonableError, UnauthorizedError


class MutableJsonResponse(HttpResponse):
    def __init__(
        self,
        data: dict[str, Any],
        *,
        content_type: str,
        status: int,
        exception: Exception | None = None,
    ) -> None:
        # Mirror the behavior of Django's TemplateResponse and pass an
        # empty string for the initial content value. Because that will
        # set _needs_serialization to False, we initialize it to True
        # after the call to super __init__.
        super().__init__("", content_type=content_type, status=status)
        self._data = data
        self._needs_serialization = True
        self.exception = exception

    def get_data(self) -> dict[str, Any]:
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
    @override  # type: ignore[explicit-override] # https://github.com/python/mypy/issues/15900
    @property
    def content(self) -> Any:
        """Get content for the response. If the content hasn't been
        overridden by the property setter, it will be the response data
        serialized lazily to JSON."""
        if self._needs_serialization:
            # Because we don't pass a default handler, OPT_PASSTHROUGH_DATETIME
            # actually causes orjson to raise a TypeError on datetime objects. This
            # helps us avoid relying on the particular serialization used by orjs
