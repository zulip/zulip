# See https://zulip.readthedocs.io/en/latest/subsystems/hotspots.html
# for documentation on this subsystem.
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.utils.translation import gettext_lazy
from django_stubs_ext import StrPromise

from zerver.models import OnboardingStep, UserProfile


@dataclass
class Hotspot:
    name: str
    title: Optional[StrPromise]
    description: Optional[StrPromise]
    has_trigger: bool = False

    def to_dict(self, delay: float = 0) -> Dict[str, Union[str, float, bool]]:
        return {
            "type": "hotspot",
            "name": self.name,
            "title": str(self.title),
            "description": str(self.description),
            "delay": delay,
            "has_trigger": self.has_trigger,
        }


INTRO_HOTSPOTS: List[Hotspot] = [
    Hotspot(
        name="intro_streams",
        title=gettext_lazy("Catch up on a channel"),
        description=gettext_lazy(
            "Messages sent to a channel are seen by everyone subscribed "
            "to that channel. Try clicking on one of the channel links below."
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


@dataclass
class OneTimeNotice:
    name: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "type": "one_time_notice",
            "name": self.name,
        }


ONE_TIME_NOTICES: List[OneTimeNotice] = [
    OneTimeNotice(
        name="visibility_policy_banner",
    ),
    OneTimeNotice(
        name="intro_inbox_view_modal",
    ),
    OneTimeNotice(
        name="intro_recent_view_modal",
    ),
    OneTimeNotice(
        name="first_stream_created_banner",
    ),
]

# We would most likely implement new hotspots in the future that aren't
# a part of the initial tutorial. To that end, classifying them into
# categories which are aggregated in ALL_HOTSPOTS, seems like a good start.
ALL_HOTSPOTS = [*INTRO_HOTSPOTS, *NON_INTRO_HOTSPOTS]
ALL_ONBOARDING_STEPS: List[Union[Hotspot, OneTimeNotice]] = [*ALL_HOTSPOTS, *ONE_TIME_NOTICES]


def get_next_onboarding_steps(user: UserProfile) -> List[Dict[str, Any]]:
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

    seen_onboarding_steps = frozenset(
        OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
    )

    onboarding_steps: List[Dict[str, Any]] = [hotspot.to_dict() for hotspot in NON_INTRO_HOTSPOTS]

    for one_time_notice in ONE_TIME_NOTICES:
        if one_time_notice.name in seen_onboarding_steps:
            continue
        onboarding_steps.append(one_time_notice.to_dict())

    if user.tutorial_status == UserProfile.TUTORIAL_FINISHED:
        return onboarding_steps

    for hotspot in INTRO_HOTSPOTS:
        if hotspot.name in seen_onboarding_steps:
            continue

        onboarding_steps.append(hotspot.to_dict(delay=0.5))
        return onboarding_steps

    user.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user.save(update_fields=["tutorial_status"])
    return onboarding_steps


def copy_hotspots(source_profile: UserProfile, target_profile: UserProfile) -> None:
    for userhotspot in frozenset(OnboardingStep.objects.filter(user=source_profile)):
        OnboardingStep.objects.create(
            user=target_profile,
            onboarding_step=userhotspot.onboarding_step,
            timestamp=userhotspot.timestamp,
        )

    target_profile.tutorial_status = source_profile.tutorial_status
    target_profile.onboarding_steps = source_profile.onboarding_steps
    target_profile.save(update_fields=["tutorial_status", "onboarding_steps"])
