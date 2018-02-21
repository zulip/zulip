
from django.conf import settings

from zerver.lib.actions import set_default_streams, bulk_add_subscriptions, \
    internal_prep_stream_message, internal_send_private_message, \
    create_stream_if_needed, create_streams_if_needed, do_send_messages, \
    do_add_reaction_legacy, create_users
from zerver.models import Realm, UserProfile, Message, Reaction, get_system_bot

from typing import Any, Dict, List, Mapping, Text

def setup_realm_internal_bots(realm: Realm) -> None:
    """Create this realm's internal bots.

    This function is idempotent; it does nothing for a bot that
    already exists.
    """
    internal_bots = [(bot['name'], bot['email_template'] % (settings.INTERNAL_BOT_DOMAIN,))
                     for bot in settings.REALM_INTERNAL_BOTS]
    create_users(realm, internal_bots, bot_type=UserProfile.DEFAULT_BOT)
    bots = UserProfile.objects.filter(
        realm=realm,
        email__in=[bot_info[1] for bot_info in internal_bots],
        bot_owner__isnull=True
    )
    for bot in bots:
        bot.bot_owner = bot
        bot.save()

def send_initial_pms(user: UserProfile) -> None:
    organization_setup_text = ""
    if user.is_realm_admin:
        help_url = user.realm.uri + "/help/getting-your-organization-started-with-zulip"
        organization_setup_text = ("* [Read the guide](%s) for getting your organization "
                                   "started with Zulip\n" % (help_url,))

    content = (
        "Hello, and welcome to Zulip!\n\nThis is a private message from me, Welcome Bot. "
        "Here are some tips to get you started:\n"
        "* Download our [Desktop and mobile apps](/apps)\n"
        "* Customize your account and notifications on your [Settings page](#settings)\n"
        "* Type `?` to check out Zulip's keyboard shortcuts\n"
        "%s"
        "\n"
        "The most important shortcut is `r` to reply.\n\n"
        "Practice sending a few messages by replying to this conversation. If you're not into "
        "keyboards, that's okay too; clicking anywhere on this message will also do the trick!") \
        % (organization_setup_text,)

    internal_send_private_message(user.realm, get_system_bot(settings.WELCOME_BOT),
                                  user, content)

def setup_initial_streams(realm: Realm) -> None:
    stream_dicts = [
        {'name': "general"},
        {'name': "new members",
         'description': "For welcoming and onboarding new members. If you haven't yet, "
         "introduce yourself in a new thread using your name as the topic!"},
        {'name': "zulip",
         'description': "For discussing Zulip, Zulip tips and tricks, and asking "
         "questions about how Zulip works"}]  # type: List[Mapping[str, Any]]
    create_streams_if_needed(realm, stream_dicts)
    set_default_streams(realm, {stream['name']: {} for stream in stream_dicts})

def send_initial_realm_messages(realm: Realm) -> None:
    welcome_bot = get_system_bot(settings.WELCOME_BOT)
    # Make sure each stream created in the realm creation process has at least one message below
    # Order corresponds to the ordering of the streams on the left sidebar, to make the initial Home
    # view slightly less overwhelming
    welcome_messages = [
        {'stream': Realm.DEFAULT_NOTIFICATION_STREAM_NAME,
         'topic': "welcome",
         'content': "This is a message on stream `%s` with the topic `welcome`. We'll use this stream "
         "for system-generated notifications." % (Realm.DEFAULT_NOTIFICATION_STREAM_NAME,)},
        {'stream': Realm.INITIAL_PRIVATE_STREAM_NAME,
         'topic': "private streams",
         'content': "This is a private stream. Only admins and people you invite "
         "to the stream will be able to see that this stream exists."},
        {'stream': "general",
         'topic': "welcome",
         'content': "Welcome to #**general**."},
        {'stream': "new members",
         'topic': "onboarding",
         'content': "A #**new members** stream is great for onboarding new members.\n\nIf you're "
         "reading this and aren't the first person here, introduce yourself in a new thread "
         "using your name as the topic! Type `c` or click on `New Topic` at the bottom of the "
         "screen to start a new topic."},
        {'stream': "zulip",
         'topic': "topic demonstration",
         'content': "Here is a message in one topic. Replies to this message will go to this topic."},
        {'stream': "zulip",
         'topic': "topic demonstration",
         'content': "A second message in this topic. With [turtles](/static/images/cute/turtle.png)!"},
        {'stream': "zulip",
         'topic': "second topic",
         'content': "This is a message in a second topic.\n\nTopics are similar to email subjects, "
         "in that each conversation should get its own topic. Keep them short, though; one "
         "or two words will do it!"},
    ]  # type: List[Dict[str, Text]]
    messages = [internal_prep_stream_message(
        realm, welcome_bot,
        message['stream'], message['topic'], message['content']) for message in welcome_messages]
    message_ids = do_send_messages(messages)

    # We find the one of our just-sent messages with turtle.png in it,
    # and react to it.  This is a bit hacky, but works and is kinda a
    # 1-off thing.
    turtle_message = Message.objects.get(
        id__in=message_ids,
        subject='topic demonstration',
        content__icontains='cute/turtle.png')
    do_add_reaction_legacy(welcome_bot, turtle_message, 'turtle')
