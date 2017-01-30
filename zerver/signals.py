from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.conf import settings
from django.template import loader
from django.utils import timezone
from typing import Any, Dict
from zerver.models import UserProfile


def get_device_browser(user_agent):
    # type: (str) -> str
    user_agent = user_agent.lower()
    if "chrome" in user_agent and "chromium" not in user_agent:
        return 'chrome'
    elif "firefox" in user_agent and "seamonkey" not in user_agent and "chrome" not in user_agent:
        return "firefox"
    elif "chromium" in user_agent:
        return "chromium"
    elif "safari" in user_agent and "chrome" not in user_agent and "chromium" not in user_agent:
        return "safari"
    elif "opera" in user_agent:
        return "opera"
    elif "msie" in user_agent or "trident" in user_agent:
        return "internet explorer"
    elif "edge" in user_agent:
        return "edge"
    else:
        return "browser unknown"


def get_device_os(user_agent):
    # type: (str) -> str
    user_agent = user_agent.lower()
    if "windows" in user_agent:
        return "windows"
    elif "macintosh" in user_agent:
        return "macintosh"
    elif "linux" in user_agent and "android" not in user_agent:
        return "linux"
    elif "android" in user_agent:
        return "android"
    elif "like mac os x" in user_agent:
        return "ios"
    else:
        return "operating system unknown"


@receiver(user_logged_in, dispatch_uid="only_on_login")
def email_on_new_login(sender, user, request, **kwargs):
    # type: (Any, UserProfile, Any, Any) -> None

    if not settings.SEND_LOGIN_EMAILS:
        return

    if request:
        login_time = timezone.now().strftime('%A, %B %d, %Y at %I:%M%p (UTC) ') + \
            timezone.get_current_timezone_name()
        user_agent = request.META.get('HTTP_USER_AGENT', "").lower()
        device_browser = get_device_browser(user_agent)
        device_os = get_device_os(user_agent)
        device_ip = request.META.get('REMOTE_ADDR') or "ip address unknown"
        device_info = {"device_browser": device_browser,
                       "device_os": device_os,
                       "device_ip": device_ip,
                       "login_time": login_time
                       }

        zulip_support = settings.ZULIP_ADMINISTRATOR

        text_template = 'zerver/emails/new_login/new_login_alert.txt'
        html_template = 'zerver/emails/new_login/new_login_alert.html'
        context = {'user': user, 'device_info': device_info, 'zulip_support': zulip_support}
        text_content = loader.render_to_string(text_template, context)
        html_content = loader.render_to_string(html_template, context)

        sender = settings.NOREPLY_EMAIL_ADDRESS
        recipients = [user.email]
        subject = loader.render_to_string('zerver/emails/new_login/new_login_alert.subject').strip()
        send_mail(subject, text_content, sender, recipients, html_message=html_content)
