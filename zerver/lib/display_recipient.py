from typing import Any, Dict, List, Optional, Union

from zerver.lib.cache import cache_with_key, display_recipient_cache_key
from zerver.models import Recipient, Stream, UserProfile

DisplayRecipientCacheT = Union[str, List[Dict[str, Any]]]
@cache_with_key(lambda *args: display_recipient_cache_key(args[0]),
                timeout=3600*24*7)
def get_display_recipient_remote_cache(recipient_id: int, recipient_type: int,
                                       recipient_type_id: Optional[int]) -> DisplayRecipientCacheT:
    """
    returns: an appropriate object describing the recipient.  For a
    stream this will be the stream name as a string.  For a huddle or
    personal, it will be an array of dicts about each recipient.
    """
    if recipient_type == Recipient.STREAM:
        assert recipient_type_id is not None
        stream = Stream.objects.get(id=recipient_type_id)
        return stream.name

    # The main priority for ordering here is being deterministic.
    # Right now, we order by ID, which matches the ordering of user
    # names in the left sidebar.
    user_profile_list = (UserProfile.objects.filter(subscription__recipient_id=recipient_id)
                                            .select_related()
                                            .order_by('id'))
    return [user_profile_to_display_recipient_dict(user_profile) for user_profile in user_profile_list]

def user_profile_to_display_recipient_dict(user_profile: 'UserProfile') -> Dict[str, Any]:
    return {'email': user_profile.email,
            'full_name': user_profile.full_name,
            'short_name': user_profile.short_name,
            'id': user_profile.id,
            'is_mirror_dummy': user_profile.is_mirror_dummy}
