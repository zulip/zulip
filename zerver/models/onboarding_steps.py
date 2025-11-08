from django.db import models
from django.db.models import CASCADE
from django.utils.timezone import now as timezone_now

from zerver.models.users import UserProfile


class OnboardingStep(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)
    onboarding_step = models.CharField(max_length=40)
    timestamp = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user", "onboarding_step")
