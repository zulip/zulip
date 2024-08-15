from django.db import transaction

from zerver.lib.onboarding_steps import get_next_onboarding_steps
from zerver.models import OnboardingStep, UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_mark_onboarding_step_as_read(user: UserProfile, onboarding_step: str) -> None:
    OnboardingStep.objects.get_or_create(user=user, onboarding_step=onboarding_step)
    event = dict(type="onboarding_steps", onboarding_steps=get_next_onboarding_steps(user))
    send_event_on_commit(user.realm, event, [user.id])
