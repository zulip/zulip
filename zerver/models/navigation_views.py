from django.db import models
from django.db.models import CASCADE

from zerver.models.users import UserProfile


class NavigationView(models.Model):
    """
    Represents a user's configuration for pinned views in the left sidebar,
    allowing views to be pinned or hidden.
    """

    # Reference to the user who owns this pinned view configuration.
    user = models.ForeignKey(UserProfile, on_delete=CASCADE)

    # A unique URL hash identifier for the view (e.g., 'inbox', 'narrow/has/reactions'),
    # used for navigation and identification of the view.
    fragment = models.TextField()

    # Whether the view is pinned (True) or hidden in the menu (False).
    is_pinned = models.BooleanField(default=False)

    # Optional display name of the view, provided by the user for custom views.
    name = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("user", "fragment")
