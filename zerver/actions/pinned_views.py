from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.models import PinnedView, UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_add_pinned_view(
    user: UserProfile,
    url_hash: str,
    is_pinned: bool,
    name: str | None = None,
) -> PinnedView:
    if PinnedView.objects.filter(user=user, url_hash=url_hash).exists():
        raise JsonableError(_("Pinned view already exists."))

    pinned_view = PinnedView.objects.create(
        user=user,
        url_hash=url_hash,
        is_pinned=is_pinned,
        name=name,
    )

    event = {
        "type": "pinned_views",
        "op": "add",
        "pinned_view": pinned_view.to_api_dict(),
    }
    send_event_on_commit(user.realm, event, [user.id])
    return pinned_view


@transaction.atomic(durable=True)
def do_update_pinned_view(
    user: UserProfile,
    url_hash: str,
    is_pinned: bool | None,
    name: str | None = None,
) -> PinnedView:
    try:
        pinned_view = PinnedView.objects.get(user=user, url_hash=url_hash)
    except PinnedView.DoesNotExist:
        raise ResourceNotFoundError(_("Pinned view does not exist."))

    if name is not None:
        pinned_view.name = name
    if is_pinned is not None:
        pinned_view.is_pinned = is_pinned

    pinned_view.save()

    event = {
        "type": "pinned_views",
        "op": "update",
        "pinned_view": pinned_view.to_api_dict(),
    }
    send_event_on_commit(user.realm, event, [user.id])
    return pinned_view


@transaction.atomic(durable=True)
def do_remove_pinned_view(
    user: UserProfile,
    url_hash: str,
) -> None:
    try:
        pinned_view = PinnedView.objects.get(user=user, url_hash=url_hash)
    except PinnedView.DoesNotExist:
        raise ResourceNotFoundError(_("Pinned view does not exist."))

    pinned_view.delete()

    event = {
        "type": "pinned_views",
        "op": "remove",
        "url_hash": url_hash,
    }
    send_event_on_commit(user.realm, event, [user.id])


def do_get_pinned_views(user: UserProfile) -> list[dict[str, Any]]:
    pinned_views = PinnedView.objects.filter(user=user)
    return [pinned_view.to_api_dict() for pinned_view in pinned_views]
