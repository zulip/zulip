from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils.translation import gettext as _
from pydantic import NonNegativeInt

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import PathOnly, typed_endpoint
from zerver.models import UserMessage, UserProfile


@typed_endpoint
def read_receipts(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: PathOnly[NonNegativeInt],
) -> HttpResponse:
    message = access_message(user_profile, message_id)

    if not user_profile.realm.enable_read_receipts:
        raise JsonableError(_("Read receipts are disabled in this organization."))

    # This query implements a few decisions:
    # * Most importantly, this is where we enforce the
    #   send_read_receipts privacy setting.
    #
    # * The message sender is never included, since presumably they
    #   read the message before sending it, and showing the sender as
    #   having read their own message is likely to be confusing.
    #
    # * Users who have muted the current user are not included, since
    #   the current user could infer that they have been muted by
    #   said users by noting that the muters immediately read every
    #   message that the current user sends to mutually subscribed
    #   streams.
    #
    # * Users muted by the current user are also not included, as this
    #   is consistent with other aspects of how muting works.
    #
    # * Deactivated users are excluded. While in theory someone
    #   could be interested in the information, not including them
    #   is a cleaner policy, and usually read receipts are only of
    #   interest shortly after a message was sent.
    #
    # * We do not filter on the historical flag. This means that a user
    #   who stars a public stream message that they did not originally
    #   receive will appear in read receipts for that message.
    #
    # * Marking a message as unread causes it to appear as not read
    #   via read receipts, as well. This is consistent with the fact
    #   that users can view a message without leaving it marked as
    #   read in other ways (desktop/email/push notifications).
    #
    # * Bots are included. Most bots never mark any messages as read,
    #   but one could imagine having them to do so via the API to
    #   communicate useful information. For example, the `read` flag
    #   could be used by a bot to track which messages have been
    #   bridged to another chat system or otherwise processed
    #   successfully by the bot, and users might find it useful to be
    #   able to inspect that in the UI. If this behavior is not
    #   desired for a bot, it can be disabled using the
    #   send_read_receipts privacy setting.
    #
    # Note that we do not attempt to present how many users received a
    # message but have NOT marked the message as read. There are
    # tricky corner cases involved in doing so, such as the
    # `historical` flag for public stream messages; but the most
    # important one is how to handle users who read a message and then
    # later unsubscribed from a stream.
    user_ids = (
        UserMessage.objects.filter(
            message_id=message.id,
            user_profile__is_active=True,
            user_profile__send_read_receipts=True,
        )
        .exclude(user_profile_id=message.sender_id)
        .exclude(user_profile__muter__muted_user_id=user_profile.id)
        .exclude(user_profile__muted__user_profile_id=user_profile.id)
        .extra(
            where=[UserMessage.where_read()],
        )
        .values_list("user_profile_id", flat=True)
    )

    return json_success(request, {"user_ids": list(user_ids)})
