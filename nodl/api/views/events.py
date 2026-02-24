"""Real-time event API views for nodl.

Proxy endpoints that accept JWT auth and call Zulip's action functions directly.
We parse request parameters manually because @typed_endpoint decorators only work
when Django routes requests through URL resolution.

The SupabaseJWTMiddleware sets request.user_profile after validating the JWT token,
so these views can use it directly.

These endpoints must be registered BEFORE Zulip's patterns in urls.py
so they take precedence over Zulip's HTTP Basic Auth protected endpoints.
"""

import json
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from zerver.actions.typing import check_send_typing_notification, do_send_stream_typing_notification
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id_for_message, access_stream_for_send_message
from zerver.models import UserProfile
from zerver.models.clients import get_client
from zerver.tornado.views import cleanup_event_queue, get_events
from zerver.views.events_register import events_register_backend

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


def _get_json_body(request: HttpRequest) -> dict:
    """Parse JSON body from request.

    Returns empty dict if body is empty or not valid JSON.
    """
    try:
        return json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return {}


@csrf_exempt
def register_queue(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/register - Register event queue.

    Creates an event queue for the authenticated user. The queue_id
    returned is used for subsequent /api/v1/events polling.

    Performance optimization: We inject default parameters to limit what
    Zulip fetches. Without these, Zulip fetches ALL data (49+ queries).
    With optimization, we reduce to ~5-10 queries.

    See: https://zulip.com/api/register-queue for parameter docs.
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

    # Inject optimization parameters to reduce Zulip's data fetching
    # These tell Zulip to only fetch what the frontend actually needs
    # Zulip docs: "A few minutes [optimizing this] often saves 90% of bandwidth"
    request.POST = request.POST.copy()

    # Parse JSON body for client_capabilities (frontend sends JSON, not form data)
    # This is needed for bulk_message_deletion capability which affects event format
    body = _get_json_body(request)
    if "client_capabilities" in body and "client_capabilities" not in request.POST:
        request.POST["client_capabilities"] = json.dumps(body["client_capabilities"])

    # NOTE: We intentionally do NOT inject fetch_event_types or event_types.
    # The Flutter Zulip client expects the full /api/v1/register response
    # (realm_users, cross_realm_bots, custom_profile_fields, etc.).
    # In do_events_register(), when fetch_event_types=None AND event_types
    # is set, Zulip uses event_types for BOTH initial data and queue
    # subscription — restricting either causes null fields that crash
    # the Flutter parser.

    # Don't fetch full subscriber lists (major performance hit)
    if "include_subscribers" not in request.POST:
        request.POST["include_subscribers"] = "false"

    # Let client compute gravatar URLs (reduces payload size)
    if "client_gravatar" not in request.POST:
        request.POST["client_gravatar"] = "true"

    # Use compact presence format
    if "slim_presence" not in request.POST:
        request.POST["slim_presence"] = "true"

    # Ensure rendered content is included in message events
    # Without this, rendered_content may be deleted from event payloads
    if "apply_markdown" not in request.POST:
        request.POST["apply_markdown"] = "true"

    logger.info(f"[nodl-events] Registering event queue for user {user_profile.id}")

    # events_register_backend expects (request, maybe_user_profile)
    try:
        return events_register_backend(request, user_profile)
    except Exception as e:
        logger.error(
            "[nodl-events] Event queue registration failed: %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        return JsonResponse(
            {
                "result": "error",
                "msg": f"Event queue registration failed: {type(e).__name__}: {e}",
            },
            status=500,
        )


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

    Parses parameters manually and calls do_send_stream_typing_notification
    directly, since Zulip's @typed_endpoint decorator only works when
    Django routes requests through URL resolution.
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

    # Parse parameters from JSON body
    body = _get_json_body(request)
    op = body.get("op")  # 'start' or 'stop'
    msg_type = body.get("type", "stream")  # 'stream' or 'direct'
    stream_id = body.get("stream_id")
    topic = body.get("topic")

    # Validate required parameters
    if not op or op not in ("start", "stop"):
        return JsonResponse(
            {"result": "error", "msg": "Missing or invalid 'op' argument"},
            status=400,
        )

    if msg_type == "stream":
        if not stream_id:
            return JsonResponse(
                {"result": "error", "msg": "Missing 'stream_id' argument"},
                status=400,
            )
        if not topic:
            return JsonResponse(
                {"result": "error", "msg": "Missing 'topic' argument"},
                status=400,
            )

        # Check if user has typing notifications enabled
        if not user_profile.send_stream_typing_notifications:
            return JsonResponse(
                {"result": "error", "msg": "User has disabled typing notifications"},
                status=400,
            )

        try:
            # Verify user has access to the stream
            stream = access_stream_by_id_for_message(user_profile, stream_id)[0]
            access_stream_for_send_message(user_profile, stream, forwarder_user_profile=None)

            # Send the typing notification
            do_send_stream_typing_notification(user_profile, op, stream, topic)

            logger.debug(
                f"[nodl-typing] Sent {op} notification for user {user_profile.id} "
                f"to stream {stream_id} topic '{topic}'"
            )
            return json_success(request)

        except Exception as e:
            logger.warning(f"[nodl-typing] Error sending typing notification: {e}")
            return JsonResponse(
                {"result": "error", "msg": str(e)},
                status=400,
            )
    else:
        # Direct message typing
        to = body.get("to")  # List of recipient user IDs

        if not to or not isinstance(to, list) or len(to) == 0:
            return JsonResponse(
                {"result": "error", "msg": "Missing 'to' argument for direct message typing"},
                status=400,
            )

        try:
            # Send the direct message typing notification
            # check_send_typing_notification automatically includes sender in user_ids
            check_send_typing_notification(
                sender=user_profile,
                user_ids=to,
                operator=op,
            )

            logger.debug(
                f"[nodl-typing] Sent DM {op} notification for user {user_profile.id} "
                f"to users {to}"
            )
            return json_success(request)

        except Exception as e:
            logger.warning(f"[nodl-typing] Error sending DM typing notification: {e}")
            return JsonResponse(
                {"result": "error", "msg": str(e)},
                status=400,
            )
