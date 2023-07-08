from typing import List, Set

from zerver.lib.types import APIStreamDict
from zerver.models import DefaultStream, Stream


def get_default_streams_for_realm(realm_id: int) -> List[Stream]:
    return [
        default.stream
        for default in DefaultStream.objects.select_related().filter(realm_id=realm_id)
    ]


def streams_to_dicts_sorted(streams: List[Stream]) -> List[APIStreamDict]:
    return sorted((stream.to_dict() for stream in streams), key=lambda elt: elt["name"])


def get_default_stream_ids_for_realm(realm_id: int) -> Set[int]:
    return set(DefaultStream.objects.filter(realm_id=realm_id).values_list("stream_id", flat=True))


def get_default_streams_for_realm_as_dicts(realm_id: int) -> List[APIStreamDict]:
    # returns default streams in JSON serializable format, sorted by stream name
    streams = get_default_streams_for_realm(realm_id)
    return streams_to_dicts_sorted(streams)
