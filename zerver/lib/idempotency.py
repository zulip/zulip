# See https://zulip.com/api/http-headers#the-idempotency-key-request-header
# for the API documentation of this feature.
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, TypedDict, TypeVar

from django.db import OperationalError, transaction
from django.http import HttpRequest
from psycopg2.errors import LockNotAvailable
from typing_extensions import override

from zerver.lib.exceptions import (
    IdempotencyKeyInUseError,
    InvalidIdempotencyKeyError,
    JsonableError,
)
from zerver.models import IdempotentRequest, UserProfile

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

ValidatedT = TypeVar("ValidatedT")
ResultT = TypeVar("ResultT", bound="DataclassInstance")


class CachedErrorDict(TypedDict):
    http_status_code: int
    msg: str
    data: dict[str, object]


class CachedError(JsonableError):
    def __init__(self, cached_error: CachedErrorDict) -> None:
        super().__init__(cached_error["msg"])
        self.http_status_code = cached_error["http_status_code"]
        self.cached_data = cached_error["data"]

    @property
    @override
    def data(self) -> dict[str, object]:
        return self.cached_data


def get_or_create_idempotent_request(
    request: HttpRequest, user_profile: UserProfile
) -> IdempotentRequest | None:
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is None:
        return None

    # The IETF draft for this header requires the value to be in
    # double quotes, like "8e03978e-40d5-43e8-bc93-6894a57f9324".
    unquoted_idempotency_key = idempotency_key
    if idempotency_key.startswith('"') and idempotency_key.endswith('"'):
        unquoted_idempotency_key = idempotency_key[1:-1]

    # uuid.UUID also accepts forms like {...} or a urn:uuid: prefix,
    # which aren't part of the API.
    if not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        unquoted_idempotency_key,
    ):
        raise InvalidIdempotencyKeyError(idempotency_key)

    idempotent_request, _ = IdempotentRequest.objects.get_or_create(
        realm_id=user_profile.realm_id,
        user=user_profile,
        idempotency_key=uuid.UUID(unquoted_idempotency_key),
    )
    return idempotent_request


def get_cached_result(
    idempotent_request: IdempotentRequest | None, result_class: type[ResultT]
) -> ResultT | None:
    """Returns the result of an earlier request with the same key, or
    raises its error. Returns None if no such request has finished.
    """
    if idempotent_request is None:
        return None
    if idempotent_request.cached_error is not None:
        raise CachedError(idempotent_request.cached_error)
    if idempotent_request.cached_result is None:
        return None
    return result_class(**idempotent_request.cached_result)


def cache_error(
    idempotent_request: IdempotentRequest, result_class: type[ResultT], error: JsonableError
) -> ResultT:
    """Saves the error as the outcome of the request, if its row still
    exists, and raises it. If a concurrent request with the same key
    finished first, returns its result or raises its error instead.

    The UPDATE waits while a concurrent request with the same key holds
    the row's lock, so that request's outcome wins if it saves one.
    """
    saved = IdempotentRequest.objects.filter(
        id=idempotent_request.id, cached_result__isnull=True, cached_error__isnull=True
    ).update(
        cached_error=CachedErrorDict(
            http_status_code=error.http_status_code, msg=error.msg, data=error.data
        )
    )
    if not saved:
        cached_result = get_cached_result(
            IdempotentRequest.objects.filter(id=idempotent_request.id).first(), result_class
        )
        if cached_result is not None:
            return cached_result
    raise error


def run_with_lock(
    idempotent_request: IdempotentRequest,
    result_class: type[ResultT],
    do_work: Callable[[], ResultT],
) -> ResultT:
    with transaction.atomic(durable=True):
        try:
            # The cron job may have deleted the row since the view
            # fetched it.
            locked_request, _ = IdempotentRequest.objects.select_for_update(
                nowait=True, no_key=True
            ).get_or_create(
                realm_id=idempotent_request.realm_id,
                user_id=idempotent_request.user_id,
                idempotency_key=idempotent_request.idempotency_key,
            )
        except OperationalError as error:
            if isinstance(error.__cause__, LockNotAvailable):
                raise IdempotencyKeyInUseError
            raise  # nocoverage

        # A concurrent request with the same key may have finished
        # after the view fetched the row.
        cached_result = get_cached_result(locked_request, result_class)
        if cached_result is not None:
            return cached_result

        result = do_work()
        locked_request.cached_result = asdict(result)
        locked_request.save(update_fields=["cached_result"])
        return result


def run_idempotently(
    idempotent_request: IdempotentRequest | None,
    result_class: type[ResultT],
    validate: Callable[[], ValidatedT],
    do_work: Callable[[ValidatedT], ResultT],
) -> ResultT:
    """Returns do_work(validate()), and saves its result, or a 4xx error
    from either function, as the outcome of the request.

    If a request with the same key has finished, returns its result or
    raises its error instead, without calling do_work. validate isn't
    called either if that request had finished when idempotent_request
    was fetched.

    do_work runs in a transaction that locks the request's row, so that
    a concurrent request with the same key can get
    IdempotencyKeyInUseError.
    """
    if idempotent_request is None:
        return do_work(validate())

    cached_result = get_cached_result(idempotent_request, result_class)
    if cached_result is not None:
        return cached_result

    try:
        validated = validate()
        return run_with_lock(idempotent_request, result_class, lambda: do_work(validated))
    except (CachedError, IdempotencyKeyInUseError):
        # These come from other requests with the same key.
        raise
    except JsonableError as error:
        if error.http_status_code >= 500:
            raise
        return cache_error(idempotent_request, result_class, error)
