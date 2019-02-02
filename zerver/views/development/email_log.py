from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET

from zerver.models import (
    get_realm, get_user_by_delivery_email, get_realm_stream, Realm,
)
from zerver.lib.notifications import enqueue_welcome_emails
from zerver.lib.response import json_success
from zerver.lib.actions import do_change_user_delivery_email, \
    do_send_realm_reactivation_email
from zproject.email_backends import (
    get_forward_address,
    set_forward_address,
)
import urllib
from confirmation.models import Confirmation, confirmation_url

import os
import subprocess
import ujson

ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')

def email_page(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        set_forward_address(request.POST["forward_address"])
        return json_success()
    try:
        with open(settings.EMAIL_CONTENT_LOG_PATH, "r+") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return render(request, 'zerver/email_log.html',
                  {'log': content,
                   'forward_address': get_forward_address()})

def clear_emails(request: HttpRequest) -> HttpResponse:
    try:
        os.remove(settings.EMAIL_CONTENT_LOG_PATH)
    except FileNotFoundError:  # nocoverage
        pass
    return redirect(email_page)

@require_GET
def generate_all_emails(request: HttpRequest) -> HttpResponse:
    if not settings.TEST_SUITE:  # nocoverage
        # It's really convenient to automatically inline the email CSS
        # here, since that saves a step when testing out changes to
        # the email CSS.  But we don't run this inside the test suite,
        # because by role, the tests shouldn't be doing a provision-like thing.
        subprocess.check_call(["./tools/inline-email-css"])

    # We import the Django test client inside the view function,
    # because it isn't needed in production elsewhere, and not
    # importing it saves ~50ms of unnecessary manage.py startup time.

    from django.test import Client
    client = Client()

    # write fake data for all variables
    registered_email = "hamlet@zulip.com"
    unregistered_email_1 = "new-person@zulip.com"
    unregistered_email_2 = "new-person-2@zulip.com"
    realm = get_realm("zulip")
    other_realm = Realm.objects.exclude(string_id='zulip').first()
    user = get_user_by_delivery_email(registered_email, realm)
    host_kwargs = {'HTTP_HOST': realm.host}

    # Password reset emails
    # active account in realm
    result = client.post('/accounts/password/reset/', {'email': registered_email}, **host_kwargs)
    assert result.status_code == 302
    # deactivated user
    user.is_active = False
    user.save(update_fields=['is_active'])
    result = client.post('/accounts/password/reset/', {'email': registered_email}, **host_kwargs)
    assert result.status_code == 302
    user.is_active = True
    user.save(update_fields=['is_active'])
    # account on different realm
    result = client.post('/accounts/password/reset/', {'email': registered_email},
                         HTTP_HOST=other_realm.host)
    assert result.status_code == 302
    # no account anywhere
    result = client.post('/accounts/password/reset/', {'email': unregistered_email_1}, **host_kwargs)
    assert result.status_code == 302

    # Confirm account email
    result = client.post('/accounts/home/', {'email': unregistered_email_1}, **host_kwargs)
    assert result.status_code == 302

    # Find account email
    result = client.post('/accounts/find/', {'emails': registered_email}, **host_kwargs)
    assert result.status_code == 302

    # New login email
    logged_in = client.login(dev_auth_username=registered_email, realm=realm)
    assert logged_in

    # New user invite and reminder emails
    stream = get_realm_stream("Denmark", get_realm("zulip"))
    result = client.post("/json/invites",
                         {"invitee_emails": unregistered_email_2,
                          "stream_ids": ujson.dumps([stream.id])},
                         **host_kwargs)
    assert result.status_code == 200

    # Verification for new email
    result = client.patch('/json/settings',
                          urllib.parse.urlencode({'email': 'hamlets-new@zulip.com'}),
                          **host_kwargs)
    assert result.status_code == 200

    # Email change successful
    key = Confirmation.objects.filter(type=Confirmation.EMAIL_CHANGE).latest('id').confirmation_key
    url = confirmation_url(key, realm.host, Confirmation.EMAIL_CHANGE)
    user_profile = get_user_by_delivery_email(registered_email, realm)
    result = client.get(url)
    assert result.status_code == 200

    # Reset the email value so we can run this again
    do_change_user_delivery_email(user_profile, registered_email)

    # Follow up day1 day2 emails for normal user
    enqueue_welcome_emails(user_profile)

    # Follow up day1 day2 emails for admin user
    enqueue_welcome_emails(get_user_by_delivery_email("iago@zulip.com", realm), realm_creation=True)

    # Realm reactivation email
    do_send_realm_reactivation_email(realm)

    return redirect(email_page)
