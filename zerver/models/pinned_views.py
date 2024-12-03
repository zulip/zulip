from enum import IntEnum
from typing import Any

from django.db import models
from django.db.models import CASCADE

from zerver.models.users import UserProfile


class LeftSidebarViewLocationEnum(IntEnum):
    MENU = 1
    EXPANDED = 2


class PinnedView(models.Model):
    """
    Represents a user's configuration for pinned views in the left sidebar, allowing views to be pinned or hidden.
    """

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    view_id = models.TextField()
    location = models.PositiveSmallIntegerField(default=LeftSidebarViewLocationEnum.EXPANDED)
    name = models.TextField(blank=True, null=True)
    url_hash = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("user_profile", "view_id")

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "view_id": self.view_id,
            "location": self.location,
            "name": self.name,
            "url_hash": self.url_hash,
        }
