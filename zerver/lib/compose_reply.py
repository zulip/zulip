# No need to keep this in sync with web/src/compose_reply.ts,
# apart from the template syntaxes.
from dataclasses import dataclass

from django.conf import settings

from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.message import truncate_content

QUOTE_MESSAGE_TEMPLATE = """
{quote_message_sender_mention} said {quote_message_link_syntax}:
{fence} quote
{quote_content}
{fence}
""".strip()

QUOTE_CONTENT_MINIMUM_LENGTH = 1000


@dataclass
class MaxContentLengths:
    reply_content: int
    quoted_content: int


def get_quote_and_reply_content_limits(
    reply_content_length: int,
    quote_content_length: int,
    template_syntax_length: int,
) -> MaxContentLengths:
    """Splits the message length limit between a reply and the message it
    quotes. The quote is guaranteed QUOTE_CONTENT_MINIMUM_LENGTH characters
    when it has that much to say, and the reply gets whatever room is left.
    """
    available_length = max(settings.MAX_MESSAGE_LENGTH - template_syntax_length, 0)
    minimum_for_quote = min(QUOTE_CONTENT_MINIMUM_LENGTH, available_length)

    quoted_content = min(
        quote_content_length,
        max(available_length - reply_content_length, minimum_for_quote),
    )
    return MaxContentLengths(
        reply_content=min(reply_content_length, available_length - quoted_content),
        quoted_content=quoted_content,
    )


def compose_quote_and_reply_message(
    reply_content: str,
    quote_content: str,
    quote_message_sender_mention: str,
    quote_message_link_syntax: str,
) -> str:
    fence = get_unused_fence(quote_content)
    max_length_for = get_quote_and_reply_content_limits(
        reply_content_length=len(reply_content),
        quote_content_length=len(quote_content),
        template_syntax_length=(
            len(
                QUOTE_MESSAGE_TEMPLATE.format(
                    quote_message_sender_mention=quote_message_sender_mention,
                    quote_message_link_syntax=quote_message_link_syntax,
                    quote_content="",
                    fence=fence,
                )
            )
            + 1
        ),
    )
    quoted_part = QUOTE_MESSAGE_TEMPLATE.format(
        quote_message_sender_mention=quote_message_sender_mention,
        quote_message_link_syntax=quote_message_link_syntax,
        quote_content=truncate_content(
            quote_content,
            max_length_for.quoted_content,
            "\n[message truncated]",
        ),
        fence=fence,
    )

    reply_part = truncate_content(
        reply_content,
        max_length_for.reply_content,
        "\n[message truncated]",
    )
    return f"{quoted_part}\n{reply_part}"
