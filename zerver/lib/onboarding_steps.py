# See https://zulip.readthedocs.io/en/latest/subsystems/onboarding-steps.html
# for documentation on this subsystem.
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from zerver.models import OnboardingStep, UserProfile


@dataclass
class OneTimeNotice:
    name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": "one_time_notice",
            "name": self.name,
        }


@dataclass
class OneTimeAction:
    name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": "one_time_action",
            "name": self.name,
        }


ONE_TIME_NOTICES: list[OneTimeNotice] = [
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
    OneTimeNotice(
        name="jump_to_conversation_banner",
    ),
    OneTimeNotice(
        name="non_interleaved_view_messages_fading",
    ),
    OneTimeNotice(
        name="interleaved_view_messages_fading",
    ),
    OneTimeNotice(
        name="intro_resolve_topic",
    ),
    OneTimeNotice(
        name="navigation_tour_video",
    ),
]

ONE_TIME_ACTIONS = [OneTimeAction(name="narrow_to_dm_with_welcome_bot_new_user")]

ALL_ONBOARDING_STEPS: list[OneTimeNotice | OneTimeAction] = ONE_TIME_NOTICES + ONE_TIME_ACTIONS


def get_next_onboarding_steps(user: UserProfile) -> list[dict[str, Any]]:
    # If a Zulip server has disabled the tutorial, never send any
    # onboarding steps.
    if not settings.TUTORIAL_ENABLED:
        return []

    seen_onboarding_steps: list[str] = list(
        OnboardingStep.objects.filter(user=user).values_list("onboarding_step", flat=True)
    )
    if settings.NAVIGATION_TOUR_VIDEO_URL is None:
        # Server admin disabled navigation tour video, treat it as seen.
        seen_onboarding_steps.append("navigation_tour_video")
    seen_onboarding_steps_set = frozenset(seen_onboarding_steps)

    onboarding_steps: list[dict[str, Any]] = []
    for onboarding_step in ALL_ONBOARDING_STEPS:
        if onboarding_step.name in seen_onboarding_steps_set:
            continue
        onboarding_steps.append(onboarding_step.to_dict())

    return onboarding_steps


def copy_onboarding_steps(source_profile: UserProfile, target_profile: UserProfile) -> None:
    for onboarding_step in frozenset(OnboardingStep.objects.filter(user=source_profile)):
        OnboardingStep.objects.create(
            user=target_profile,
            onboarding_step=onboarding_step.onboarding_step,
            timestamp=onboarding_step.timestamp,
        )
