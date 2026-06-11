"""Internal API endpoints for task-owned chat streams."""

import json
import logging
import uuid
from typing import Annotated, cast

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, Field, ValidationError

from nodl.api.views.internal import require_service_auth
from nodl.extensions.models import (
    NodlRealmExtension,
    NodlRealmUserExtension,
    NodlTaskStreamExtension,
    NodlUserExtension,
)
from zerver.actions.create_user import do_create_user
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_deactivate_stream,
)
from zerver.lib.streams import create_stream_if_needed
from zerver.models import Realm, Stream, Subscription, UserProfile

logger = logging.getLogger(__name__)


class TaskStreamMemberPayload(BaseModel):
    supabase_user_id: Annotated[str, Field(description="Supabase user UUID")]
    email: Annotated[str, Field(description="User email address")]
    full_name: Annotated[str | None, Field(default=None, description="Display name")]
    avatar_url: Annotated[str | None, Field(default=None, description="Avatar URL")]
    role: Annotated[str | None, Field(default=None, description="Task participant role")]


class TaskStreamSyncPayload(BaseModel):
    workspace_id: str
    task_id: str
    stream_name: str
    task_title: str | None = None
    privacy_tag: str | None = None
    members: list[TaskStreamMemberPayload] = Field(default_factory=list)


class TaskStreamSubscribersPayload(BaseModel):
    workspace_id: str
    task_id: str
    zulip_stream_id: int
    add: list[TaskStreamMemberPayload] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class TaskStreamArchivePayload(BaseModel):
    workspace_id: str
    task_id: str
    zulip_stream_id: int
    task_title: str | None = None


def _parse_payload[PayloadT: BaseModel](
    request: HttpRequest, payload_type: type[PayloadT]
) -> PayloadT | JsonResponse:
    try:
        body = json.loads(request.body)
        return payload_type(**body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as exc:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(exc)},
            status=400,
        )


def _get_realm(workspace_id: str) -> Realm:
    workspace_uuid = uuid.UUID(workspace_id)
    extension = cast(
        NodlRealmExtension,
        NodlRealmExtension.objects.select_related("zulip_realm").get(
            nodl_workspace_id=workspace_uuid
        ),
    )
    return cast(Realm, extension.zulip_realm)


def _resolve_realm_user(realm: Realm, member: TaskStreamMemberPayload) -> UserProfile:
    """Resolve a Supabase user inside the target realm without re-homing globals."""
    supabase_uuid = uuid.UUID(member.supabase_user_id)
    existing_mapping = (
        NodlRealmUserExtension.objects.select_related("zulip_user")
        .filter(zulip_realm=realm, supabase_user_id=supabase_uuid)
        .first()
    )
    if existing_mapping and existing_mapping.zulip_user.realm_id == realm.id:
        return cast(UserProfile, existing_mapping.zulip_user)

    global_mapping = (
        NodlUserExtension.objects.select_related("zulip_user")
        .filter(supabase_user_id=supabase_uuid, zulip_user__realm=realm)
        .first()
    )
    user: UserProfile | None
    if global_mapping and global_mapping.zulip_user:
        user = cast(UserProfile, global_mapping.zulip_user)
    else:
        user = cast(
            UserProfile | None,
            UserProfile.objects.filter(
                realm=realm,
                delivery_email__iexact=member.email,
                is_active=True,
            ).first(),
        )

    if not user:
        user = cast(
            UserProfile,
            do_create_user(
                email=member.email,
                password=None,
                realm=realm,
                full_name=member.full_name or member.email,
                role=UserProfile.ROLE_MEMBER,
                acting_user=None,
            ),
        )

    NodlRealmUserExtension.objects.update_or_create(
        zulip_realm=realm,
        supabase_user_id=supabase_uuid,
        defaults={"zulip_user": user, "last_synced_at": timezone.now()},
    )
    return user


def _resolve_members(realm: Realm, members: list[TaskStreamMemberPayload]) -> list[UserProfile]:
    users: dict[int, UserProfile] = {}
    for member in members:
        user = _resolve_realm_user(realm, member)
        if user.realm_id != realm.id:
            raise ValueError("Resolved user belongs to a different realm")
        users[user.id] = user
    return list(users.values())


def _set_task_subscription_preferences(stream: Stream, users: list[UserProfile]) -> None:
    if not users:
        return
    Subscription.objects.filter(
        recipient=stream.recipient,
        user_profile__in=users,
        active=True,
    ).update(is_muted=True, pin_to_top=False)


def _get_task_stream(
    payload: TaskStreamArchivePayload | TaskStreamSubscribersPayload,
) -> NodlTaskStreamExtension:
    return cast(
        NodlTaskStreamExtension,
        NodlTaskStreamExtension.objects.select_related("zulip_stream", "zulip_realm").get(
            nodl_workspace_id=uuid.UUID(payload.workspace_id),
            nodl_task_id=uuid.UUID(payload.task_id),
            zulip_stream_id=payload.zulip_stream_id,
        ),
    )


def _clean_task_title(task_title: str | None) -> str:
    return (task_title or "").strip()[:500]


