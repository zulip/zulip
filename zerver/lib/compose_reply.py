# The web app composes the same quote-and-reply format in
# web/src/compose_reply.ts; keep the two in sync.
from dataclasses import dataclass

from django.conf import settings
from django.utils.translation import gettext_lazy

from zerver.lib.markdown.fenced_code import get_unused_fence
from zerver.lib.message import truncate_content

CHANNEL_MESSAGE_QUOTE_CONTEXT = gettext_lazy(
    "{user_silent_mention} [said]({conversation_url}) in {topic_pretty_link}:"
)
DIRECT_MESSAGE_QUOTE_CONTEXT = gettext_lazy(
    "{user_silent_mention} [said]({conversation_url}) to {list_of_recipient_mentions}:"
)
MESSAGE_QUOTE_BODY = "{fence}quote\n{content}\n{fence}"
QUOTE_AND_REPLY_TEMPLATE = "{quote_context}\n{quote_body}\n{reply_content}"
QUOTE_CONTENT_MINIMUM_LENGTH = 1000


@dataclass
class MaxContentLengths:
    reply_content: int
    quoted_content: int


def get_measurements_for_quote_and_reply_content(
    reply_content_length: int,
    quote_content_length: int,
    template_syntax_length: int,
) -> MaxContentLengths:
    """Splits the message length limit between a reply and the message it
    quotes. The quote is guaranteed QUOTE_CONTENT_MINIMUM_LENGTH characters
    when it at least has that much to say, and the reply gets whatever room
    is left.
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


def compose_quote_and_reply_for_channel_message(
    reply_content: str,
    quote_content: str,
    quote_message_sender_silent_mention: str,
    quote_message_url: str,
    quote_message_topic_pretty_link: str,
) -> str:
    fence = get_unused_fence(quote_content)
    quote_context = CHANNEL_MESSAGE_QUOTE_CONTEXT.format(
        user_silent_mention=quote_message_sender_silent_mention,
        conversation_url=quote_message_url,
        topic_pretty_link=quote_message_topic_pretty_link,
    )
    max_length_for = get_measurements_for_quote_and_reply_content(
        reply_content_length=len(reply_content),
        quote_content_length=len(quote_content),
        # Measured with the same template the result is built from, so that
        # every character of syntax between the two parts is accounted for.
        template_syntax_length=len(
            QUOTE_AND_REPLY_TEMPLATE.format(
                quote_context=quote_context,
                quote_body=MESSAGE_QUOTE_BODY.format(fence=fence, content=""),
                reply_content="",
            )
        ),
    )
    return QUOTE_AND_REPLY_TEMPLATE.format(
        quote_context=quote_context,
        quote_body=MESSAGE_QUOTE_BODY.format(
            fence=fence,
            content=truncate_content(
                quote_content,
                max_length_for.quoted_content,
                "\n[message truncated]",
            ),
        ),
        reply_content=truncate_content(
            reply_content,
            max_length_for.reply_content,
            "\n[message truncated]",
        ),
    )
