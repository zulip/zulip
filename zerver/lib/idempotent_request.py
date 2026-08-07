import uuid
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

from django.db import transaction
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse
from psycopg2.errors import LockNotAvailable

from zerver.lib import exceptions
from zerver.lib.exceptions import InvalidIdempotencyKeyError
from zerver.models import IdempotentRequest, UserProfile

# See https://zulip.readthedocs.io/en/latest/subsystems/idempotency.html
# for documentation on this subsystem.

# See https://zulip.com/api/http-headers#the-idempotency-key-request-header
# for API documentation.

WorkReturnT = TypeVar("WorkReturnT")
ParamT = ParamSpec("ParamT")


idempotency_context: ContextVar[str | None] = ContextVar("idempotency_context", default=None)


def idempotent_work(
    *,
    transactional: bool = True,
    durable: bool = False,
    savepoint: bool = True,
    cached_result_serializer: Callable[[Any], dict[str, Any]],
    cached_result_deserializer: Callable[[dict[str, Any]], Any],
) -> Callable[[Callable[ParamT, WorkReturnT]], Callable[ParamT, WorkReturnT]]:
    """This what ensures idempotency for the actual work (e.g.,
    do_send_messages) and controls the start and the end of its
    transaction.

    This decorator decorates the function (doing the work) that is
    called, within the scope of an endpoint/view decorated with
    @idempotent_endpoint.

    That decorated function is still expected to be called without
    being idempotent if called:
    1. outside the scope of @idempotent_endpoint.
    2. inside the scope but idempotency_key is None.

    In case of being idempotent, that decorated function must receive
    acting_user as kwargs.

    For idempotency, we have 3 cases:
    1. New work (succeeded=None) -- proceed with the work and cache
    the result.
    2. Duplicate succeeded work (succeeded=True) -- immediately return
    the cached result.
    3. Not implemented yet: Duplicate failed work (succeeded=False)

    Will raise LockedError if another request with the same
    idempotency_key is concurrently in progress.
    """

    def idempotency_decorator(
        do_work: Callable[ParamT, WorkReturnT],
    ) -> Callable[ParamT, WorkReturnT]:
        @wraps(do_work)
        def wrapper(*args: ParamT.args, **kwargs: ParamT.kwargs) -> WorkReturnT:
            # Cast kwargs to a dict to access its values like a normal dict and keep mypy happy.
            # **kwargs (without ParamSpec) is already treated as dict in python anyway.
            _kwargs = cast(dict[str, Any], kwargs)
            acting_user = _kwargs.get("acting_user")
            idempotency_key = idempotency_context.get()

            # idempotency_key is NOT mandatory, so we proceed with
            # doing the work normally if it's omitted, which is these cases:
            # 1- API call from client omitting the Idempotency-Key header.
            # 2- Internal callers directly calling the decorated function.
            if idempotency_key is None:
                # We wrap the work in a transaction only if it was already meant to be inside one.
                if transactional is True:
                    with transaction.atomic(durable=durable, savepoint=savepoint):
                        return do_work(*args, **kwargs)

                # This case isn't covered by tests because idempotency
                # system is currently only applied to do_send_messages
                # (which is inside a transaction), so we don't have
                # non-transactional work to test.
                return do_work(*args, **kwargs)  # nocoverage

            # In case of applying idempotency, the work must be inside a transaction.
            assert transactional is True
            assert acting_user is not None

            with transaction.atomic(durable=durable, savepoint=savepoint):
                try:
                    # Select the matching row from idempotency table
                    # and apply a row-lock on it during the whole transaction,
                    # but abort (nowait=True) if another concurrent transaction
                    # is already holding a lock.
                    idempotent_request = (
                        IdempotentRequest.objects.select_for_update(nowait=True, no_key=True)
                        .values("succeeded", "cached_result")
                        .get(
                            realm_id=acting_user.realm_id,
                            user_id=acting_user.id,
                            idempotency_key=idempotency_key,
                        )
                    )

                except IdempotentRequest.DoesNotExist:  # nocoverage
                    # The above try block is ONLY reachable in case @idempotent_work
                    # was called within the scope of @idempotent_endpoint which sets
                    # the key in the contextvar. Therefore, this exception should
                    # never occur, but it's better to be explicit and include the most
                    # probable cause for this exception for debugging clarity
                    # and to catch unintentional future changes.
                    raise AssertionError(
                        f"No matching row found for idempotency_key: {idempotency_key}, idempotency_key maybe leaked."
                    )

                # Row is locked by another concurrent request doing the work.
                except OperationalError as error:  # nocoverage
                    if isinstance(error.__cause__, LockNotAvailable):
                        raise exceptions.LockedError
                    raise

                else:
                    # Duplicate succeeded work.
                    if idempotent_request["succeeded"] is True:
                        return cached_result_deserializer(
                            cast(dict[str, Any], idempotent_request["cached_result"])
                        )

                    # TODO: In the future, if we decide to cache error,
                    # we should return the cached error response for
                    # the previous request here.
                    if idempotent_request["succeeded"] is False:  # nocoverage
                        pass

                    # New work.
                    result = do_work(*args, **kwargs)
                    # Work has succeeded, cache its result.
                    IdempotentRequest.objects.filter(
                        realm_id=acting_user.realm_id,
                        user_id=acting_user.id,
                        idempotency_key=idempotency_key,
                    ).update(succeeded=True, cached_result=cached_result_serializer(result))
                    return result

        return wrapper

    return idempotency_decorator


def idempotent_endpoint(
    view_func: Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, UserProfile, ParamT], HttpResponse]:
    @wraps(view_func)
    def _wrapped_view_func(
        request: HttpRequest,
        user_profile: UserProfile,
        /,
        *args: ParamT.args,
        **kwargs: ParamT.kwargs,
    ) -> HttpResponse:
        """
        The first step in applying idempotency. It decorates
        a non-idempotent view like send_message_backend.

        We insert the idempotency row which initially represents a new
        unattempted work.
        """
        idempotency_key = request.headers.get("Idempotency-Key")

        # Idempotency-Key header is NOT mandatory.
        if idempotency_key is None:
            return view_func(request, user_profile, *args, **kwargs)

        # Ensure Idempotency-Key is a valid UUID.
        try:
            uuid.UUID(idempotency_key)
        except ValueError:
            # Tested by checking the response in test_invalid_idempotency_key.
            raise InvalidIdempotencyKeyError(idempotency_key)  # nocoverage

        idempotency_token = idempotency_context.set(idempotency_key)
        # Insert a row, initially representing a work that's not yet attempted.
        # We must expect an already existing row in case of duplicate requests,
        # so we use bulk_create() that offers ignore_conflicts.
        IdempotentRequest.objects.bulk_create(
            [
                IdempotentRequest(
                    realm_id=user_profile.realm_id,
                    user_id=user_profile.id,
                    idempotency_key=idempotency_key,
                )
            ],
            ignore_conflicts=True,
        )

        try:
            # Do the actual non-idempotent work.
            return view_func(request, user_profile, *args, **kwargs)

        finally:
            # Ensure idempotency_key doesn't leak across requests.
            idempotency_context.reset(idempotency_token)

    return _wrapped_view_func
