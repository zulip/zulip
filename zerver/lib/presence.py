from collections import defaultdict
import time
from typing import Any, Dict
from zerver.models import UserProfile, UserPresence

def get_status_dict(requesting_user_profile: UserProfile,
                    slim_presence: bool) -> Dict[str, Dict[str, Dict[str, Any]]]:

    if requesting_user_profile.realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict)

    return UserPresence.get_status_dict_by_realm(requesting_user_profile.realm_id, slim_presence)

def get_presence_response(requesting_user_profile: UserProfile,
                          slim_presence: bool) -> Dict[str, Any]:
    server_timestamp = time.time()
    presences = get_status_dict(requesting_user_profile, slim_presence)
    return dict(presences=presences, server_timestamp=server_timestamp)
