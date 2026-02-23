"""API views for nodl internal endpoints.

These endpoints are called by nodl-backend (service-to-service) and use
Bearer token authentication (CHAT_SERVICE_KEY), not browser sessions.
CSRF protection is disabled as it's designed for browser-based attacks
and doesn't apply to API-to-API calls with Authorization headers.
"""

import json
import logging
from functools import wraps
from typing import Annotated

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, Field, ValidationError

from nodl.sync.user_sync import UserSyncRequest, UserSyncResult, UserSyncService
from nodl.sync.workspace_sync import (
    WorkspaceSyncRequest,
    WorkspaceSyncResult,
    WorkspaceSyncService,
)

logger = logging.getLogger(__name__)


class UserSyncPayload(BaseModel):
    """Request payload for user sync endpoint."""

    supabase_user_id: Annotated[str, Field(description="Supabase user UUID")]
    email: Annotated[str, Field(description="User email address")]
    full_name: Annotated[str, Field(description="User full name")]
    avatar_url: Annotated[str | None, Field(default=None, description="User avatar URL")]
    workspace_id: Annotated[str, Field(description="nodl workspace UUID")]
    role: Annotated[str, Field(description="User role: owner, admin, editor, viewer")]


class MemberPayload(BaseModel):
    """Member data within a workspace sync request."""

    supabase_user_id: Annotated[str, Field(description="Supabase user UUID")]
    email: Annotated[str, Field(description="User email address")]
    full_name: Annotated[str | None, Field(default=None, description="User full name")]
    avatar_url: Annotated[str | None, Field(default=None, description="User avatar URL")]
    role: Annotated[str, Field(description="User role: owner, admin, editor, viewer")]


class WorkspaceSyncPayload(BaseModel):
    """Request payload for realm/workspace sync endpoint."""

    nodl_workspace_id: Annotated[str, Field(description="nodl workspace UUID")]
    name: Annotated[str, Field(description="Workspace name")]
    description: Annotated[str | None, Field(default=None, description="Workspace description")]
    members: Annotated[list[MemberPayload], Field(default=[], description="Workspace members")]


def require_service_auth(view_func):
    """Decorator to enforce service key authentication.

    The ServiceKeyAuthMiddleware already validates the key and sets
    request.is_service_request = True. This decorator just ensures
    the flag is set.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not getattr(request, "is_service_request", False):
            return JsonResponse(
                {"result": "error", "code": "UNAUTHORIZED", "msg": "Service key required"},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


@csrf_exempt
@require_service_auth
def sync_user(request: HttpRequest) -> HttpResponse:
    """Sync a user from nodl to Zulip.

    POST /api/v1/internal/users/sync

    Request body:
    {
        "supabase_user_id": "uuid",
        "email": "user@example.com",
        "full_name": "John Doe",
        "avatar_url": "https://...",
        "workspace_id": "workspace-uuid",
        "role": "editor"
    }

    Response:
    {
        "result": "success",
        "zulip_user_id": 123
    }

    Or on error:
    {
        "result": "error",
        "code": "SYNC_FAILED",
        "msg": "Error message"
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    try:
        body = json.loads(request.body)
        logger.info("sync_user_request received", extra={"payload": body})
        payload = UserSyncPayload(**body)
    except json.JSONDecodeError:
        logger.error("sync_user_request invalid JSON")
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as e:
        logger.error("sync_user_validation_error", extra={"error": str(e), "body": body})
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(e)},
            status=400,
        )

    sync_request = UserSyncRequest(
        supabase_user_id=payload.supabase_user_id,
        email=payload.email,
        full_name=payload.full_name,
        avatar_url=payload.avatar_url,
        workspace_id=payload.workspace_id,
        role=payload.role,
    )

    service = UserSyncService()
    result: UserSyncResult = service.sync_user(sync_request)

    if result.success:
        return JsonResponse(
            {"result": "success", "zulip_user_id": result.zulip_user_id},
            status=200,
        )
    else:
        return JsonResponse(
            {"result": "error", "code": "SYNC_FAILED", "msg": result.error},
            status=500,
        )


@csrf_exempt
@require_service_auth
def sync_realm(request: HttpRequest) -> HttpResponse:
    """Sync a workspace from nodl to Zulip realm.

    POST /api/v1/internal/realms/sync

    Request body:
    {
        "nodl_workspace_id": "uuid",
        "name": "Workspace Name",
        "description": "Optional description",
        "members": [
            {
                "supabase_user_id": "uuid",
                "email": "user@example.com",
                "full_name": "John Doe",
                "role": "editor"
            }
        ]
    }

    Response:
    {
        "result": "success",
        "zulip_realm_id": 123
    }

    Or on error:
    {
        "result": "error",
        "code": "SYNC_FAILED",
        "msg": "Error message"
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    try:
        body = json.loads(request.body)
        payload = WorkspaceSyncPayload(**body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as e:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(e)},
            status=400,
        )

    # Convert Pydantic models to dicts for the service
    members = [
        {
            "supabase_user_id": m.supabase_user_id,
            "email": m.email,
            "full_name": m.full_name,
            "avatar_url": m.avatar_url,
            "role": m.role,
        }
        for m in payload.members
    ]

    sync_request = WorkspaceSyncRequest(
        nodl_workspace_id=payload.nodl_workspace_id,
        name=payload.name,
        description=payload.description,
        members=members,
    )

    service = WorkspaceSyncService()
    result: WorkspaceSyncResult = service.sync_workspace(sync_request)

    if result.success:
        return JsonResponse(
            {"result": "success", "zulip_realm_id": result.zulip_realm_id},
            status=200,
        )
    else:
        return JsonResponse(
            {"result": "error", "code": "SYNC_FAILED", "msg": result.error},
            status=500,
        )


@csrf_exempt
@require_service_auth
def deactivate_realm(request: HttpRequest) -> HttpResponse:
    """Deactivate a realm when workspace is deleted.

    POST /api/v1/internal/realms/deactivate

    Request body:
    {
        "nodl_workspace_id": "uuid"
    }

    Response:
    {
        "result": "success",
        "zulip_realm_id": 123
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    try:
        body = json.loads(request.body)
        nodl_workspace_id = body.get("nodl_workspace_id")
        if not nodl_workspace_id:
            return JsonResponse(
                {
                    "result": "error",
                    "code": "VALIDATION_ERROR",
                    "msg": "nodl_workspace_id required",
                },
                status=400,
            )
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )

    service = WorkspaceSyncService()
    result: WorkspaceSyncResult = service.deactivate_realm(nodl_workspace_id)

    if result.success:
        return JsonResponse(
            {"result": "success", "zulip_realm_id": result.zulip_realm_id},
            status=200,
        )
    else:
        return JsonResponse(
            {"result": "error", "code": "DEACTIVATION_FAILED", "msg": result.error},
            status=500,
        )
