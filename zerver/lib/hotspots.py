from zerver.models import UserProfile, UserHotspot

from typing import List, Text, Dict

ALL_HOTSPOTS = {
    'click_to_reply': 'Click anywhere on a message to reply.',
    'new_topic_botton': 'Click the "New topic" button to start a new conversation.',
    'stream_settings': 'Most discussion on Zulip happens in streams. Click here to create or join additional streams.',
}

def get_next_hotspots(user):
    # type: (UserProfile) -> List[Dict[str, Text]]
    seen_hotspots = frozenset(UserHotspot.objects.filter(user=user).values_list('hotspot', flat=True))
    for hotspot in ['click_to_reply', 'new_topic_botton', 'stream_settings']:
        if hotspot not in seen_hotspots:
            return [{'name': hotspot, 'description': ALL_HOTSPOTS[hotspot]}]
    return []
