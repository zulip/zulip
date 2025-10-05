import inspect
from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate, ParamSpec, TypeVar, cast

import orjson
from django.db import connection, transaction
from django.db.utils import OperationalError
from django.http import HttpRequest, HttpResponse
from psycopg2.errors import LockNotAvailable
from psycopg2.sql import SQL, Identifier

from zerver.lib import exceptions
from zerver.lib.exceptions import JsonableError
from zerver.models import IdempotentRequest, UserProfile

WorkReturnT = TypeVar("WorkReturnT")
ParamT = ParamSpec("ParamT")


def json_error_deserializer(json_error_dict: dict[str, Any]) -> JsonableError:
    """
    Deserialize json_error_dict back to an instance of JsonableError
    or one of its sub-classes.
    """
    # During serialization "clas_name" key is guaranteed
    # to have a string value.
    class_name = cast(str, json_error_dict.get("cls_name"))
    error_cls = getattr(exceptions, class_name)

    # MUST be a JsonableError or its sub-class.
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


def idempotent_work_transaction(
    durable: bool = False,
    savepoint: bool = True,
    *,
    cached_result_serializer: Callable[[Any], dict[str, Any]],
    cached_result_deserializer: Callable[[dict[str, Any]], Any],
) -> Callable[[Callable[ParamT, WorkReturnT]], Callable[ParamT, WorkReturnT]]:
    """
    CRITICAL: MUST ONLY be used within the scope of an
    endpoint/view decroated by idempotent_endpoint.

    This what actually ensures idempotency for
    the actual work (e.g. do_send_messages)
    and to more finely control the start/end of a transaction.

    We have 3 cases:
    1- New work (completed=None), proceed with the work and
    cache the result.

    2- Duplicate succeeded work (completed=True), immediately return
    the cached result.

    3- Duplicate failed work (completed=False), immediately raise
    the cached error (non-transient error).

    It also handles the case of concurrent requests, by locking
    the corresponding row during the transaction.

    This decorator expects the decorated function to receive
    idempotency_key and user as kwargs.
    """

    def idempotency_decorator(
        do_work: Callable[ParamT, WorkReturnT],
    ) -> Callable[ParamT, WorkReturnT]:
        @wraps(do_work)
        def wrapper(*args: ParamT.args, **kwargs: ParamT.kwargs) -> WorkReturnT:
            # Cast it to a dict to access its values like a normal dict and keep mypy happy.
            # **kwargs (without ParamSpec) is already treated as dict in python anyway.
            _kwargs = cast(dict[str, Any], kwargs)
            idempotency_key = _kwargs.get("idempotency_key")
            user = _kwargs.get("user")

            with transaction.atomic(durable=durable, savepoint=savepoint):
                # Idempotency-Key is currently optional, so we still do the work normally
                # in case it's omitted by client.
                if idempotency_key is None:
                    return do_work(*args, **kwargs)

                try:
                    assert user is not None
                    with connection.cursor() as cursor:
                        # Here we select the matching row from idempotency table,
                        # locks that row during the whole transaction but abort if another request
                        # is already holding a lock.
                        query = SQL("""
                                    SELECT completed, cached_result FROM {idempotency_table}
                                    WHERE realm_id = %(realm_id)s
                                    AND user_id = %(user_id)s
                                    AND idempotency_key = %(idempotency_key_value)s
                                    FOR UPDATE NOWAIT;
                                    """).format(
                            idempotency_table=Identifier(IdempotentRequest._meta.db_table)
                        )
                        cursor.execute(
                            query,
                            {
                                "idempotency_key_value": idempotency_key,
                                "realm_id": user.realm_id,
                                "user_id": user.id,
                            },
                        )
                        result = cursor.fetchall()
                        completed = result[0][0]
                        cached_result = result[0][1]

                        # Duplicate succeeded work.
                        if completed:
                            return cached_result_deserializer(orjson.loads(cached_result))

                        # Duplicate failed work.
                        if completed is False:  # nocoverage
                            raise json_error_deserializer(orjson.loads(cached_result))

                    # New work.
                    result = do_work(*args, **kwargs)
                    # Mark the work as completed and cache its result.
                    IdempotentRequest.objects.filter(
                        realm_id=user.realm_id, user_id=user.id, idempotency_key=idempotency_key
                    ).update(completed=True, cached_result=cached_result_serializer(result))
                    return result

                # Row is locked by another concurrent request doing the work.
                except OperationalError as error:  # nocoverage
                    # We don't test this, because it's raised only during TRUE concurrent requests
                    # which can't be reproduced in zulip tests.
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

        1- Inserts the idempotency row which initially represents
        a new unattempted work.
        2- Catches and caches any non-transient json_error, and marks the work as failed.
        """
        idempotency_key = request.headers.get("Idempotency-Key")
        # Idempotency-Key is currently optional.
        if idempotency_key is None:
            return view_func(request, user_profile, *args, **kwargs)

        with connection.cursor() as cursor:
            query = SQL("""
                        INSERT INTO {idempotency_table} (realm_id, user_id, idempotency_key)
                        VALUES (%(realm_id)s, %(user_id)s, %(idempotency_key_value)s)
                        ON CONFLICT DO NOTHING;
                        """).format(idempotency_table=Identifier(IdempotentRequest._meta.db_table))
            cursor.execute(
                query,
                {
                    "idempotency_key_value": idempotency_key,
                    "realm_id": user_profile.realm_id,
                    "user_id": user_profile.id,
                },
            )
        try:
            return view_func(request, user_profile, *args, **kwargs)
        except JsonableError as json_error:
            if not isinstance(json_error, exceptions.LockedError):
                # Mark the work as failed and cache the error.
                IdempotentRequest.objects.filter(
                    realm_id=user_profile.realm_id,
                    user_id=user_profile.id,
                    idempotency_key=idempotency_key,
                ).update(completed=False, cached_result=json_error_serializer(json_error))
            raise

    return _wrapped_view_func
