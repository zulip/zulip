import json
import logging
import re

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.models import UserProfile
from zproject.nodl.contacts import match_phone_hashes
from zproject.nodl.throttle import check_rate_limit

logger = logging.getLogger(__name__)

# SHA-256 hex output: exactly 64 lowercase hex chars
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@authenticated_rest_api_view(skip_rate_limiting=True)
def contacts_match(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Match submitted phone hashes against registered nodl users.

    POST /nodl/contacts/match
    Authorization: Basic base64(email:api_key)
    Body: {"phone_hashes": ["a1b2c3...", ...]}

    Returns: {"result": "success", "msg": "", "matches": [...]}
    """
    # Rate limit: 10 requests/minute per user
    rate_limit_response = check_rate_limit(
        request,
        limit=10,
        window=60,
        cache_key=f"nodl_contacts_match:{user_profile.id}",
    )
    if rate_limit_response is not None:
        return rate_limit_response

    # Parse JSON body
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid request format", "code": "BAD_REQUEST"},
            status=400,
        )

    # Validate phone_hashes field
    if not isinstance(body, dict) or "phone_hashes" not in body:
        return JsonResponse(
            {"result": "error", "msg": "Invalid request format", "code": "BAD_REQUEST"},
            status=400,
        )

    phone_hashes = body["phone_hashes"]
    if not isinstance(phone_hashes, list):
        return JsonResponse(
            {"result": "error", "msg": "Invalid request format", "code": "BAD_REQUEST"},
            status=400,
        )

    # Check max batch size
    max_hashes = getattr(settings, "NODL_CONTACTS_MATCH_LIMIT", 500)
    if len(phone_hashes) > max_hashes:
        return JsonResponse(
            {
                "result": "error",
                "msg": f"Too many hashes. Maximum {max_hashes} per request.",
                "code": "BAD_REQUEST",
            },
            status=400,
        )

    # Validate each entry is a string and a valid SHA-256 hex hash
    for item in phone_hashes:
        if not isinstance(item, str) or not SHA256_HEX_PATTERN.match(item):
            return JsonResponse(
                {"result": "error", "msg": "Invalid request format", "code": "BAD_REQUEST"},
                status=400,
            )

    # Perform matching
    matches = match_phone_hashes(phone_hashes, user_profile.id, user_profile.realm)

    return JsonResponse({"result": "success", "msg": "", "matches": matches})
