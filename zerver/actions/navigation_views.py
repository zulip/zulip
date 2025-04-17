from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError, ResourceNotFoundError
from zerver.models import NavigationView, UserProfile
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_add_navigation_view(
    user: UserProfile,
    fragment: str,
    is_pinned: bool,
    name: str | None = None,
) -> None:
    if NavigationView.objects.filter(user=user, fragment=fragment).exists():
        raise JsonableError(_("Navigation view already exists."))

    navigation_view = NavigationView.objects.create(
        user=user,
        fragment=fragment,
        is_pinned=is_pinned,
        name=name,
    )

    event = {
        "type": "navigation_view",
        "op": "add",
        "navigation_view": navigation_view.to_api_dict(),
    }
    send_event_on_commit(user.realm, event, [user.id])


@transaction.atomic(durable=True)
def do_update_navigation_view(
    user: UserProfile,
    fragment: str,
    is_pinned: bool | None,
    name: str | None = None,
) -> None:
    try:
        navigation_view = NavigationView.objects.get(user=user, fragment=fragment)
    except NavigationView.DoesNotExist:
        raise ResourceNotFoundError(_("Navigation view does not exist."))

    update_dict: dict[str, str | bool] = {}
    if name is not None:
        navigation_view.name = name
        update_dict["name"] = name
    if is_pinned is not None:
        navigation_view.is_pinned = is_pinned
        update_dict["is_pinned"] = is_pinned

    navigation_view.save()

    event = {
        "type": "navigation_view",
        "op": "update",
        "fragment": fragment,
        "data": update_dict,
    }
    send_event_on_commit(user.realm, event, [user.id])


@transaction.atomic(durable=True)
def do_remove_navigation_view(
    user: UserProfile,
    fragment: str,
) -> None:
    try:
        navigation_view = NavigationView.objects.get(user=user, fragment=fragment)
    except NavigationView.DoesNotExist:
        raise ResourceNotFoundError(_("Navigation view does not exist."))

    navigation_view.delete()

    event = {
        "type": "navigation_view",
        "op": "remove",
        "fragment": fragment,
    }
    send_event_on_commit(user.realm, event, [user.id])


def do_get_navigation_views(user: UserProfile) -> list[dict[str, Any]]:
    navigation_views = NavigationView.objects.filter(user=user)
    return [navigation_view.to_api_dict() for navigation_view in navigation_views]
