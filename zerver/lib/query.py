from __future__ import absolute_import

from django.db.models.query import QuerySet
from typing import TypeVar, List

T = TypeVar('T')

def last_n(n, query_set):
    # type: (int, QuerySet[T]) -> List[T]
    """Get the last n results from a Django QuerySet, in a semi-efficient way.
       Returns a list."""

    # We don't use reversed() because we would get a generator,
    # which causes bool(last_n(...)) to be True always.

    xs = list(query_set.reverse()[:n])
    xs.reverse()
    return xs
