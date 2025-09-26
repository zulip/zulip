from collections import defaultdict
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING, Any, Optional, cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse, QueryDict
from django.http.multipartparser import MultiPartParser
from django.utils.translation import gettext as _
from typing_extensions import override

from zerver.lib import rate_limiter
from zerver.lib.exceptions import ErrorCode, JsonableError
from zerver.lib.notes import BaseNotes
from zerver.models import Client, Realm

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemoteZulipServer

if TYPE_CHECKING:
    from django.http.request import _ImmutableQueryDict


@dataclass
class RequestNotes(BaseNotes[HttpRequest, "RequestNotes"]):
    """This class contains extra metadata that Zulip associated with a
    Django HttpRequest object. See the docstring for BaseNotes for
    details on how it works.

    Note that most Optional fields will be definitely not None once
    middleware has run. In the future, we may want to express that in
    the types by having different types EarlyRequestNotes and
    post-middleware RequestNotes types, but for now we have a lot
    of `assert request_notes.foo is not None` when accessing them.
    """

    client: Client | None = None
    client_name: str | None = None
    client_version: str | None = None
    log_data: MutableMapping[str, Any] | None = None
    requester_for_logs: str | None = None
    # We use realm_cached to indicate whether the realm is cached or not.
    # Because the default value of realm is None, which can indicate "unset"
    # and "nonexistence" at the same time.
    realm: Realm | None = None
    has_fetched_realm: bool = False
    set_language: str | None = None
    ratelimits_applied: list[rate_limiter.RateLimitResult] = field(default_factory=list)
    query: str | None = None
    error_format: str | None = None
    saved_response: HttpResponse | None = None
    tornado_handler_id: int | None = None
    processed_parameters: set[str] = field(default_factory=set)
    remote_server: Optional["RemoteZulipServer"] = None
    is_webhook_view: bool = False

    @classmethod
    @override
    def init_notes(cls) -> "RequestNotes":
        return RequestNotes()


class RequestConfusingParamsError(JsonableError):
    code = ErrorCode.REQUEST_CONFUSING_VAR
    data_fields = ["var_name1", "var_name2"]

    def __init__(self, var_name1: str, var_name2: str) -> None:
        self.var_name1: str = var_name1
        self.var_name2: str = var_name2

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Can't decide between '{var_name1}' and '{var_name2}' arguments")


class RequestVariableMissingError(JsonableError):
    code = ErrorCode.REQUEST_VARIABLE_MISSING
    data_fields = ["var_name"]

    def __init__(self, var_name: str) -> None:
        self.var_name: str = var_name

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Missing '{var_name}' argument")


class RequestVariableConversionError(JsonableError):
    code = ErrorCode.REQUEST_VARIABLE_INVALID
    data_fields = ["var_name", "bad_value"]

    def __init__(self, var_name: str, bad_value: Any) -> None:
        self.var_name: str = var_name
        self.bad_value = bad_value

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Bad value for '{var_name}': {bad_value}")


arguments_map: dict[str, list[str]] = defaultdict(list)


def populate_post_data(request: HttpRequest) -> HttpRequest:
    # Only take action if POST is empty.
    if request.content_type == "multipart/form-data":
        POST, files = MultiPartParser(
            request.META,
            BytesIO(request.body),
            request.upload_handlers,
            request.encoding,
        ).parse()
        # request.POST is an immutable QueryDict in most cases, while
        # MultiPartParser.parse() returns a mutable instance of QueryDict.
        # This can be fix when https://code.djangoproject.com/ticket/17235
        # is resolved.
        # django-stubs makes QueryDict of different mutabilities incompatible
        # types. There is no way to acknowledge the django-stubs mypy plugin
        # the change of POST's mutability, so we bypass the check with cast.
        # See also: https://github.com/typeddjango/django-stubs/pull/925#issue-1206399444
        POST._mutable = False
        request.POST = cast("_ImmutableQueryDict", POST)
        request.FILES.update(files)
    elif request.content_type == "application/x-www-form-urlencoded":
        request.POST = QueryDict(request.body, encoding=request.encoding)

    return request
