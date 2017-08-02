from zerver.models import UserProfile, UserHotspot

from typing import List, Text, Dict

SEND_ALL = False

ALL_HOTSPOTS = {
    # TODO: Tag these for translation once we've finalized the content.
    'click_to_reply': {
        'title': 'Respond to a message',
        'description': 'Click anywhere on a message to reply.',
    },
    'new_topic_button': {
        'title': 'Start a new topic',
        'description': 'Click the "New topic" button to start a new conversation.',
    },
    'stream_settings': {
        'title': 'Stream settings',
        'description': 'Most discussion on Zulip happens in streams. Click here to create or join additional streams.',
    },
}  # type Dict[str, Dict[str, Text]]

def get_next_hotspots(user):
    # type: (UserProfile) -> List[Dict[str, object]]

    if SEND_ALL:
        result = []
        for hotspot in ALL_HOTSPOTS:
            result.append({
                'name': hotspot,
                'title': ALL_HOTSPOTS[hotspot]['title'],
                'description': ALL_HOTSPOTS[hotspot]['description'],
                'delay': 5,
            })

        return result

    seen_hotspots = frozenset(UserHotspot.objects.filter(user=user).values_list('hotspot', flat=True))
    for hotspot in ['click_to_reply', 'new_topic_button', 'stream_settings']:
        if hotspot not in seen_hotspots:
            return [{
                'name': hotspot,
                'title': ALL_HOTSPOTS[hotspot]['title'],
                'description': ALL_HOTSPOTS[hotspot]['description'],
                'delay': 5,
            }]
    return []
