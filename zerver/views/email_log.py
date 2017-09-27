#!/usr/bin/env python3

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.test import Client
from django.views.decorators.http import require_GET

from zerver.models import get_realm, get_user
from zerver.lib.initial_password import initial_password
from zerver.lib.notifications import enqueue_welcome_emails
from six.moves import urllib
from confirmation.models import Confirmation, confirmation_url

import os
from typing import List, Dict, Any, Optional
import datetime
ZULIP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')
client = Client()

def email_page(request, message=None):
    # type: (HttpRequest, Optional[str]) -> HttpResponse
    if message is None:
        message = '''
All the emails sent in the Zulip development environment are logged here. You can also
manually generate most of the emails by clicking <a href="/emails/generate">here</a>.
To clear this log click <a href="/emails/clear">here</a>.
'''
    try:
        with open(settings.EMAIL_CONTENT_LOG_PATH, "r+") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return render(request, 'zerver/email_log.html', {'log': content, 'message': message})

def clear_emails(request):
    # type: (HttpRequest) -> HttpResponse
    try:
        os.remove(settings.EMAIL_CONTENT_LOG_PATH)
    except FileNotFoundError:
        pass
    return redirect(email_page)

@require_GET
def generate_all_emails(request):
    # type: (HttpRequest) -> HttpResponse

    # write fake data for all variables
    registered_email = "hamlet@zulip.com"
    unregistered_email_1 = "new-person@zulip.com"
    unregistered_email_2 = "new-person-2@zulip.com"
    realm = get_realm("zulip")

    # Password reset email
    client.post('/accounts/password/reset/', {'email': registered_email})

    # Confirm account email
    client.post('/accounts/home/', {'email': unregistered_email_1})

    # Find account email
    client.post('/accounts/find/', {'emails': registered_email})

    # New login email
    password = initial_password(registered_email)
    client.login(username=registered_email, password=password)

    # New user invite and reminder emails
    client.post("/json/invites", {"invitee_emails": unregistered_email_2, "stream": ["Denmark"], "custom_body": ""})

    # Verification for new email
    client.patch('/json/settings', urllib.parse.urlencode({'email': 'hamlets-new@zulip.com'}))

    # Email change successful
    key = Confirmation.objects.filter(type=Confirmation.EMAIL_CHANGE).latest('id').confirmation_key
    url = confirmation_url(key, realm.host, Confirmation.EMAIL_CHANGE)
    user_profile = get_user(registered_email, realm)
    client.get(url)
    user_profile.emails = "hamlet@zulip.com"
    user_profile.save()

    # Follow up day1 day2 emails
    enqueue_welcome_emails(user_profile)
    message = '''
Emails generated successfully. Reload this page to generate them again.
To clear this log click <a href="/emails/clear">here</a>.
'''
    return email_page(request, message)
