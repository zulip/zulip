from typing import Annotated, Any

import orjson
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_pascal

from zerver.decorator import get_basic_credentials, validate_api_key
from zerver.lib.exceptions import AccessDeniedError, JsonableError
from zerver.lib.mime_types import guess_type
from zerver.lib.rate_limiter import is_local_addr
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.upload import (
    RealmUploadQuotaError,
    attachment_vips_source,
    check_upload_within_quota,
    create_attachment,
    delete_message_attachment,
    sanitize_name,
    upload_backend,
)
from zerver.models import UserProfile


# See https://tus.github.io/tusd/advanced-topics/hooks/ for the spec
# for these.
class TusUpload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_pascal)
    id: Annotated[str, Field(alias="ID")]
    size: int | None
    size_is_deferred: bool
    offset: int
    meta_data: dict[str, str]
    is_partial: bool
    is_final: bool
    partial_uploads: list[str] | None
    storage: dict[str, str] | None


class TusHTTPRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_pascal)
    method: str
    uri: Annotated[str, Field(alias="URI")]
    remote_addr: str
    header: dict[str, list[str]]


class TusEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_pascal)
    upload: TusUpload
    http_request: Annotated[TusHTTPRequest, Field(alias="HTTPRequest")]


class TusHook(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_pascal)
    type: str
    event: TusEvent


# Note that we do not raise JsonableError in these views
# because our client is not a consumer of the Zulip API -- it's tusd,
# which has its own ideas of what error responses look like.
def tusd_json_response(data: dict[str, Any]) -> HttpResponse:
    return HttpResponse(
        content=orjson.dumps(data, option=orjson.OPT_APPEND_NEWLINE),
        content_type="application/json",
        status=200,
    )


def reject_upload(message: str, status_code: int) -> HttpResponse:
    # Due to https://github.com/transloadit/uppy/issues/5460, uppy
    # will retry responses with a statuscode of exactly 400, so we
    # return 4xx status codes which are more specific to trigger an
    # immediate rejection.
    return tusd_json_response(
        {
            "HttpResponse": {
                "StatusCode": status_code,
                "Body": orjson.dumps({"message": message}).decode(),
                "Header": {
                    "Content-Type": "application/json",
                },
            },
            "RejectUpload": True,
        }
    )


def handle_upload_pre_create_hook(
    request: HttpRequest, user_profile: UserProfile, data: TusUpload
) -> HttpResponse:
    if data.size_is_deferred or data.size is None:
        return reject_upload("SizeIsDeferred is not supported", 411)

    if data.size > settings.MAX_FILE_UPLOAD_SIZE * 1024 * 1024:
        return reject_upload(
            _("Uploaded file is larger than the allowed limit of {max_file_size} MiB").format(
                max_file_size=settings.MAX_FILE_UPLOAD_SIZE
            ),
            413,
        )
    try:
        check_upload_within_quota(user_profile.realm, data.size)
    except RealmUploadQuotaError as e:
        return reject_upload(str(e), 413)

    # Determine the path_id to store it at
    file_name = sanitize_name(data.meta_data.get("filename", ""))
    path_id = upload_backend.generate_message_upload_path(str(user_profile.realm_id), file_name)
    return tusd_json_response({"ChangeFileInfo": {"ID": path_id}})


def handle_upload_pre_finish_hook(
    request: HttpRequest, user_profile: UserProfile, data: TusUpload
) -> HttpResponse:
    metadata = data.meta_data
    filename = metadata.get("filename", "")
    # We want to store as the filename a version that clients are
    # likely to be able to accept via "Save as..."
    if filename in {"", ".", ".."}:
        filename = "uploaded-file"

    content_type = metadata.get("filetype")
    if not content_type:
        content_type = guess_type(filename)[0]
        if content_type is None:
            content_type = "application/octet-stream"

    # With an S3 backend, the filename we passed in pre_create's
    # data.id has a randomly-generated "mutlipart-id" appended with a
    # `+`.  Our path_ids cannot contain `+`, so we strip any suffix
    # starting with `+`.
    path_id = data.id.partition("+")[0]

    # https://tus.github.io/tusd/storage-backends/overview/#storage-format
    # tusd creates a .info file next to the upload, which we do not
    # need to keep.  Clean it up.
    delete_message_attachment(f"{path_id}.info")

    with transaction.atomic():
        create_attachment(
            filename,
            path_id,
            content_type,
            attachment_vips_source(path_id),
            user_profile,
            user_profile.realm,
        )

    path = "/user_uploads/" + path_id
    return tusd_json_response(
        {
            "HttpResponse": {
                "StatusCode": 200,
                "Body": orjson.dumps({"url": path, "filename": filename}).decode(),
                "Header": {
                    "Content-Type": "application/json",
                },
            },
        }
    )


def authenticate_user(request: HttpRequest) -> UserProfile | AnonymousUser:
    # This acts like the authenticated_rest_api_view wrapper, while
    # allowing fallback to session-based request.user
    if "Authorization" in request.headers:
        try:
            role, api_key = get_basic_credentials(request)
            return validate_api_key(
                request,
                role,
                api_key,
            )

        except JsonableError:
            pass

    # If that failed, fall back to session auth
    return request.user


@csrf_exempt
@typed_endpoint
def handle_tusd_hook(
    request: HttpRequest,
    *,
    payload: JsonBodyPayload[TusHook],
) -> HttpResponse:
    # Make sure this came from localhost
    if not is_local_addr(request.META["REMOTE_ADDR"]):
        raise AccessDeniedError

    maybe_user = authenticate_user(request)
    if isinstance(maybe_user, AnonymousUser):
        return reject_upload("Unauthenticated upload", 401)

    hook_name = payload.type
    if hook_name == "pre-create":
        return handle_upload_pre_create_hook(request, maybe_user, payload.event.upload)
    elif hook_name == "pre-finish":
        return handle_upload_pre_finish_hook(request, maybe_user, payload.event.upload)
    else:
        return HttpResponseNotFound()
