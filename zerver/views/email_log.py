from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.test import Client
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

from zerver.models import get_realm, get_user
from zerver.lib.notifications import enqueue_welcome_emails
from zerver.lib.response import json_success
from zproject.email_backends import (
    get_forward_address,
    set_forward_address,
)
from six.moves import urllib
from confirmation.models import Confirmation, confirmation_url

import os
from typing import List, Dict, Any, Optional
import datetime
ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')
client = Client()

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

    # write fake data for all variables
    registered_email = "hamlet@zulip.com"
    unregistered_email_1 = "new-person@zulip.com"
    unregistered_email_2 = "new-person-2@zulip.com"
    realm = get_realm("zulip")
    host_kwargs = {'HTTP_HOST': realm.host}

    # Password reset email
    result = client.post('/accounts/password/reset/', {'email': registered_email}, **host_kwargs)
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
    result = client.post("/json/invites",
                         {"invitee_emails": unregistered_email_2, "stream": ["Denmark"]},
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
    user_profile = get_user(registered_email, realm)
    result = client.get(url)
    assert result.status_code == 200

    # Reset the email value so we can run this again
    user_profile.email = registered_email
    user_profile.save(update_fields=['email'])

    # Follow up day1 day2 emails
    enqueue_welcome_emails(user_profile)
    return redirect(email_page)
