# See https://zulip.readthedocs.io/en/latest/subsystems/hotspots.html
# for documentation on this subsystem.
from typing import Dict, List

from django.conf import settings
from django.utils.functional import Promise
from django.utils.translation import ugettext_lazy

from zerver.models import UserHotspot, UserProfile

ALL_HOTSPOTS: Dict[str, Dict[str, Promise]] = {
    'intro_reply': {
        'title': ugettext_lazy('Reply to a message'),
        'description': ugettext_lazy('Click anywhere on a message to reply.'),
    },
    'intro_streams': {
        'title': ugettext_lazy('Catch up on a stream'),
        'description': ugettext_lazy(
            'Messages sent to a stream are seen by everyone subscribed '
            'to that stream. Try clicking on one of the stream links below.'
        ),
    },
    'intro_topics': {
        'title': ugettext_lazy('Topics'),
        'description': ugettext_lazy(
            'Every message has a topic. Topics keep conversations '
            'easy to follow, and make it easy to reply to conversations that start '
            'while you are offline.'
        ),
    },
    'intro_gear': {
        'title': ugettext_lazy('Settings'),
        'description': ugettext_lazy(
            'Go to Settings to configure your notifications and display settings.'
        ),
    },
    'intro_compose': {
        'title': ugettext_lazy('Compose'),
        'description': ugettext_lazy(
            'Click here to start a new conversation. Pick a topic '
            '(2-3 words is best), and give it a go!'
        ),
    },
}

def get_next_hotspots(user: UserProfile) -> List[Dict[str, object]]:
    # For manual testing, it can be convenient to set
    # ALWAYS_SEND_ALL_HOTSPOTS=True in `zproject/dev_settings.py` to
    # make it easy to click on all of the hotspots.  Note that
    # ALWAYS_SEND_ALL_HOTSPOTS has some bugs; see ReadTheDocs (link
    # above) for details.
    if settings.ALWAYS_SEND_ALL_HOTSPOTS:
        return [{
            'name': hotspot,
            'title': str(ALL_HOTSPOTS[hotspot]['title']),
            'description': str(ALL_HOTSPOTS[hotspot]['description']),
            'delay': 0,
        } for hotspot in ALL_HOTSPOTS]

    if user.tutorial_status == UserProfile.TUTORIAL_FINISHED:
        return []

    seen_hotspots = frozenset(UserHotspot.objects.filter(user=user).values_list('hotspot', flat=True))
    for hotspot in ['intro_reply', 'intro_streams', 'intro_topics', 'intro_gear', 'intro_compose']:
        if hotspot not in seen_hotspots:
            return [{
                'name': hotspot,
                'title': str(ALL_HOTSPOTS[hotspot]['title']),
                'description': str(ALL_HOTSPOTS[hotspot]['description']),
                'delay': 0.5,
            }]

    user.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user.save(update_fields=['tutorial_status'])
    return []

def copy_hotpots(source_profile: UserProfile, target_profile: UserProfile) -> None:
    for userhotspot in frozenset(UserHotspot.objects.filter(user=source_profile)):
        UserHotspot.objects.create(user=target_profile, hotspot=userhotspot.hotspot,
                                   timestamp=userhotspot.timestamp)

    target_profile.tutorial_status = source_profile.tutorial_status
    target_profile.onboarding_steps = source_profile.onboarding_steps
    target_profile.save(update_fields=['tutorial_status', 'onboarding_steps'])
