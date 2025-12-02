"""Real-time event API views for nodl.

Proxy endpoints that accept JWT auth and forward to Zulip's
event system functions. The SupabaseJWTMiddleware sets request.user_profile
after validating the JWT token, so these views can use it directly.

These endpoints must be registered BEFORE Zulip's patterns in urls.py
so they take precedence over Zulip's HTTP Basic Auth protected endpoints.
"""

import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from zerver.lib.request import RequestNotes
from zerver.models import UserProfile
from zerver.models.clients import get_client
from zerver.tornado.views import cleanup_event_queue, get_events
from zerver.views.events_register import events_register_backend
from zerver.views.typing import send_notification_backend

logger = logging.getLogger(__name__)


def _require_user_profile(
    request: HttpRequest,
) -> tuple[HttpResponse | None, UserProfile | None]:
    """Check if user_profile is set by JWT middleware.

    Returns:
        Tuple of (error_response, user_profile).
        If error_response is not None, return it immediately.
        Otherwise, user_profile is guaranteed to be set.
    """
    user_profile = getattr(request, "user_profile", None)
    if not user_profile:
        logger.warning(
            f"[nodl-events] No user_profile on request to {request.path} "
            f"(missing JWT or user not synced)"
        )
        return (
            JsonResponse(
                {"result": "error", "msg": "Authentication required"},
                status=401,
            ),
            None,
        )
    return None, user_profile


def _setup_client(request: HttpRequest) -> None:
    """Ensure RequestNotes has a client set (required by Zulip views).

    Zulip views expect RequestNotes.client to be set. We use "nodl-web"
    as the client name for tracking purposes.
    """
    notes = RequestNotes.get_notes(request)
    if notes.client is None:
        notes.client = get_client("nodl-web")


@csrf_exempt
def register_queue(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/register - Register event queue.

    Creates an event queue for the authenticated user. The queue_id
    returned is used for subsequent /api/v1/events polling.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed"},
            status=405,
        )

    error_response, user_profile = _require_user_profile(request)
    if error_response:
        return error_response

    _setup_client(request)

    logger.info(f"[nodl-events] Registering event queue for user {user_profile.id}")

    # events_register_backend expects (request, maybe_user_profile)
    return events_register_backend(request, user_profile)


@csrf_exempt
def events_view(request: HttpRequest) -> HttpResponse:
    """Handle /api/v1/events - supports GET (poll) and DELETE (cleanup).

    GET: Long-poll for events from the queue.
    DELETE: Cleanup/delete an event queue.
    """
    error_response, user_profile = _require_user_profile(request)
    if error_response:
        return error_response

    _setup_client(request)

    if request.method == "GET":
        # Long-poll for events
        return get_events(request, user_profile)
    elif request.method == "DELETE":
        # Cleanup event queue
        return cleanup_event_queue(request, user_profile)
    else:
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed"},
            status=405,
        )


@csrf_exempt
def send_typing(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/typing - Send typing notification.

    Sends a typing start/stop notification to other users in the
    same stream/topic or DM conversation.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed"},
            status=405,
        )

    error_response, user_profile = _require_user_profile(request)
    if error_response:
        return error_response

    _setup_client(request)

    # send_notification_backend expects (request, user_profile, ...)
    # The Zulip function handles parameter extraction from request
    return send_notification_backend(request, user_profile)
