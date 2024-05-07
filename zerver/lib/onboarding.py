from typing import Dict, List

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language

from zerver.actions.create_realm import setup_realm_internal_bots
from zerver.actions.message_send import (
    do_send_messages,
    internal_prep_stream_message_by_name,
    internal_send_private_message,
)
from zerver.actions.reactions import do_add_reaction
from zerver.lib.emoji import get_emoji_data
from zerver.lib.message import SendMessageRequest, remove_single_newlines
from zerver.models import Message, Realm, UserProfile
from zerver.models.users import get_system_bot


def missing_any_realm_internal_bots() -> bool:
    bot_emails = [
        bot["email_template"] % (settings.INTERNAL_BOT_DOMAIN,)
        for bot in settings.REALM_INTERNAL_BOTS
    ]
    realm_count = Realm.objects.count()
    return UserProfile.objects.filter(email__in=bot_emails).values("email").annotate(
        count=Count("id")
    ).filter(count=realm_count).count() != len(bot_emails)


def create_if_missing_realm_internal_bots() -> None:
    """This checks if there is any realm internal bot missing.

    If that is the case, it creates the missing realm internal bots.
    """
    if missing_any_realm_internal_bots():
        for realm in Realm.objects.all():
            setup_realm_internal_bots(realm)


def send_initial_direct_message(user: UserProfile) -> None:
    # We adjust the initial Welcome Bot direct message for education organizations.
    education_organization = user.realm.org_type in (
        Realm.ORG_TYPES["education_nonprofit"]["id"],
        Realm.ORG_TYPES["education"]["id"],
    )

    # We need to override the language in this code path, because it's
    # called from account registration, which is a pre-account API
    # request and thus may not have the user's language context yet.
    with override_language(user.default_language):
        if education_organization:
            getting_started_help = user.realm.uri + "/help/using-zulip-for-a-class"
            getting_started_string = (
                _(
                    "If you are new to Zulip, check out our [Using Zulip for a class guide]({getting_started_url})!"
                )
            ).format(getting_started_url=getting_started_help)
        else:
            getting_started_help = user.realm.uri + "/help/getting-started-with-zulip"
            getting_started_string = (
                _(
                    "If you are new to Zulip, check out our [Getting started guide]({getting_started_url})!"
                )
            ).format(getting_started_url=getting_started_help)

        organization_setup_string = ""
        # Add extra content on setting up a new organization for administrators.
        if user.is_realm_admin:
            if education_organization:
                organization_setup_help = user.realm.uri + "/help/setting-up-zulip-for-a-class"
                organization_setup_string = (
                    " "
                    + _(
                        "We also have a guide for [Setting up Zulip for a class]({organization_setup_url})."
                    )
                ).format(organization_setup_url=organization_setup_help)
            else:
                organization_setup_help = (
                    user.realm.uri + "/help/getting-your-organization-started-with-zulip"
                )
                organization_setup_string = (
                    " "
                    + _(
                        "We also have a guide for [Setting up your organization]({organization_setup_url})."
                    )
                ).format(organization_setup_url=organization_setup_help)

        demo_organization_warning_string = ""
        # Add extra content about automatic deletion for demo organization owners.
        if user.is_realm_owner and user.realm.demo_organization_scheduled_deletion_date is not None:
            demo_organization_help = user.realm.uri + "/help/demo-organizations"
            demo_organization_warning_string = (
                _(
                    "Note that this is a [demo organization]({demo_organization_help_url}) and will be "
                    "**automatically deleted** in 30 days."
                )
                + "\n\n"
            ).format(demo_organization_help_url=demo_organization_help)

        content = "".join(
            [
                _("Hello, and welcome to Zulip!") + "👋" + " ",
                _("This is a direct message from me, Welcome Bot.") + "\n\n",
                "{getting_started_text}",
                "{organization_setup_text}\n\n",
                "{demo_organization_text}",
                _(
                    "I can also help you get set up! Just click anywhere on this message or press `r` to reply."
                )
                + "\n\n",
                _("Here are a few messages I understand:") + " ",
                bot_commands(),
            ]
        )

    content = content.format(
        getting_started_text=getting_started_string,
        organization_setup_text=organization_setup_string,
        demo_organization_text=demo_organization_warning_string,
    )

    internal_send_private_message(
        get_system_bot(settings.WELCOME_BOT, user.realm_id),
        user,
        content,
        # Note: Welcome bot doesn't trigger email/push notifications,
        # as this is intended to be seen contextually in the application.
        disable_external_notifications=True,
    )


