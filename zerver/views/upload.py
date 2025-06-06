import base64
import binascii
import os
from datetime import timedelta
from urllib.parse import quote, urlsplit

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import UploadedFile
from django.core.signing import BadSignature, TimestampSigner
from django.db import transaction
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.utils.http import content_disposition_header
from django.utils.translation import gettext as _

from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import zulip_redirect_to_login
from zerver.lib.attachments import validate_attachment_request
from zerver.lib.exceptions import JsonableError
from zerver.lib.mime_types import INLINE_MIME_TYPES, guess_type
from zerver.lib.response import json_success
from zerver.lib.storage import static_path
from zerver.lib.thumbnail import (
    THUMBNAIL_OUTPUT_FORMATS,
    BaseThumbnailFormat,
    StoredThumbnailFormat,
    get_image_thumbnail_path,
)
from zerver.lib.upload import (
    check_upload_within_quota,
    get_public_upload_root_url,
    upload_message_attachment_from_request,
)
from zerver.lib.upload.local import assert_is_local_storage_path
from zerver.lib.upload.s3 import get_signed_upload_url
from zerver.models import Attachment, ImageAttachment, Realm, UserProfile
from zerver.worker.thumbnail import ensure_thumbnails


def patch_disposition_header(response: HttpResponse, filename: str, is_attachment: bool) -> None:
    content_disposition = content_disposition_header(is_attachment, filename)

    if content_disposition is not None:
        response.headers["Content-Disposition"] = content_disposition


def internal_nginx_redirect(internal_path: str, content_type: str | None = None) -> HttpResponse:
    # The following headers from this initial response are
    # _preserved_, if present, and sent unmodified to the client;
    # all other headers are overridden by the redirected URL:
    #  - Content-Type
    #  - Content-Disposition
    #  - Accept-Ranges
    #  - Set-Cookie
    #  - Cache-Control
    #  - Expires
    # As such, we default to unsetting the Content-type header to
    # allow nginx to set it from the static file; the caller can set
    # Content-Disposition and Cache-Control on this response as they
    # desire, and the client will see those values.  In some cases
    # (local files) we do wish to control the Content-Type, so also
    # support setting it explicitly.
    response = HttpResponse(content_type=content_type)
    response["X-Accel-Redirect"] = internal_path
    if content_type is None:
        del response["Content-Type"]
    return response


def serve_s3(
    request: HttpRequest, path_id: str, filename: str, force_download: bool = False
) -> HttpResponse:
    url = get_signed_upload_url(path_id, filename, force_download=force_download)
    assert url.startswith("https://")

    if settings.DEVELOPMENT:
        # In development, we do not have the nginx server to offload
        # the response to; serve a redirect to the short-lived S3 URL.
        # This means the content cannot be cached by the browser, but
        # this is acceptable in development.
        return redirect(url)

    # We over-escape the path, to work around it being impossible to
    # get the _unescaped_ new internal request URL in nginx.
    parsed_url = urlsplit(url)
    assert parsed_url.hostname is not None
    assert parsed_url.path is not None
    assert parsed_url.query is not None
    escaped_path_parts = parsed_url.hostname + quote(parsed_url.path) + "?" + parsed_url.query
    response = internal_nginx_redirect("/internal/s3/" + escaped_path_parts)

    # It is important that S3 generate both the Content-Type and
    # Content-Disposition headers; when the file was uploaded, we
    # stored the browser-provided value for the former, and set
    # Content-Disposition according to if that was safe.  As such,
    # only S3 knows if a given attachment is safe to inline; we only
    # override Content-Disposition to "attachment", and do so by
    # telling S3 that is what we want in the signed URL.
    patch_cache_control(response, private=True, immutable=True)
    return response


