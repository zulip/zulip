from django.conf import settings

from zerver.lib.compose_reply import (
    MaxContentLengths,
    compose_quote_and_reply_message,
    get_quote_and_reply_content_limits,
)
from zerver.lib.test_classes import ZulipTestCase


class ComposeQuoteAndReplyTest(ZulipTestCase):
    def test_compose_quote_and_reply_message(self) -> None:
        composed_message = compose_quote_and_reply_message(
            reply_content="I agree.",
            quote_content="Good morning!",
            quote_message_sender_mention="@_**Iago**",
            quote_message_link_syntax="#**Verona>hello@15**",
        )
        self.assertEqual(
            composed_message,
            """
@_**Iago** said #**Verona>hello@15**:
``` quote
Good morning!
```
I agree.
""".strip(),
        )

    def test_compose_quote_and_reply_message_with_fenced_quote(self) -> None:
        composed_message = compose_quote_and_reply_message(
            reply_content="Thanks!",
            quote_content="```\nprint('hello')\n```",
            quote_message_sender_mention="@_**Iago**",
            quote_message_link_syntax="#**Verona>hello@15**",
        )
        # The quote's own fence has to be shorter than the one wrapping it.
        self.assertEqual(
            composed_message,
            """
@_**Iago** said #**Verona>hello@15**:
```` quote
```
print('hello')
```
````
Thanks!
""".strip(),
        )

    def test_compose_quote_and_reply_message_truncates_long_content(self) -> None:
        max_message_length = 10000
        with self.settings(MAX_MESSAGE_LENGTH=max_message_length):
            composed_message = compose_quote_and_reply_message(
                reply_content="b" * max_message_length,
                quote_content="a" * 2000,
                quote_message_sender_mention="@_**Iago**",
                quote_message_link_syntax="#**Verona>hello@15**",
            )

        # The quote is cut down to the 1000 characters left for it, marked as
        # truncated, and still closes its fence; the reply keeps the rest of
        # the limit.
        self.assert_length(composed_message, max_message_length)
        self.assertIn(f"``` quote\n{'a' * 980}\n[message truncated]\n```\n", composed_message)
        truncated_reply = composed_message.split("```\n")[-1]
        self.assertTrue(truncated_reply.endswith("\n[message truncated]"))
        self.assertSetEqual(set(truncated_reply.removesuffix("\n[message truncated]")), {"b"})

    def test_get_quote_and_reply_content_limits(self) -> None:
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
                    limits = get_quote_and_reply_content_limits(
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
