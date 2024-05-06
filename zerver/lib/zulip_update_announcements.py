from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import override as override_language

from zerver.actions.message_send import (
    do_send_messages,
    internal_prep_huddle_message,
    internal_prep_stream_message,
)
from zerver.lib.message import SendMessageRequest, remove_single_newlines
from zerver.models.realm_audit_logs import RealmAuditLog
from zerver.models.realms import Realm
from zerver.models.users import UserProfile, get_system_bot


@dataclass
class ZulipUpdateAnnouncement:
    level: int
    message: str


# We don't translate the announcement message because they are quite unlikely to be
# translated during the time between when we draft them and when they are published.
zulip_update_announcements: List[ZulipUpdateAnnouncement] = [
    ZulipUpdateAnnouncement(
        level=1,
        message="""
Zulip is introducing **Zulip updates**! To help you learn about new features and
configuration options, this topic will receive messages about important changes in Zulip.

You can read these update messages whenever it's convenient, or [mute]({mute_topic_help_url})
this topic if you are not interested. If your organization does not want to receive these
announcements, they can be disabled. [Learn more]({zulip_update_announcements_help_url}).
""".format(
            zulip_update_announcements_help_url="/help/configure-automated-notices#zulip-update-announcements",
            mute_topic_help_url="/help/mute-a-topic",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=2,
        message="""
**Web and desktop updates**

- When you paste content into the compose box, Zulip will now do its best to preserve
the formatting, including links, bulleted lists, bold, italics, and more.
Pasting as plain text remains an alternative option. [Learn
more]({keyboard_shortcuts_basics_help_url}).
- To [quote and reply]({quote_and_reply_help_url}) to part of a message, you can
now select the part that you want to quote.
- You can now hide the user list in the right sidebar to reduce distraction.
[Learn more]({user_list_help_url}).
""".format(
            keyboard_shortcuts_basics_help_url="/help/keyboard-shortcuts#the-basics",
            user_list_help_url="/help/user-list",
            quote_and_reply_help_url="/help/quote-and-reply",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=3,
        message="""
- The **All messages** view has been renamed to **Combined feed**.
[Learn more]({combined_feed_help_url}).

**Web and desktop updates**
- When you start composing, the most recently edited draft for the conversation
you are composing to now automatically appears in the compose box. You can
always save a draft and start a new message using the **send options** menu next
to the **Send** button. [Learn more]({save_draft_help_url}).
- If you'd prefer not to see notifications when others type, you can now disable
them. [Learn more]({typing_notifications_help_url}).
""".format(
            typing_notifications_help_url="/help/typing-notifications",
            combined_feed_help_url="/help/combined-feed",
            save_draft_help_url="/help/view-and-edit-your-message-drafts#save-a-draft-and-start-a-new-message",
        ),
    ),
]


def get_latest_zulip_update_announcements_level() -> int:
    latest_zulip_update_announcement = zulip_update_announcements[-1]
    return latest_zulip_update_announcement.level


def get_zulip_update_announcements_message_for_level(level: int) -> str:
    zulip_update_announcement = zulip_update_announcements[level - 1]
    return remove_single_newlines(zulip_update_announcement.message)


def get_realms_behind_zulip_update_announcements_level(level: int) -> QuerySet[Realm]:
    # Filter out deactivated realms. When a realm is later
    # reactivated, send the notices it missed while it was deactivated.
    realms = Realm.objects.filter(
        Q(zulip_update_announcements_level__isnull=True)
        | Q(zulip_update_announcements_level__lt=level),
        deactivated=False,
    ).exclude(string_id=settings.SYSTEM_BOT_REALM)
    return realms


def internal_prep_group_direct_message_for_old_realm(
    realm: Realm, sender: UserProfile
) -> Optional[SendMessageRequest]:
    administrators = list(realm.get_human_admin_users())
    with override_language(realm.default_language):
        topic_name = str(realm.ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME)
    if realm.zulip_update_announcements_stream is None:
        content = """
Zulip now supports [configuring]({organization_settings_url}) a stream where Zulip will
send [updates]({zulip_update_announcements_help_url}) about new Zulip features.
These notifications are currently turned off in your organization. If you configure
a stream within one week, your organization will not miss any update messages.
""".format(
            zulip_update_announcements_help_url="/help/configure-automated-notices#zulip-update-announcements",
            organization_settings_url="/#organization/organization-settings",
        )
    else:
        content = """
Starting tomorrow, users in your organization will receive [updates]({zulip_update_announcements_help_url})
about new Zulip features in #**{zulip_update_announcements_stream}>{topic_name}**.

If you like, you can [configure]({organization_settings_url}) a different stream for
these updates (and [move]({move_content_another_stream_help_url}) any updates sent before the
configuration change), or [turn this feature off]({organization_settings_url}) altogether.
""".format(
            zulip_update_announcements_help_url="/help/configure-automated-notices#zulip-update-announcements",
            zulip_update_announcements_stream=realm.zulip_update_announcements_stream.name,
            topic_name=topic_name,
            organization_settings_url="/#organization/organization-settings",
            move_content_another_stream_help_url="/help/move-content-to-another-channel",
        )
    return internal_prep_huddle_message(
        realm, sender, remove_single_newlines(content), recipient_users=administrators
    )


def is_group_direct_message_sent_to_admins_within_days(realm: Realm, days: int) -> bool:
    level_none_to_zero_auditlog = RealmAuditLog.objects.filter(
        realm=realm,
        event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
        extra_data__contains={
            RealmAuditLog.OLD_VALUE: None,
            RealmAuditLog.NEW_VALUE: 0,
            "property": "zulip_update_announcements_level",
        },
    ).first()
    assert level_none_to_zero_auditlog is not None
    group_direct_message_sent_on = level_none_to_zero_auditlog.event_time
    return timezone_now() - group_direct_message_sent_on < timedelta(days=days)


def internal_prep_zulip_update_announcements_stream_messages(
    current_level: int, latest_level: int, sender: UserProfile, realm: Realm
) -> List[Optional[SendMessageRequest]]:
    message_requests = []
    stream = realm.zulip_update_announcements_stream
    assert stream is not None
    with override_language(realm.default_language):
        topic_name = str(realm.ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME)
    while current_level < latest_level:
        content = get_zulip_update_announcements_message_for_level(level=current_level + 1)
        message_requests.append(
            internal_prep_stream_message(
                sender,
                stream,
                topic_name,
                content,
            )
        )
        current_level += 1
    return message_requests


@transaction.atomic(savepoint=False)
def send_messages_and_update_level(
    realm: Realm,
    new_zulip_update_announcements_level: int,
    send_message_requests: List[Optional[SendMessageRequest]],
) -> None:
    sent_message_ids = []
    if send_message_requests:
        sent_messages = do_send_messages(send_message_requests)
        sent_message_ids = [sent_message.message_id for sent_message in sent_messages]

    RealmAuditLog.objects.create(
        realm=realm,
        event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
        event_time=timezone_now(),
        extra_data={
            RealmAuditLog.OLD_VALUE: realm.zulip_update_announcements_level,
            RealmAuditLog.NEW_VALUE: new_zulip_update_announcements_level,
            "property": "zulip_update_announcements_level",
            "zulip_update_announcements_message_ids": sent_message_ids,
        },
    )

    realm.zulip_update_announcements_level = new_zulip_update_announcements_level
    realm.save(update_fields=["zulip_update_announcements_level"])


def send_zulip_update_announcements(skip_delay: bool) -> None:
    latest_zulip_update_announcements_level = get_latest_zulip_update_announcements_level()

    realms = get_realms_behind_zulip_update_announcements_level(
        level=latest_zulip_update_announcements_level
    )

    for realm in realms:
        # Refresh the realm from the database and check its
        # properties, to protect against racing with another copy of
        # ourself.
        realm.refresh_from_db()
        realm_zulip_update_announcements_level = realm.zulip_update_announcements_level
        assert (
            realm_zulip_update_announcements_level is None
            or realm_zulip_update_announcements_level < latest_zulip_update_announcements_level
        )

        sender = get_system_bot(settings.NOTIFICATION_BOT, realm.id)

        messages = []
        new_zulip_update_announcements_level = None

        if realm_zulip_update_announcements_level is None:
            # realm predates the zulip update announcements feature.
            # Group DM the administrators to set or verify the stream for
            # zulip update announcements.
            group_direct_message = internal_prep_group_direct_message_for_old_realm(realm, sender)
            messages = [group_direct_message]
            new_zulip_update_announcements_level = 0
        elif (
            realm_zulip_update_announcements_level == 0
            and realm.zulip_update_announcements_stream is None
        ):
            # We wait for a week after sending group DMs to let admins configure
            # stream for zulip update announcements. After that, they miss updates
            # until they don't configure.
            if not is_group_direct_message_sent_to_admins_within_days(realm, days=7):
                new_zulip_update_announcements_level = latest_zulip_update_announcements_level
        else:
            # Wait for 24 hours after sending group DM to allow admins to change the
            # stream for zulip update announcements from it's default value if desired.
            if (
                realm_zulip_update_announcements_level == 0
                and is_group_direct_message_sent_to_admins_within_days(realm, days=1)
                and not skip_delay
            ):
                continue

            if realm.zulip_update_announcements_stream is not None:
                messages = internal_prep_zulip_update_announcements_stream_messages(
                    current_level=realm_zulip_update_announcements_level,
                    latest_level=latest_zulip_update_announcements_level,
                    sender=sender,
                    realm=realm,
                )

            new_zulip_update_announcements_level = latest_zulip_update_announcements_level

        if new_zulip_update_announcements_level is not None:
            send_messages_and_update_level(realm, new_zulip_update_announcements_level, messages)
