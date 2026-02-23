"""API views for file upload endpoints.

Implements REST API for file uploads with JWT authentication.
CSRF protection is disabled as this endpoint uses Bearer token (JWT)
authentication, not browser session cookies.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from zerver.lib.exceptions import JsonableError
from zerver.lib.upload import check_upload_within_quota, upload_message_attachment_from_request

logger = logging.getLogger(__name__)


def require_jwt_auth(view_func: Callable) -> Callable:
    """Decorator to require JWT authentication.

    Expects that authentication middleware has already validated the JWT
    and set request.user_profile.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = getattr(request, "user_profile", None)
        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"result": "error", "code": "UNAUTHORIZED", "msg": "Authentication required"},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapper


@csrf_exempt
@require_POST
@require_jwt_auth
def upload_file(request: HttpRequest) -> JsonResponse:
    """Upload a file and return URL for embedding in messages.

    POST /api/v1/uploads
    Content-Type: multipart/form-data

    Request body:
        file: The file to upload (multipart form field)

    Returns:
        {
            "url": "/user_uploads/...",
            "filename": "uploaded_filename.ext"
        }

    Errors:
        - 400: No file provided / Only one file at a time
        - 400: File exceeds maximum size
        - 400: Upload quota exceeded
        - 401: Authentication required
    """
    user_profile = request.user_profile

    # Validate file presence
    if len(request.FILES) == 0:
        raise JsonableError("No file provided")
    if len(request.FILES) != 1:
        raise JsonableError("Only one file at a time")

    # Get the uploaded file
    [user_file] = request.FILES.values()
    assert isinstance(user_file, UploadedFile)

    file_size = user_file.size
    assert file_size is not None

    # Validate file size
    max_file_upload_size_mib = user_profile.realm.get_max_file_upload_size_mebibytes()
    if file_size > max_file_upload_size_mib * 1024 * 1024:
        raise JsonableError(
            f"File is larger than the maximum upload size ({max_file_upload_size_mib} MiB)."
        )

    # Check upload quota
    check_upload_within_quota(user_profile.realm, file_size)

    # Upload the file using Zulip's infrastructure
    url, filename = upload_message_attachment_from_request(user_file, user_profile)

    logger.info(
        "File uploaded: %s by user %s (realm %s)",
        filename,
        user_profile.id,
        user_profile.realm.string_id,
    )

    return JsonResponse(
        {
            "url": url,
            "filename": filename,
        }
    )
