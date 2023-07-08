from typing import List, Set

from zerver.lib.types import APIStreamDict
from zerver.models import DefaultStream, Stream


def get_default_streams_for_realm(realm_id: int) -> List[Stream]:
    # TODO: Deprecate this extremely expensive query. We can't immediately
    #       just improve it by removing select_related(), because then you
    #       may get the opposite problem of multiple round trips.
    return [
        default.stream
        for default in DefaultStream.objects.select_related().filter(realm_id=realm_id)
    ]


def get_default_stream_ids_for_realm(realm_id: int) -> Set[int]:
    return set(DefaultStream.objects.filter(realm_id=realm_id).values_list("stream_id", flat=True))


def get_default_streams_for_realm_as_dicts(realm_id: int) -> List[APIStreamDict]:
    """
    Return all the default streams for a realm using a list of dictionaries sorted
    by stream name.
    """

    # This slightly convoluted construction makes it so that the Django ORM gets
    # all the data it needs to serialize default streams as a list of dictionaries
    # using a single query without using select_related().
    # This is enforced by test_query_count in test_subs.py.
    stream_ids = DefaultStream.objects.filter(realm_id=realm_id).values_list("stream_id")
    streams = Stream.objects.filter(id__in=stream_ids)
    return sorted((stream.to_dict() for stream in streams), key=lambda elt: elt["name"])
