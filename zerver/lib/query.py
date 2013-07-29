from __future__ import absolute_import

def last_n(n, query_set):
    """Get the last n results from a Django QuerySet, in a semi-efficient way.
       Returns a list."""

    # We don't use reversed() because we would get a generator,
    # which causes bool(last_n(...)) to be True always.

    xs = list(query_set.reverse()[:n])
    xs.reverse()
    return xs
