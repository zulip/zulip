from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, StringConstraints

from zerver.actions.navigation_views import (
    do_add_navigation_view,
    do_get_navigation_views,
    do_remove_navigation_view,
    do_update_navigation_view,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

BUILT_IN_VIEW_FRAGMENT = [
    "inbox",
    "recent",
    "feed",
    "drafts",
    "narrow/has/reaction/sender/me",  # Reactions
    "narrow/is/mentioned",  # Mentions
    "narrow/is/starred",  # Starred messages
]


def get_navigation_views(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """
    Fetch navigation views for the specified user.
    """
    navigation_views = do_get_navigation_views(user_profile)
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
    Add a new navigation view for the user.
    """
    if fragment in BUILT_IN_VIEW_FRAGMENT:
        if name is not None:
            raise JsonableError(_("Built-in views cannot have a custom name."))
    else:
        if not name:
            raise JsonableError(_("Custom views must have a valid name."))

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
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None,
    is_pinned: Json[bool] | None = None,
) -> HttpResponse:
    """
    Update an existing navigation view for the user.
    """
    if fragment in BUILT_IN_VIEW_FRAGMENT and name is not None:
        raise JsonableError(_("Built-in views cannot have a custom name."))

    do_update_navigation_view(
        user_profile,
        fragment,
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
    do_remove_navigation_view(user_profile, fragment)
    return json_success(request)
