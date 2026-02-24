from typing import Annotated

import orjson
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.push_notifications import (
    do_register_push_device,
    do_rotate_push_key,
    do_rotate_token,
)
from zerver.decorator import human_users_only, zulip_login_required
from zerver.lib import redis_utils
from zerver.lib.devices import b64decode_token_id_base64, check_device_id
from zerver.lib.exceptions import (
    ErrorCode,
    JsonableError,
    MissingRemoteRealmError,
    OrganizationOwnerRequiredError,
    PushServiceNotConfiguredError,
    RemoteRealmServerMismatchError,
    ResourceNotFoundError,
)
from zerver.lib.push_notifications import (
    InvalidPushDeviceTokenError,
    NoActivePushDeviceError,
    add_push_device_token,
    remove_push_device_token,
    send_e2ee_test_push_notification,
    send_test_push_notification,
    uses_notification_bouncer,
    validate_token,
)
from zerver.lib.push_registration import RegisterPushDeviceToBouncerQueueItem, check_push_key
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.remote_server import (
    SELF_HOSTING_REGISTRATION_TAKEOVER_CHALLENGE_TOKEN_REDIS_KEY,
    UserDataForRemoteBilling,
    get_realms_info_for_push_bouncer,
    send_server_data_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import (
    ApiParamConfig,
    ApnsAppId,
    typed_endpoint,
    typed_endpoint_without_parameters,
)
from zerver.lib.typed_endpoint_validators import check_string_in_validator, uint32_validator
from zerver.models import Device, PushDeviceToken, UserProfile
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


@human_users_only
@typed_endpoint
def send_e2ee_test_push_notification_api(
    request: HttpRequest, user_profile: UserProfile, *, device_id: Json[int] | None = None
) -> HttpResponse:
    # We skip devices with `push_token_id` set to `null` as they are
    # not yet registered with the bouncer to send mobile push notifications.
    if device_id is not None:
        push_devices = Device.objects.filter(
            id=device_id, user=user_profile, push_token_id__isnull=False
        )
    else:
        # Uses 'zerver_device_user_push_token_id_idx' index.
        push_devices = Device.objects.filter(user=user_profile, push_token_id__isnull=False)

    if len(push_devices) == 0:
        raise NoActivePushDeviceError

    send_e2ee_test_push_notification(user_profile, push_devices)

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
    # `device_id` to configure for push notifications.
    device_id: Json[int],
    token_kind: Annotated[
        str | None, check_string_in_validator(Device.PushTokenKind.values)
    ] = None,
    # Key that the client is requesting be used for encrypting
    # push notifications for delivery to it.
    # Consists of a 1-byte prefix identifying the symmetric
    # cryptosystem in use, followed by the secret key.
    push_key: str | None = None,
    # ID which client uses to reference `push_key`.
    push_key_id: Annotated[Json[int] | None, uint32_validator()] = None,
    # Key that the client claims was used to encrypt
    # `encrypted_push_registration`.
    bouncer_public_key: str | None = None,
    # Registration data encrypted by mobile client for bouncer.
    encrypted_push_registration: str | None = None,
    # ID which client uses to reference token provided by FCM/APNs.
    token_id_base64: Annotated[str | None, ApiParamConfig("token_id")] = None,
) -> HttpResponse:
    if not (settings.ZILENCER_ENABLED or uses_notification_bouncer()):
        raise PushServiceNotConfiguredError

    device = check_device_id(device_id, user_profile.id)

    push_key_fields_present = push_key is not None and push_key_id is not None
    token_fields_present = (
        bouncer_public_key is not None
        and encrypted_push_registration is not None
        and token_id_base64 is not None
        and token_kind is not None
    )

    if not (push_key_fields_present or token_fields_present):
        raise JsonableError(
            _(
                "Missing parameters: must provide either all push key fields, all token fields, or both."
            )
        )

    if push_key_fields_present and not token_fields_present:
        if device.push_key_id is None:
            raise JsonableError(_("No push registration exists to rotate key for."))

        assert push_key is not None and push_key_id is not None
        push_key_bytes = check_push_key(push_key)
        do_rotate_push_key(user_profile, device, push_key_bytes, push_key_id)
        return json_success(request)

    # A registration request already in progress, don't enqueue another one
    # to bouncer to avoid bugs due to race.
    if device.push_registration_error_code is None and device.pending_push_token_id is not None:
        raise JsonableError(_("A registration for the device already in progress."))

    with transaction.atomic(durable=True):
        assert token_id_base64 is not None
        assert token_kind is not None
        assert bouncer_public_key is not None
        assert encrypted_push_registration is not None

        token_id_int = b64decode_token_id_base64(token_id_base64)
        if token_fields_present and not push_key_fields_present:
            if device.push_key_id is None:
                raise JsonableError(_("No push registration exists to rotate token for."))

            if device.push_registration_error_code is None and device.push_token_id == token_id_int:
                return json_success(request)

            do_rotate_token(user_profile, device, token_id_int, token_id_base64)

        # All fields present
        if push_key_fields_present and token_fields_present:
            assert push_key is not None
            assert push_key_id is not None
            push_key_bytes = check_push_key(push_key)

            # Idempotent
            if (
                device.push_registration_error_code is None
                and device.push_key_id == push_key_id
                and device.push_key is not None
                and bytes(device.push_key) == push_key_bytes
                and device.push_token_id == token_id_int
                and device.push_token_kind == token_kind
            ):
                return json_success(request)

            do_register_push_device(
                user_profile,
                device,
                token_kind=token_kind,
                push_key_bytes=push_key_bytes,
                push_key_id=push_key_id,
                token_id_int=token_id_int,
                token_id_base64=token_id_base64,
            )

        # We use a queue worker to make the request to the bouncer
        # to complete the registration, so that any transient failures
        # can be managed between the two servers, without the mobile
        # device and its often-irregular network access in the picture.
        queue_item: RegisterPushDeviceToBouncerQueueItem = {
            "user_profile_id": user_profile.id,
            "device_id": device_id,
            "bouncer_public_key": bouncer_public_key,
            "encrypted_push_registration": encrypted_push_registration,
            "token_id_base64": token_id_base64,
        }
        queue_event_on_commit(
            "missedmessage_mobile_notifications",
            {
                "type": "register_push_device_to_bouncer",
                "payload": queue_item,
            },
        )

    return json_success(request)
