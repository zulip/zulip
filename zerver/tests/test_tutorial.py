from django.conf import settings
from typing_extensions import override

from zerver.actions.message_send import internal_send_private_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import message_stream_count, most_recent_message
from zerver.models.users import get_system_bot


class TutorialTests(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        # This emulates the welcome message sent by the welcome bot to hamlet@zulip.com
        # This is only a quick fix - ideally, we would have this message sent by the initialization
        # code in populate_db.py
        user = self.example_user("hamlet")
        welcome_bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        content = "Shortened welcome message."
        internal_send_private_message(
            welcome_bot,
            user,
            content,
            # disable_external_notifications set to False will still lead
            # the tests to pass. Setting this to True, because we contextually
            # set this to true for welcome_bot in the codebase.
            disable_external_notifications=True,
        )

    def test_response_to_pm_for_app(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["app", "Apps"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "You can [download](/apps/) the [mobile and desktop apps](/apps/). "
                "Zulip also works great in a browser."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_edit(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["profile", "Profile"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "Go to [Profile settings](#settings/profile) "
                "to add a [profile picture](/help/change-your-profile-picture) "
                "and edit your [profile information](/help/edit-your-profile)."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_theme(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["theme", "Theme"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "You can switch between [light and dark theme](/help/dark-theme), "
                "[pick your favorite emoji set](/help/emoji-and-emoticons#change-your-emoji-set), "
                "[change your language](/help/change-your-language), and otherwise customize "
                "your Zulip experience in your [Preferences](#settings/preferences)."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_stream(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["Streams", "streams", "channels"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "Channels organize conversations based on who needs to see them. "
                "For example, it's common to have a channel for each team in an organization.\n\n"
                "[Browse and subscribe to channels](#channels/all)."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_topic(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["Topics", "topics"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "[Topics](/help/introduction-to-topics) summarize what each conversation in Zulip "
                "is about. You can read Zulip one topic at a time, seeing each message in context, "
                "no matter how many other conversations are going on.\n\n"
                "When you start a conversation, label it with a new topic. For a good topic name, "
                "think about finishing the sentence: “Hey, can we chat about…?”\n\n"
                "Check out [Recent conversations](#recent) for a list of topics that are being discussed."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_shortcuts(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["Keyboard shortcuts", "shortcuts", "Shortcuts"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "Zulip's [keyboard shortcuts](#keyboard-shortcuts) "
                "let you navigate the app quickly and efficiently.\n\n"
                "Press `?` any time to see a [cheat sheet](#keyboard-shortcuts)."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_formatting(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["message formatting", "Formatting"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "You can **format** *your* `message` using the handy formatting "
                "buttons, or by typing your formatting with Markdown.\n\n"
                "Check out the [cheat sheet](#message-formatting) to learn about "
                "spoilers, global times, and more."
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_help(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["help", "Help", "?"]
        self.login_user(user)
        for content in messages:
            self.send_personal_message(user, bot, content)
            expected_response = (
                "Here are a few messages I understand: "
                "`apps`, `profile`, `theme`, "
                "`channels`, `topics`, `message formatting`, `keyboard shortcuts`.\n\n"
                "Check out our [Getting started guide](/help/getting-started-with-zulip), "
                "or browse the [Help center](/help/) to learn more!"
            )
            self.assertEqual(most_recent_message(user).content, expected_response)

    def test_response_to_pm_for_undefined(self) -> None:
        user = self.example_user("hamlet")
        bot = get_system_bot(settings.WELCOME_BOT, user.realm_id)
        messages = ["Hello", "HAHAHA", "OKOK", "LalulaLapas"]
        self.login_user(user)
        # First undefined message sent.
        self.send_personal_message(user, bot, "Hello")
        expected_response = (
            "You can chat with me as much as you like! To get help, try one of the following messages: "
            "`apps`, `profile`, `theme`, `channels`, "
            "`topics`, `message formatting`, `keyboard shortcuts`, `help`."
        )
        self.assertEqual(most_recent_message(user).content, expected_response)

        # For future undefined messages, welcome bot won't send a reply.
        for content in messages:
            self.send_personal_message(user, bot, content)
            self.assertEqual(most_recent_message(user).content, content)

        # Check if Welcome bot still replies for bot commands
        self.send_personal_message(user, bot, "apps")
        expected_response = (
            "You can [download](/apps/) the [mobile and desktop apps](/apps/). "
            "Zulip also works great in a browser."
        )
        self.assertEqual(most_recent_message(user).content, expected_response)

    def test_no_response_to_group_pm(self) -> None:
        user1 = self.example_user("hamlet")
        user2 = self.example_user("cordelia")
        bot = get_system_bot(settings.WELCOME_BOT, user1.realm_id)
        content = "whatever"
        self.login_user(user1)
        self.send_group_direct_message(user1, [bot, user2], content)
        user1_messages = message_stream_count(user1)
        self.assertEqual(most_recent_message(user1).content, content)
        # Welcome bot should still respond to initial direct message
        # after group direct message.
        self.send_personal_message(user1, bot, content)
        self.assertEqual(message_stream_count(user1), user1_messages + 2)
