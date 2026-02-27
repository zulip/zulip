import json
import logging
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from zerver.models import UserProfile
from zproject.nodl.models import DeviceVoipToken

logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"ios", "android"}


def _require_jwt_auth(view_func):
    """Require JWT authentication via middleware (request.user_profile)."""
    @csrf_exempt
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = getattr(request, "user_profile", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return JsonResponse(
                {"result": "error", "code": "UNAUTHORIZED", "msg": "Authentication required"},
                status=401,
            )
        return view_func(request, user, *args, **kwargs)
    return wrapper


@_require_jwt_auth
def register_voip_token(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Register or update a VoIP/FCM push token for a device.

    POST /nodl/devices/voip-token
    Body: {"platform": "ios"|"android", "device_id": "...", "voip_token": "..." (iOS), "fcm_token": "..." (Android)}

    Upserts on UNIQUE(user_id, device_id) — re-registering the same device
    updates the token and sets is_active=True.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JSON", "code": "BAD_REQUEST"},
            status=400,
        )

    if not isinstance(body, dict):
        return JsonResponse(
            {"result": "error", "msg": "Request body must be a JSON object", "code": "BAD_REQUEST"},
            status=400,
        )

    platform = body.get("platform")
    device_id = body.get("device_id")
    voip_token = body.get("voip_token")
    fcm_token = body.get("fcm_token")

    if not platform or not isinstance(platform, str):
        return JsonResponse(
            {"result": "error", "msg": "platform is required", "code": "BAD_REQUEST"},
            status=400,
        )

    if platform not in VALID_PLATFORMS:
        return JsonResponse(
            {"result": "error", "msg": "platform must be 'ios' or 'android'", "code": "BAD_REQUEST"},
            status=400,
        )

    if not device_id or not isinstance(device_id, str):
        return JsonResponse(
            {"result": "error", "msg": "device_id is required", "code": "BAD_REQUEST"},
            status=400,
        )

    # Platform-token integrity: iOS must have voip_token, Android must have fcm_token
    if platform == "ios" and not voip_token:
        return JsonResponse(
            {"result": "error", "msg": "voip_token is required for iOS", "code": "BAD_REQUEST"},
            status=400,
        )

    if platform == "android" and not fcm_token:
        return JsonResponse(
            {"result": "error", "msg": "fcm_token is required for Android", "code": "BAD_REQUEST"},
            status=400,
        )

    defaults = {
        "platform": platform,
        "is_active": True,
        "voip_token": voip_token if platform == "ios" else None,
        "fcm_token": fcm_token if platform == "android" else None,
    }

    token_obj, created = DeviceVoipToken.objects.update_or_create(
        user=user_profile,
        device_id=device_id,
        defaults=defaults,
    )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "device_id": token_obj.device_id,
            "created": created,
        }
    )


@_require_jwt_auth
def unregister_voip_token(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Unregister (soft-delete) a VoIP/FCM push token.

    DELETE /nodl/devices/voip-token
    Body: {"device_id": "..."}

    Sets is_active=False for the matching token. Returns success even if
    no matching token exists (idempotent).
    """
    if request.method != "DELETE":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JSON", "code": "BAD_REQUEST"},
            status=400,
        )

    if not isinstance(body, dict):
        return JsonResponse(
            {"result": "error", "msg": "Request body must be a JSON object", "code": "BAD_REQUEST"},
            status=400,
        )

    device_id = body.get("device_id")
    if not device_id or not isinstance(device_id, str):
        return JsonResponse(
            {"result": "error", "msg": "device_id is required", "code": "BAD_REQUEST"},
            status=400,
        )

    updated = DeviceVoipToken.objects.filter(
        user=user_profile,
        device_id=device_id,
    ).update(is_active=False)

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "deactivated": updated > 0,
        }
    )
