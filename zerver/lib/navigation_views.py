from typing import TypedDict

from django.utils.translation import gettext as _

from zerver.lib.exceptions import ResourceNotFoundError
from zerver.models import NavigationView, UserProfile


class NavigationViewDict(TypedDict):
    fragment: str
    is_pinned: bool
    name: str | None


def get_navigation_view(user: UserProfile, fragment: str) -> NavigationView:
    try:
        navigation_view = NavigationView.objects.get(user=user, fragment=fragment)
        return navigation_view
    except NavigationView.DoesNotExist:
        raise ResourceNotFoundError(_("Navigation view does not exist."))


def get_navigation_view_dict(navigation_view: NavigationView) -> NavigationViewDict:
    return NavigationViewDict(
        fragment=navigation_view.fragment,
        is_pinned=navigation_view.is_pinned,
        name=navigation_view.name,
    )


def get_navigation_views_for_user(user: UserProfile) -> list[NavigationViewDict]:
    navigation_views = NavigationView.objects.filter(user=user)
    return [get_navigation_view_dict(navigation_view) for navigation_view in navigation_views]
