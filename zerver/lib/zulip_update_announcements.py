import logging
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import override as override_language

from zerver.actions.message_send import (
    do_send_messages,
    internal_prep_group_direct_message,
    internal_prep_stream_message,
)
from zerver.lib.message import SendMessageRequest, remove_single_newlines
from zerver.lib.topic import messages_for_topic
from zerver.models.realm_audit_logs import AuditLogEventType, RealmAuditLog
from zerver.models.realms import Realm
from zerver.models.users import UserProfile, get_system_bot


@dataclass
class ZulipUpdateAnnouncement:
    level: int
    message: str


# We don't translate the announcement message because they are quite unlikely to be
# translated during the time between when we draft them and when they are published.
zulip_update_announcements: list[ZulipUpdateAnnouncement] = [
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
- To [quote and reply]({quote_message_help_url}) to part of a message, you can
now select the part that you want to quote.
- You can now hide the user list in the right sidebar to reduce distraction.
[Learn more]({user_list_help_url}).
""".format(
            keyboard_shortcuts_basics_help_url="/help/keyboard-shortcuts#the-basics",
            user_list_help_url="/help/user-list",
            quote_message_help_url="/help/quote-and-reply",
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
    ZulipUpdateAnnouncement(
        level=4,
        message="""
- To simplify Zulip for new users, **Streams** have been renamed to **Channels**.
The functionality remains exactly the same, and bots do not need
to be updated. [Learn more]({introduction_to_channels_help_url}).

- Topics and messages now load much faster when you open the web or desktop app.
""".format(
            introduction_to_channels_help_url="/help/introduction-to-channels",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=5,
        message="""
**Web and desktop updates**
- Use the new **Reactions** view to see how others have reacted to your
messages. [Learn more]({view_your_messages_with_reactions_help_url}).
- For a more focused reading experience, you can now hide the
[left]({left_sidebar_help_url}) and [right]({user_list_help_url})
sidebars any time using the buttons in the top navigation bar. When the left
sidebar is hidden, use [keyboard
navigation]({keyboard_shortcuts_navigation_help_url}) to jump to the next unread
topic or go back to your [home view]({configure_home_view_help_url}).
- You can now search for messages in topics you
  [follow]({follow_a_topic_help_url}) using the `is:followed` filter. [Learn
  more]({search_by_message_status_help_url}).
""".format(
            view_your_messages_with_reactions_help_url="/help/emoji-reactions#view-your-messages-with-reactions",
            left_sidebar_help_url="/help/left-sidebar",
            user_list_help_url="/help/user-list",
            keyboard_shortcuts_navigation_help_url="/help/keyboard-shortcuts#navigation",
            configure_home_view_help_url="/help/configure-home-view",
            follow_a_topic_help_url="/help/follow-a-topic",
            search_by_message_status_help_url="/help/search-for-messages#search-by-message-status",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=6,
        message="""
**Web and desktop updates**
- You can now configure whether channel links in the left sidebar go to the most
recent topic (default option), or to the channel feed. With the default
configuration, you can access the feed from the channel menu.
[Learn more]({channel_feed_help_url}).
- You can also [configure]({automatically_go_to_conversation_help_url}) whether Zulip
automatically takes you to the conversation to which you sent a message, if you
aren't already viewing it (on by default).
- You can now [filter]({find_a_dm_conversation_help_url}) direct message
conversations in the left sidebar to conversations that include a specific
person.
""".format(
            channel_feed_help_url="/help/channel-feed",
            automatically_go_to_conversation_help_url="/help/mastering-the-compose-box#automatically-go-to-conversation-where-you-sent-a-message",
            find_a_dm_conversation_help_url="/help/direct-messages#find-a-direct-message-conversation",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=7,
        message="""
**Web and desktop updates**
- To make reading more comfortable, Zulip has been redesigned with a larger font
size and line spacing. If you prefer to see more content at once, [enable
compact mode]({settings_preferences_url}) to go back to the previous design.
- The main search has been redesigned with pills for [search
filters]({search_help_url}), making it easier to use.
- Pasted [channel and topic URLs]({link_help_url}) are now automatically
converted into nicely formatted links.
""".format(
            settings_preferences_url="/#settings/preferences",
            search_help_url="/help/search-for-messages",
            link_help_url="/help/link-to-a-message-or-conversation",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=8,
        message=(
            """
- New image uploads now load much faster in all Zulip apps.
- In the desktop and web apps, you can now [configure]({image_previews_help_url})
previews of animated images to **always show** the animation, show it **when you
hover** over the image with your mouse (default), or **not show** it at all. You can
always see the animated image by opening it in the [image
viewer]({view_images_help_url})."""
            + (
                """

We make many improvements to Zulip beyond what we can share here. Learn about
additional feature highlights, and other Zulip project updates since December
2023, in the [blog post]({blog_post_9_0_url}) announcing today's release of
Zulip Server 9.0.
"""
                if settings.CORPORATE_ENABLED
                else """

We make many improvements to Zulip beyond what we can share here. Check out our
[release announcement blog post]({blog_post_9_0_url}) to learn about additional
feature highlights in Zulip Server 9.0, and other Zulip project updates.
"""
            )
        ).format(
            image_previews_help_url="/help/allow-image-link-previews",
            view_images_help_url="/help/view-images-and-videos",
            blog_post_9_0_url="https://blog.zulip.com/zulip-server-9-0",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=9,
        message=(
            (
                """
- You can now [upload large files]({file_upload_limits_help_url}) up to
  1 GB in organizations on Zulip Cloud
  Standard or Zulip Cloud Plus [plans]({cloud_plans_url}).
"""
                if settings.CORPORATE_ENABLED
                else """
- You can now [upload large files]({file_upload_limits_help_url}), up to
  the limit configured by your server's administrator (currently {max_file_upload_size} MB).
"""
            )
            + """

**Web and desktop updates**
- You can now start a new conversation from the left sidebar. Click the `+`
button next to the name of a channel to [start a new
topic]({how_to_start_a_new_topic_help_url}) in that channel, or the `+` next to
DIRECT MESSAGES to [start a DM]({starting_a_new_direct_message_help_url}).
- The [user list]({user_list_help_url}) now shows recent participants in the
  conversation you're viewing.
"""
        ).format(
            how_to_start_a_new_topic_help_url="/help/introduction-to-topics#how-to-start-a-new-topic",
            starting_a_new_direct_message_help_url="/help/starting-a-new-direct-message",
            user_list_help_url="/help/user-list",
            cloud_plans_url="/plans/",
            file_upload_limits_help_url="/help/share-and-upload-files#file-upload-limits",
            max_file_upload_size=settings.MAX_FILE_UPLOAD_SIZE,
        ),
    ),
    ZulipUpdateAnnouncement(
        level=10,
        message=(
            """
- Most permissions in Zulip can now be granted to any combination of
  [roles]({roles_and_permissions_help_url}), [groups]({user_groups_help_url}),
  and individual [users]({users_help_url}). Previously, permissions were
  configurable only by user role."""
            + (
                """
- Creating new user groups now requires a Zulip Cloud Standard or Zulip Cloud
  Plus [plan]({cloud_plans_url}).
"""
                if settings.CORPORATE_ENABLED
                else ""
            )
            + """

**Web and desktop updates**
- To provide more information, long topic names are now shown on two lines in
  the left sidebar.
- Pasted [message links]({message_links_help_url}) are now automatically
  converted into nicely formatted links.
"""
        ).format(
            roles_and_permissions_help_url="/help/roles-and-permissions",
            user_groups_help_url="/help/user-groups",
            users_help_url="/help/manage-a-user",
            cloud_plans_url="/plans/",
            message_links_help_url="/help/link-to-a-message-or-conversation#get-a-link-to-a-specific-message",
        ),
    ),
    ZulipUpdateAnnouncement(
        level=11,
        message="""
- Zulip’s next-gen mobile app is now in public beta. If offers a sleek new
  design and a faster, smoother experience. [Check out the announcement
  post]({flutter_beta_blog_post}) for details and instructions on how to try the
  beta!

**Web and desktop updates**
- There's a [new option]({user_list_style_help_url}) to show avatars in the
  user list.
- You can now conveniently [forward]({quote_or_forward_help_url}) a message to
  another conversation from the message menu.
""".format(
            flutter_beta_blog_post="https://blog.zulip.com/2024/12/12/new-flutter-mobile-app-beta/",
            user_list_style_help_url="/help/user-list#configure-user-list-style",
            quote_or_forward_help_url="/help/quote-or-forward-a-message",
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
) -> SendMessageRequest | None:
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
    return internal_prep_group_direct_message(
        realm, sender, remove_single_newlines(content), recipient_users=administrators
    )


def get_level_none_to_initial_auditlog(realm: Realm) -> RealmAuditLog | None:
    return RealmAuditLog.objects.filter(
        realm=realm,
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
        extra_data__contains={
            # Note: We're looking for the transition away from None,
            # which usually will be to level 0, but can be to a higher
            # initial level if the organization was imported from
            # another chat tool.
            RealmAuditLog.OLD_VALUE: None,
            "property": "zulip_update_announcements_level",
        },
    ).first()


def is_group_direct_message_sent_to_admins_within_days(realm: Realm, days: int) -> bool:
    level_none_to_initial_auditlog = get_level_none_to_initial_auditlog(realm)
    assert level_none_to_initial_auditlog is not None
    group_direct_message_sent_on = level_none_to_initial_auditlog.event_time
    return timezone_now() - group_direct_message_sent_on < timedelta(days=days)


def internal_prep_zulip_update_announcements_stream_messages(
    current_level: int, latest_level: int, sender: UserProfile, realm: Realm
) -> list[SendMessageRequest | None]:
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
    send_message_requests: list[SendMessageRequest | None],
) -> None:
    sent_message_ids = []
    if send_message_requests:
        sent_messages = do_send_messages(send_message_requests)
        sent_message_ids = [sent_message.message_id for sent_message in sent_messages]

    RealmAuditLog.objects.create(
        realm=realm,
        event_type=AuditLogEventType.REALM_PROPERTY_CHANGED,
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
    for realm in get_realms_behind_zulip_update_announcements_level(
        level=latest_zulip_update_announcements_level
    ):
        try:
            send_zulip_update_announcements_to_realm(realm, skip_delay)
        except Exception as e:  # nocoverage
            logging.exception(e)


def send_zulip_update_announcements_to_realm(
    realm: Realm, skip_delay: bool, realm_imported_from_other_product: bool = False
) -> None:
    latest_zulip_update_announcements_level = get_latest_zulip_update_announcements_level()
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
        # This realm predates the zulip update announcements feature, or
        # was imported from another product (Slack, Mattermost, etc.).
        # Group DM the administrators to set or verify the stream for
        # zulip update announcements.
        group_direct_message = internal_prep_group_direct_message_for_old_realm(realm, sender)
        messages = [group_direct_message]
        if realm_imported_from_other_product:
            new_zulip_update_announcements_level = latest_zulip_update_announcements_level
        else:
            new_zulip_update_announcements_level = 0
    elif realm.zulip_update_announcements_stream is None:
        # Realm misses the update messages in two cases:
        # Case 1: New realm created, and later stream manually set to None.
        # No group direct message is sent. Introductory message in the topic is sent.
        # Case 2: For old realm or realm imported from other product, we wait for A WEEK
        # after sending group DMs to let admins configure stream for zulip update announcements.
        # After that, they miss updates until they don't configure.
        level_none_to_initial_auditlog = get_level_none_to_initial_auditlog(realm)
        if level_none_to_initial_auditlog is None or not (
            timezone_now() - level_none_to_initial_auditlog.event_time < timedelta(days=7)
        ):
            new_zulip_update_announcements_level = latest_zulip_update_announcements_level
    else:
        # Wait for 24 hours after sending group DM to allow admins to change the
        # stream for zulip update announcements from it's default value if desired.
        if (
            realm_zulip_update_announcements_level == 0
            and is_group_direct_message_sent_to_admins_within_days(realm, days=1)
            and not skip_delay
        ):
            return

        # Send an introductory message just before the first update message.
        with override_language(realm.default_language):
            topic_name = str(realm.ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME)

        stream = realm.zulip_update_announcements_stream
        assert stream.recipient_id is not None
        topic_has_messages = messages_for_topic(realm.id, stream.recipient_id, topic_name).exists()

        if not topic_has_messages:
            content_of_introductory_message = (
                """
To help you learn about new features and configuration options,
this topic will receive messages about important changes in Zulip.

You can read these update messages whenever it's convenient, or
[mute]({mute_topic_help_url}) this topic if you are not interested.
If your organization does not want to receive these announcements,
they can be disabled. [Learn more]({zulip_update_announcements_help_url}).
"""
            ).format(
                zulip_update_announcements_help_url="/help/configure-automated-notices#zulip-update-announcements",
                mute_topic_help_url="/help/mute-a-topic",
            )
            messages = [
                internal_prep_stream_message(
                    sender,
                    stream,
                    topic_name,
                    remove_single_newlines(content_of_introductory_message),
                )
            ]

        messages.extend(
            internal_prep_zulip_update_announcements_stream_messages(
                current_level=realm_zulip_update_announcements_level,
                latest_level=latest_zulip_update_announcements_level,
                sender=sender,
                realm=realm,
            )
        )

        new_zulip_update_announcements_level = latest_zulip_update_announcements_level

    if new_zulip_update_announcements_level is not None:
        send_messages_and_update_level(realm, new_zulip_update_announcements_level, messages)
