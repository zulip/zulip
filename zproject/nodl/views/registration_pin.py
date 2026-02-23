import json
import logging
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zproject.nodl.models import NodlRegistrationPin
from zproject.nodl.throttle import check_rate_limit

logger = logging.getLogger(__name__)

# Lockout constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30

# Rate limit: 10 PIN verify requests per minute per user
PIN_RATE_LIMIT = 10
PIN_RATE_WINDOW = 60


def _get_authenticated_user(request: HttpRequest) -> "UserProfile | None":
    """Extract authenticated Zulip user from the request.

    PIN endpoints require a valid Zulip API key (same as other /nodl/ endpoints).
    The API key is passed via HTTP Basic Auth: email:api_key.
    """
    from zerver.lib.request import get_request_notes
    from zerver.models import UserProfile

    # Check if the request has been authenticated by Zulip's auth middleware
    request_notes = get_request_notes(request)
    if request_notes.requestor is not None:
        return request_notes.requestor

    # Fallback: try HTTP Basic Auth with API key
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Basic "):
        import base64

        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            email, api_key = decoded.split(":", 1)
            user = UserProfile.objects.get(
                delivery_email__iexact=email,
                api_key=api_key,
                is_active=True,
            )
            return user
        except (ValueError, UserProfile.DoesNotExist, Exception):
            pass

    return None


