from typing import Any

from django.db import transaction
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import ResourceNotFoundError
from zerver.models import RealmAuditLog, SavedSnippet, UserProfile
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.tornado.django_api import send_event_on_commit


@transaction.atomic(durable=True)
def do_create_saved_snippet(
    title: str,
    content: str,
    user_profile: UserProfile,
) -> SavedSnippet:
    saved_snippet = SavedSnippet.objects.create(
        realm=user_profile.realm,
        user_profile=user_profile,
        title=title,
        content=content,
    )

    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=AuditLogEventType.SAVED_SNIPPET_CREATED,
        event_time=timezone_now(),
        extra_data={"saved_snippet_id": saved_snippet.id},
    )

    event = {
        "type": "saved_snippets",
        "op": "add",
        "saved_snippet": saved_snippet.to_api_dict(),
    }
    send_event_on_commit(user_profile.realm, event, [user_profile.id])

    return saved_snippet


def do_edit_saved_snippet(
    saved_snippet_id: int,
    title: str | None,
    content: str | None,
    user_profile: UserProfile,
) -> SavedSnippet:
    try:
        saved_snippet = SavedSnippet.objects.get(id=saved_snippet_id, user_profile=user_profile)
    except SavedSnippet.DoesNotExist:
        raise ResourceNotFoundError(_("Saved snippet does not exist."))

    if title is not None:
        saved_snippet.title = title
    if content is not None:
        saved_snippet.content = content

    with transaction.atomic(durable=True):
        saved_snippet.save()

        event = {
            "type": "saved_snippets",
            "op": "update",
            "saved_snippet": saved_snippet.to_api_dict(),
        }
        send_event_on_commit(user_profile.realm, event, [user_profile.id])

    return saved_snippet


def do_get_saved_snippets(user_profile: UserProfile) -> list[dict[str, Any]]:
    saved_snippets = SavedSnippet.objects.filter(user_profile=user_profile)

    return [saved_snippet.to_api_dict() for saved_snippet in saved_snippets]


def do_delete_saved_snippet(
    saved_snippet_id: int,
    user_profile: UserProfile,
) -> None:
    try:
        saved_snippet = SavedSnippet.objects.get(id=saved_snippet_id, user_profile=user_profile)
    except SavedSnippet.DoesNotExist:
        raise ResourceNotFoundError(_("Saved snippet does not exist."))
    saved_snippet.delete()

    event = {"type": "saved_snippets", "op": "remove", "saved_snippet_id": saved_snippet_id}
    send_event_on_commit(user_profile.realm, event, [user_profile.id])
