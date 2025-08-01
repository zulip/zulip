from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from django.db import connection, models, transaction
from psycopg2.errors import LockNotAvailable
from psycopg2.extras import DictCursor, DictRow
from psycopg2.sql import SQL, Identifier, Placeholder

from zerver.lib.exceptions import LockedError
from zerver.models import IdempotentRequest, Realm, UserProfile

WorkReturnT = TypeVar("WorkReturnT")
ParamT = ParamSpec("ParamT")


def do_idempotent_insert(
    idempotency_key: str,
    realm: Realm,
    user: UserProfile,
    destination_model: type[models.Model],
    field_names: list[str],
    column_to_value: dict[str, Any],
) -> DictRow:
    """
    Important: MUST run inside idempotent_request_transaction.

    The goal of this query is to:
    1- Insert a single row (e.g. new message) in the target table and inserts
    the corresponding realm, user, idempotency_key in the idempotency table.

    2- Ensure 1.idempotency and 2.that only one request does the same work at a time.

    Returns: id of the new inserted row.

    First SELECT: selects the corresponding row from idempotency table
    and locks the row, but abort if another request is holding the lock (using FOR UPDATE NOWAIT)

    We have two CTEs:

    1.insertion_cte:
    Inserts a new row returning the new db-generated id of that inserted row.
    Note: The INSERT statement is not conditional as this query runs ONLy for
    new work (e.g. non-duplicate message) except in the case of a concurrent request
    which is handled correctly by FOR UPDATE NOWAIT.

    2.update_cte:
    References insertion_cte to SET insertion_cte.identifier to the
    id of the new inserted row (insertion_cte.new_id).
    Note: nothing actually updates if insertion_cte returns no rows,
    but insertion_cte should always inserts and returns the id.
    """

    with connection.connection.cursor(cursor_factory=DictCursor) as cursor:
        query = SQL(
            """
            SELECT identifier FROM {idempotency_table}
            WHERE realm_id = %(realm_id)s
            AND user_id = %(user_id)s
            AND idempotency_key = %(idempotency_key_value)s
            FOR UPDATE NOWAIT;

            WITH insertion_cte AS(
                INSERT INTO {dest_table} ({cols})
                SELECT {values_placeholders}
                RETURNING {pk} AS new_id
            ),
            update_cte AS(
                UPDATE {idempotency_table}
                SET identifier = insertion_cte.new_id FROM insertion_cte
                WHERE realm_id = %(realm_id)s
                AND user_id = %(user_id)s
                AND idempotency_key = %(idempotency_key_value)s
            )
            SELECT new_id FROM insertion_cte AS new_id
        """
        ).format(
            dest_table=Identifier(destination_model._meta.db_table),
            idempotency_table=Identifier(IdempotentRequest._meta.db_table),
            cols=SQL(", ").join(map(Identifier, field_names)),
            values_placeholders=SQL(", ").join(map(Placeholder, field_names)),
            pk=Identifier(destination_model._meta.pk.name),
        )
        cursor.execute(
            query,
            {
                **column_to_value,
                "idempotency_key_value": idempotency_key,
                "realm_id": realm.id,
                "user_id": user.id,
            },
        )
        result = cursor.fetchall()

        # We should only get a single result row.
        assert len(result) == 1
        return result[0]


def idempotent_request_transaction(
    durable: bool = False,
    savepoint: bool = True,
    *,
    cached_response_serializer: Callable[[Any], dict[str, Any]],
    cached_response_deserializer: Callable[[str], Any],
) -> Callable[[Callable[ParamT, WorkReturnT]], Callable[ParamT, WorkReturnT]]:
    """
    Our custom decorator to apply idempotency for
    non-idempotent operations (e.g. do_send_messages)
    and to more finely control the start/end of a transaction.

    This decorator expects the decorated function to receive
    idempotency_key and user as kwargs, Both are optional but are required
    to apply idempotency.

    Note: Currently only wraps do_send_messages().
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

            # Idempotency-Key is optional, so we should still do the work normally
            # if i'ts omitted by client.
            if idempotency_key is None:
                with transaction.atomic(durable=durable, savepoint=savepoint):
                    return do_work(*args, **kwargs)

            assert user is not None
            with connection.connection.cursor(cursor_factory=DictCursor) as cursor:
                query = SQL("""
                            INSERT INTO {idempotency_table} (realm_id, user_id, idempotency_key)
                            VALUES (%(realm_id)s, %(user_id)s, %(idempotency_key_value)s)
                            ON CONFLICT DO NOTHING;

                            SELECT cached_response AS cached_response FROM {idempotency_table}
                            WHERE realm_id = %(realm_id)s
                            AND user_id = %(user_id)s
                            AND idempotency_key = %(idempotency_key_value)s;
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
                cached_result = result[0]["cached_response"]
                if cached_result is not None:
                    return cached_response_deserializer(cached_result)

            with transaction.atomic(durable=durable, savepoint=savepoint):
                try:
                    # This code path runs only if the work is new, except in the case of a concurrent request,
                    # which is handled separately and correctly by do_idempotent_insert
                    # and raises LockedError accordingly.
                    result = do_work(*args, **kwargs)
                    IdempotentRequest.objects.filter(idempotency_key=idempotency_key).update(
                        cached_response=cached_response_serializer(result)
                    )
                    return result

                except LockNotAvailable:
                    # Row is locked by another concurrent request doing the work.
                    raise LockedError

        return wrapper

    return idempotency_decorator
