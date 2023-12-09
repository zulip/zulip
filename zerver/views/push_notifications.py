import re
from typing import Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils.translation import gettext as _

from zerver.decorator import human_users_only, zulip_login_required
from zerver.lib.exceptions import (
    JsonableError,
    MissingRemoteRealmError,
    OrganizationOwnerRequiredError,
    RemoteRealmServerMismatchError,
)
from zerver.lib.push_notifications import (
    InvalidPushDeviceTokenError,
    add_push_device_token,
    b64_to_hex,
    remove_push_device_token,
    send_test_push_notification,
    uses_notification_bouncer,
)
from zerver.lib.remote_server import (
    UserDataForRemoteBilling,
    get_realms_info_for_push_bouncer,
    send_analytics_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import check_string
from zerver.models import PushDeviceToken, UserProfile


def check_app_id(var_name: str, val: object) -> str:
    # Garbage values should be harmless, but we can be picky
    # as insurance against bugs somewhere.
    s = check_string(var_name, val)
    if not re.fullmatch("[.a-zA-Z0-9-]+", s):
        raise JsonableError(_("Invalid app ID"))
    return s


def validate_token(token_str: str, kind: int) -> None:
    if token_str == "" or len(token_str) > 4096:
        raise JsonableError(_("Empty or invalid length token"))
    if kind == PushDeviceToken.APNS:
        # Validate that we can actually decode the token.
        try:
            b64_to_hex(token_str)
        except Exception:
            raise JsonableError(_("Invalid APNS token"))


@human_users_only
@has_request_variables
def add_apns_device_token(
    request: HttpRequest,
    user_profile: UserProfile,
    token: str = REQ(),
    appid: str = REQ(str_validator=check_app_id),
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    add_push_device_token(user_profile, token, PushDeviceToken.APNS, ios_app_id=appid)
    return json_success(request)


@human_users_only
@has_request_variables
def add_android_reg_id(
    request: HttpRequest, user_profile: UserProfile, token: str = REQ()
) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    add_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success(request)


@human_users_only
@has_request_variables
def remove_apns_device_token(
    request: HttpRequest, user_profile: UserProfile, token: str = REQ()
) -> HttpResponse:
    validate_token(token, PushDeviceToken.APNS)
    remove_push_device_token(user_profile, token, PushDeviceToken.APNS)
    return json_success(request)


@human_users_only
@has_request_variables
def remove_android_reg_id(
    request: HttpRequest, user_profile: UserProfile, token: str = REQ()
) -> HttpResponse:
    validate_token(token, PushDeviceToken.GCM)
    remove_push_device_token(user_profile, token, PushDeviceToken.GCM)
    return json_success(request)


@human_users_only
@has_request_variables
def send_test_push_notification_api(
    request: HttpRequest, user_profile: UserProfile, token: Optional[str] = REQ(default=None)
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


@zulip_login_required
@typed_endpoint
def self_hosting_auth_redirect(
    request: HttpRequest,
    *,
    next_page: Optional[str] = None,
) -> HttpResponse:  # nocoverage
    if not settings.DEVELOPMENT or not uses_notification_bouncer():
        return render(request, "404.html", status=404)

    user = request.user
    assert user.is_authenticated
    assert isinstance(user, UserProfile)
    if not user.has_billing_access:
        # We may want to replace this with an html error page at some point,
        # but this endpoint shouldn't be accessible via the UI to an unauthorized
        # user - and they need to directly enter the URL in their browser. So a json
        # error may be sufficient.
        raise OrganizationOwnerRequiredError

    realm_info = get_realms_info_for_push_bouncer(user.realm_id)[0]

    user_info = UserDataForRemoteBilling(
        uuid=user.uuid,
        email=user.delivery_email,
        full_name=user.full_name,
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
        send_analytics_to_push_bouncer(consider_usage_statistics=False)
        result = send_to_push_bouncer("POST", "server/billing", post_data)
    except RemoteRealmServerMismatchError:
        return render(request, "zilencer/remote_realm_server_mismatch_error.html", status=403)

    if result["result"] != "success":
        raise JsonableError(_("Error returned by the bouncer: {result}").format(result=result))

    redirect_url = result["billing_access_url"]
    assert isinstance(redirect_url, str)
    return HttpResponseRedirect(redirect_url)
