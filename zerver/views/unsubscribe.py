from typing import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from confirmation.models import Confirmation, ConfirmationKeyError, get_object_from_key
from zerver.actions.user_settings import do_change_user_setting
from zerver.context_processors import common_context
from zerver.lib.send_email import clear_scheduled_emails
from zerver.models import ScheduledEmail, UserProfile


def process_unsubscribe(
    request: HttpRequest,
    confirmation_key: str,
    subscription_type: str,
    unsubscribe_function: Callable[[UserProfile], None],
) -> HttpResponse:
    try:
        user_profile = get_object_from_key(
            confirmation_key, [Confirmation.UNSUBSCRIBE], mark_object_used=False
        )
    except ConfirmationKeyError:
        return render(request, "zerver/unsubscribe_link_error.html")

    assert isinstance(user_profile, UserProfile)
    unsubscribe_function(user_profile)
    context = common_context(user_profile)
    context.update(subscription_type=subscription_type)
    return render(request, "zerver/unsubscribe_success.html", context=context)


# Email unsubscribe functions. All have the function signature
# processor(user_profile).


def do_missedmessage_unsubscribe(user_profile: UserProfile) -> None:
    do_change_user_setting(
        user_profile, "enable_offline_email_notifications", False, acting_user=user_profile
    )


def do_welcome_unsubscribe(user_profile: UserProfile) -> None:
    clear_scheduled_emails(user_profile.id, ScheduledEmail.WELCOME)


def do_digest_unsubscribe(user_profile: UserProfile) -> None:
    do_change_user_setting(user_profile, "enable_digest_emails", False, acting_user=user_profile)


def do_login_unsubscribe(user_profile: UserProfile) -> None:
    do_change_user_setting(user_profile, "enable_login_emails", False, acting_user=user_profile)


def do_marketing_unsubscribe(user_profile: UserProfile) -> None:
    do_change_user_setting(user_profile, "enable_marketing_emails", False, acting_user=user_profile)


# The keys are part of the URL for the unsubscribe link and must be valid
# without encoding.
# The values are a tuple of (display name, unsubscribe function), where the
# display name is what we call this class of email in user-visible text.
email_unsubscribers = {
    "missed_messages": ("missed messages", do_missedmessage_unsubscribe),
    "welcome": ("welcome", do_welcome_unsubscribe),
    "digest": ("digest", do_digest_unsubscribe),
    "login": ("login", do_login_unsubscribe),
    "marketing": ("marketing", do_marketing_unsubscribe),
}


# Login NOT required. These are for one-click unsubscribes.
@csrf_exempt
def email_unsubscribe(request: HttpRequest, email_type: str, confirmation_key: str) -> HttpResponse:
    if email_type in email_unsubscribers:
        display_name, unsubscribe_function = email_unsubscribers[email_type]
        return process_unsubscribe(request, confirmation_key, display_name, unsubscribe_function)

    return render(request, "zerver/unsubscribe_link_error.html")
