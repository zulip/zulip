from typing import List, Set

from zerver.lib.types import DefaultStreamDict
from zerver.models import DefaultStream, Stream


def get_slim_realm_default_streams(realm_id: int) -> List[Stream]:
    # We really want this query to be simple and just get "thin" Stream objects
    # in one round trip.
    #
    # The above is enforced by at least three tests that verify query counts,
    # and test_query_count in test_subs.py makes sure that the query itself is
    # not like 11000 bytes, which is what we had in a prior version that used
    # select_related() with not arguments (and thus joined to too many tables).
    #
    # Please be careful about modifying this code, as it has had a history
    # of performance problems.
    return list(Stream.objects.filter(defaultstream__realm_id=realm_id))


def get_default_stream_ids_for_realm(realm_id: int) -> Set[int]:
    return set(DefaultStream.objects.filter(realm_id=realm_id).values_list("stream_id", flat=True))


def get_default_streams_for_realm_as_dicts(realm_id: int) -> List[DefaultStreamDict]:
    """
    Return all the default streams for a realm using a list of dictionaries sorted
    by stream name.
    """
    streams = get_slim_realm_default_streams(realm_id)
    stream_dicts = [stream.to_dict() for stream in streams]
    return sorted(stream_dicts, key=lambda stream: stream["name"])
