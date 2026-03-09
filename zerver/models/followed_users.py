from django.db import models
from django.db.models import CASCADE
from django.db.models.signals import post_delete, post_save
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.lib.cache import flush_following_users_cache
from zerver.models.users import UserProfile


class FollowedUser(models.Model):
    user_profile = models.ForeignKey(UserProfile, related_name="follower", on_delete=CASCADE)
    followed_user = models.ForeignKey(UserProfile, related_name="followed", on_delete=CASCADE)
    date_followed = models.DateTimeField(default=timezone_now)

    class Meta:
        unique_together = ("user_profile", "followed_user")

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.email} -> {self.followed_user.email}"


post_save.connect(flush_following_users_cache, sender=FollowedUser)
post_delete.connect(flush_following_users_cache, sender=FollowedUser)