@csrf_exempt
@require_POST
def pin_set(request: HttpRequest) -> JsonResponse:
    """Set or update the user's Registration Lock PIN.

    POST /nodl/pin/set
    Authorization: Basic <email:api_key>
    Body: {"pin": "1234"} for first-time setup
    Body: {"pin": "1234", "current_pin": "0000"} to change existing PIN

    If a PIN already exists, the current_pin must be provided and verified
    before the new PIN is accepted. This prevents SIM swap attackers from
    overwriting the PIN without knowing it.

    The PIN is hashed server-side with bcrypt before storage.
    """
    user = _get_authenticated_user(request)
    if user is None:
        return JsonResponse(
            {"result": "error", "msg": "Authentication required", "code": "UNAUTHORIZED"},
            status=401,
        )

    # Per-user rate limit (matches pin_verify rate limit)
    rate_key = f"nodl_pin_set:{user.id}"
    rate_response = check_rate_limit(
        request, limit=PIN_RATE_LIMIT, window=PIN_RATE_WINDOW, cache_key=rate_key
    )
    if rate_response is not None:
        return rate_response

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JSON body", "code": "BAD_REQUEST"},
            status=400,
        )

    pin = body.get("pin", "")
    if not isinstance(pin, str) or not pin.isdigit() or not (4 <= len(pin) <= 6):
        return JsonResponse(
            {
                "result": "error",
                "msg": "PIN must be 4-6 digits",
                "code": "INVALID_PIN",
            },
            status=400,
        )

    # Check if a PIN already exists for this user
    existing_record = NodlRegistrationPin.objects.filter(user=user).first()

    if existing_record is not None:
        # Existing PIN -- require current_pin to change it
        if existing_record.is_locked():
            retry_after = existing_record.remaining_lockout_seconds()
            minutes = max(1, (retry_after + 59) // 60)
            return JsonResponse(
                {
                    "result": "error",
                    "msg": f"Account temporarily locked. Try again in {minutes} minutes.",
                    "code": "PIN_LOCKED",
                    "retry_after_seconds": retry_after,
                },
                status=429,
            )

        current_pin = body.get("current_pin", "")
        if not current_pin:
            return JsonResponse(
                {
                    "result": "error",
                    "msg": "A PIN is already set. Provide current_pin to change it.",
                    "code": "PIN_EXISTS",
                },
                status=409,
            )

        if not check_password(current_pin, existing_record.pin_hash):
            existing_record.failed_attempts += 1
            if existing_record.failed_attempts >= MAX_FAILED_ATTEMPTS:
                existing_record.locked_until = timezone.now() + timedelta(
                    minutes=LOCKOUT_DURATION_MINUTES
                )
            existing_record.save(
                update_fields=["failed_attempts", "locked_until", "updated_at"]
            )
            remaining = max(0, MAX_FAILED_ATTEMPTS - existing_record.failed_attempts)
            return JsonResponse(
                {
                    "result": "error",
                    "msg": f"Incorrect current PIN. {remaining} attempts remaining.",
                    "code": "PIN_INCORRECT",
                },
                status=403,
            )

        # Current PIN verified -- update to new PIN
        existing_record.pin_hash = make_password(pin, hasher="bcrypt")
        existing_record.failed_attempts = 0
        existing_record.locked_until = None
        existing_record.save(
            update_fields=["pin_hash", "failed_attempts", "locked_until", "updated_at"]
        )
        return JsonResponse({"result": "success", "msg": ""})

    # No existing PIN -- create new one
    pin_hash = make_password(pin, hasher="bcrypt")
    NodlRegistrationPin.objects.create(
        user=user,
        pin_hash=pin_hash,
        failed_attempts=0,
        locked_until=None,
    )

    return JsonResponse({"result": "success", "msg": ""})


@csrf_exempt
@require_POST
def pin_verify(request: HttpRequest) -> JsonResponse:
    """Verify the user's Registration Lock PIN.

    POST /nodl/pin/verify
    Authorization: Basic <email:api_key>
    Body: {"pin": "1234"}

    Returns verified=true on success, or an error on failure/lockout.
    """
    user = _get_authenticated_user(request)
    if user is None:
        return JsonResponse(
            {"result": "error", "msg": "Authentication required", "code": "UNAUTHORIZED"},
            status=401,
        )

    # Per-user rate limit
    rate_key = f"nodl_pin_verify:{user.id}"
    rate_response = check_rate_limit(
        request, limit=PIN_RATE_LIMIT, window=PIN_RATE_WINDOW, cache_key=rate_key
    )
    if rate_response is not None:
        return rate_response

    try:
        pin_record = NodlRegistrationPin.objects.get(user=user)
    except NodlRegistrationPin.DoesNotExist:
        return JsonResponse(
            {"result": "error", "msg": "No PIN set for this user", "code": "NO_PIN"},
            status=404,
        )

    # Check lockout
    if pin_record.is_locked():
        retry_after = pin_record.remaining_lockout_seconds()
        minutes = max(1, (retry_after + 59) // 60)
        return JsonResponse(
            {
                "result": "error",
                "msg": f"Account temporarily locked. Try again in {minutes} minutes.",
                "code": "PIN_LOCKED",
                "retry_after_seconds": retry_after,
            },
            status=429,
        )

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid JSON body", "code": "BAD_REQUEST"},
            status=400,
        )

    pin = body.get("pin", "")
    if not isinstance(pin, str):
        return JsonResponse(
            {"result": "error", "msg": "PIN must be a string", "code": "BAD_REQUEST"},
            status=400,
        )

    is_valid = check_password(pin, pin_record.pin_hash)

    if is_valid:
        # Reset failed attempts on success
        pin_record.failed_attempts = 0
        pin_record.locked_until = None
        pin_record.save(update_fields=["failed_attempts", "locked_until", "updated_at"])
        return JsonResponse(
            {"result": "success", "msg": "", "verified": True}
        )

    # Incorrect PIN
    pin_record.failed_attempts += 1
    remaining = MAX_FAILED_ATTEMPTS - pin_record.failed_attempts

    if pin_record.failed_attempts >= MAX_FAILED_ATTEMPTS:
        pin_record.locked_until = timezone.now() + timedelta(
            minutes=LOCKOUT_DURATION_MINUTES
        )
        pin_record.save(
            update_fields=["failed_attempts", "locked_until", "updated_at"]
        )
        retry_after = LOCKOUT_DURATION_MINUTES * 60
        return JsonResponse(
            {
                "result": "error",
                "msg": f"Account temporarily locked. Try again in {LOCKOUT_DURATION_MINUTES} minutes.",
                "code": "PIN_LOCKED",
                "retry_after_seconds": retry_after,
            },
            status=429,
        )

    pin_record.save(update_fields=["failed_attempts", "updated_at"])
    return JsonResponse(
        {
            "result": "error",
            "msg": f"Incorrect PIN. {remaining} attempts remaining.",
            "code": "PIN_INCORRECT",
            "verified": False,
        },
        status=403,
    )