def serve_local(
    request: HttpRequest,
    path_id: str,
    filename: str,
    force_download: bool = False,
    mimetype: str | None = None,
) -> HttpResponseBase:
    assert settings.LOCAL_FILES_DIR is not None
    local_path = os.path.join(settings.LOCAL_FILES_DIR, path_id)
    assert_is_local_storage_path("files", local_path)
    if not os.path.isfile(local_path):
        return HttpResponseNotFound("<p>File not found</p>")

    if mimetype is None:
        mimetype = guess_type(filename)[0]
    download = force_download or mimetype not in INLINE_MIME_TYPES

    if settings.DEVELOPMENT:
        # In development, we do not have the nginx server to offload
        # the response to; serve it directly ourselves.  FileResponse
        # handles setting Content-Type, Content-Disposition, etc.
        response: HttpResponseBase = FileResponse(
            open(local_path, "rb"),  # noqa: SIM115
            as_attachment=download,
            filename=filename,
            content_type=mimetype,
        )
        patch_cache_control(response, private=True, immutable=True)
        return response

    # For local responses, we are in charge of generating both
    # Content-Type and Content-Disposition headers; unlike with S3
    # storage, the Content-Type is not stored with the file in any
    # way, so Django makes the determination of it, and thus as well
    # if that type is safe to have a Content-Disposition of "inline".
    # nginx respects the values we send.
    response = internal_nginx_redirect(
        quote(f"/internal/local/uploads/{path_id}"), content_type=mimetype
    )
    patch_disposition_header(response, filename, download)
    patch_cache_control(response, private=True, immutable=True)
    return response


def serve_file_download_backend(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    realm_id_str: str,
    filename: str,
) -> HttpResponseBase:
    return serve_file(
        request, maybe_user_profile, realm_id_str, filename, url_only=False, force_download=True
    )


def serve_file_backend(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    realm_id_str: str,
    filename: str,
    thumbnail_format: str | None = None,
) -> HttpResponseBase:
    return serve_file(
        request,
        maybe_user_profile,
        realm_id_str,
        filename,
        url_only=False,
        thumbnail_format=thumbnail_format,
    )


def serve_file_url_backend(
    request: HttpRequest, user_profile: UserProfile, realm_id_str: str, filename: str
) -> HttpResponseBase:
    """
    We should return a signed, short-lived URL
    that the client can use for native mobile download, rather than serving a redirect.
    """

    return serve_file(request, user_profile, realm_id_str, filename, url_only=True)


def closest_thumbnail_format(
    requested_format: BaseThumbnailFormat,
    request: HttpRequest,
    rendered_formats: list[StoredThumbnailFormat],
) -> StoredThumbnailFormat:
    # Serve a "close" format -- preferring animated which
    # matches, followed by the format they requested, or one
    # their browser supports, in the size closest to what they
    # requested, with the minimum bytes.
    def grade_format(
        possible_format: StoredThumbnailFormat,
    ) -> tuple[bool, bool, float, int, int]:
        return (
            possible_format.animated != requested_format.animated,
            possible_format.extension != requested_format.extension,
            0.0
            if (accepted_type := request.accepted_type(possible_format.content_type)) is None
            else -accepted_type.quality,
            abs(requested_format.max_width - possible_format.max_width),
            possible_format.byte_size,
        )

    return min(rendered_formats, key=grade_format)


