from django.conf import settings

from zerver.lib.compose_reply import (
    MaxContentLengths,
    compose_quote_and_reply_for_channel_message,
    get_measurements_for_quote_and_reply_content,
    truncate_quote_content,
)
from zerver.lib.markdown import markdown_convert
from zerver.lib.test_classes import ZulipTestCase
from zerver.models.realms import get_realm

MESSAGE_URL = "#narrow/channel/9-Verona/topic/hello/near/15"
TOPIC_PRETTY_LINK = "#**Verona>hello**"


class ComposeQuoteAndReplyTest(ZulipTestCase):
    def test_compose_quote_and_reply_for_channel_message(self) -> None:
        composed_message = compose_quote_and_reply_for_channel_message(
            reply_content="I agree.",
            quote_content="Good morning!",
            quote_message_sender_silent_mention="@_**Iago**",
            quote_message_url=MESSAGE_URL,
            quote_message_topic_pretty_link=TOPIC_PRETTY_LINK,
        )
        self.assertEqual(
            composed_message,
            f"""
@_**Iago** [said]({MESSAGE_URL}) in {TOPIC_PRETTY_LINK}:
```quote
Good morning!
```
I agree.
""".strip(),
        )

    def test_compose_quote_and_reply_for_channel_message_with_fenced_quote(self) -> None:
        composed_message = compose_quote_and_reply_for_channel_message(
            reply_content="Thanks!",
            quote_content="```\nprint('hello')\n```",
            quote_message_sender_silent_mention="@_**Iago**",
            quote_message_url=MESSAGE_URL,
            quote_message_topic_pretty_link=TOPIC_PRETTY_LINK,
        )
        # The quote's own fence has to be shorter than the one wrapping it.
        self.assertEqual(
            composed_message,
            f"""
@_**Iago** [said]({MESSAGE_URL}) in {TOPIC_PRETTY_LINK}:
````quote
```
print('hello')
```
````
Thanks!
""".strip(),
        )

    def test_compose_quote_and_reply_for_channel_message_with_unclosed_fence(self) -> None:
        composed_message = compose_quote_and_reply_for_channel_message(
            reply_content="Thanks!",
            quote_content="```\nprint('hello')```",
            quote_message_sender_silent_mention="@_**Iago**",
            quote_message_url=MESSAGE_URL,
            quote_message_topic_pretty_link=TOPIC_PRETTY_LINK,
        )
        # The code block the quoted message leaves open is closed inside
        # the quote, so that it can't swallow the reply.
        self.assertEqual(
            composed_message,
            f"""
@_**Iago** [said]({MESSAGE_URL}) in {TOPIC_PRETTY_LINK}:
````quote
```
print('hello')```
```
````
Thanks!
""".strip(),
        )
        rendered_content = markdown_convert(
            composed_message, message_realm=get_realm("zulip")
        ).rendered_content
        self.assertTrue(rendered_content.endswith("</blockquote>\n<p>Thanks!</p>"))

    def test_compose_quote_and_reply_for_channel_message_truncates_quote_in_code_block(
        self,
    ) -> None:
        composed_message = compose_quote_and_reply_for_channel_message(
            reply_content="b" * settings.MAX_MESSAGE_LENGTH,
            quote_content="```\n" + "x = 1\n" * 400 + "```",
            quote_message_sender_silent_mention="@_**Iago**",
            quote_message_url=MESSAGE_URL,
            quote_message_topic_pretty_link=TOPIC_PRETTY_LINK,
        )

        self.assert_length(composed_message, settings.MAX_MESSAGE_LENGTH)
        rendered_content = markdown_convert(
            composed_message, message_realm=get_realm("zulip")
        ).rendered_content
        self.assertIn("<p>[message truncated]</p>\n</blockquote>\n<p>bbb", rendered_content)

    def test_compose_quote_and_reply_for_channel_message_with_empty_quote(self) -> None:
        for quote_content in ["", " \n "]:
            with self.subTest(quote_content=quote_content):
                composed_message = compose_quote_and_reply_for_channel_message(
                    reply_content="I agree.",
                    quote_content=quote_content,
                    quote_message_sender_silent_mention="@_**Iago**",
                    quote_message_url=MESSAGE_URL,
                    quote_message_topic_pretty_link=TOPIC_PRETTY_LINK,
                )
                self.assertEqual(composed_message, "I agree.")

    def test_truncate_quote_content(self) -> None:
        self.assertEqual(truncate_quote_content("```\ncode\n```", 12), "```\ncode\n```")
        self.assertEqual(truncate_quote_content("a" * 50, 30), "a" * 10 + "\n[message truncated]")
        # Cutting to 24 characters leaves the code block open, and closing
        # it would overflow, so the cut moves back to make room.
        self.assertEqual(
            truncate_quote_content("```\n" + "c" * 100 + "\n```", 44),
            "```\n" + "c" * 16 + "\n```\n[message truncated]",
        )
        self.assertEqual(truncate_quote_content("a" * 50, 10), "\n[message truncated]")

    def test_compose_quote_and_reply_for_channel_message_truncates_long_content(self) -> None:
        max_message_length = 10000
        with self.settings(MAX_MESSAGE_LENGTH=max_message_length):
            composed_message = compose_quote_and_reply_for_channel_message(
                reply_content="b" * max_message_length,
                quote_content="a" * 2000,
                quote_message_sender_silent_mention="@_**Iago**",
                quote_message_url=MESSAGE_URL,
                quote_message_topic_pretty_link=TOPIC_PRETTY_LINK,
            )

        # The quote is cut down to the 1000 characters left for it, marked as
        # truncated, and still closes its fence; the reply keeps the rest of
        # the limit, using it exactly.
        self.assert_length(composed_message, max_message_length)
        self.assertIn(f"```quote\n{'a' * 980}\n[message truncated]\n```\n", composed_message)
        truncated_reply = composed_message.split("```\n")[-1]
        self.assertTrue(truncated_reply.endswith("\n[message truncated]"))
        self.assertSetEqual(set(truncated_reply.removesuffix("\n[message truncated]")), {"b"})

    def test_get_measurements_for_quote_and_reply_content(self) -> None:
        cases = [
            # (case, template syntax, reply length, quote length,
            #  expected reply limit, expected quote limit)
            ("both fit", 200, 100, 100, 100, 100),
            ("exactly fills the limit", 200, 8800, 1000, 8800, 1000),
            ("quote shorter than its guaranteed minimum", 200, 9790, 50, 9750, 50),
            ("long reply crowds the quote to its minimum", 200, 9000, 5000, 8800, 1000),
            ("short reply leaves the quote the rest", 200, 500, 20000, 500, 9300),
            ("both too long", 200, 20000, 20000, 8800, 1000),
            ("longer template syntax shrinks the reply", 700, 9790, 50, 9250, 50),
            ("template syntax alone exceeds the limit", 10001, 9790, 50, 0, 0),
        ]

        with self.settings(MAX_MESSAGE_LENGTH=10000):
            for (
                case,
                syntax_length,
                reply_length,
                quote_length,
                expected_reply_limit,
                expected_quote_limit,
            ) in cases:
                with self.subTest(case=case):
                    limits = get_measurements_for_quote_and_reply_content(
                        reply_content_length=reply_length,
                        quote_content_length=quote_length,
                        template_syntax_length=syntax_length,
                    )
                    self.assertEqual(
                        limits,
                        MaxContentLengths(
                            reply_content=expected_reply_limit,
                            quoted_content=expected_quote_limit,
                        ),
                    )
                    # Whatever the split, the two parts fit in the room the
                    # template syntax leaves them.
                    self.assertLessEqual(
                        limits.reply_content + limits.quoted_content,
                        max(settings.MAX_MESSAGE_LENGTH - syntax_length, 0),
                    )
