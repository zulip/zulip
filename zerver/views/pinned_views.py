from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import Json, StringConstraints

from zerver.actions.pinned_views import (
    do_add_pinned_view,
    do_get_pinned_views,
    do_update_pinned_view_location,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile
from zerver.models.pinned_views import LeftSidebarViewLocationEnum


def get_pinned_views(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """
    Fetch pinned views for the specified user.
    """
    pinned_views = do_get_pinned_views(user_profile)
    return json_success(request, data={"pinned_views": pinned_views})


@typed_endpoint
def add_pinned_view(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    view_id: Annotated[str, StringConstraints(strip_whitespace=True)],
    location: Json[int] = LeftSidebarViewLocationEnum.EXPANDED.value,
    name: str | None = None,
    url_hash: str | None = None,
) -> HttpResponse:
    """
    Add a new pinned view for the user.
    """
    view_id = view_id.strip()
    name = name.strip() if name else None
    url_hash = url_hash.strip() if url_hash else None
    pinned_view = do_add_pinned_view(user_profile, view_id, location, name, url_hash)
    return json_success(request, data={"pinned_view_id": pinned_view.view_id})


@typed_endpoint
def update_pinned_view_location(
    request: HttpRequest,
    user_profile: UserProfile,
    view_id: Json[str],
    *,
    location: Json[int],
) -> HttpResponse:
    """
    Update the location of an existing pinned view.
    """
    do_update_pinned_view_location(user_profile, view_id, location)
    return json_success(request)
