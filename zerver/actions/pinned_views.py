from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.models import PinnedView, UserProfile
from zerver.models.pinned_views import LeftSidebarViewLocationEnum
from zerver.tornado.django_api import send_event_on_commit

VALID_VIEW_IDS = ["inbox", "recent", "reactions", "mentions", "feed", "drafts", "starred"]


def validate_sidebar_location(location: int) -> None:
    if location not in LeftSidebarViewLocationEnum.__members__.values():
        raise JsonableError(_("Invalid location."))


def validate_sidebar_view_id(view_id: str) -> None:
    if view_id not in VALID_VIEW_IDS:
        raise JsonableError(_("Invalid view_id."))


@transaction.atomic(durable=True)
def do_add_pinned_view(
    user_profile: UserProfile,
    view_id: str,
    location: int,
    name: str | None = None,
    url_hash: str | None = None,
) -> PinnedView:
    validate_sidebar_location(location)
    validate_sidebar_view_id(view_id)

    if PinnedView.objects.filter(user_profile=user_profile, view_id=view_id).exists():
        raise JsonableError(_("Pinned view already exists."))

    pinned_view = PinnedView.objects.create(
        user_profile=user_profile,
        view_id=view_id,
        location=location,
        name=name,
        url_hash=url_hash,
    )

    event = {
        "type": "pinned_views",
        "op": "add",
        "pinned_view": pinned_view.to_api_dict(),
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])

    return pinned_view


def do_get_pinned_views(user_profile: UserProfile) -> list[dict[str, Any]]:
    pinned_views = PinnedView.objects.filter(user_profile=user_profile)

    return [pinned_view.to_api_dict() for pinned_view in pinned_views]


def do_update_pinned_view_location(
    user_profile: UserProfile,
    view_id: str,
    target_location: int,
) -> None:
    try:
        pinned_view = PinnedView.objects.get(user_profile=user_profile, view_id=view_id)
    except PinnedView.DoesNotExist:
        raise ResourceNotFoundError(_("Pinned view does not exist."))

    if target_location not in LeftSidebarViewLocationEnum.__members__.values():
        raise JsonableError(_("Invalid location."))

    pinned_view.location = target_location
    pinned_view.save(update_fields=["location"])

    event = {
        "type": "pinned_views",
        "op": "update",
        "pinned_view": pinned_view.to_api_dict(),
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
