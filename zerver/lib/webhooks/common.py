from django.http import HttpRequest
from typing import Optional, Text

from zerver.lib.actions import check_send_stream_message, \
    check_send_private_message
from zerver.lib.exceptions import StreamDoesNotExistError
from zerver.lib.request import REQ, has_request_variables
from zerver.models import UserProfile


@has_request_variables
def check_send_webhook_message(
        request: HttpRequest, user_profile: UserProfile,
        topic: Text, body: Text, stream: Optional[Text]=REQ(default=None),
        user_specified_topic: Optional[Text]=REQ("topic", default=None)
) -> None:

    if stream is None:
        assert user_profile.bot_owner is not None
        check_send_private_message(user_profile, request.client,
                                   user_profile.bot_owner, body)
    else:
        if user_specified_topic is not None:
            topic = user_specified_topic

        try:
            check_send_stream_message(user_profile, request.client,
                                      stream, topic, body)
        except StreamDoesNotExistError:
            # A PM will be sent to the bot_owner by check_message, notifying
            # that the webhook bot just tried to send a message to a non-existent
            # stream, so we don't need to re-raise it since it clutters up
            # webhook-errors.log
            pass
