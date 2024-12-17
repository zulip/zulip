from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import BaseModel, ConfigDict, Json, StringConstraints, model_validator

from zerver.actions.pinned_views import (
    do_add_pinned_view,
    do_get_pinned_views,
    do_remove_pinned_view,
    do_update_pinned_view,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

BUILT_IN_VIEW_URL_HASH = [
    "inbox",
    "recent",
    "feed",
    "drafts",
    "narrow/has/reaction/sender/me",  # Reactions
    "narrow/is/mentioned",  # Mentions
    "narrow/is/starred",  # Starred messages
]


class PinnedViewBaseModel(BaseModel):
    """
    Base model for pinned view operations with shared validation logic.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    url_hash: str


class AddPinnedViewModel(PinnedViewBaseModel):
    """
    Model for adding a new pinned view with validation.
    """

    is_pinned: bool
    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_pinned_view_add(
        cls, values: dict[str, str | bool | None]
    ) -> dict[str, str | bool | None]:
        url_hash = values.get("url_hash")
        name = values.get("name")
        if url_hash in BUILT_IN_VIEW_URL_HASH:
            if name is not None:
                raise JsonableError(_("Built-in views cannot have a custom name"))
        else:
            if not name or name == "":
                raise JsonableError(_("Custom views must have a valid name"))

        return values


class UpdatePinnedViewModel(PinnedViewBaseModel):
    """
    Model for updating an existing pinned view with validation.
    """

    name: str | None = None
    is_pinned: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_pinned_view_update(
        cls, values: dict[str, str | bool | None]
    ) -> dict[str, str | bool | None]:
        url_hash = values.get("url_hash")
        name = values.get("name")

        if url_hash in BUILT_IN_VIEW_URL_HASH and name is not None:
            raise JsonableError(_("Built-in views cannot have a custom name"))

        return values


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
    url_hash: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    is_pinned: Json[bool],
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None,
) -> HttpResponse:
    """
    Add a new pinned view for the user.
    """
    validated_data = AddPinnedViewModel(url_hash=url_hash, is_pinned=is_pinned, name=name)

    pinned_view = do_add_pinned_view(
        user_profile, validated_data.url_hash, validated_data.is_pinned, validated_data.name
    )
    return json_success(request, data={"url_hash": pinned_view.url_hash})


@typed_endpoint
def update_pinned_view(
    request: HttpRequest,
    user_profile: UserProfile,
    url_hash: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
    *,
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None,
    is_pinned: Json[bool] | None = None,
) -> HttpResponse:
    """
    Update an existing pinned view for the user.
    """
    validated_data = UpdatePinnedViewModel(url_hash=url_hash, name=name, is_pinned=is_pinned)

    pinned_view = do_update_pinned_view(
        user_profile, validated_data.url_hash, validated_data.is_pinned, validated_data.name
    )
    return json_success(request, data={"url_hash": pinned_view.url_hash})


def remove_pinned_view(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    url_hash: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)],
) -> HttpResponse:
    """
    Remove a pinned view for the user.
    """
    do_remove_pinned_view(user_profile, url_hash)
    return json_success(request)
