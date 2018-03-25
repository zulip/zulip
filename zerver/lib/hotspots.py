from django.conf import settings
from zerver.models import UserProfile, UserHotspot

from typing import List, Text, Dict

ALL_HOTSPOTS = {
    # TODO: Tag these for translation once we've finalized the content.
    'intro_reply': {
        'title': 'Reply to a message',
        'description': 'Click anywhere on a message to reply.',
    },
    'intro_streams': {
        'title': 'Catch up on a stream',
        'description': 'Messages sent to a stream are seen by everyone subscribed '
        'to that stream. Try clicking on one of the stream links below.',
    },
    'intro_topics': {
        'title': 'Topics',
        'description': 'Every message has a topic. Topics keep conversations '
        'easy to follow, and make it easy to reply to conversations that start '
        'while you are offline.',
    },
    'intro_compose': {
        'title': 'Compose',
        'description': 'Click here to start a new conversation. Pick a topic '
        '(2-3 words is best), and give it a go!',
    },
}  # type: Dict[str, Dict[str, Text]]

def get_next_hotspots(user: UserProfile) -> List[Dict[str, object]]:
    # For manual testing, it can be convenient to set
    # ALWAYS_SEND_ALL_HOTSPOTS=True in `zproject/dev_settings.py` to
    # make it easy to click on all of the hotspots.
    if settings.ALWAYS_SEND_ALL_HOTSPOTS:
        return [{
            'name': hotspot,
            'title': ALL_HOTSPOTS[hotspot]['title'],
            'description': ALL_HOTSPOTS[hotspot]['description'],
            'delay': 0,
        } for hotspot in ALL_HOTSPOTS]

    if user.tutorial_status == UserProfile.TUTORIAL_FINISHED:
        return []

    seen_hotspots = frozenset(UserHotspot.objects.filter(user=user).values_list('hotspot', flat=True))
    for hotspot in ['intro_reply', 'intro_streams', 'intro_topics', 'intro_compose']:
        if hotspot not in seen_hotspots:
            return [{
                'name': hotspot,
                'title': ALL_HOTSPOTS[hotspot]['title'],
                'description': ALL_HOTSPOTS[hotspot]['description'],
                'delay': 0.5,
            }]

    user.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user.save(update_fields=['tutorial_status'])
    return []
