from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from zerver.actions.navigation_views import (
    do_add_navigation_view,
    do_remove_navigation_view,
    do_update_navigation_view,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.navigation_views import get_navigation_view, get_navigation_views_for_user
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import NavigationView, UserProfile

BUILT_IN_VIEW_FRAGMENTS = [
    "inbox",
    "recent",
    "feed",
    "drafts",
    # Reactions view
    "narrow/has/reaction/sender/me",
    # Mentions view
    "narrow/is/mentioned",
    # Starred messages view
    "narrow/is/starred",
    "scheduled",
]


def get_navigation_views(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """
    Fetch navigation views for the specified user.
    """
    navigation_views = get_navigation_views_for_user(user_profile)
    return json_success(request, data={"navigation_views": navigation_views})


@typed_endpoint
def add_navigation_view(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    fragment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    is_pinned: Json[bool],
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None,
) -> HttpResponse:
    """
    Add a new navigation view (or settings for a default view) for the user.
    """
    if fragment in BUILT_IN_VIEW_FRAGMENTS:
        if name is not None:
            raise JsonableError(_("Built-in views cannot have a custom name."))
    else:
        if not name:
            raise JsonableError(_("Custom views must have a valid name."))

    if NavigationView.objects.filter(user=user_profile, fragment=fragment).exists():
        raise JsonableError(_("Navigation view already exists."))
    if name is not None and NavigationView.objects.filter(user=user_profile, name=name).exists():
        raise JsonableError(_("Navigation view already exists."))

    do_add_navigation_view(
        user_profile,
        fragment,
        is_pinned,
        name,
    )
    return json_success(request)


@typed_endpoint
def update_navigation_view(
    request: HttpRequest,
    user_profile: UserProfile,
    fragment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    *,
    is_pinned: Json[bool] | None = None,
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None,
) -> HttpResponse:
    """
    Update an existing navigation view for the user.
    """
    if fragment in BUILT_IN_VIEW_FRAGMENTS and name is not None:
        raise JsonableError(_("Built-in views cannot have a custom name."))
    if name is not None and NavigationView.objects.filter(user=user_profile, name=name).exists():
        raise JsonableError(_("Navigation view already exists."))

    navigation_view = get_navigation_view(user_profile, fragment)

    do_update_navigation_view(
        user_profile,
        navigation_view,
        is_pinned,
        name,
    )
    return json_success(request)


def remove_navigation_view(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    fragment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
) -> HttpResponse:
    """
    Remove a navigation view for the user.
    """
    navigation_view = get_navigation_view(user_profile, fragment)
    do_remove_navigation_view(user_profile, navigation_view)
    return json_success(request)
