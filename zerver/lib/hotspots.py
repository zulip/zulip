# See https://zulip.readthedocs.io/en/latest/subsystems/hotspots.html
# for documentation on this subsystem.
from django.conf import settings
from django.utils.translation import ugettext as _

from zerver.models import UserProfile, UserHotspot

from typing import List, Dict

ALL_HOTSPOTS = {
    'intro_reply': {
        'title': _('Reply to a message'),
        'description': _('Click anywhere on a message to reply.'),
    },
    'intro_streams': {
        'title': _('Catch up on a stream'),
        'description': _('Messages sent to a stream are seen by everyone subscribed '
                         'to that stream. Try clicking on one of the stream links below.'),
    },
    'intro_topics': {
        'title': _('Topics'),
        'description': _('Every message has a topic. Topics keep conversations '
                         'easy to follow, and make it easy to reply to conversations that start '
                         'while you are offline.'),
    },
    'intro_gear': {
        'title': _('Settings'),
        'description': _('Go to Settings to configure your '
                         'notifications and display settings.'),
    },
    'intro_compose': {
        'title': _('Compose'),
        'description': _('Click here to start a new conversation. Pick a topic '
                         '(2-3 words is best), and give it a go!'),
    },
}  # type: Dict[str, Dict[str, str]]

def get_next_hotspots(user: UserProfile) -> List[Dict[str, object]]:
    # For manual testing, it can be convenient to set
    # ALWAYS_SEND_ALL_HOTSPOTS=True in `zproject/dev_settings.py` to
    # make it easy to click on all of the hotspots.  Note that
    # ALWAYS_SEND_ALL_HOTSPOTS has some bugs; see ReadTheDocs (link
    # above) for details.
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
    for hotspot in ['intro_reply', 'intro_streams', 'intro_topics', 'intro_gear', 'intro_compose']:
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

def copy_hotpots(source_profile: UserProfile, target_profile: UserProfile) -> None:
    for userhotspot in frozenset(UserHotspot.objects.filter(user=source_profile)):
        UserHotspot.objects.create(user=target_profile, hotspot=userhotspot.hotspot,
                                   timestamp=userhotspot.timestamp)

    target_profile.tutorial_status = source_profile.tutorial_status
    target_profile.onboarding_steps = source_profile.onboarding_steps
    target_profile.save(update_fields=['tutorial_status', 'onboarding_steps'])
