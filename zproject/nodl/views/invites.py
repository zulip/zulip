import json
import logging
import re
from datetime import timedelta
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from zerver.models import UserProfile
from zproject.nodl.models import INVITE_EXPIRY_DAYS, NodlInvite
from zproject.nodl.throttle import check_rate_limit

logger = logging.getLogger(__name__)


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
def invites_list(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """List all invites for the authenticated user.

    GET /nodl/invites
    Authorization: Basic base64(email:apiKey)
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    rate_resp = check_rate_limit(
        request,
        limit=20,
        window=60,
        cache_key=f"nodl_invites_list:{user_profile.id}",
    )
    if rate_resp is not None:
        return rate_resp

    invites = (
        NodlInvite.objects.filter(inviter=user_profile)
        .select_related("invited_user")
        .order_by("-created_at")[:100]
    )
    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "invites": [inv.to_api_dict() for inv in invites],
        }
    )


@_require_jwt_auth
def invites_create(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Record a new invite.

    POST /nodl/invites/create
    Authorization: Basic base64(email:apiKey)
    Body: {"phone_hash": "sha256hex", "phone_display": "***1234"}
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    rate_resp = check_rate_limit(
        request,
        limit=10,
        window=60,
        cache_key=f"nodl_invites_create:{user_profile.id}",
    )
    if rate_resp is not None:
        return rate_resp

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JSON", "code": "BAD_REQUEST"},
            status=400,
        )

    phone_hash = body.get("phone_hash", "")
    phone_display = body.get("phone_display", "")

    if not re.fullmatch(r"[0-9a-f]{64}", phone_hash):
        return JsonResponse(
            {"result": "error", "msg": "Invalid phone_hash", "code": "BAD_REQUEST"},
            status=400,
        )

    if not re.fullmatch(r"\*{3}\d{4}", phone_display):
        return JsonResponse(
            {"result": "error", "msg": "Invalid phone_display", "code": "BAD_REQUEST"},
            status=400,
        )

    # Dedup: return existing active invite for same phone_hash if one exists
    existing = (
        NodlInvite.objects.filter(
            inviter=user_profile,
            invited_phone_hash=phone_hash,
            invited_user__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return JsonResponse(
            {
                "result": "success",
                "msg": "",
                "invite": existing.to_api_dict(),
            }
        )

    invite = NodlInvite.objects.create(
        inviter=user_profile,
        invited_phone_hash=phone_hash,
        invited_phone_display=phone_display,
        expires_at=timezone.now() + timedelta(days=INVITE_EXPIRY_DAYS),
    )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "invite": invite.to_api_dict(),
        }
    )


@_require_jwt_auth
def invites_resend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Resend an expired invite (resets expiry).

    POST /nodl/invites/resend
    Authorization: Basic base64(email:apiKey)
    Body: {"invite_id": 123}
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    rate_resp = check_rate_limit(
        request,
        limit=10,
        window=60,
        cache_key=f"nodl_invites_resend:{user_profile.id}",
    )
    if rate_resp is not None:
        return rate_resp

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JSON", "code": "BAD_REQUEST"},
            status=400,
        )

    invite_id = body.get("invite_id")
    if invite_id is None:
        return JsonResponse(
            {"result": "error", "msg": "invite_id required", "code": "BAD_REQUEST"},
            status=400,
        )

    try:
        invite = NodlInvite.objects.get(pk=invite_id, inviter=user_profile)
    except NodlInvite.DoesNotExist:
        return JsonResponse(
            {"result": "error", "msg": "Invite not found", "code": "NOT_FOUND"},
            status=404,
        )

    if invite.computed_status != "expired":
        return JsonResponse(
            {"result": "error", "msg": "Only expired invites can be resent", "code": "BAD_REQUEST"},
            status=400,
        )

    invite.expires_at = timezone.now() + timedelta(days=INVITE_EXPIRY_DAYS)
    invite.save(update_fields=["expires_at", "updated_at"])

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "invite": invite.to_api_dict(),
        }
    )


def mark_invite_registered(phone_hash: str, user_profile: UserProfile) -> None:
    """Mark any pending invites for this phone hash as registered.

    Called from auth_bridge when a new user is provisioned.
    """
    updated = NodlInvite.objects.filter(
        invited_phone_hash=phone_hash,
        invited_user__isnull=True,
    ).update(invited_user=user_profile, updated_at=timezone.now())

    if updated:
        logger.info(
            "Marked %d invite(s) as registered for user %d",
            updated,
            user_profile.id,
        )
