import json
import logging
import uuid

from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from zerver.decorator import authenticated_rest_api_view
from zerver.models import UserProfile
from zproject.nodl.models import CallRecord
from zproject.nodl.serializers.call_serializers import (
    serialize_call_accept_response,
    serialize_call_initiate_response,
    serialize_call_record,
)
from zproject.nodl.services.call_push_service import dispatch_call_push_async
from zproject.nodl.services.livekit_service import (
    LIVEKIT_URL,
    create_room_sync,
    generate_token,
)

logger = logging.getLogger(__name__)


@authenticated_rest_api_view(skip_rate_limiting=True)
def initiate_call(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Initiate a call to another user.

    POST /nodl/calls/initiate
    Body: {"callee_id": <int>}

    Creates a LiveKit room, generates caller token, inserts call_record(status=ringing).
    Dispatches push notifications to callee's devices (fire-and-forget).
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

    raw_callee_id = body.get("callee_id")
    if raw_callee_id is None:
        return JsonResponse(
            {"result": "error", "msg": "callee_id is required", "code": "BAD_REQUEST"},
            status=400,
        )

    # Strict type check: reject bool (subclass of int) and float; allow int and str only
    if isinstance(raw_callee_id, bool) or not isinstance(raw_callee_id, (int, str)):
        return JsonResponse(
            {"result": "error", "msg": "callee_id must be an integer", "code": "BAD_REQUEST"},
            status=400,
        )

    try:
        callee_id = int(raw_callee_id)
    except (ValueError, TypeError):
        return JsonResponse(
            {"result": "error", "msg": "callee_id must be an integer", "code": "BAD_REQUEST"},
            status=400,
        )

    # Validate callee exists
    try:
        callee = UserProfile.objects.get(id=callee_id, is_active=True)
    except UserProfile.DoesNotExist:
        return JsonResponse(
            {"result": "error", "msg": "Callee not found", "code": "BAD_REQUEST"},
            status=400,
        )

    # Prevent calling yourself
    if callee.id == user_profile.id:
        return JsonResponse(
            {"result": "error", "msg": "Cannot call yourself", "code": "BAD_REQUEST"},
            status=400,
        )

    # Create room name, provision LiveKit room, generate token
    room_name = f"call-{uuid.uuid4()}"
    caller_identity = str(user_profile.id)

    try:
        create_room_sync(room_name, max_participants=2, empty_timeout=35)
    except Exception as e:
        logger.error("LiveKit room creation failed: %s", e)
        return JsonResponse(
            {"result": "error", "msg": "Call service unavailable", "code": "SERVICE_ERROR"},
            status=503,
        )

    try:
        token = generate_token(caller_identity, room_name)
    except Exception as e:
        logger.error("LiveKit token generation failed: %s", e)
        return JsonResponse(
            {"result": "error", "msg": "Call service unavailable", "code": "SERVICE_ERROR"},
            status=503,
        )

    call = CallRecord.objects.create(
        room_name=room_name,
        caller=user_profile,
        callee=callee,
        status="ringing",
    )

    # Fire-and-forget push dispatch to callee's devices (Story 11.3)
    caller_name = user_profile.full_name or user_profile.delivery_email
    caller_avatar_url = ""
    dispatch_call_push_async(
        callee_id=callee.id,
        call_id=str(call.id),
        room_name=room_name,
        caller_name=caller_name,
        caller_avatar_url=caller_avatar_url,
    )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            **serialize_call_initiate_response(call, room_name, LIVEKIT_URL, token),
        }
    )


