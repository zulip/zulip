from __future__ import absolute_import

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from typing import Callable

from confirmation.models import Confirmation
from zerver.lib.actions import do_change_enable_offline_email_notifications, \
    do_change_enable_digest_emails, clear_followup_emails_queue
from zerver.models import UserProfile
from zerver.context_processors import common_context

def process_unsubscribe(request, token, subscription_type, unsubscribe_function):
    # type: (HttpRequest, str, str, Callable[[UserProfile], None]) -> HttpResponse
    try:
        confirmation = Confirmation.objects.get(confirmation_key=token)
    except Confirmation.DoesNotExist:
        return render(request, 'zerver/unsubscribe_link_error.html')

    user_profile = confirmation.content_object
    unsubscribe_function(user_profile)
    context = common_context(user_profile)
    context.update({"subscription_type": subscription_type})
    return render(request, 'zerver/unsubscribe_success.html', context=context)

# Email unsubscribe functions. All have the function signature
# processor(user_profile).

def do_missedmessage_unsubscribe(user_profile):
    # type: (UserProfile) -> None
    do_change_enable_offline_email_notifications(user_profile, False)

def do_welcome_unsubscribe(user_profile):
    # type: (UserProfile) -> None
    clear_followup_emails_queue(user_profile.email)

def do_digest_unsubscribe(user_profile):
    # type: (UserProfile) -> None
    do_change_enable_digest_emails(user_profile, False)

# The keys are part of the URL for the unsubscribe link and must be valid
# without encoding.
# The values are a tuple of (display name, unsubscribe function), where the
# display name is what we call this class of email in user-visible text.
email_unsubscribers = {
    "missed_messages": ("missed messages", do_missedmessage_unsubscribe),
    "welcome": ("welcome", do_welcome_unsubscribe),
    "digest": ("digest", do_digest_unsubscribe)
}

# Login NOT required. These are for one-click unsubscribes.
def email_unsubscribe(request, type, token):
    # type: (HttpRequest, str, str) -> HttpResponse
    if type in email_unsubscribers:
        display_name, unsubscribe_function = email_unsubscribers[type]
        return process_unsubscribe(request, token, display_name, unsubscribe_function)

    return render(request, 'zerver/unsubscribe_link_error.html')