def serve_file(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    realm_id_str: str,
    filename: str,
    thumbnail_format: str | None = None,
    url_only: bool = False,
    force_download: bool = False,
) -> HttpResponseBase:
    path_id = f"{realm_id_str}/{filename}"
    realm = get_valid_realm_from_request(request)
    is_authorized, attachment = validate_attachment_request(maybe_user_profile, path_id, realm)

    def serve_image_error(status: int, image_path: str) -> HttpResponseBase:
        # We cannot use X-Accel-Redirect to offload the serving of
        # this image to nginx, because it does not preserve the status
        # code of this response, nor the Vary: header.
        return FileResponse(open(static_path(image_path), "rb"), status=status)

    if attachment is None:
        if request.get_preferred_type(["text/html", "image/png"]) == "image/png":
            response = serve_image_error(404, "images/errors/image-not-exist.png")
        else:
            response = HttpResponseNotFound(
                _("<p>This file does not exist or has been deleted.</p>")
            )
        patch_vary_headers(response, ("Accept",))
        return response
    if not is_authorized:
        if request.get_preferred_type(["text/html", "image/png"]) == "image/png":
            response = serve_image_error(403, "images/errors/image-no-auth.png")
        elif isinstance(maybe_user_profile, AnonymousUser):
            response = zulip_redirect_to_login(request)
        else:
            response = HttpResponseForbidden(_("<p>You are not authorized to view this file.</p>"))
        patch_vary_headers(response, ("Accept",))
        return response
    if url_only:
        url = generate_unauthed_file_access_url(path_id)
        return json_success(request, data=dict(url=url))

    if thumbnail_format is not None:
        # Check if this is something that we thumbnail at all
        try:
            image_attachment = ImageAttachment.objects.get(path_id=path_id)
        except ImageAttachment.DoesNotExist:
            return serve_image_error(404, "images/errors/image-not-exist.png")

        # Validate that this is a potential thumbnail format
        requested_format = BaseThumbnailFormat.from_string(thumbnail_format)
        if requested_format is None:
            return serve_image_error(404, "images/errors/image-not-exist.png")

        rendered_formats = [StoredThumbnailFormat(**f) for f in image_attachment.thumbnail_metadata]

        # We never generate animated versions if the input was still,
        # so filter those out
        if image_attachment.frames == 1:
            potential_output_formats = [
                thumbnail_format
                for thumbnail_format in THUMBNAIL_OUTPUT_FORMATS
                if not thumbnail_format.animated
            ]
        else:
            potential_output_formats = list(THUMBNAIL_OUTPUT_FORMATS)
        if requested_format not in potential_output_formats:
            if rendered_formats == []:
                # We haven't rendered anything, and they requested
                # something we don't support.
                return serve_image_error(404, "images/errors/image-not-exist.png")
            elif requested_format in rendered_formats:
                # Not a _current_ format, but we did render it at the
                # time, so fine to serve.  We also end up here for
                # TRANSCODED_IMAGE_FORMAT requests, which are not in
                # the default THUMBNAIL_OUTPUT_FORMATS, but may exist
                # for some images types not in INLINE_MIME_TYPES.
                pass
            else:
                # Find something "close enough".  This will not be a
                # common occurrence -- the client has out of date
                # information about which formats are supported, and
                # the thumbnails were generated with an even earlier
                # set, or the client is just guessing a format and
                # hoping.
                requested_format = closest_thumbnail_format(
                    requested_format, request, rendered_formats
                )
        elif requested_format not in rendered_formats:
            # They requested a valid format, but one we've not
            # rendered yet.  Take a lock on the row, then render every
            # missing format, synchronously.  The lock prevents us
            # from doing double-work if the background worker is
            # currently processing the row.
            with transaction.atomic(savepoint=False):
                ensure_thumbnails(
                    ImageAttachment.objects.select_for_update().get(id=image_attachment.id),
                )

        # Update the path that we are fetching to be the thumbnail
        path_id = get_image_thumbnail_path(image_attachment, requested_format)
        served_filename = str(requested_format)
        mimetype: str | None = None  # Guess from filename
    else:
        served_filename = attachment.file_name
        mimetype = attachment.content_type

    if settings.LOCAL_UPLOADS_DIR is not None:
        return serve_local(
            request,
            path_id,
            filename=served_filename,
            force_download=force_download,
            mimetype=mimetype,
        )
    else:
        return serve_s3(request, path_id, served_filename, force_download=force_download)


USER_UPLOADS_ACCESS_TOKEN_SALT = "user_uploads_"


def generate_unauthed_file_access_url(path_id: str) -> str:
    signed_data = TimestampSigner(salt=USER_UPLOADS_ACCESS_TOKEN_SALT).sign(path_id)
    token = base64.b16encode(signed_data.encode()).decode()

    filename = path_id.split("/")[-1]
    return reverse("file_unauthed_from_token", args=[token, filename])


