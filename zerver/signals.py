import sys
from typing import Any, FrozenSet, Optional

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.timezone import get_current_timezone_name as timezone_get_current_timezone_name
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from confirmation.models import one_click_unsubscribe_link
from zerver.actions.message_send import do_send_messages, internal_prep_private_message
from zerver.lib.queue import queue_json_publish
from zerver.lib.send_email import FromAddress
from zerver.models import UserProfile, get_system_bot

if sys.version_info < (3, 9):  # nocoverage
    from backports import zoneinfo
else:  # nocoverage
    import zoneinfo

JUST_CREATED_THRESHOLD = 60


def get_device_browser(user_agent: str) -> Optional[str]:
    user_agent = user_agent.lower()
    if "zulip" in user_agent:
        return "Zulip"
    elif "edge" in user_agent:
        return "Edge"
    elif "opera" in user_agent or "opr/" in user_agent:
        return "Opera"
    elif ("chrome" in user_agent or "crios" in user_agent) and "chromium" not in user_agent:
        return "Chrome"
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
    elif " cros " in user_agent:
        return "ChromeOS"
    else:
        return None


@receiver(user_logged_in, dispatch_uid="only_on_login")
def email_on_new_login(sender: Any, user: UserProfile, request: Any, **kwargs: Any) -> None:
    if not user.enable_login_emails:
        return
    # We import here to minimize the dependencies of this module,
    # since it runs as part of `manage.py` initialization
    from zerver.context_processors import common_context

    if not settings.SEND_LOGIN_EMAILS:
        return

    if request:
        # If the user's account was just created, avoid sending an email.
        if (timezone_now() - user.date_joined).total_seconds() <= JUST_CREATED_THRESHOLD:
            return

        user_agent = request.headers.get("User-Agent", "").lower()

        context = common_context(user)
        context["user_email"] = user.delivery_email
        user_tz = user.timezone
        if user_tz == "":
            user_tz = timezone_get_current_timezone_name()
        local_time = timezone_now().astimezone(zoneinfo.ZoneInfo(user_tz))
        if user.twenty_four_hour_time:
            hhmm_string = local_time.strftime("%H:%M")
        else:
            hhmm_string = local_time.strftime("%I:%M%p")
        context["login_time"] = local_time.strftime(f"%A, %B %d, %Y at {hhmm_string} %Z")
        context["device_ip"] = request.META.get("REMOTE_ADDR") or _("Unknown IP address")
        context["device_os"] = get_device_os(user_agent) or _("an unknown operating system")
        context["device_browser"] = get_device_browser(user_agent) or _("An unknown browser")
        context["unsubscribe_link"] = one_click_unsubscribe_link(user, "login")

        email_dict = {
            "template_prefix": "zerver/emails/notify_new_login",
            "to_user_ids": [user.id],
            "from_name": FromAddress.security_email_from_name(user_profile=user),
            "from_address": FromAddress.NOREPLY,
            "context": context,
        }
        queue_json_publish("email_senders", email_dict)


@receiver(user_logged_out)
def clear_zoom_token_on_logout(
    sender: object, *, user: Optional[UserProfile], **kwargs: object
) -> None:
    # Loaded lazily so django.setup() succeeds before static asset generation
    from zerver.actions.video_calls import do_set_zoom_token

    if user is not None and user.zoom_token is not None:
        do_set_zoom_token(user, None)


@receiver(pre_save, sender=UserProfile)
def send_profile_change_notif(
    sender: object, instance: UserProfile, update_fields: FrozenSet[str], **kwargs: object
) -> None:

    if not update_fields:
        return

    # when an object is created for the first time, the id is None at this stage(pre_save)
    if not instance.id:
        return

    if not instance.is_active:
        return

    # from the test-case AppleAuthBackendNativeFlowTest.test_social_auth_desktop_registration
    # because it sends triggers signal multiple times and bulk_create() is prohibited due to unsaved related object "recipient"
    # within the test case, signal will be triggered again after recipient is set, so it is skipped before that step
    if not instance.recipient:
        return

    if instance.is_bot:
        return

    profile_as_in_db = UserProfile.objects.get(id=instance.id)
    notif_sender = get_system_bot(settings.NOTIFICATION_BOT, instance.realm_id)

    message_fields_to_show = {
        "email",
        "full_name",
        "role",
        "default_language",
        "notification_sound",
        "emojiset",
    }

    update_fields_set = (set(update_fields)).intersection(message_fields_to_show)

    if not update_fields_set:
        return

    with override_language(instance.default_language):
        message_text = _("The following updates have been made to your account.") + "\n\n"
        for field in update_fields_set:
            message_text += "old " + field + ":\n"
            message_text += str(getattr(profile_as_in_db, field))
            message_text += "\n"
            message_text += "new " + field + ":\n"
            message_text += str(getattr(instance, field))

    notifications = []
    notifications.append(
        internal_prep_private_message(
            sender=notif_sender,
            recipient_user=instance,
            content=message_text,
        )
    )

    do_send_messages(notifications)