@authenticated_rest_api_view(skip_rate_limiting=True)
def accept_call(
    request: HttpRequest, user_profile: UserProfile, call_id: str
) -> HttpResponse:
    """Accept an incoming call.

    POST /nodl/calls/<call_id>/accept

    Transitions status ringing → connected, sets answered_at, returns callee LiveKit token.
    First accept wins (multi-device); subsequent attempts get error.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        call_uuid = uuid.UUID(str(call_id))
    except ValueError:
        return JsonResponse(
            {"result": "error", "msg": "Invalid call_id", "code": "BAD_REQUEST"},
            status=400,
        )

    with transaction.atomic():
        try:
            call = CallRecord.objects.select_for_update().get(id=call_uuid)
        except CallRecord.DoesNotExist:
            return JsonResponse(
                {"result": "error", "msg": "Call not found", "code": "NOT_FOUND"},
                status=404,
            )

        # Only callee can accept
        if call.callee_id != user_profile.id:
            return JsonResponse(
                {"result": "error", "msg": "Not authorized", "code": "UNAUTHORIZED"},
                status=403,
            )

        # Must be in ringing state
        if call.status != "ringing":
            return JsonResponse(
                {
                    "result": "error",
                    "msg": f"Call cannot be accepted (status: {call.status})",
                    "code": "INVALID_STATE",
                },
                status=409,
            )

        # Generate token BEFORE persisting state change — if this fails,
        # the transaction rolls back and call stays in "ringing" state.
        callee_identity = str(user_profile.id)
        try:
            token = generate_token(callee_identity, call.room_name)
        except Exception as e:
            logger.error("LiveKit token generation failed: %s", e)
            return JsonResponse(
                {"result": "error", "msg": "Call service unavailable", "code": "SERVICE_ERROR"},
                status=503,
            )

        call.status = "connected"
        call.answered_at = timezone.now()
        call.save(update_fields=["status", "answered_at"])

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            **serialize_call_accept_response(call, call.room_name, LIVEKIT_URL, token),
        }
    )


@authenticated_rest_api_view(skip_rate_limiting=True)
def decline_call(
    request: HttpRequest, user_profile: UserProfile, call_id: str
) -> HttpResponse:
    """Decline an incoming call.

    POST /nodl/calls/<call_id>/decline

    Transitions status ringing → declined, sets ended_at + end_reason=callee_declined.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        call_uuid = uuid.UUID(str(call_id))
    except ValueError:
        return JsonResponse(
            {"result": "error", "msg": "Invalid call_id", "code": "BAD_REQUEST"},
            status=400,
        )

    with transaction.atomic():
        try:
            call = CallRecord.objects.select_for_update().get(id=call_uuid)
        except CallRecord.DoesNotExist:
            return JsonResponse(
                {"result": "error", "msg": "Call not found", "code": "NOT_FOUND"},
                status=404,
            )

        # Only callee can decline
        if call.callee_id != user_profile.id:
            return JsonResponse(
                {"result": "error", "msg": "Not authorized", "code": "UNAUTHORIZED"},
                status=403,
            )

        if call.status != "ringing":
            return JsonResponse(
                {
                    "result": "error",
                    "msg": f"Call cannot be declined (status: {call.status})",
                    "code": "INVALID_STATE",
                },
                status=409,
            )

        call.status = "declined"
        call.ended_at = timezone.now()
        call.end_reason = "callee_declined"
        call.save(update_fields=["status", "ended_at", "end_reason"])

    return JsonResponse({"result": "success", "msg": ""})


