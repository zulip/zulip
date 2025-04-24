from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db.models import Exists, OuterRef, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError, RateLimitedError
from zerver.lib.streams import is_user_in_groups_granting_content_access
from zerver.lib.upload import delete_message_attachment
from zerver.lib.user_groups import get_recursive_membership_groups
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)


def user_attachments(user_profile: UserProfile) -> list[dict[str, Any]]:
    attachments = Attachment.objects.filter(owner=user_profile).prefetch_related("messages")
    return [a.to_dict() for a in attachments]


def access_attachment_by_id(
    user_profile: UserProfile, attachment_id: int, needs_owner: bool = False
) -> Attachment:
    query = Attachment.objects.filter(id=attachment_id)
    if needs_owner:
        query = query.filter(owner=user_profile)

    attachment = query.first()
    if attachment is None:
        raise JsonableError(_("Invalid attachment"))
    return attachment


def remove_attachment(user_profile: UserProfile, attachment: Attachment) -> None:
    try:
        delete_message_attachment(attachment.path_id)
    except Exception:
        raise JsonableError(
            _("An error occurred while deleting the attachment. Please try again later.")
        )
    attachment.delete()


def validate_attachment_request_for_spectator_access(realm: Realm, attachment: Attachment) -> bool:
    if attachment.realm != realm:
        return False

    # Update cached is_web_public property, if necessary.
    if attachment.is_web_public is None:
        # Fill the cache in a single query. This is important to avoid
        # a potential race condition between checking and setting,
        # where the attachment could have been moved again.
        Attachment.objects.filter(id=attachment.id, is_web_public__isnull=True).update(
            is_web_public=Exists(
                Message.objects.filter(
                    # Uses index: zerver_attachment_messages_attachment_id_message_id_key
                    realm_id=realm.id,
                    attachment=OuterRef("id"),
                    recipient__stream__invite_only=False,
                    recipient__stream__is_web_public=True,
                ),
            ),
        )
        attachment.refresh_from_db()

    if not attachment.is_web_public:
        return False

    if settings.RATE_LIMITING:
        try:
            from zerver.lib.rate_limiter import rate_limit_spectator_attachment_access_by_file

            rate_limit_spectator_attachment_access_by_file(attachment.path_id)
        except RateLimitedError:
            return False

    return True


