import importlib
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

from django.db import transaction
from django.db.models import Q
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse
from psycopg2.errors import LockNotAvailable

from zerver.lib import exceptions
from zerver.lib.exceptions import InvalidIdempotencyKeyError, JsonableError
from zerver.models import IdempotentRequest, UserProfile

# See https://zulip.readthedocs.io/en/latest/subsystems/idempotency.html
# for documentation on this subsystem.

# See https://zulip.com/api/http-headers#the-idempotency-key-request-header
# for API documentation.

WorkReturnT = TypeVar("WorkReturnT")
ParamT = ParamSpec("ParamT")


idempotency_context: ContextVar[str | None] = ContextVar("idempotency_context", default=None)


def json_error_deserializer(json_error_dict: dict[str, Any]) -> JsonableError:
    """
    Deserialize json_error_dict back into a JsonableError (or any subclass)
    instance.

    Ensure json_error_dict was serialized only through json_error_serializer.
    """
    class_path = json_error_dict.get("__class__")
    state = json_error_dict.get("__state__")

    assert class_path is not None
    assert state is not None

    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    assert issubclass(cls, JsonableError)

    # Create a blank instance, bypassing __init__
    instance = cls.__new__(cls)

    # Re-hydrate the instance's state
    instance.__dict__.update(state)

    return instance


def json_error_serializer(json_error: JsonableError) -> dict[str, Any]:
    """
    Serialize a JsonableError (or any subclass) into a dict.
    """
    cls = json_error.__class__

    return {
        "__class__": f"{cls.__module__}.{cls.__name__}",
        "__state__": json_error.__dict__.copy(),
    }


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
    3. Duplicate failed work (succeeded=False) -- immediately raise
    the cached error (non-transient error).

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
            # 2- Internal functions directly calling the decorated function.
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

                    # Duplicate failed work.
                    # If the actual work failed in the previous request,
                    # we return the cached response for that failure.
                    if idempotent_request["succeeded"] is False:
                        raise json_error_deserializer(
                            cast(dict[str, Any], idempotent_request["cached_result"])
                        )

                    # New work.
                    result = do_work(*args, **kwargs)
                    # Mark the work as succeeded and cache its result.
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
        unattempted work. In the end, after calling the view and
        doing the work we catch any raised json_error and cache it if
        it's non-transient, then mark the work as failed.
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
            return view_func(request, user_profile, *args, **kwargs)
        except JsonableError as json_error:
            # If the error is non-transient (e.g., 4xx),
            # we mark the work as failed and cache the error.
            if (400 <= json_error.http_status_code < 500) and not isinstance(
                json_error, exceptions.LockedError
            ):
                IdempotentRequest.objects.filter(
                    # Never overwrite an already succeeded and committed work.
                    ~Q(succeeded=True),
                    realm_id=user_profile.realm_id,
                    user_id=user_profile.id,
                    idempotency_key=idempotency_key,
                ).update(succeeded=False, cached_result=json_error_serializer(json_error))

            raise

        finally:
            # Ensure idempotency_key doesn't leak across requests.
            idempotency_context.reset(idempotency_token)

    return _wrapped_view_func
