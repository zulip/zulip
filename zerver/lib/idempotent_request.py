import inspect
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
from zerver.lib.exceptions import InvalidIdempotencyKeyError, JsonableError
from zerver.models import IdempotentRequest, UserProfile

# See https://zulip.com/api/http-headers for documentation and
# the different types of requests this idempotency system handles.

WorkReturnT = TypeVar("WorkReturnT")
ParamT = ParamSpec("ParamT")


idempotency_context: ContextVar[str | None] = ContextVar("idempotency_context", default=None)


def json_error_deserializer(json_error_dict: dict[str, Any]) -> JsonableError:
    """
    Deserialize json_error_dict back to an instance of JsonableError
    or one of its sub-classes.
    """
    # During serialization "cls_name" key is guaranteed
    # to have a string value.
    class_name = cast(str, json_error_dict.get("cls_name"))
    error_cls = getattr(exceptions, class_name)

    # error_cls must be a JsonableError or its sub-class.
    assert issubclass(error_cls, JsonableError)

    json_error_dict.pop("cls_name")
    return error_cls(**json_error_dict)


def json_error_serializer(json_error: JsonableError) -> dict[str, Any]:
    """
    Serialize an instance of JsonableError/Subclass into a dict.
    """
    signature = inspect.signature(type(json_error).__init__)

    # Here, we populate the dict with ONLY the fields
    # that were used to initialize the instance,
    # the rest of the instance fields are constructed internally inside
    # the instance's class definition.
    json_error_dict = {
        name: getattr(json_error, name)
        for name in signature.parameters
        if hasattr(json_error, name)
    }
    json_error_dict["cls_name"] = json_error.__class__.__name__
    return json_error_dict


def idempotent_work(
    *,
    # Is the decorated work originally wrapped in a transaction.
    transactional: bool = True,
    durable: bool = False,
    savepoint: bool = True,
    cached_result_serializer: Callable[[Any], dict[str, Any]],
    cached_result_deserializer: Callable[[dict[str, Any]], Any],
) -> Callable[[Callable[ParamT, WorkReturnT]], Callable[ParamT, WorkReturnT]]:
    """
    This what ensures idempotency for the actual work
    (e.g. do_send_messages) and controls the start and the end of
    its transaction.

    This decorator decorates the function (doing the work) that is called,
    within the scope of an endpoint/view decorated with @idempotent_endpoint.

    That decorated function is still expected to be called without being idempotent
    if called:
    1- outside the scope of @idempotent_endpoint.
    2- inside the scope but idempotency_key is None.

    In case of being idempotent, that decorated function must receive acting_user as kwargs.

    For idempotency, we have 3 cases:
    1. New work (succeeded=None) -- proceed with the work and
    cache the result.
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
                # We wrap the work in a transaction only if it was originally inside one.
                if transactional is True:
                    with transaction.atomic(durable=durable, savepoint=savepoint):
                        return do_work(*args, **kwargs)

                # This case isn't covered by tests because
                # idempotency system is currently only applied to do_send_messages
                # (which is inside a transaction), so we don't have non-transactional work
                # to test.
                return do_work(*args, **kwargs)  # nocoverage

            # In case of applying idempotency, the work must be inside a transaction.
            assert transactional is True
            assert acting_user is not None

            with transaction.atomic(durable=durable, savepoint=savepoint):
                try:
                    # Here, we select the matching row from idempotency table and
                    # apply a row-lock on it during the whole transaction,
                    # but abort if another concurrent transaction is already holding a lock.
                    try:
                        idempotent_request = (
                            IdempotentRequest.objects.select_for_update(nowait=True)
                            .values("succeeded", "cached_result")
                            .get(
                                realm_id=acting_user.realm_id,
                                user_id=acting_user.id,
                                idempotency_key=idempotency_key,
                            )
                        )
                    except IdempotentRequest.DoesNotExist:  # nocoverage
                        # The above try block is ONLY reachable in case @idempotent_work was called
                        # within the scope of @idempotent_endpoint which sets the key in the contextvar.
                        # Therefore, this exception should never occur, but it's better to be explicit and
                        # include the most probable cause for this exception. This is
                        # for debugging clarity and to catch unintentional future changes.
                        raise AssertionError(
                            f"No matching row found for idempotency_key: {idempotency_key}, idempotency_key maybe leaked."
                        )

                    # Duplicate succeeded work.
                    if idempotent_request["succeeded"] is True:
                        # We know cached_result is already json-deserialized.
                        return cached_result_deserializer(
                            cast(dict[str, Any], idempotent_request["cached_result"])
                        )

                    # Duplicate failed work.
                    # If the actual work failed in the previous request,
                    # we return the cachd response for that failure.
                    if idempotent_request["succeeded"] is False:
                        # We know cached_result is already json-deserialized.
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

                # Row is locked by another concurrent request doing the work.
                except OperationalError as error:  # nocoverage
                    if isinstance(error.__cause__, LockNotAvailable):
                        raise exceptions.LockedError
                    raise

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
        The 1st step in applying idempotency.
        Decorates non-idempotent view (e.g. send_message_backend).

        We insert the idempotency row which initially represents
        a new unattempted work.
        In the end and after calling the view (and doing the work)
        we catch any raised json_error and cache it if it's non-transient, then
        mark the work as failed.
        """
        idempotency_key = request.headers.get("Idempotency-Key")

        # Idempotency-Key header is NOT mandatory.
        if idempotency_key is None:
            return view_func(request, user_profile, *args, **kwargs)

        # Ensure Idempotency-Key is a valid UUID.
        try:
            uuid.UUID(idempotency_key)
        except ValueError:
            # This is already tested by checking the response.
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
            # If the error is non-transient (e.g. 4xx),
            # we mark the work as failed and cache the error.
            if (400 <= json_error.http_status_code < 500) and not isinstance(
                json_error, exceptions.LockedError
            ):
                IdempotentRequest.objects.filter(
                    realm_id=user_profile.realm_id,
                    user_id=user_profile.id,
                    idempotency_key=idempotency_key,
                ).update(succeeded=False, cached_result=json_error_serializer(json_error))
            raise
        finally:
            # Ensure idempotency_key doesn't leak across requests.
            idempotency_context.reset(idempotency_token)

    return _wrapped_view_func