def validate_attachment_request(
    maybe_user_profile: UserProfile | AnonymousUser,
    path_id: str,
    realm: Realm | None = None,
) -> tuple[bool, Attachment | None]:
    try:
        attachment = Attachment.objects.get(path_id=path_id)
    except Attachment.DoesNotExist:
        return False, None

    if isinstance(maybe_user_profile, AnonymousUser):
        assert realm is not None
        return validate_attachment_request_for_spectator_access(realm, attachment), attachment

    user_profile = maybe_user_profile
    assert isinstance(user_profile, UserProfile)

    # Update cached is_realm_public property, if necessary.
    if attachment.is_realm_public is None:
        # Fill the cache in a single query. This is important to avoid
        # a potential race condition between checking and setting,
        # where the attachment could have been moved again.
        Attachment.objects.filter(id=attachment.id, is_realm_public__isnull=True).update(
            is_realm_public=Exists(
                Message.objects.filter(
                    # Uses index: zerver_attachment_messages_attachment_id_message_id_key
                    realm_id=user_profile.realm_id,
                    attachment=OuterRef("id"),
                    recipient__stream__invite_only=False,
                ),
            ),
        )
        attachment.refresh_from_db()

    if user_profile.id == attachment.owner_id:
        # If you own the file, you can access it.
        return True, attachment
    if (
        attachment.is_realm_public
        and attachment.realm == user_profile.realm
        and user_profile.can_access_public_streams()
    ):
        # Any user in the realm can access realm-public files
        return True, attachment

    messages = attachment.messages.all().select_related("recipient")

    usermessages_channel_ids = set()
    usermessage_rows = UserMessage.objects.filter(
        user_profile=user_profile, message__in=messages
    ).select_related("message", "message__recipient")
    for um in usermessage_rows:
        if not um.message.is_stream_message():
            # If the attachment was sent in a direct message or group direct
            # message then anyone who received that message can access it.
            return True, attachment
        else:
            usermessages_channel_ids.add(um.message.recipient.type_id)

    # These are subscriptions to a channel one of the messages was sent to
    subscribed_channel_ids = Subscription.objects.filter(
        user_profile=user_profile,
        active=True,
        recipient__type=Recipient.STREAM,
        recipient__in=[m.recipient_id for m in messages],
    ).values_list("recipient__type_id", flat=True)

    if usermessages_channel_ids.intersection(subscribed_channel_ids):
        # If the attachment was sent in a channel with public
        # or protected history and the user is still subscribed
        # to the channel then anyone who received that message
        # can access it.
        return True, attachment

    message_channel_ids = set()
    for message in messages:
        if message.is_stream_message():
            message_channel_ids.add(message.recipient.type_id)

    if len(message_channel_ids) == 0:
        # If only DMs are relevant, return early here.
        return False, attachment

    # The remaining code path is slow but should only be relevant
    # rarely: Users trying to view an attachment that was shared with
    # at least one channel, but the user is not subscribed to any such
    # channel. So it's not important that the accurate check for this
    # corner case is somewhat more expensive to check groups-based
    # permissions; we're no longer in a hot code path.
    message_channels = Stream.objects.filter(id__in=message_channel_ids)
    for channel in message_channels:
        # The user didn't receive any of the messages that included
        # this attachment. But they might still have access to it,
        # if it was sent to a stream they are subscribed to where
        # history is public to subscribers.
        if channel.id in subscribed_channel_ids and channel.is_history_public_to_subscribers():
            return True, attachment

    user_recursive_group_ids = set(
        get_recursive_membership_groups(user_profile).values_list("id", flat=True)
    )
    for channel in message_channels:
        if is_user_in_groups_granting_content_access(channel, user_recursive_group_ids):
            if channel.is_history_public_to_subscribers():
                return True, attachment
            # If the user had received the message at one point of
            # time, but they are no longer subscribed to a stream
            # with protected history. They can still access that
            # message and it's attachment
            elif channel.id in usermessages_channel_ids:
                return True, attachment

    return False, attachment


def get_old_unclaimed_attachments(
    weeks_ago: int,
) -> tuple[QuerySet[Attachment], QuerySet[ArchivedAttachment]]:
    """
    The logic in this function is fairly tricky. The essence is that
    a file should be cleaned up if and only if it not referenced by any
    Message, ScheduledMessage or ArchivedMessage. The way to find that out is through the
    Attachment and ArchivedAttachment tables.
    The queries are complicated by the fact that an uploaded file
    may have either only an Attachment row, only an ArchivedAttachment row,
    or both - depending on whether some, all or none of the messages
    linking to it have been archived.
    """
    delta_weeks_ago = timezone_now() - timedelta(weeks=weeks_ago)

    # The Attachment vs ArchivedAttachment queries are asymmetric because only
    # Attachment has the scheduled_messages relation.
    old_attachments = Attachment.objects.alias(
        has_other_messages=Exists(
            ArchivedAttachment.objects.filter(id=OuterRef("id")).exclude(messages=None)
        )
    ).filter(
        messages=None,
        scheduled_messages=None,
        create_time__lt=delta_weeks_ago,
        has_other_messages=False,
    )
    old_archived_attachments = ArchivedAttachment.objects.alias(
        has_other_messages=Exists(
            Attachment.objects.filter(id=OuterRef("id")).exclude(
                messages=None, scheduled_messages=None
            )
        )
    ).filter(messages=None, create_time__lt=delta_weeks_ago, has_other_messages=False)

    return old_attachments, old_archived_attachments
