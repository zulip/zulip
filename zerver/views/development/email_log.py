import os
import urllib
from contextlib import suppress
from typing import Optional

import orjson
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_safe

from confirmation.models import Confirmation, confirmation_url
from zerver.actions.realm_settings import do_send_realm_reactivation_email
from zerver.actions.user_settings import do_change_user_delivery_email
from zerver.actions.users import change_user_is_active
from zerver.lib.email_notifications import enqueue_welcome_emails, send_account_registered_email
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import Realm, get_realm, get_realm_stream, get_user_by_delivery_email
from zerver.views.invite import INVITATION_LINK_VALIDITY_MINUTES
from zproject.email_backends import get_forward_address, set_forward_address

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")


@has_request_variables
def email_page(
    request: HttpRequest, forward_address: Optional[str] = REQ(default=None)
) -> HttpResponse:
    if request.method == "POST":
        assert forward_address is not None
        set_forward_address(forward_address)
        return json_success(request)
    try:
        with open(settings.EMAIL_CONTENT_LOG_PATH, "r+") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return render(
        request,
        "zerver/development/email_log.html",
        {"log": content, "forward_address": get_forward_address()},
    )


def clear_emails(request: HttpRequest) -> HttpResponse:
    with suppress(FileNotFoundError):
        os.remove(settings.EMAIL_CONTENT_LOG_PATH)
    return redirect(email_page)


@require_safe
def generate_all_emails(request: HttpRequest) -> HttpResponse:
    # We import the Django test client inside the view function,
    # because it isn't needed in production elsewhere, and not
    # importing it saves ~50ms of unnecessary manage.py startup time.

    from django.test import Client

    client = Client()

    # write fake data for all variables
    registered_email = "hamlet@zulip.com"
    unregistered_email_1 = "new-person@zulip.com"
    unregistered_email_2 = "new-person-2@zulip.com"
    invite_expires_in_minutes = INVITATION_LINK_VALIDITY_MINUTES
    realm = get_realm("zulip")
    other_realm = Realm.objects.exclude(string_id="zulip").first()
    user = get_user_by_delivery_email(registered_email, realm)

    # Password reset emails
    # active account in realm
    result = client.post(
        "/accounts/password/reset/", {"email": registered_email}, HTTP_HOST=realm.host
    )
    assert result.status_code == 302
    # deactivated user
    change_user_is_active(user, False)
    result = client.post(
        "/accounts/password/reset/", {"email": registered_email}, HTTP_HOST=realm.host
    )
    assert result.status_code == 302
    change_user_is_active(user, True)
    # account on different realm
    assert other_realm is not None
    result = client.post(
        "/accounts/password/reset/", {"email": registered_email}, HTTP_HOST=other_realm.host
    )
    assert result.status_code == 302
    # no account anywhere
    result = client.post(
        "/accounts/password/reset/", {"email": unregistered_email_1}, HTTP_HOST=realm.host
    )
    assert result.status_code == 302

    # Confirm account email
    result = client.post("/accounts/home/", {"email": unregistered_email_1}, HTTP_HOST=realm.host)
    assert result.status_code == 302

    # Find account email
    result = client.post("/accounts/find/", {"emails": registered_email}, HTTP_HOST=realm.host)
    assert result.status_code == 302

    # New login email
    logged_in = client.login(dev_auth_username=registered_email, realm=realm)
    assert logged_in

    # New user invite and reminder emails
    stream = get_realm_stream("Denmark", user.realm.id)
    result = client.post(
        "/json/invites",
        {
            "invitee_emails": unregistered_email_2,
            "invite_expires_in_minutes": invite_expires_in_minutes,
            "stream_ids": orjson.dumps([stream.id]).decode(),
        },
        HTTP_HOST=realm.host,
    )
    assert result.status_code == 200

    # Verification for new email
    result = client.patch(
        "/json/settings",
        urllib.parse.urlencode({"email": "hamlets-new@zulip.com"}),
        content_type="application/x-www-form-urlencoded",
        HTTP_HOST=realm.host,
    )
    assert result.status_code == 200

    # Email change successful
    key = Confirmation.objects.filter(type=Confirmation.EMAIL_CHANGE).latest("id").confirmation_key
    url = confirmation_url(key, realm, Confirmation.EMAIL_CHANGE)
    user_profile = get_user_by_delivery_email(registered_email, realm)
    result = client.get(url)
    assert result.status_code == 200

    # Reset the email value so we can run this again
    do_change_user_delivery_email(user_profile, registered_email)

    # Initial email with new account information for normal user.
    send_account_registered_email(user_profile)

    # Follow up day2 and onboarding zulip guide emails for normal user
    enqueue_welcome_emails(user_profile)

    # Initial email with new account information for admin user
    send_account_registered_email(get_user_by_delivery_email("iago@zulip.com", realm))

    # Follow up day2 and onboarding zulip guide emails for admin user
    enqueue_welcome_emails(get_user_by_delivery_email("iago@zulip.com", realm))

    # Realm reactivation email
    do_send_realm_reactivation_email(realm, acting_user=None)

    return redirect(email_page)
