from django.conf import settings
from django.db import transaction
from django.utils.translation import gettext as _
from django.utils.translation import override

from zerver.actions.message_send import internal_send_private_message, render_incoming_message
from zerver.lib.compose_reply import compose_quote_and_reply_for_channel_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.mention import silent_mention_syntax_for_user
from zerver.lib.message import access_message
from zerver.lib.streams import is_user_in_groups_granting_content_access
from zerver.lib.topic_link_util import get_message_link_label
from zerver.lib.url_encoding import stream_message_url
from zerver.lib.user_groups import get_recursive_membership_groups
from zerver.models import Recipient, Stream, Subscription, UserProfile
from zerver.models.messages import MentionNotification
from zerver.models.users import get_system_bot


@transaction.atomic(savepoint=False)
def notify_unsubscribed_mention(actor: UserProfile, message_id: int, recipient_id: int) -> bool:
    actor = UserProfile.objects.get(id=actor.id)
    # Locking the original serializes deliveries, including requests from separate workers.
    message = access_message(actor, message_id, lock_message=True, is_modifying_message=False)
    if (
        not actor.is_active
        or message.sender_id != actor.id
        or message.recipient.type != Recipient.STREAM
    ):
        return False
    stream = Stream.objects.get(id=message.recipient.type_id)
    assert stream.recipient_id is not None
    recipient = UserProfile.objects.filter(
        id=recipient_id, realm_id=actor.realm_id, is_active=True, is_bot=False
    ).first()
    if recipient is None or recipient.is_guest or stream.deactivated:
        return False
    if Subscription.objects.filter(
        user_profile=recipient, recipient_id=stream.recipient_id, active=True
    ).exists():
        return False
    groups = set(get_recursive_membership_groups(recipient).values_list("id", flat=True))
    if stream.invite_only and not is_user_in_groups_granting_content_access(stream, groups):
        return False
    try:
        access_message(recipient, message.id, is_modifying_message=False)
    except JsonableError:
        return False
    rendering = render_incoming_message(message, message.content, actor.realm)
    if recipient.id not in rendering.mentions_user_ids:
        return False
    _notification, created = MentionNotification.objects.get_or_create(
        message=message, recipient=recipient
    )
    if not created:
        return False
    url = stream_message_url(
        actor.realm,
        {
            "id": message.id,
            "stream_id": stream.id,
            "display_recipient": stream.name,
            "topic": message.topic_name(),
        },
    )
    with override(recipient.default_language):
        content = compose_quote_and_reply_for_channel_message(
            _("You have been mentioned in a channel you are not subscribed to."),
            message.content,
            silent_mention_syntax_for_user(message.sender),
            url,
            f"[{get_message_link_label(stream.name, message.topic_name(), message.id)}]({url})",
        )
    dm_id = internal_send_private_message(
        get_system_bot(settings.NOTIFICATION_BOT, actor.realm_id), recipient, content
    )
    if dm_id is None:
        raise JsonableError(_("Unable to send notification"))
    return True