def bot_commands(no_help_command: bool = False) -> str:
    commands = [
        "apps",
        "profile",
        "theme",
        "channels",
        "topics",
        "message formatting",
        "keyboard shortcuts",
    ]
    if not no_help_command:
        commands.append("help")
    return ", ".join("`" + command + "`" for command in commands) + "."


def select_welcome_bot_response(human_response_lower: str) -> str:
    # Given the raw (pre-markdown-rendering) content for a private
    # message from the user to Welcome Bot, select the appropriate reply.
    if human_response_lower in ["app", "apps"]:
        return _(
            "You can [download](/apps/) the [mobile and desktop apps](/apps/). "
            "Zulip also works great in a browser."
        )
    elif human_response_lower == "profile":
        return _(
            "Go to [Profile settings](#settings/profile) "
            "to add a [profile picture](/help/change-your-profile-picture) "
            "and edit your [profile information](/help/edit-your-profile)."
        )
    elif human_response_lower == "theme":
        return _(
            "Go to [Preferences](#settings/preferences) "
            "to [switch between the light and dark themes](/help/dark-theme), "
            "[pick your favorite emoji theme](/help/emoji-and-emoticons#change-your-emoji-set), "
            "[change your language](/help/change-your-language), "
            "and make other tweaks to your Zulip experience."
        )
    elif human_response_lower in ["stream", "streams", "channel", "channels"]:
        return "".join(
            [
                _("In Zulip, channels [determine who gets a message]({help_link}).").format(
                    help_link="/help/introduction-to-channels"
                )
                + "\n\n",
                _("[Browse and subscribe to channels]({settings_link}).").format(
                    settings_link="#channels/all"
                ),
            ]
        )
    elif human_response_lower in ["topic", "topics"]:
        return "".join(
            [
                _(
                    "In Zulip, topics [tell you what a message is about](/help/introduction-to-topics). "
                    "They are light-weight subjects, very similar to the subject line of an email."
                )
                + "\n\n",
                _(
                    "Check out [Recent conversations](#recent) to see what's happening! "
                    'You can return to this conversation by clicking "Direct messages" in the upper left.'
                ),
            ]
        )
    elif human_response_lower in ["keyboard", "shortcuts", "keyboard shortcuts"]:
        return "".join(
            [
                _(
                    "Zulip's [keyboard shortcuts](#keyboard-shortcuts) "
                    "let you navigate the app quickly and efficiently."
                )
                + "\n\n",
                _("Press `?` any time to see a [cheat sheet](#keyboard-shortcuts)."),
            ]
        )
    elif human_response_lower in ["formatting", "message formatting"]:
        return "".join(
            [
                _(
                    "Zulip uses [Markdown](/help/format-your-message-using-markdown), "
                    "an intuitive format for **bold**, *italics*, bulleted lists, and more. "
                    "Click [here](#message-formatting) for a cheat sheet."
                )
                + "\n\n",
                _(
                    "Check out our [messaging tips](/help/messaging-tips) "
                    "to learn about emoji reactions, code blocks and much more!"
                ),
            ]
        )
    elif human_response_lower in ["help", "?"]:
        return "".join(
            [
                _("Here are a few messages I understand:") + " ",
                bot_commands(no_help_command=True) + "\n\n",
                _(
                    "Check out our [Getting started guide](/help/getting-started-with-zulip), "
                    "or browse the [Help center](/help/) to learn more!"
                ),
            ]
        )
    else:
        return "".join(
            [
                _(
                    "I’m sorry, I did not understand your message. Please try one of the following commands:"
                )
                + " ",
                bot_commands(),
            ]
        )


def send_welcome_bot_response(send_request: SendMessageRequest) -> None:
    """Given the send_request object for a direct message from the user
    to welcome-bot, trigger the welcome-bot reply."""
    welcome_bot = get_system_bot(settings.WELCOME_BOT, send_request.realm.id)
    human_response_lower = send_request.message.content.lower()
    content = select_welcome_bot_response(human_response_lower)

    internal_send_private_message(
        welcome_bot,
        send_request.message.sender,
        content,
        # Note: Welcome bot doesn't trigger email/push notifications,
        # as this is intended to be seen contextually in the application.
        disable_external_notifications=True,
    )


