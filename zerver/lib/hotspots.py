# See https://zulip.readthedocs.io/en/latest/subsystems/hotspots.html
# for documentation on this subsystem.
from typing import Dict, List, Union

from django.conf import settings
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise

from zerver.models import UserHotspot, UserProfile

INTRO_HOTSPOTS: Dict[str, Dict[str, Union[StrPromise, str]]] = {
    "intro_streams": {
        "title": gettext_lazy("Catch up on a stream"),
        "description": gettext_lazy(
            "Messages sent to a stream are seen by everyone subscribed "
            "to that stream. Try clicking on one of the stream links below."
        ),
    },
    "intro_topics": {
        "title": gettext_lazy("Topics"),
        "description": gettext_lazy(
            "Every message has a topic. Topics keep conversations "
            "easy to follow, and make it easy to reply to conversations that start "
            "while you are offline."
        ),
    },
    "intro_gear": {
        "title": gettext_lazy("Settings"),
        "description": gettext_lazy(
            "Go to Settings to configure your notifications and preferences."
        ),
    },
    "intro_compose": {
        "title": gettext_lazy("Compose"),
        "description": gettext_lazy(
            "Click here to start a new conversation. Pick a topic "
            "(2-3 words is best), and give it a go!"
        ),
    },
}


NON_INTRO_HOTSPOTS: Dict[str, Dict[str, Union[StrPromise, str]]] = {}

# We would most likely implement new hotspots in the future that aren't
# a part of the initial tutorial. To that end, classifying them into
# categories which are aggregated in ALL_HOTSPOTS, seems like a good start.
ALL_HOTSPOTS: Dict[str, Dict[str, Union[StrPromise, str, bool]]] = {
    **{
        hotspot_name: {**INTRO_HOTSPOTS[hotspot_name], "has_trigger": False}
        for hotspot_name in INTRO_HOTSPOTS
    },
    **{
        hotspot_name: {**NON_INTRO_HOTSPOTS[hotspot_name], "has_trigger": True}  # type: ignore[arg-type] # reason: Its a temporary hack
        for hotspot_name in NON_INTRO_HOTSPOTS
    },
}


def get_next_hotspots(user: UserProfile) -> List[Dict[str, object]]:
    # For manual testing, it can be convenient to set
    # ALWAYS_SEND_ALL_HOTSPOTS=True in `zproject/dev_settings.py` to
    # make it easy to click on all of the hotspots.
    #
    # Since this is just for development purposes, it's convenient for us to send
    # all the hotspots rather than any specific category.
    if settings.ALWAYS_SEND_ALL_HOTSPOTS:
        return [
            {
                **base_hotspot,
                "name": name,
                "title": str(base_hotspot["title"]),
                "description": str(base_hotspot["description"]),
                "delay": 0,
            }
            for name, base_hotspot in ALL_HOTSPOTS.items()
        ]

    # If a Zulip server has disabled the tutorial, never send hotspots.
    if not settings.TUTORIAL_ENABLED:
        return []

    seen_hotspots = frozenset(
        UserHotspot.objects.filter(user=user).values_list("hotspot", flat=True)
    )

    hotspots = []

    for name, base_hotspot in NON_INTRO_HOTSPOTS.items():
        if name in seen_hotspots:
            continue

        hotspot = {
            **base_hotspot,
            "name": name,
            "title": str(base_hotspot["title"]),
            "description": str(base_hotspot["description"]),
            "delay": 0,
            "has_trigger": True,
        }
        hotspots.append(hotspot)

    if user.tutorial_status == UserProfile.TUTORIAL_FINISHED:
        return hotspots

    for name, base_hotspot in INTRO_HOTSPOTS.items():
        if name in seen_hotspots:
            continue

        # Make a copy to set delay and finalize i18n strings.
        hotspot = {
            **base_hotspot,
            "name": name,
            "title": str(base_hotspot["title"]),
            "description": str(base_hotspot["description"]),
            "delay": 0.5,
            "has_trigger": False,
        }
        hotspots.append(hotspot)
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
