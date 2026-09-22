# The web app composes the same quote-and-reply format in
# web/src/compose_reply.ts; keep the two in sync.
from django.utils.translation import gettext_lazy

CHANNEL_MESSAGE_QUOTE_CONTEXT = gettext_lazy(
    "{user_silent_mention} [said]({conversation_url}) in {topic_pretty_link}:"
)
DIRECT_MESSAGE_QUOTE_CONTEXT = gettext_lazy(
    "{user_silent_mention} [said]({conversation_url}) to {list_of_recipient_mentions}:"
)
MESSAGE_QUOTE_BODY = "{fence}quote\n{content}\n{fence}"