@authenticated_rest_api_view(skip_rate_limiting=True)
def cancel_call(
    request: HttpRequest, user_profile: UserProfile, call_id: str
) -> HttpResponse:
    """Cancel an outgoing call before it's answered.

    POST /nodl/calls/<call_id>/cancel

    Only the caller can cancel. Transitions ringing → cancelled.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        call_uuid = uuid.UUID(str(call_id))
    except ValueError:
        return JsonResponse(
            {"result": "error", "msg": "Invalid call_id", "code": "BAD_REQUEST"},
            status=400,
        )

    with transaction.atomic():
        try:
            call = CallRecord.objects.select_for_update().get(id=call_uuid)
        except CallRecord.DoesNotExist:
            return JsonResponse(
                {"result": "error", "msg": "Call not found", "code": "NOT_FOUND"},
                status=404,
            )

        # Only caller can cancel
        if call.caller_id != user_profile.id:
            return JsonResponse(
                {"result": "error", "msg": "Not authorized", "code": "UNAUTHORIZED"},
                status=403,
            )

        if call.status != "ringing":
            return JsonResponse(
                {
                    "result": "error",
                    "msg": f"Call cannot be cancelled (status: {call.status})",
                    "code": "INVALID_STATE",
                },
                status=409,
            )

        call.status = "cancelled"
        call.ended_at = timezone.now()
        call.end_reason = "caller_cancelled"
        call.save(update_fields=["status", "ended_at", "end_reason"])

    return JsonResponse({"result": "success", "msg": ""})


@authenticated_rest_api_view(skip_rate_limiting=True)
def end_call(
    request: HttpRequest, user_profile: UserProfile, call_id: str
) -> HttpResponse:
    """End a connected call.

    POST /nodl/calls/<call_id>/end

    Transitions connected → ended, computes duration_seconds. Idempotent —
    second simultaneous /end returns 200 OK.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        call_uuid = uuid.UUID(str(call_id))
    except ValueError:
        return JsonResponse(
            {"result": "error", "msg": "Invalid call_id", "code": "BAD_REQUEST"},
            status=400,
        )

    with transaction.atomic():
        try:
            call = CallRecord.objects.select_for_update().get(id=call_uuid)
        except CallRecord.DoesNotExist:
            return JsonResponse(
                {"result": "error", "msg": "Call not found", "code": "NOT_FOUND"},
                status=404,
            )

        # Only caller or callee can end
        if call.caller_id != user_profile.id and call.callee_id != user_profile.id:
            return JsonResponse(
                {"result": "error", "msg": "Not authorized", "code": "UNAUTHORIZED"},
                status=403,
            )

        # Idempotent: if already ended, return success
        if call.status == "ended":
            return JsonResponse({"result": "success", "msg": ""})

        if call.status != "connected":
            return JsonResponse(
                {
                    "result": "error",
                    "msg": f"Call cannot be ended (status: {call.status})",
                    "code": "INVALID_STATE",
                },
                status=409,
            )

        now = timezone.now()
        duration = None
        if call.answered_at:
            duration = int((now - call.answered_at).total_seconds())

        # Determine who hung up
        if call.caller_id == user_profile.id:
            end_reason = "caller_hangup"
        else:
            end_reason = "callee_hangup"

        call.status = "ended"
        call.ended_at = now
        call.duration_seconds = duration
        call.end_reason = end_reason
        call.save(update_fields=["status", "ended_at", "duration_seconds", "end_reason"])

    return JsonResponse({"result": "success", "msg": ""})


@authenticated_rest_api_view(skip_rate_limiting=True)
def call_history(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Get paginated call history for the authenticated user.

    GET /nodl/calls/history?limit=20&offset=0

    Returns calls where user is caller OR callee, newest first.
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        limit = int(request.GET.get("limit", "20"))
        offset = int(request.GET.get("offset", "0"))
    except (ValueError, TypeError):
        return JsonResponse(
            {"result": "error", "msg": "Invalid limit/offset", "code": "BAD_REQUEST"},
            status=400,
        )

    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    calls = (
        CallRecord.objects.filter(
            Q(caller=user_profile) | Q(callee=user_profile)
        )
        .order_by("-initiated_at")[offset : offset + limit]
    )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "calls": [serialize_call_record(c) for c in calls],
        }
    )


@authenticated_rest_api_view(skip_rate_limiting=True)
def call_detail(
    request: HttpRequest, user_profile: UserProfile, call_id: str
) -> HttpResponse:
    """Get a single call record.

    GET /nodl/calls/<call_id>

    Only returns the record if the authenticated user is caller or callee.
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed", "code": "METHOD_NOT_ALLOWED"},
            status=405,
        )

    try:
        call_uuid = uuid.UUID(str(call_id))
    except ValueError:
        return JsonResponse(
            {"result": "error", "msg": "Invalid call_id", "code": "BAD_REQUEST"},
            status=400,
        )

    try:
        call = CallRecord.objects.get(
            id=call_uuid,
        )
    except CallRecord.DoesNotExist:
        return JsonResponse(
            {"result": "error", "msg": "Call not found", "code": "NOT_FOUND"},
            status=404,
        )

    # Only caller or callee can view
    if call.caller_id != user_profile.id and call.callee_id != user_profile.id:
        return JsonResponse(
            {"result": "error", "msg": "Not authorized", "code": "UNAUTHORIZED"},
            status=403,
        )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "call": serialize_call_record(call),
        }
    )
