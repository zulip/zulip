# See https://zulip.readthedocs.io/en/latest/subsystems/hotspots.html
# for documentation on this subsystem.
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise

from zerver.models import UserHotspot, UserProfile


@dataclass
class Hotspot:
    name: str
    title: Optional[StrPromise]
    description: Optional[StrPromise]
    has_trigger: bool = False

    def to_dict(self, delay: float = 0) -> Dict[str, Union[str, float, bool]]:
        return {
            "name": self.name,
            "title": str(self.title),
            "description": str(self.description),
            "delay": delay,
            "has_trigger": self.has_trigger,
        }


INTRO_HOTSPOTS: List[Hotspot] = [
    Hotspot(
        name="intro_streams",
        title=gettext_lazy("Catch up on a stream"),
        description=gettext_lazy(
            "Messages sent to a stream are seen by everyone subscribed "
            "to that stream. Try clicking on one of the stream links below."
        ),
    ),
    Hotspot(
        name="intro_topics",
        title=gettext_lazy("Topics"),
        description=gettext_lazy(
            "Every message has a topic. Topics keep conversations "
            "easy to follow, and make it easy to reply to conversations that start "
            "while you are offline."
        ),
    ),
    Hotspot(
        # In theory, this should be renamed to intro_personal, since
        # it's no longer attached to the gear menu, but renaming these
        # requires a migration that is not worth doing at this time.
        name="intro_gear",
        title=gettext_lazy("Settings"),
        description=gettext_lazy("Go to Settings to configure your notifications and preferences."),
    ),
    Hotspot(
        name="intro_compose",
        title=gettext_lazy("Compose"),
        description=gettext_lazy(
            "Click here to start a new conversation. Pick a topic "
            "(2-3 words is best), and give it a go!"
        ),
    ),
]


NON_INTRO_HOTSPOTS: List[Hotspot] = []

# We would most likely implement new hotspots in the future that aren't
# a part of the initial tutorial. To that end, classifying them into
# categories which are aggregated in ALL_HOTSPOTS, seems like a good start.
ALL_HOTSPOTS = [*INTRO_HOTSPOTS, *NON_INTRO_HOTSPOTS]


def get_next_hotspots(user: UserProfile) -> List[Dict[str, Union[str, float, bool]]]:
    # For manual testing, it can be convenient to set
    # ALWAYS_SEND_ALL_HOTSPOTS=True in `zproject/dev_settings.py` to
    # make it easy to click on all of the hotspots.
    #
    # Since this is just for development purposes, it's convenient for us to send
    # all the hotspots rather than any specific category.
    if settings.ALWAYS_SEND_ALL_HOTSPOTS:
        return [hotspot.to_dict() for hotspot in ALL_HOTSPOTS]

    # If a Zulip server has disabled the tutorial, never send hotspots.
    if not settings.TUTORIAL_ENABLED:
        return []

    seen_hotspots = frozenset(
        UserHotspot.objects.filter(user=user).values_list("hotspot", flat=True)
    )

    hotspots = [hotspot.to_dict() for hotspot in NON_INTRO_HOTSPOTS]

    if user.tutorial_status == UserProfile.TUTORIAL_FINISHED:
        return hotspots

    for hotspot in INTRO_HOTSPOTS:
        if hotspot.name in seen_hotspots:
            continue

        hotspots.append(hotspot.to_dict(delay=0.5))
        return hotspots

    user.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user.save(update_fields=["tutorial_status"])
    return hotspots


def copy_hotspots(source_profile: UserProfile, target_profile: UserProfile) -> None:
    for userhotspot in frozenset(UserHotspot.objects.filter(user=source_profile)):
        UserHotspot.objects.create(
            user=target_profile, hotspot=userhotspot.hotspot, timestamp=userhotspot.timestamp
        )

    target_profile.tutorial_status = source_profile.tutorial_status
    target_profile.onboarding_steps = source_profile.onboarding_steps
    target_profile.save(update_fields=["tutorial_status", "onboarding_steps"])
