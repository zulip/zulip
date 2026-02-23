import logging

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zerver.models import UserProfile
from zerver.models.realms import get_realm
from zproject.nodl.actions import derive_email, get_or_create_zulip_user
from zproject.nodl.auth import JWTValidationError, validate_supabase_jwt
from zproject.nodl.models import NodlRegistrationPin
from zproject.nodl.throttle import check_rate_limit

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def auth_bridge(request: HttpRequest) -> JsonResponse:
    """Exchange a Supabase JWT for a Zulip API key.

    POST /nodl/auth/bridge
    Authorization: Bearer <supabase-jwt>

    Returns:
        {"result": "success", "msg": "", "api_key": "...", "user_id": 123, "email": "..."}
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

    # Get realm (configurable for self-hosted deployments)
    realm_id = getattr(settings, "NODL_ZULIP_REALM_ID", "zulip")
    try:
        realm = get_realm(realm_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "msg": "Realm not found", "code": "INTERNAL_ERROR"},
            status=500,
        )

    # Check if user already exists (for is_new_device detection)
    email = derive_email(payload)
    user_existed_before = UserProfile.objects.filter(
        delivery_email__iexact=email,
        realm=realm,
        is_active=True,
    ).exists()

    # Get or create user
    try:
        user_profile = get_or_create_zulip_user(payload, realm)
    except Exception:
        logger.exception("Failed to get or create user for Supabase sub=%s", payload.get("sub"))
        return JsonResponse(
            {"result": "error", "msg": "User provisioning failed", "code": "INTERNAL_ERROR"},
            status=500,
        )

    # is_new_device: true if user already had an account (existing API key)
    # and this call is from a different device context. For single-device
    # policy, an existing user re-authenticating means a new device.
    is_new_device = user_existed_before

    # has_pin: true if user has a Registration Lock PIN set
    has_pin = NodlRegistrationPin.objects.filter(user=user_profile).exists()

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "api_key": user_profile.api_key,
            "user_id": user_profile.id,
            "email": user_profile.delivery_email,
            "has_pin": has_pin,
            "is_new_device": is_new_device,
        }
    )
