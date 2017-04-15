from __future__ import absolute_import

from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.conf import settings
from django.template import loader
from django.utils.timezone import get_current_timezone_name as timezone_get_current_timezone_name
from django.utils.timezone import now as timezone_now
from typing import Any, Dict, Optional
from zerver.models import UserProfile

def get_device_browser(user_agent):
    # type: (str) -> Optional[str]
    user_agent = user_agent.lower()
    if "chrome" in user_agent and "chromium" not in user_agent:
        return 'Chrome'
    elif "firefox" in user_agent and "seamonkey" not in user_agent and "chrome" not in user_agent:
        return "Firefox"
    elif "chromium" in user_agent:
        return "Chromium"
    elif "safari" in user_agent and "chrome" not in user_agent and "chromium" not in user_agent:
        return "Safari"
    elif "opera" in user_agent:
        return "Opera"
    elif "msie" in user_agent or "trident" in user_agent:
        return "Internet Explorer"
    elif "edge" in user_agent:
        return "Edge"
    else:
        return None


def get_device_os(user_agent):
    # type: (str) -> Optional[str]
    user_agent = user_agent.lower()
    if "windows" in user_agent:
        return "Windows"
    elif "macintosh" in user_agent:
        return "MacOS"
    elif "linux" in user_agent and "android" not in user_agent:
        return "Linux"
    elif "android" in user_agent:
        return "Android"
    elif "like mac os x" in user_agent:
        return "iOS"
    else:
        return None


@receiver(user_logged_in, dispatch_uid="only_on_login")
def email_on_new_login(sender, user, request, **kwargs):
    # type: (Any, UserProfile, Any, Any) -> None

    # We import here to minimize the dependencies of this module,
    # since it runs as part of `manage.py` initialization
    from zerver.context_processors import common_context

    if not settings.SEND_LOGIN_EMAILS:
        return

    if request:
        # Login emails are for returning users, not new registrations.
        # Determine if login request was from new registration.
        path = request.META.get('PATH_INFO', None)

        if path:
            if path == "/accounts/register/":
                return

        login_time = timezone_now().strftime('%A, %B %d, %Y at %I:%M%p ') + \
            timezone_get_current_timezone_name()
        user_agent = request.META.get('HTTP_USER_AGENT', "").lower()
        device_browser = get_device_browser(user_agent)
        device_os = get_device_os(user_agent)
        device_ip = request.META.get('REMOTE_ADDR') or "Uknown IP address"
        device_info = {"device_browser": device_browser,
                       "device_os": device_os,
                       "device_ip": device_ip,
                       "login_time": login_time
                       }

        context = common_context(user)
        context['device_info'] = device_info
        context['zulip_support'] = settings.ZULIP_ADMINISTRATOR
        context['user'] = user

        text_template = 'zerver/emails/new_login/new_login_alert.txt'
        html_template = 'zerver/emails/new_login/new_login_alert.html'
        text_content = loader.render_to_string(text_template, context)
        html_content = loader.render_to_string(html_template, context)

        sender = settings.NOREPLY_EMAIL_ADDRESS
        recipients = [user.email]
        subject = loader.render_to_string('zerver/emails/new_login/new_login_alert.subject').strip()
        send_mail(subject, text_content, sender, recipients, html_message=html_content)
