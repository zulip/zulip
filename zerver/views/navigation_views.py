from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import BaseModel, ConfigDict, Json, StringConstraints, model_validator

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


class NavigationViewBaseModel(BaseModel):
    """
    Base model for navigation view operations with shared validation logic.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    fragment: str


class AddNavigationViewModel(NavigationViewBaseModel):
    """
    Model for adding a new navigation view with validation.
    """

    is_pinned: bool
    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_navigation_view_add(
        cls, values: dict[str, str | bool | None]
    ) -> dict[str, str | bool | None]:
        fragment = values.get("fragment")
        name = values.get("name")
        if fragment in BUILT_IN_VIEW_FRAGMENT:
            if name is not None:
                raise JsonableError(_("Built-in views cannot have a custom name"))
        else:
            if not name or name == "":
                raise JsonableError(_("Custom views must have a valid name"))
        return values


class UpdateNavigationViewModel(NavigationViewBaseModel):
    """
    Model for updating an existing navigation view with validation.
    """

    name: str | None = None
    is_pinned: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_navigation_view_update(
        cls, values: dict[str, str | bool | None]
    ) -> dict[str, str | bool | None]:
        fragment = values.get("fragment")
        name = values.get("name")
        if fragment in BUILT_IN_VIEW_FRAGMENT and name is not None:
            raise JsonableError(_("Built-in views cannot have a custom name"))
        return values


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
    # Instantiate using keyword arguments.
    validated_data = AddNavigationViewModel(fragment=fragment, is_pinned=is_pinned, name=name)

    navigation_view = do_add_navigation_view(
        user_profile,
        validated_data.fragment,
        validated_data.is_pinned,
        validated_data.name,
    )
    return json_success(request, data={"fragment": navigation_view.fragment})


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
    # Instantiate using keyword arguments.
    validated_data = UpdateNavigationViewModel(fragment=fragment, name=name, is_pinned=is_pinned)

    navigation_view = do_update_navigation_view(
        user_profile,
        validated_data.fragment,
        validated_data.is_pinned,
        validated_data.name,
    )
    return json_success(request, data={"fragment": navigation_view.fragment})


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
