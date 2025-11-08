from django.db import models
from django.db.models import CASCADE
from django.db.models.signals import post_delete, post_save
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.cache import flush_muting_users_cache
from zerver.models.users import UserProfile


class MutedUser(models.Model):
    user_profile = models.ForeignKey(UserProfile, related_name="muter", on_delete=CASCADE)
    muted_user = models.ForeignKey(UserProfile, related_name="muted", on_delete=CASCADE)
    date_muted = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user_profile", "muted_user")

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} -> {self.muted_user.email}"


post_save.connect(flush_muting_users_cache, sender=MutedUser)
post_delete.connect(flush_muting_users_cache, sender=MutedUser)
