from typing import Dict, List, Optional, Set, Tuple, TypedDict, cast

from zerver.lib.cache import (
    cache_with_key,
    display_recipient_cache_key,
)
from zerver.lib.types import DisplayRecipientT, UserDisplayRecipient
from zerver.models import (
    Recipient,
    Stream,
    UserProfile,
    bulk_get_huddle_user_ids,
    get_column_values_from_single_table_using_id_lookup,
)

display_recipient_fields = [
    "id",
    "email",
    "full_name",
    "is_mirror_dummy",
]


class TinyStreamResult(TypedDict):
    recipient_id: int
    name: str


def get_display_recipient_cache_key(
    recipient_id: int, recipient_type: int, recipient_type_id: Optional[int]
) -> str:
    return display_recipient_cache_key(recipient_id)


@cache_with_key(get_display_recipient_cache_key, timeout=3600 * 24 * 7)
def get_display_recipient_remote_cache(
    recipient_id: int, recipient_type: int, recipient_type_id: Optional[int]
) -> DisplayRecipientT:
    """
    returns: an appropriate object describing the recipient.  For a
    stream this will be the stream name as a string.  For a huddle or
    personal, it will be an array of dicts about each recipient.
    """
    if recipient_type == Recipient.STREAM:
        assert recipient_type_id is not None
        stream = Stream.objects.values("name").get(id=recipient_type_id)
        return stream["name"]

    # The main priority for ordering here is being deterministic.
    # Right now, we order by ID, which matches the ordering of user
    # names in the left sidebar.
    user_profile_list = (
        UserProfile.objects.filter(
            subscription__recipient_id=recipient_id,
        )
        .order_by("id")
        .values(*display_recipient_fields)
    )
    return list(user_profile_list)


def bulk_fetch_single_user_display_recipients(
    *, user_ids: List[int]
) -> Dict[int, UserDisplayRecipient]:
    db_rows = get_column_values_from_single_table_using_id_lookup(
        columns=display_recipient_fields,
        table="zerver_userprofile",
        id_field="id",
        ids=user_ids,
        order_by_columns=["id"],
    )
    rows = cast(List[UserDisplayRecipient], db_rows)
    return {row["id"]: row for row in rows}


def bulk_fetch_stream_names(
    recipient_tuples: Set[Tuple[int, int, int]],
) -> Dict[int, str]:
    """
    Takes set of tuples of the form (recipient_id, recipient_type, recipient_type_id)
    Returns dict mapping recipient_id to corresponding stream name
    """

    if len(recipient_tuples) == 0:
        return {}

    stream_ids = [tup[2] for tup in recipient_tuples]

    db_rows = get_column_values_from_single_table_using_id_lookup(
        columns=["recipient_id", "name"],
        table="zerver_stream",
        id_field="id",
        ids=stream_ids,
        order_by_columns=["recipient_id"],
    )

    rows = cast(List[TinyStreamResult], db_rows)

    def get_recipient_id(row: TinyStreamResult) -> int:
        return row["recipient_id"]

    def get_name(row: TinyStreamResult) -> str:
        return row["name"]

    return {get_recipient_id(row): get_name(row) for row in rows}


def bulk_fetch_user_display_recipients(
    recipient_tuples: Set[Tuple[int, int, int]],
) -> Dict[int, List[UserDisplayRecipient]]:
    """
    Takes set of tuples of the form (recipient_id, recipient_type, recipient_type_id)
    Returns dict mapping recipient_id to corresponding display_recipient
    """

    if len(recipient_tuples) == 0:
        return {}

    get_recipient_id = lambda tup: tup[0]
    get_type = lambda tup: tup[1]

    personal_tuples = [tup for tup in recipient_tuples if get_type(tup) == Recipient.PERSONAL]
    huddle_tuples = [tup for tup in recipient_tuples if get_type(tup) == Recipient.HUDDLE]

    huddle_recipient_ids = [get_recipient_id(tup) for tup in huddle_tuples]
    huddle_recipient_id_to_user_ids = bulk_get_huddle_user_ids(huddle_recipient_ids)

    # Find all user ids whose UserProfiles we will need to fetch:
    user_ids_to_fetch: Set[int] = set()

    for ignore_recipient_id, ignore_recipient_type, user_id in personal_tuples:
        user_ids_to_fetch.add(user_id)

    for recipient_id in huddle_recipient_ids:
        huddle_user_ids = huddle_recipient_id_to_user_ids[recipient_id]
        user_ids_to_fetch |= huddle_user_ids

    # Fetch the needed user dictionaries.
    user_display_recipients = bulk_fetch_single_user_display_recipients(
        user_ids=list(user_ids_to_fetch),
    )

    result = {}

    for recipient_id, ignore_recipient_type, user_id in personal_tuples:
        display_recipients = [user_display_recipients[user_id]]
        result[recipient_id] = display_recipients

    for recipient_id in huddle_recipient_ids:
        user_ids = sorted(huddle_recipient_id_to_user_ids[recipient_id])
        display_recipients = [user_display_recipients[user_id] for user_id in user_ids]
        result[recipient_id] = display_recipients

    return result


def bulk_fetch_display_recipients(
    recipient_tuples: Set[Tuple[int, int, int]],
) -> Dict[int, DisplayRecipientT]:
    """
    Takes set of tuples of the form (recipient_id, recipient_type, recipient_type_id)
    Returns dict mapping recipient_id to corresponding display_recipient
    """

    stream_recipients = {
        recipient for recipient in recipient_tuples if recipient[1] == Recipient.STREAM
    }
    personal_and_huddle_recipients = recipient_tuples - stream_recipients

    stream_display_recipients = bulk_fetch_stream_names(stream_recipients)
    personal_and_huddle_display_recipients = bulk_fetch_user_display_recipients(
        personal_and_huddle_recipients
    )

    # Glue the dicts together and return:
    return {**stream_display_recipients, **personal_and_huddle_display_recipients}