@transaction.atomic
def send_initial_realm_messages(realm: Realm) -> None:
    welcome_bot = get_system_bot(settings.WELCOME_BOT, realm.id)
    # Make sure each stream created in the realm creation process has at least one message below
    # Order corresponds to the ordering of the streams on the left sidebar, to make the initial Home
    # view slightly less overwhelming
    with override_language(realm.default_language):
        content_of_private_streams_topic_name = (
            _("This is a private channel, as indicated by the lock icon next to the channel name.")
            + " "
            + _("Private channels are only visible to channel members.")
            + "\n"
            "\n"
            + _(
                "To manage this channel, go to [Channel settings]({channel_settings_url}) "
                "and click on `{initial_private_channel_name}`."
            )
        ).format(
            channel_settings_url="#channels/subscribed",
            initial_private_channel_name=Realm.INITIAL_PRIVATE_STREAM_NAME,
        )

        content1_of_topic_demonstration_topic_name = (
            _(
                "This is a message on channel #**{default_notification_channel_name}** with the "
                "topic `topic demonstration`."
            )
        ).format(default_notification_channel_name=Realm.DEFAULT_NOTIFICATION_STREAM_NAME)

        content2_of_topic_demonstration_topic_name = (
            _("Topics are a lightweight tool to keep conversations organized.")
            + " "
            + _(
                "You can learn more about topics at [Introduction to topics]({about_topics_help_url})."
            )
        ).format(about_topics_help_url="/help/introduction-to-topics")

        content_of_swimming_turtles_topic_name = (
            _(
                "This is a message on channel #**{default_notification_channel_name}** with the "
                "topic `swimming turtles`."
            )
            + "\n"
            "\n"
            "[](/static/images/cute/turtle.png)"
            "\n"
            "\n"
            + _(
                "[Start a new topic]({start_topic_help_url}) any time you're not replying to a \
            previous message."
            )
        ).format(
            default_notification_channel_name=Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
            start_topic_help_url="/help/introduction-to-topics#how-to-start-a-new-topic",
        )

        content_of_zulip_update_announcements_topic_name = remove_single_newlines(
            (
                _("""
Welcome! To help you learn about new features and configuration options,
this topic will receive messages about important changes in Zulip.

You can read these update messages whenever it's convenient, or
[mute]({mute_topic_help_url}) this topic if you are not interested.
If your organization does not want to receive these announcements,
they can be disabled. [Learn more]({zulip_update_announcements_help_url}).
            """)
            ).format(
                zulip_update_announcements_help_url="/help/configure-automated-notices#zulip-update-announcements",
                mute_topic_help_url="/help/mute-a-topic",
            )
        )

    welcome_messages: List[Dict[str, str]] = [
        {
            "stream": Realm.INITIAL_PRIVATE_STREAM_NAME,
            "topic_name": "private channels",
            "content": content_of_private_streams_topic_name,
        },
        {
            "stream": Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
            "topic_name": "topic demonstration",
            "content": content1_of_topic_demonstration_topic_name,
        },
        {
            "stream": Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
            "topic_name": "topic demonstration",
            "content": content2_of_topic_demonstration_topic_name,
        },
        {
            "stream": realm.DEFAULT_NOTIFICATION_STREAM_NAME,
            "topic_name": "swimming turtles",
            "content": content_of_swimming_turtles_topic_name,
        },
        {
            "stream": Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
            "topic_name": str(Realm.ZULIP_UPDATE_ANNOUNCEMENTS_TOPIC_NAME),
            "content": content_of_zulip_update_announcements_topic_name,
        },
    ]

    messages = [
        internal_prep_stream_message_by_name(
            realm,
            welcome_bot,
            message["stream"],
            message["topic_name"],
            message["content"],
        )
        for message in welcome_messages
    ]
    message_ids = [
        sent_message_result.message_id for sent_message_result in do_send_messages(messages)
    ]

    # We find the one of our just-sent messages with turtle.png in it,
    # and react to it.  This is a bit hacky, but works and is kinda a
    # 1-off thing.
    turtle_message = Message.objects.select_for_update().get(
        id__in=message_ids, content__icontains="cute/turtle.png"
    )
    emoji_data = get_emoji_data(realm.id, "turtle")
    do_add_reaction(
        welcome_bot, turtle_message, "turtle", emoji_data.emoji_code, emoji_data.reaction_type
    )
