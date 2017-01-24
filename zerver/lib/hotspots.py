from zerver.models import UserProfile, UserHotspot

from typing import List, Text

ALL_HOTSPOTS = ['welcome', 'streams', 'topics', 'narrowing', 'replying', 'get_started']
def get_next_hotspots(user):
    # type: (UserProfile) -> List[Text]
    seen_hotspots = frozenset(UserHotspot.objects.filter(user=user).values_list('hotspot', flat=True))
    for hotspot in ALL_HOTSPOTS:
        if hotspot not in seen_hotspots:
            return [hotspot]
    return []
