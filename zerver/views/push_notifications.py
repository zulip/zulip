from typing import Annotated

import orjson
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.decorator import human_users_only, zulip_login_required
from zerver.lib import redis_utils
from zerver.lib.exceptions import (
    ErrorCode,
    JsonableError,
    MissingRemoteRealmError,
    OrganizationOwnerRequiredError,
    RemoteRealmServerMismatchError,
    ResourceNotFoundError,
)
from zerver.lib.push_notifications import (
    InvalidPushDeviceTokenError,
    add_push_device_token,
    remove_push_device_token,
    send_test_push_notification,
    uses_notification_bouncer,
    validate_token,
)
from zerver.lib.push_registration import RegisterPushDeviceToBouncerQueueItem
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.remote_server import (
    SELF_HOSTING_REGISTRATION_TAKEOVER_CHALLENGE_TOKEN_REDIS_KEY,
    UserDataForRemoteBilling,
    get_realms_info_for_push_bouncer,
    send_server_data_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApnsAppId, typed_endpoint, typed_endpoint_without_parameters
from zerver.lib.typed_endpoint_validators import check_string_in_validator
from zerver.models import PushDevice, PushDeviceToken, UserProfile
from zerver.views.errors import config_error

redis_client = redis_utils.get_redis_client()


@human_users_only
@typed_endpoint
def add_apns_device_token(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    appid: ApnsAppId,
    token: str,
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    add_push_device_token(user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)
    return json_success(request)


@human_users_only
@typed_endpoint
def add_android_reg_id(
    request: HttpRequest, user_profile: UserProfile, *, token: str
) -> HttpResponse:
    validate_token(token, PushDeviceToken.FCM)
    add_push_device_token(user_profile, token, PushDeviceToken.FCM)
    return json_success(request)


@human_users_only
@typed_endpoint
def remove_apns_device_token(
    request: HttpRequest, user_profile: UserProfile, *, token: str
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    remove_push_device_token(user_profile, token, PushDeviceToken.APNS)
    return json_success(request)


@human_users_only
@typed_endpoint
def remove_android_reg_id(
    request: HttpRequest, user_profile: UserProfile, *, token: str
) -> HttpResponse:
    validate_token(token, PushDeviceToken.FCM)
    remove_push_device_token(user_profile, token, PushDeviceToken.FCM)
    return json_success(request)


@human_users_only
@typed_endpoint
def send_test_push_notification_api(
    request: HttpRequest, user_profile: UserProfile, *, token: str | None = None
) -> HttpResponse:
    # If a token is specified in the request, the test notification is supposed to be sent
    # to that device. If no token is provided, the test notification should be sent to
    # all devices registered for the user.
    if token is not None:
        try:
            devices = [PushDeviceToken.objects.get(token=token, user=user_profile)]
        except PushDeviceToken.DoesNotExist:
            raise InvalidPushDeviceTokenError
    else:
        devices = list(PushDeviceToken.objects.filter(user=user_profile))

    send_test_push_notification(user_profile, devices)

    return json_success(request)


def self_hosting_auth_view_common(
    request: HttpRequest, user_profile: UserProfile, next_page: str | None = None
) -> str:
    if not user_profile.has_billing_access:
        # We may want to replace this with an html error page at some point,
        # but this endpoint shouldn't be accessible via the UI to an unauthorized
        # user_profile - and they need to directly enter the URL in their browser. So a json
        # error may be sufficient.
        raise OrganizationOwnerRequiredError

    if not uses_notification_bouncer():
        if settings.CORPORATE_ENABLED:
            # This endpoint makes no sense on zulipchat.com, so just 404.
            raise ResourceNotFoundError(_("Server doesn't use the push notification service"))
        else:
            return reverse(self_hosting_auth_not_configured)

    realm_info = get_realms_info_for_push_bouncer(user_profile.realm_id)[0]

    user_info = UserDataForRemoteBilling(
        uuid=user_profile.uuid,
        email=user_profile.delivery_email,
        full_name=user_profile.full_name,
    )

    post_data = {
        "user": user_info.model_dump_json(),
        "realm": realm_info.model_dump_json(),
        # The uri_scheme is necessary for the bouncer to know the correct URL
        # to redirect the user to for re-authing in case the session expires.
        # Otherwise, the bouncer would know only the realm.host but be missing
        # the knowledge of whether to use http or https.
        "uri_scheme": settings.EXTERNAL_URI_SCHEME,
    }
    if next_page is not None:
        post_data["next_page"] = next_page

    try:
        result = send_to_push_bouncer("POST", "server/billing", post_data)
    except MissingRemoteRealmError:
        # Upload realm info and re-try. It should work now.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        result = send_to_push_bouncer("POST", "server/billing", post_data)

    if result["result"] != "success":  # nocoverage
        raise JsonableError(_("Error returned by the bouncer: {result}").format(result=result))

    redirect_url = result["billing_access_url"]
    assert isinstance(redirect_url, str)
    return redirect_url


@zulip_login_required
@typed_endpoint
def self_hosting_auth_redirect_endpoint(
    request: HttpRequest,
    *,
    next_page: str | None = None,
) -> HttpResponse:
    """
    This endpoint is used by the web app running in the browser. We serve HTML
    error pages, and in case of success a simple redirect to the remote billing
    access link received from the bouncer.
    """

    user = request.user
    assert user.is_authenticated
    assert isinstance(user, UserProfile)

    try:
        redirect_url = self_hosting_auth_view_common(request, user, next_page)
    except ResourceNotFoundError:
        return render(request, "404.html", status=404)
    except RemoteRealmServerMismatchError:
        return render(
            request,
            "zerver/portico_error_pages/remote_realm_server_mismatch_error.html",
            status=403,
        )

    return HttpResponseRedirect(redirect_url)


@typed_endpoint
def self_hosting_auth_json_endpoint(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    next_page: str | None = None,
) -> HttpResponse:
    """
    This endpoint is used by the desktop application. It makes an API request here,
    expecting a JSON response with either the billing access link, or appropriate
    error information.
    """

    redirect_url = self_hosting_auth_view_common(request, user_profile, next_page)

    return json_success(request, data={"billing_access_url": redirect_url})


@zulip_login_required
def self_hosting_auth_not_configured(request: HttpRequest) -> HttpResponse:
    # Use the same access model as the main endpoints for consistency
    # and to not have to worry about this endpoint leaking some kind of
    # sensitive configuration information in the future.
    user = request.user
    assert user.is_authenticated
    assert isinstance(user, UserProfile)
    if not user.has_billing_access:
        raise OrganizationOwnerRequiredError

    if settings.CORPORATE_ENABLED or uses_notification_bouncer():
        # This error page should only be available if the config error
        # is actually real.
        return render(request, "404.html", status=404)

    return config_error(
        request,
        "remote_billing_bouncer_not_configured",
        go_back_to_url="/",
        go_back_to_url_name="the app",
    )


class VerificationSecretNotPreparedError(JsonableError):
    code = ErrorCode.REMOTE_SERVER_VERIFICATION_SECRET_NOT_PREPARED

    def __init__(self) -> None:
        super().__init__(_("Verification secret not prepared"))


@typed_endpoint_without_parameters
def self_hosting_registration_transfer_challenge_verify(
    request: HttpRequest, access_token: str
) -> HttpResponse:
    json_data = redis_client.get(
        redis_utils.REDIS_KEY_PREFIX + SELF_HOSTING_REGISTRATION_TAKEOVER_CHALLENGE_TOKEN_REDIS_KEY
    )
    if json_data is None:
        raise VerificationSecretNotPreparedError

    data = orjson.loads(json_data)
    if data["access_token"] != access_token:
        # Without knowing the access_token, the client gets the same error
        # as if we're not serving the verification secret at all.
        raise VerificationSecretNotPreparedError

    verification_secret = data["verification_secret"]

    return json_success(request, data={"verification_secret": verification_secret})


@human_users_only
@typed_endpoint
def register_push_device(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    token_kind: Annotated[str, check_string_in_validator(PushDevice.TokenKind.values)],
    push_account_id: Json[int],
    # Key that the client is requesting be used for
    # encrypting push notifications for delivery to it.
    push_public_key: str,
    # Key that the client claims was used to encrypt
    # `encrypted_push_registration`.
    bouncer_public_key: str,
    # Registration data encrypted by mobile client for bouncer.
    encrypted_push_registration: str,
) -> HttpResponse:
    if not (settings.ZILENCER_ENABLED or uses_notification_bouncer()):
        raise JsonableError(_("Server is not configured to use push notification service."))

    # Idempotency
    already_registered = PushDevice.objects.filter(
        user=user_profile, push_account_id=push_account_id, error_code__isnull=True
    ).exists()
    if already_registered:
        return json_success(request)

    PushDevice.objects.update_or_create(
        user=user_profile,
        push_account_id=push_account_id,
        defaults={"token_kind": token_kind, "push_public_key": push_public_key, "error_code": None},
    )

    # We use a queue worker to make the request to the bouncer
    # to complete the registration, so that any transient failures
    # can be managed between the two servers, without the mobile
    # device and its often-irregular network access in the picture.
    queue_item: RegisterPushDeviceToBouncerQueueItem = {
        "user_profile_id": user_profile.id,
        "bouncer_public_key": bouncer_public_key,
        "encrypted_push_registration": encrypted_push_registration,
        "push_account_id": push_account_id,
    }
    queue_event_on_commit(
        "missedmessage_mobile_notifications",
        {
            "type": "register_push_device_to_bouncer",
            "payload": queue_item,
        },
    )

    return json_success(request)