@csrf_exempt  # type: ignore[untyped-decorator]
@require_service_auth  # type: ignore[untyped-decorator]
def sync_task_stream(request: HttpRequest) -> HttpResponse:
    """Create/reuse a private task stream and subscribe task participants."""
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    payload = _parse_payload(request, TaskStreamSyncPayload)
    if isinstance(payload, JsonResponse):
        return payload

    try:
        realm = _get_realm(payload.workspace_id)
        task_uuid = uuid.UUID(payload.task_id)
        existing = (
            NodlTaskStreamExtension.objects.select_related("zulip_stream")
            .filter(nodl_task_id=task_uuid)
            .first()
        )
        if existing:
            stream = existing.zulip_stream
            created = False
            task_title = _clean_task_title(payload.task_title)
            if task_title and existing.task_title != task_title:
                existing.task_title = task_title
                existing.save(update_fields=["task_title"])
        else:
            stream, created = create_stream_if_needed(
                realm,
                payload.stream_name,
                invite_only=True,
                stream_description=f"Task discussion {payload.task_id}",
                history_public_to_subscribers=False,
                acting_user=None,
            )
            NodlTaskStreamExtension.objects.create(
                zulip_realm=realm,
                zulip_stream=stream,
                nodl_workspace_id=uuid.UUID(payload.workspace_id),
                nodl_task_id=task_uuid,
                task_title=_clean_task_title(payload.task_title),
            )

        users = _resolve_members(realm, payload.members)
        if users:
            bulk_add_subscriptions(
                realm,
                [stream],
                users,
                from_user_creation=True,
                acting_user=None,
            )
            _set_task_subscription_preferences(stream, users)

        return JsonResponse(
            {
                "result": "success",
                "zulip_stream_id": stream.id,
                "stream_name": stream.name,
                "created": created,
            },
            status=200,
        )
    except NodlRealmExtension.DoesNotExist:
        return JsonResponse(
            {"result": "error", "code": "REALM_NOT_FOUND", "msg": "Workspace realm not found"},
            status=404,
        )
    except Exception as exc:
        logger.exception("task_stream_sync_failed")
        return JsonResponse(
            {"result": "error", "code": "SYNC_FAILED", "msg": str(exc)},
            status=500,
        )


@csrf_exempt  # type: ignore[untyped-decorator]
@require_service_auth  # type: ignore[untyped-decorator]
def sync_task_stream_subscribers(request: HttpRequest) -> HttpResponse:
    """Idempotently add/remove task stream subscribers."""
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    payload = _parse_payload(request, TaskStreamSubscribersPayload)
    if isinstance(payload, JsonResponse):
        return payload

    try:
        extension = _get_task_stream(payload)
        realm = extension.zulip_realm
        stream = extension.zulip_stream

        add_users = _resolve_members(realm, payload.add)
        if add_users:
            bulk_add_subscriptions(
                realm,
                [stream],
                add_users,
                from_user_creation=True,
                acting_user=None,
            )
            _set_task_subscription_preferences(stream, add_users)

        remove_users = list(
            UserProfile.objects.filter(
                nodl_realm_user_extension__zulip_realm=realm,
                nodl_realm_user_extension__supabase_user_id__in=[
                    uuid.UUID(user_id) for user_id in payload.remove
                ],
                realm=realm,
            )
        )
        if remove_users:
            bulk_remove_subscriptions(realm, remove_users, [stream], acting_user=None)

        return JsonResponse(
            {
                "result": "success",
                "added": len(add_users),
                "removed": len(remove_users),
            },
            status=200,
        )
    except NodlTaskStreamExtension.DoesNotExist:
        return JsonResponse(
            {"result": "error", "code": "TASK_STREAM_NOT_FOUND", "msg": "Task stream not found"},
            status=404,
        )
    except Exception as exc:
        logger.exception("task_stream_subscribers_failed")
        return JsonResponse(
            {"result": "error", "code": "SUBSCRIBER_SYNC_FAILED", "msg": str(exc)},
            status=500,
        )


@csrf_exempt  # type: ignore[untyped-decorator]
@require_service_auth  # type: ignore[untyped-decorator]
def archive_task_stream(request: HttpRequest) -> HttpResponse:
    """Archive a task-owned stream idempotently."""
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    payload = _parse_payload(request, TaskStreamArchivePayload)
    if isinstance(payload, JsonResponse):
        return payload

    try:
        extension = _get_task_stream(payload)
        stream = extension.zulip_stream
        if not stream.deactivated:
            do_deactivate_stream(stream, acting_user=None)
        task_title = _clean_task_title(payload.task_title)
        update_fields = []
        if task_title and extension.task_title != task_title:
            extension.task_title = task_title
            update_fields.append("task_title")
        if extension.archived_at is None:
            extension.archived_at = timezone.now()
            update_fields.append("archived_at")
        if update_fields:
            extension.save(update_fields=update_fields)
        return JsonResponse({"result": "success", "archived": True}, status=200)
    except NodlTaskStreamExtension.DoesNotExist:
        return JsonResponse({"result": "success", "archived": True}, status=200)
    except Exception as exc:
        logger.exception("task_stream_archive_failed")
        return JsonResponse(
            {"result": "error", "code": "ARCHIVE_FAILED", "msg": str(exc)},
            status=500,
        )
