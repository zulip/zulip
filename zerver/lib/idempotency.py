# See https://zulip.com/api/http-headers#the-idempotency-key-request-header
# for the API documentation of this feature.
import uuid
from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, TypeVar

from django.db import OperationalError, transaction
from django.http import HttpRequest
from psycopg2.errors import LockNotAvailable

from zerver.lib.exceptions import IdempotencyKeyInUseError, InvalidIdempotencyKeyError
from zerver.models import IdempotentRequest, UserProfile

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

ResultT = TypeVar("ResultT", bound="DataclassInstance")


def get_or_create_idempotent_request(
    request: HttpRequest, user_profile: UserProfile
) -> IdempotentRequest | None:
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key is None:
        return None

    try:
        parsed_idempotency_key = uuid.UUID(idempotency_key)
    except ValueError:
        raise InvalidIdempotencyKeyError(idempotency_key)

    idempotent_request, _ = IdempotentRequest.objects.get_or_create(
        realm_id=user_profile.realm_id,
        user=user_profile,
        idempotency_key=parsed_idempotency_key,
    )
    return idempotent_request


def get_cached_result(
    idempotent_request: IdempotentRequest | None, result_class: type[ResultT]
) -> ResultT | None:
    if idempotent_request is None or idempotent_request.cached_result is None:
        return None
    return result_class(**idempotent_request.cached_result)


def run_idempotently(
    idempotent_request: IdempotentRequest | None,
    result_class: type[ResultT],
    do_work: Callable[[], ResultT],
) -> ResultT:
    if idempotent_request is None:
        return do_work()

    with transaction.atomic(savepoint=False):
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

        # A concurrent request with the same key may have succeeded
        # after the view fetched the row.
        cached_result = get_cached_result(locked_request, result_class)
        if cached_result is not None:
            return cached_result

        result = do_work()
        locked_request.cached_result = asdict(result)
        locked_request.save(update_fields=["cached_result"])
        return result
