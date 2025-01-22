from zerver.models import DefaultStream, Stream


def get_slim_realm_default_streams(realm_id: int) -> set[Stream]:
    # We really want this query to be simple and just get "thin" Stream objects
    # in one round trip.
    #
    # The above is enforced by at least three tests that verify query counts,
    # and test_query_count in test_subs.py makes sure that the query itself is
    # not like 11000 bytes, which is what we had in a prior version that used
    # select_related() with no arguments (and thus joined to too many tables).
    #
    # Please be careful about modifying this code, as it has had a history
    # of performance problems.
    return set(Stream.objects.filter(defaultstream__realm_id=realm_id))


def get_default_stream_ids_for_realm(realm_id: int) -> set[int]:
    return set(DefaultStream.objects.filter(realm_id=realm_id).values_list("stream_id", flat=True))
