from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import Exists, F, OuterRef, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from analytics.models import RealmCount
from zerver.lib.cache import cache_delete_many, get_realm_used_upload_space_cache_key
from zerver.lib.exceptions import JsonableError, RateLimitedError
from zerver.lib.streams import is_user_in_groups_granting_content_access
from zerver.lib.upload import delete_message_attachment
from zerver.lib.user_groups import get_recursive_membership_groups
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    ImageAttachment,
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
    ImageAttachment.objects.filter(path_id=attachment.path_id).delete()
    _num_deleted, deleted_by_model = attachment.delete()

    # A concurrent request may have already deleted this attachment,
    # and adjusted the upload space snapshot for it.
    if deleted_by_model.get(Attachment._meta.label):
        adjust_upload_space_snapshots(
            [AttachmentSpaceUsage(attachment.realm_id, attachment.create_time, attachment.size)],
            removed=True,
        )


class AttachmentSpaceUsage(NamedTuple):
    realm_id: int
    create_time: datetime
    size: int


def adjust_upload_space_snapshots(
    attachments: Iterable[AttachmentSpaceUsage], *, removed: bool
) -> None:
    """Realm.currently_used_upload_space_bytes adds the sizes of
    attachments created since a realm's latest daily upload space
    snapshot to that snapshot's value. Removing (or restoring) an
    attachment created before the snapshot doesn't change that sum, so
    we adjust the snapshot itself, rather than leaving the realm's
    usage wrong until the next snapshot is computed."""
    sizes_by_realm: dict[int, list[tuple[datetime, int]]] = defaultdict(list)
    for attachment in attachments:
        sizes_by_realm[attachment.realm_id].append((attachment.create_time, attachment.size))

    for realm_id, sizes in sizes_by_realm.items():
        snapshot = (
            RealmCount.objects.filter(
                realm_id=realm_id, property="upload_quota_used_bytes::day", subgroup=None
            )
            .order_by("-end_time")
            .values_list("id", "end_time")
            .first()
        )
        if snapshot is not None:
            snapshot_id, snapshot_end_time = snapshot
            size_in_snapshot = sum(
                size for create_time, size in sizes if create_time < snapshot_end_time
            )
            if size_in_snapshot > 0:
                change = -size_in_snapshot if removed else size_in_snapshot
                RealmCount.objects.filter(id=snapshot_id).update(value=F("value") + change)

    # Flush after commit, so that a concurrent request can't recompute
    # the used space without these changes and cache that value.
    cache_keys = [get_realm_used_upload_space_cache_key(realm_id) for realm_id in sizes_by_realm]
    transaction.on_commit(lambda: cache_delete_many(cache_keys))


def delete_attachments_and_adjust_upload_space(attachments: QuerySet[Attachment]) -> int:
    with transaction.atomic(savepoint=False):
        # Lock the rows, so that we only adjust the upload space
        # snapshots for attachments that this transaction deletes.
        attachment_rows = list(
            attachments.select_for_update(of=("self",), no_key=False)
            .order_by("id")
            .values_list("id", "realm_id", "create_time", "size")
        )
        num_deleted, _deleted_by_model = Attachment.objects.filter(
            id__in=[row[0] for row in attachment_rows]
        ).delete()
        adjust_upload_space_snapshots(
            [
                AttachmentSpaceUsage(realm_id, create_time, size)
                for _attachment_id, realm_id, create_time, size in attachment_rows
            ],
            removed=True,
        )
    return num_deleted


def validate_attachment_request_for_spectator_access(
    realm: Realm, attachment: Attachment
) -> bool | None:
    """Returns whether the spectator is authorized to access the
    attachment, or None if the attachment was deleted concurrently
    with the request.
    """
    if attachment.realm != realm:
        return False

    if not realm.web_public_streams_enabled():
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

        try:
            attachment.refresh_from_db()
        except Attachment.DoesNotExist:
            return None

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
        is_authorized = validate_attachment_request_for_spectator_access(realm, attachment)
        if is_authorized is None:
            # The attachment was deleted concurrently with this
            # request; report it as not existing, just as if we
            # had observed that initially.
            return False, None
        return is_authorized, attachment

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
        try:
            attachment.refresh_from_db()
        except Attachment.DoesNotExist:
            # The attachment was deleted concurrently with this
            # request; report it as not existing, just as if we
            # had observed that initially.
            return False, None

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
        if not um.message.is_channel_message:
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
        if message.is_channel_message:
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

    if user_profile.is_guest:
        # All existing groups granting content access have
        # allow_everyone_group=False, so they never grant guests access.
        return False, attachment

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
    old_attachments = (
        Attachment.objects.alias(
            has_other_messages=Exists(
                ArchivedAttachment.objects.filter(id=OuterRef("id")).exclude(messages=None)
            )
        )
        .filter(
            messages=None,
            scheduled_messages=None,
            create_time__lt=delta_weeks_ago,
            has_other_messages=False,
        )
        .order_by("id")
    )
    old_archived_attachments = (
        ArchivedAttachment.objects.alias(
            has_other_messages=Exists(
                Attachment.objects.filter(id=OuterRef("id")).exclude(
                    messages=None, scheduled_messages=None
                )
            )
        )
        .filter(
            messages=None,
            create_time__lt=delta_weeks_ago,
            has_other_messages=False,
        )
        .order_by("id")
    )

    return old_attachments, old_archived_attachments
