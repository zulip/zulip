import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zerver.models import Realm
from zerver.models.realms import get_realm

from zproject.nodl.actions import (
    check_duplicate_phone,
    check_link_rate_limit,
    find_email_identity,
    find_existing_zulip_user_by_email,
    get_or_create_zulip_user,
    get_supabase_user_by_id,
    link_phone_to_existing_user,
    mask_email,
)
from zproject.nodl.auth import JWTValidationError, validate_supabase_jwt
from zproject.nodl.throttle import check_rate_limit

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def auth_bridge(request: HttpRequest) -> JsonResponse:
    """Exchange a Supabase JWT for a Zulip API key, with account linking support.

    POST /nodl/auth/bridge
    Authorization: Bearer <supabase-jwt>

    Optional body (JSON):
        link_action: "link" | "create_new"  -- confirm linking decision

    Returns:
        Normal: {"result": "success", "msg": "", "api_key": "...", "user_id": 123, "email": "..."}
        Linking available: {"result": "success", "msg": "", "linking_available": true,
                           "existing_email_masked": "m***@example.com", "existing_user_id": 123}
        Duplicate phone: {"result": "success", "msg": "", "duplicate_phone": true}
    """
    # Rate limit by IP
    rate_limit_response = check_rate_limit(request)
    if rate_limit_response is not None:
        return rate_limit_response

    # Extract Bearer token
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JWT token", "code": "UNAUTHORIZED"},
            status=401,
        )
    token = auth_header[7:]

    # Validate JWT
    try:
        payload = validate_supabase_jwt(token)
    except JWTValidationError:
        return JsonResponse(
            {"result": "error", "msg": "Invalid JWT token", "code": "UNAUTHORIZED"},
            status=401,
        )

    # Get realm (default single-realm deployment)
    try:
        realm = get_realm("zulip")
    except Exception:
        return JsonResponse(
            {"result": "error", "msg": "Realm not found", "code": "INTERNAL_ERROR"},
            status=500,
        )

    # Parse optional link_action from request body
    link_action = None
    if request.content_type == "application/json" and request.body:
        try:
            body = json.loads(request.body)
            link_action = body.get("link_action")
        except (json.JSONDecodeError, ValueError):
            pass

    supabase_user_id = payload.get("sub", "")
    phone = payload.get("phone", "")

    # Handle link confirmation (Task 2)
    if link_action is not None:
        return _handle_link_action(link_action, payload, phone, supabase_user_id, realm)

    # Account detection logic (Task 1)
    # Check for duplicate phone first
    if phone and check_duplicate_phone(supabase_user_id, phone):
        return JsonResponse(
            {"result": "success", "msg": "", "duplicate_phone": True}
        )

    # Check if the phone user has an email identity in Supabase
    if supabase_user_id:
        supabase_user = get_supabase_user_by_id(supabase_user_id)
        if supabase_user is not None:
            existing_email = find_email_identity(supabase_user)
            if existing_email:
                # Check if a Zulip user exists with that email
                existing_zulip_user = find_existing_zulip_user_by_email(
                    existing_email, realm
                )
                if existing_zulip_user is not None:
                    return JsonResponse(
                        {
                            "result": "success",
                            "msg": "",
                            "linking_available": True,
                            "existing_email_masked": mask_email(existing_email),
                            "existing_user_id": existing_zulip_user.id,
                        }
                    )

    # Default: get or create user (same as Story 1.2 flow)
    try:
        user_profile = get_or_create_zulip_user(payload, realm)
    except Exception:
        logger.exception(
            "Failed to get or create user for Supabase sub=%s", payload.get("sub")
        )
        return JsonResponse(
            {
                "result": "error",
                "msg": "User provisioning failed",
                "code": "INTERNAL_ERROR",
            },
            status=500,
        )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "api_key": user_profile.api_key,
            "user_id": user_profile.id,
            "email": user_profile.delivery_email,
        }
    )


def _handle_link_action(
    link_action: str,
    payload: dict,
    phone: str,
    supabase_user_id: str,
    realm: Realm,
) -> JsonResponse:
    """Handle link confirmation or create_new actions."""
    if link_action not in ("link", "create_new"):
        return JsonResponse(
            {"result": "error", "msg": "Invalid link_action", "code": "BAD_REQUEST"},
            status=400,
        )

    # Rate limit link attempts per phone
    if phone and check_link_rate_limit(phone):
        response = JsonResponse(
            {
                "result": "error",
                "msg": "Too many link attempts",
                "code": "RATE_LIMIT_HIT",
            },
            status=429,
        )
        response["Retry-After"] = "3600"
        return response

    if link_action == "link":
        return _handle_link(payload, phone, supabase_user_id, realm)
    else:  # create_new
        return _handle_create_new(payload, realm)


def _handle_link(
    payload: dict,
    phone: str,
    supabase_user_id: str,
    realm: Realm,
) -> JsonResponse:
    """Link the phone identity to an existing account."""
    # Re-verify: fetch the Supabase user and find the email identity
    supabase_user = get_supabase_user_by_id(supabase_user_id)
    if supabase_user is None:
        return JsonResponse(
            {
                "result": "error",
                "msg": "Failed to verify account",
                "code": "INTERNAL_ERROR",
            },
            status=500,
        )

    existing_email = find_email_identity(supabase_user)
    if not existing_email:
        return JsonResponse(
            {
                "result": "error",
                "msg": "No email identity found",
                "code": "BAD_REQUEST",
            },
            status=400,
        )

    existing_zulip_user = find_existing_zulip_user_by_email(existing_email, realm)
    if existing_zulip_user is None:
        # Zulip user was deleted but Supabase email exists -- treat as no-match
        return JsonResponse(
            {
                "result": "error",
                "msg": "Existing account not found",
                "code": "BAD_REQUEST",
            },
            status=400,
        )

    # Get the existing Supabase user ID (the one with the email identity)
    existing_supabase_id = supabase_user.get("id", supabase_user_id)

    # Link phone to existing Supabase user
    if phone:
        success = link_phone_to_existing_user(existing_supabase_id, phone)
        if not success:
            return JsonResponse(
                {
                    "result": "error",
                    "msg": "Account linking failed",
                    "code": "INTERNAL_ERROR",
                },
                status=500,
            )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "api_key": existing_zulip_user.api_key,
            "user_id": existing_zulip_user.id,
            "email": existing_zulip_user.delivery_email,
        }
    )


def _handle_create_new(payload: dict, realm: Realm) -> JsonResponse:
    """Provision a new Zulip account for the phone-only Supabase user."""
    try:
        user_profile = get_or_create_zulip_user(payload, realm)
    except Exception:
        logger.exception(
            "Failed to create new user for Supabase sub=%s", payload.get("sub")
        )
        return JsonResponse(
            {
                "result": "error",
                "msg": "User provisioning failed",
                "code": "INTERNAL_ERROR",
            },
            status=500,
        )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "api_key": user_profile.api_key,
            "user_id": user_profile.id,
            "email": user_profile.delivery_email,
        }
    )
