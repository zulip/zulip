from zerver.lib.hotspots import get_next_hotspots
from zerver.models import OnboardingStep, UserProfile
from zerver.tornado.django_api import send_event


def do_mark_onboarding_step_as_read(user: UserProfile, onboarding_step: str) -> None:
    OnboardingStep.objects.get_or_create(user=user, onboarding_step=onboarding_step)
    event = dict(type="hotspots", hotspots=get_next_hotspots(user))
    send_event(user.realm, event, [user.id])