def get_file_path_id_from_token(token: str) -> str | None:
    signer = TimestampSigner(salt=USER_UPLOADS_ACCESS_TOKEN_SALT)
    try:
        signed_data = base64.b16decode(token).decode()
        path_id = signer.unsign(
            signed_data, max_age=timedelta(seconds=settings.SIGNED_ACCESS_TOKEN_VALIDITY_IN_SECONDS)
        )
    except (BadSignature, binascii.Error):
        return None

    return path_id


def serve_file_unauthed_from_token(
    request: HttpRequest, token: str, filename: str
) -> HttpResponseBase:
    path_id = get_file_path_id_from_token(token)
    if path_id is None:
        raise JsonableError(_("Invalid token"))
    if path_id.split("/")[-1] != filename:
        raise JsonableError(_("Invalid filename"))
    try:
        attachment = Attachment.objects.get(path_id=path_id)
    except Attachment.DoesNotExist:
        raise JsonableError(_("Invalid token"))

    if settings.LOCAL_UPLOADS_DIR is not None:
        return serve_local(
            request,
            path_id,
            filename=attachment.file_name,
            mimetype=attachment.content_type,
        )
    else:
        return serve_s3(request, path_id, attachment.file_name)


def serve_local_avatar_unauthed(request: HttpRequest, path: str) -> HttpResponseBase:
    """Serves avatar images off disk, via nginx (or directly in dev), with no auth.

    This is done unauthed because these need to be accessed from HTML
    emails, where the client does not have any auth.  We rely on the
    URL being generated using the AVATAR_SALT secret.

    """
    if settings.LOCAL_AVATARS_DIR is None:
        # We do not expect clients to hit this URL when using the S3
        # backend; however, there is no reason to not serve the
        # redirect to S3 where the content lives.
        url = get_public_upload_root_url() + path
        return redirect(url, permanent=True)

    local_path = os.path.join(settings.LOCAL_AVATARS_DIR, path)
    assert_is_local_storage_path("avatars", local_path)
    if not os.path.isfile(local_path):
        return HttpResponseNotFound("<p>File not found</p>")

    if settings.DEVELOPMENT:
        response: HttpResponseBase = FileResponse(open(local_path, "rb"))  # noqa: SIM115
    else:
        response = internal_nginx_redirect(quote(f"/internal/local/user_avatars/{path}"))

    patch_cache_control(response, max_age=31536000, public=True, immutable=True)
    return response


def upload_file_backend(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if len(request.FILES) == 0:
        raise JsonableError(_("You must specify a file to upload"))
    if len(request.FILES) != 1:
        raise JsonableError(_("You may only upload one file at a time"))

    [user_file] = request.FILES.values()
    assert isinstance(user_file, UploadedFile)
    file_size = user_file.size
    assert file_size is not None
    max_file_upload_size_mebibytes = user_profile.realm.get_max_file_upload_size_mebibytes()
    if file_size > max_file_upload_size_mebibytes * 1024 * 1024:
        if user_profile.realm.plan_type != Realm.PLAN_TYPE_SELF_HOSTED:
            raise JsonableError(
                _(
                    "File is larger than the maximum upload size ({max_size} MiB) allowed by your organization's plan."
                ).format(
                    max_size=max_file_upload_size_mebibytes,
                )
            )
        else:
            raise JsonableError(
                _(
                    "File is larger than this server's configured maximum upload size ({max_size} MiB)."
                ).format(
                    max_size=max_file_upload_size_mebibytes,
                )
            )
    check_upload_within_quota(user_profile.realm, file_size)

    url, filename = upload_message_attachment_from_request(user_file, user_profile)

    # TODO/compatibility: uri is a deprecated alias for url that can
    # be removed once there are no longer clients relying on it.
    return json_success(request, data={"uri": url, "url": url, "filename": filename})
