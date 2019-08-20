from typing import Dict, List, Optional, Set, Tuple
from zerver.lib.types import DisplayRecipientT, UserDisplayRecipient

from zerver.lib.cache import cache_with_key, display_recipient_cache_key, generic_bulk_cached_fetch, \
    display_recipient_bulk_get_users_by_id_cache_key
from zerver.models import Recipient, Stream, UserProfile, bulk_get_huddle_user_ids

display_recipient_fields = [
    "id",
    "email",
    "full_name",
    "short_name",
    "is_mirror_dummy",
]

@cache_with_key(lambda *args: display_recipient_cache_key(args[0]),
                timeout=3600*24*7)
def get_display_recipient_remote_cache(recipient_id: int, recipient_type: int,
                                       recipient_type_id: Optional[int]) -> DisplayRecipientT:
    """
    returns: an appropriate object describing the recipient.  For a
    stream this will be the stream name as a string.  For a huddle or
    personal, it will be an array of dicts about each recipient.
    """
    if recipient_type == Recipient.STREAM:
        assert recipient_type_id is not None
        stream = Stream.objects.values('name').get(id=recipient_type_id)
        return stream['name']

    # The main priority for ordering here is being deterministic.
    # Right now, we order by ID, which matches the ordering of user
    # names in the left sidebar.
    user_profile_list = UserProfile.objects.filter(
        subscription__recipient_id=recipient_id
    ).order_by('id').values(*display_recipient_fields)
    return list(user_profile_list)

def user_dict_id_fetcher(user_dict: UserDisplayRecipient) -> int:
    return user_dict['id']

def bulk_get_user_profile_by_id(uids: List[int]) -> Dict[int, UserDisplayRecipient]:
    return generic_bulk_cached_fetch(
        # Use a separate cache key to protect us from conflicts with
        # the get_user_profile_by_id cache.
        # (Since we fetch only several fields here)
        cache_key_function=display_recipient_bulk_get_users_by_id_cache_key,
        query_function=lambda ids: list(
            UserProfile.objects.filter(id__in=ids).values(*display_recipient_fields)),
        object_ids=uids,
        id_fetcher=user_dict_id_fetcher
    )

def bulk_fetch_display_recipients(recipient_tuples: Set[Tuple[int, int, int]]
                                  ) -> Dict[int, DisplayRecipientT]:
    """
    Takes set of tuples of the form (recipient_id, recipient_type, recipient_type_id)
    Returns dict mapping recipient_id to corresponding display_recipient
    """

    # Build dict mapping recipient id to (type, type_id) of the corresponding recipient:
    recipient_id_to_type_pair_dict = {
        recipient[0]: (recipient[1], recipient[2])
        for recipient in recipient_tuples
    }
    # And the inverse mapping:
    type_pair_to_recipient_id_dict = {
        (recipient[1], recipient[2]): recipient[0]
        for recipient in recipient_tuples
    }

    stream_recipients = set(
        recipient for recipient in recipient_tuples if recipient[1] == Recipient.STREAM
    )
    personal_and_huddle_recipients = recipient_tuples - stream_recipients

    def stream_query_function(recipient_ids: List[int]) -> List[Stream]:
        stream_ids = [
            recipient_id_to_type_pair_dict[recipient_id][1] for recipient_id in recipient_ids
        ]
        return Stream.objects.filter(id__in=stream_ids)

    def stream_id_fetcher(stream: Stream) -> int:
        return type_pair_to_recipient_id_dict[(Recipient.STREAM, stream.id)]

    def stream_cache_transformer(stream: Stream) -> str:
        return stream.name

    # ItemT = Stream, CacheItemT = str (name), ObjKT = int (recipient_id)
    stream_display_recipients = generic_bulk_cached_fetch(
        cache_key_function=display_recipient_cache_key,
        query_function=stream_query_function,
        object_ids=[recipient[0] for recipient in stream_recipients],
        id_fetcher=stream_id_fetcher,
        cache_transformer=stream_cache_transformer,
    )  # type: Dict[int, str]

    # Now we have to create display_recipients for personal and huddle messages.
    # We do this via generic_bulk_cached_fetch, supplying apprioprate functions to it.

    def personal_and_huddle_query_function(recipient_ids: List[int]
                                           ) -> List[Tuple[int, List[UserDisplayRecipient]]]:
        """
        Return a list of tuples of the form (recipient_id, [list of UserProfiles])
        where [list of UserProfiles] has users corresponding to the recipient,
        so the receiving userin Recipient.PERSONAL case,
        or in Personal.HUDDLE case - users in the huddle.
        This is a pretty hacky return value, but it needs to be in this form,
        for this function to work as the query_function in generic_bulk_cached_fetch.
        """

        recipients = [Recipient(
            id=recipient_id,
            type=recipient_id_to_type_pair_dict[recipient_id][0],
            type_id=recipient_id_to_type_pair_dict[recipient_id][1]
        ) for recipient_id in recipient_ids]

        # Find all user ids whose UserProfiles we will need to fetch:
        user_ids_to_fetch = set()  # type: Set[int]
        huddle_user_ids = {}  # type: Dict[int, List[int]]
        huddle_user_ids = bulk_get_huddle_user_ids([recipient for recipient in recipients
                                                    if recipient.type == Recipient.HUDDLE])
        for recipient in recipients:
            if recipient.type == Recipient.PERSONAL:
                user_ids_to_fetch.add(recipient.type_id)
            else:
                user_ids_to_fetch = user_ids_to_fetch.union(huddle_user_ids[recipient.id])

        # Fetch the needed UserProfiles:
        user_profiles = bulk_get_user_profile_by_id(list(user_ids_to_fetch))  # type: Dict[int, UserDisplayRecipient]

        # Build the return value:
        result = []  # type: List[Tuple[int, List[UserDisplayRecipient]]]
        for recipient in recipients:
            if recipient.type == Recipient.PERSONAL:
                result.append((recipient.id, [user_profiles[recipient.type_id]]))
            else:
                result.append((recipient.id, [user_profiles[user_id]
                                              for user_id in huddle_user_ids[recipient.id]]))

        return result

    def personal_and_huddle_cache_transformer(db_object: Tuple[int, List[UserDisplayRecipient]]
                                              ) -> List[UserDisplayRecipient]:
        """
        Takes an element of the list returned by the query_function, maps it to the final
        display_recipient list.
        """
        user_profile_list = db_object[1]
        display_recipient = user_profile_list

        return display_recipient

    def personal_and_huddle_id_fetcher(db_object: Tuple[int, List[UserDisplayRecipient]]) -> int:
        # db_object is a tuple, with recipient_id in the first position
        return db_object[0]

    # ItemT = Tuple[int, List[UserDisplayRecipient]] (recipient_id, list of corresponding users)
    # CacheItemT = List[UserDisplayRecipient] (display_recipient list)
    # ObjKT = int (recipient_id)
    personal_and_huddle_display_recipients = generic_bulk_cached_fetch(
        cache_key_function=display_recipient_cache_key,
        query_function=personal_and_huddle_query_function,
        object_ids=[recipient[0] for recipient in personal_and_huddle_recipients],
        id_fetcher=personal_and_huddle_id_fetcher,
        cache_transformer=personal_and_huddle_cache_transformer
    )

    # Glue the dicts together and return:
    return {**stream_display_recipients, **personal_and_huddle_display_recipients}
