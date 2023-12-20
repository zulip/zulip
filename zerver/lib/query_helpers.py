from typing import List, TypeVar

from django.db import models
from django_stubs_ext import ValuesQuerySet

ModelT = TypeVar("ModelT", bound=models.Model)
RowT = TypeVar("RowT")


def query_for_ids(
    query: ValuesQuerySet[ModelT, RowT],
    user_ids: List[int],
    field: str,
) -> ValuesQuerySet[ModelT, RowT]:
    """
    This function optimizes searches of the form
    `user_profile_id in (1, 2, 3, 4)` by quickly
    building the where clauses.  Profiling shows significant
    speedups over the normal Django-based approach.

    Use this very carefully!  Also, the caller should
    guard against empty lists of user_ids.
    """
    assert user_ids
    clause = f"{field} IN %s"
    query = query.extra(
        where=[clause],
        params=(tuple(user_ids),),
    )
    return query
