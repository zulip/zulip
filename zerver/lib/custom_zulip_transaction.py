from collections.abc import Callable
from dataclasses import asdict
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

from django.db import OperationalError, connection, models, transaction
from django.utils.translation import gettext as _

from psycopg2.errors import LockNotAvailable
from psycopg2.sql import Identifier, Placeholder, SQL

from zerver.lib.exceptions import LockedError
from zerver.models import IdempotentRequest

WrappedReturnT = TypeVar("WrappedReturnT")
ParamT = ParamSpec("ParamT")


def do_idempotent_work(
    idempotency_key: str,
    destination_model: type[models.Model],
    field_names: list[str],
    column_to_value: dict[str, Any]
) -> list[tuple[Any, ...]]:
    """
    This query applies Idempotency on work being done (e.g. inserting a message row),
    and ensures only one request can do that work at a time.

    The final SELECT combines data from the 3 CTEs and
    returns 3 deterministic values in the following order:
    1- status: Indicatesa a NEW or DUPLICATE work.
    2- new_id: The DB-generated id of the inserted row (None in case of no insertion).
    3- cached_response: The saved result returned as the API response for duplicate work.

    Example output, only one of the following:
    new work: ('NEW', 315, None)
    duplicate work: ('DUPLICATE', None, '{"message_id": 313, "automatic_new_visibility_policy": 3}')

    CTEs:

    1.status_cte:
    The status of work, NEW or DUPLIATE.

    MATERIALIZED: Preserve the state across the rest of query.
    This is already the default behaviour (i.e. CTE is evaluated only once)
    but we are just being explicit.
    See https://www.postgresql.org/docs/current/queries-with.html#QUERIES-WITH-CTE-MATERIALIZATION

    FOR UPDATE NOWAIT: Locks the row, but abort if another request is holding the lock
    i.e. doing the work.

    2.insertion_cte:
    References status_cte to conditionally insert a row
    (when status_cte.identifier IS NULL).
    Returns the new db-generated id of that row (null in case of no insertion).

    3.update_cte:
    References insertion_cte to conditionally SET insertion_cte.identifier to the
    id of the new inserted row (insertion_cte.new_id).
    Although there is no explicit condition (WHERE), nothing actually updates
    if insertion_cte returns null.
    """
    with connection.cursor() as cursor:
        query = SQL(
            """
            WITH status_cte AS MATERIALIZED (
                SELECT * FROM {idempotency_table}
                WHERE idempotency_key = %(idempotency_key_value)s
                FOR UPDATE NOWAIT
            ),
            insertion_cte AS(
                INSERT INTO {dest_table} ({cols})
                SELECT {values_placeholders}
                WHERE (SELECT identifier FROM status_cte) IS NULL
                RETURNING {pk} AS new_id
            ),
            update_cte AS(
                UPDATE {idempotency_table}
                SET identifier = insertion_cte.new_id
                FROM insertion_cte
                WHERE idempotency_key = %(idempotency_key_value)s
            )
            SELECT
                CASE
                    WHEN (SELECT identifier FROM status_cte) IS NULL THEN 'NEW' ELSE 'DUPLICATE'
                END AS status,
                (SELECT new_id FROM insertion_cte),
                (SELECT cached_response FROM status_cte);
        """
        ).format(
            dest_table=Identifier(destination_model._meta.db_table),
            idempotency_table=Identifier(IdempotentRequest._meta.db_table),
            cols=SQL(", ").join(map(Identifier, field_names)),
            values_placeholders=SQL(", ").join(map(Placeholder, field_names)),
            pk=Identifier(destination_model._meta.pk.name),
        )
        cursor.execute(query, {**column_to_value, "idempotency_key_value": idempotency_key})
        result = cursor.fetchall()
        return result


# Currently, the decorated function do_work always returns [SentMessageResult],
# but zulip_transaction decorator is designed to be generic for future support of other work.
# That's why we check the work being done (by func name) and handle each type accordingly.
def post_do_work(work_result: WrappedReturnT, work_name: str, idempotency_key: str) -> None:
    from zerver.actions.message_send import SentMessageResult

    if work_name == "do_send_messages":
        work_result = work_result[0]  # type: ignore[index] # It is certainly list[SentMessageResult]
        assert isinstance(work_result, SentMessageResult)
        # Cache response if it's a new message,
        # since automatic_new_visibility_policy (conditionally included in a response)
        # isn't known until do_send_message() completes.
        if work_result.status == "NEW":
            sent_messate_result_dict = asdict(work_result)
            # "status" is only SentMessageResult related.
            sent_messate_result_dict.pop("status")
            IdempotentRequest.objects.filter(idempotency_key=idempotency_key).update(
                cached_response=sent_messate_result_dict
            )


def zulip_transaction(
    durable: bool = False,
    savepoint: bool = True,
) -> Callable[[Callable[ParamT, WrappedReturnT]], Callable[ParamT, WrappedReturnT]]:
    """
    Our custom decorator to apply idempotency for
    non-idempotent operations (e.g. sending message)
    and to more finely control the start/end of a transaction.

    This decorator expects the decorated function
    to optionally receive the idempotency_key as one of its arguments.

    Note: Currently only wraps do_send_messages().
    """

    def idempotency_decorator(
        do_work: Callable[ParamT, WrappedReturnT],
    ) -> Callable[ParamT, WrappedReturnT]:
        @wraps(do_work)
        def wrapper(*args: ParamT.args, **kwargs: ParamT.kwargs) -> WrappedReturnT:
            # Cast it to a dict to access its values like a normal dict and keep mypy happy.
            # **kwargs (without ParamSpec) is treated as dict in python anyway.
            _kwargs = cast(dict[str, Any], kwargs)
            idempotency_key = _kwargs.get("idempotency_key")

            if idempotency_key is None:
                with transaction.atomic(durable=durable, savepoint=savepoint):
                    return do_work(*args, **kwargs)

            with connection.cursor() as cursor:
                query = SQL("""
                            INSERT INTO {idempotency_table} (idempotency_key) VALUES
                            (%(idempotency_key_value)s) ON CONFLICT DO NOTHING;
                            """).format(
                    idempotency_table=Identifier(IdempotentRequest._meta.db_table)
                )
                cursor.execute(query, {"idempotency_key_value": idempotency_key})

            with transaction.atomic(durable=durable, savepoint=savepoint):
                try:
                    result = do_work(*args, **kwargs)

                    # Handle post work operations, like caching responses to db.
                    post_do_work(
                        work_result=result,
                        work_name=do_work.__name__,
                        idempotency_key=idempotency_key,
                    )
                    return result
                except OperationalError as error:
                    # Row is locked by another concurrent request doing the work.
                    if isinstance(error.__cause__, LockNotAvailable):
                        raise LockedError(
                            _("Conflict, Another concurrent request is being processed.")
                        )
                    else:
                        raise
                # TODO:
                # Here we can catch errors (e.g. JsonableError) and cache them.
                # But for the purpose of sending messages, most errors
                # are already checked and raised early before this code path.

        return wrapper

    return idempotency_decorator
