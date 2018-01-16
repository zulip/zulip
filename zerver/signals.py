
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.template import loader
from django.utils.timezone import \
    get_current_timezone_name as timezone_get_current_timezone_name
from django.utils.timezone import now as timezone_now

from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress, send_email
from zerver.models import UserProfile

def get_device_browser(user_agent: str) -> Optional[str]:
    user_agent = user_agent.lower()
    if "zulip" in user_agent:
        return "Zulip"
    elif "edge" in user_agent:
        return "Edge"
    elif "opera" in user_agent or "opr/" in user_agent:
        return "Opera"
    elif ("chrome" in user_agent or "crios" in user_agent) and "chromium" not in user_agent:
        return 'Chrome'
    elif "firefox" in user_agent and "seamonkey" not in user_agent and "chrome" not in user_agent:
        return "Firefox"
    elif "chromium" in user_agent:
        return "Chromium"
    elif "safari" in user_agent and "chrome" not in user_agent and "chromium" not in user_agent:
        return "Safari"
    elif "msie" in user_agent or "trident" in user_agent:
        return "Internet Explorer"
    else:
        return None


def get_device_os(user_agent: str) -> Optional[str]:
    user_agent = user_agent.lower()
    if "windows" in user_agent:
        return "Windows"
    elif "macintosh" in user_agent:
        return "macOS"
    elif "linux" in user_agent and "android" not in user_agent:
        return "Linux"
    elif "android" in user_agent:
        return "Android"
    elif "ios" in user_agent:
        return "iOS"
    elif "like mac os x" in user_agent:
        return "iOS"
    else:
        return None


@receiver(user_logged_in, dispatch_uid="only_on_login")
def email_on_new_login(sender: Any, user: UserProfile, request: Any, **kwargs: Any) -> None:
    # We import here to minimize the dependencies of this module,
    # since it runs as part of `manage.py` initialization
    from zerver.context_processors import common_context

    if not settings.SEND_LOGIN_EMAILS:
        return

    if request:
        # If the user's account was just created, avoid sending an email.
        if getattr(user, "just_registered", False):
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
        context['user_email'] = user.email

        email_dict = {
            'template_prefix': 'zerver/emails/notify_new_login',
            'to_user_id': user.id,
            'from_name': 'Zulip Account Security',
            'from_address': FromAddress.NOREPLY,
            'context': context}
        queue_json_publish("email_senders", email_dict)
