import itertools
from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language
from django_stubs_ext import StrPromise

from zerver.actions.message_delete import DeleteMessagesEvent, do_delete_messages
from zerver.actions.message_flags import do_update_mobile_push_notification
from zerver.actions.message_send import (
    filter_presence_idle_user_ids,
    get_recipient_info,
    internal_send_stream_message,
    render_incoming_message,
)
from zerver.actions.uploads import AttachmentChangeResult, check_attachment_reference_change
from zerver.actions.user_topics import bulk_do_set_user_topic_visibility_policy
from zerver.lib import utils
from zerver.lib.exceptions import (
    JsonableError,
    MessageMoveError,
    MessagesNotAllowedInEmptyTopicError,
    PreviousMessageContentMismatchedError,
    StreamWildcardMentionNotAllowedError,
    TopicsNotAllowedError,
    TopicWildcardMentionNotAllowedError,
)
from zerver.lib.markdown import MessageRenderingResult, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionBackend, MentionData, silent_mention_syntax_for_user
from zerver.lib.message import (
    access_message,
    bulk_access_stream_messages_query,
    check_user_group_mention_allowed,
    event_recipient_ids_for_action_on_messages,
    normalize_body,
    stream_wildcard_mention_allowed,
    topic_wildcard_mention_allowed,
    truncate_topic,
)
from zerver.lib.message_cache import update_message_cache
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_by_id_for_message,
    can_access_stream_history,
    can_edit_topic,
    can_move_messages_out_of_channel,
    can_resolve_topics,
    check_for_can_create_topic_group_violation,
    check_stream_access_based_on_can_send_message_group,
    get_stream_topics_policy,
    notify_stream_is_recently_active_update,
)
from zerver.lib.string_validation import check_stream_topic
from zerver.lib.thumbnail import manifest_and_get_user_upload_previews, rewrite_thumbnailed_images
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import (
    ORIG_TOPIC,
    RESOLVED_TOPIC_PREFIX,
    TOPIC_LINKS,
    TOPIC_NAME,
    get_topic_display_name,
    maybe_rename_general_chat_to_empty_topic,
    messages_for_topic,
    participants_for_topic,
    save_message_for_edit_use_case,
    update_edit_history,
    update_messages_for_topic_edit,
)
from zerver.lib.topic_link_util import get_stream_topic_link_syntax
from zerver.lib.types import DirectMessageEditRequest, EditHistoryEvent, StreamMessageEditRequest
from zerver.lib.url_encoding import stream_message_url
from zerver.lib.user_message import bulk_insert_all_ums
from zerver.lib.user_topics import get_users_with_user_topic_visibility_policy
from zerver.lib.widget import is_widget_message
from zerver.models import (
    ArchivedAttachment,
    ArchivedMessage,
    Attachment,
    Message,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
    UserTopic,
)
from zerver.models.streams import (
    StreamTopicsPolicyEnum,
    get_stream_by_id_for_sending_message,
    get_stream_by_id_in_realm,
)
from zerver.models.users import ResolvedTopicNoticeAutoReadPolicyEnum, get_system_bot
from zerver.tornado.django_api import send_event_on_commit


@dataclass
class UpdateMessageResult:
    changed_message_count: int
    detached_uploads: list[dict[str, Any]]


def subscriber_info(user_id: int) -> dict[str, Any]:
    return {"id": user_id, "flags": ["read"]}


def validate_message_edit_payload(
    message: Message,
    stream_id: int | None,
    topic_name: str | None,
    propagate_mode: str | None,
    content: str | None,
    prev_content_sha256: str | None,
) -> None:
    """
    Validates that a message edit request is well-formed. Does not handle permissions.
    """
    if topic_name is None and content is None and stream_id is None:
        raise JsonableError(_("Nothing to change"))

    if not message.is_channel_message:
        if stream_id is not None:
            raise JsonableError(_("Direct messages cannot be moved to channels."))
        if topic_name is not None:
            raise JsonableError(_("Direct messages cannot have topics."))

    if propagate_mode != "change_one" and topic_name is None and stream_id is None:
        raise JsonableError(_("Invalid propagate_mode without topic edit"))

    if topic_name in {
        RESOLVED_TOPIC_PREFIX.strip(),
        f"{RESOLVED_TOPIC_PREFIX}{Message.EMPTY_TOPIC_FALLBACK_NAME}",
    }:
        raise JsonableError(_("General chat cannot be marked as resolved"))

    if topic_name is not None:
        check_stream_topic(topic_name)

    if stream_id is not None and content is not None:
        raise JsonableError(_("Cannot change message content while changing channel"))

    # Right now, we prevent users from editing widgets.
    if content is not None and is_widget_message(message):
        raise JsonableError(_("Widgets cannot be edited."))

    # We don't restrict this check to requests to edit content, to
    # give the parameter a pure meaning. But clients sending this for
    # topic moves are likely doing so in error.
    if prev_content_sha256 is not None and prev_content_sha256 != utils.sha256_hash(
        message.content
    ):
        raise PreviousMessageContentMismatchedError


def validate_user_can_edit_message(
    user_profile: UserProfile, message: Message, edit_limit_buffer: int
) -> None:
    """
    Checks if the user has the permission to edit the message.
    """
    if not user_profile.realm.allow_message_editing:
        raise JsonableError(_("Your organization has turned off message editing"))

    # You cannot edit the content of message sent by someone else.
    if message.sender_id != user_profile.id:
        raise JsonableError(_("You don't have permission to edit this message"))

    if user_profile.realm.message_content_edit_limit_seconds is not None:
        deadline_seconds = user_profile.realm.message_content_edit_limit_seconds + edit_limit_buffer
        if (timezone_now() - message.date_sent) > timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has passed"))


def get_unread_user_ids_for_resolved_topic_notifications(
    stream: Stream,
    topic_name: str,
    users_following_topic: set[UserProfile] | None,
) -> set[int]:
    unread_user_ids: set[int] = set()

    all_stream_user_profiles = UserProfile.objects.filter(
        id__in=get_active_subscriptions_for_stream_id(
            stream.id, include_deactivated_users=False
        ).values_list("user_profile_id", flat=True),
        is_bot=False,
    )

    user_ids_following_topic: set[int] = set()
    if users_following_topic is not None:
        user_ids_following_topic = {user.id for user in users_following_topic}
    else:
        user_ids_following_topic = set(
            UserTopic.objects.filter(
                stream=stream,
                topic_name__iexact=topic_name,
                visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
            ).values_list("user_profile_id", flat=True)
        )

    for user_profile in all_stream_user_profiles:
        if (
            user_profile.resolved_topic_notice_auto_read_policy
            == ResolvedTopicNoticeAutoReadPolicyEnum.never.value
        ):
            unread_user_ids.add(user_profile.id)
        elif (
            user_profile.resolved_topic_notice_auto_read_policy
            == ResolvedTopicNoticeAutoReadPolicyEnum.except_followed.value
            and user_profile.id in user_ids_following_topic
        ):
            unread_user_ids.add(user_profile.id)

    return unread_user_ids


def maybe_send_resolve_topic_notifications(
    *,
    user_profile: UserProfile,
    message_edit_request: StreamMessageEditRequest,
    users_following_topic: set[UserProfile] | None,
) -> tuple[int | None, bool]:
    """Returns resolved_topic_message_id if resolve topic notifications were in fact sent."""
    # Note that topics will have already been stripped in check_update_message.
    topic_resolved = message_edit_request.topic_resolved
    topic_unresolved = message_edit_request.topic_unresolved
    if not topic_resolved and not topic_unresolved:
        # If there's some other weird topic that does not toggle the
        # state of "topic starts with RESOLVED_TOPIC_PREFIX", we do
        # nothing. Any other logic could result in cases where we send
        # these notifications in a non-alternating fashion.
        #
        # Note that it is still possible for an individual topic to
        # have multiple "This topic was marked as resolved"
        # notifications in a row: one can send new messages to the
        # pre-resolve topic and then resolve the topic created that
        # way to get multiple in the resolved topic. And then an
        # administrator can delete the messages in between. We consider this
        # to be a fundamental risk of irresponsible message deletion,
        # not a bug with the "resolve topics" feature.
        return None, False

    stream = message_edit_request.orig_stream
    # Sometimes a user might accidentally resolve a topic, and then
    # have to undo the action. We don't want to spam "resolved",
    # "unresolved" messages one after another in such a situation.
    # For that reason, we apply a short grace period during which
    # such an undo action will just delete the previous notification
    # message instead.
    if maybe_delete_previous_resolve_topic_notification(
        user_profile, stream, message_edit_request.target_topic_name
    ):
        return None, True

    # Compute the users for whom this message should be marked as unread
    # based on the `resolved_topic_notice_auto_read_policy` user setting.
    topic_name = message_edit_request.target_topic_name
    unread_user_ids = get_unread_user_ids_for_resolved_topic_notifications(
        stream=stream,
        topic_name=topic_name,
        users_following_topic=users_following_topic,
    )

    sender = get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id)
    user_mention = silent_mention_syntax_for_user(user_profile)
    with override_language(stream.realm.default_language):
        if topic_resolved:
            notification_string = _("{user} has marked this topic as resolved.")
        elif topic_unresolved:
            notification_string = _("{user} has marked this topic as unresolved.")

        resolved_topic_message_id = internal_send_stream_message(
            sender,
            stream,
            topic_name,
            notification_string.format(
                user=user_mention,
            ),
            message_type=Message.MessageType.RESOLVE_TOPIC_NOTIFICATION,
            limit_unread_user_ids=unread_user_ids,
            mark_as_read_for_acting_user=True,
            acting_user=user_profile,
        )

    return resolved_topic_message_id, False


def maybe_delete_previous_resolve_topic_notification(
    user_profile: UserProfile, stream: Stream, topic: str
) -> bool:
    assert stream.recipient_id is not None
    last_message = messages_for_topic(stream.realm_id, stream.recipient_id, topic).last()

    if last_message is None:
        return False

    if last_message.type != Message.MessageType.RESOLVE_TOPIC_NOTIFICATION:
        return False

    current_time = timezone_now()
    time_difference = (current_time - last_message.date_sent).total_seconds()

    if time_difference > settings.RESOLVE_TOPIC_UNDO_GRACE_PERIOD_SECONDS:
        return False

    do_delete_messages(stream.realm, [last_message], acting_user=user_profile)
    return True


def send_message_moved_breadcrumbs(
    target_message: Message,
    user_profile: UserProfile,
    message_edit_request: StreamMessageEditRequest,
    old_thread_notification_string: StrPromise | None,
    new_thread_notification_string: StrPromise | None,
    changed_messages_count: int,
) -> None:
    # Since moving content between streams is highly disruptive,
    # it's worth adding a couple tombstone messages showing what
    # happened.
    old_stream = message_edit_request.orig_stream
    sender = get_system_bot(settings.NOTIFICATION_BOT, old_stream.realm_id)

    user_mention = silent_mention_syntax_for_user(user_profile)
    old_topic_name = message_edit_request.orig_topic_name
    new_stream = message_edit_request.target_stream
    new_topic_name = message_edit_request.target_topic_name
    old_topic_link = get_stream_topic_link_syntax(old_stream.id, old_stream.name, old_topic_name)
    new_topic_link = get_stream_topic_link_syntax(new_stream.id, new_stream.name, new_topic_name)
    message = {
        "id": target_message.id,
        "stream_id": new_stream.id,
        "display_recipient": new_stream.name,
        "topic": new_topic_name,
    }
    moved_message_link = stream_message_url(target_message.realm, message)

    if new_thread_notification_string is not None:
        with override_language(new_stream.realm.default_language):
            internal_send_stream_message(
                sender,
                new_stream,
                new_topic_name,
                new_thread_notification_string.format(
                    message_link=moved_message_link,
                    old_location=old_topic_link,
                    user=user_mention,
                    changed_messages_count=changed_messages_count,
                ),
                mark_as_read_for_acting_user=True,
                acting_user=user_profile,
            )

    if old_thread_notification_string is not None:
        with override_language(old_stream.realm.default_language):
            # Send a notification to the old stream that the topic was moved.
            internal_send_stream_message(
                sender,
                old_stream,
                old_topic_name,
                old_thread_notification_string.format(
                    user=user_mention,
                    new_location=new_topic_link,
                    changed_messages_count=changed_messages_count,
                ),
                mark_as_read_for_acting_user=True,
                acting_user=user_profile,
            )


def get_mentions_for_message_updates(message: Message) -> set[int]:
    # We exclude UserMessage.flags.historical rows since those
    # users did not receive the message originally, and thus
    # probably are not relevant for reprocessed alert_words,
    # mentions and similar rendering features.  This may be a
    # decision we change in the future.
    mentioned_user_ids = (
        UserMessage.objects.filter(
            message=message.id,
            flags=~UserMessage.flags.historical,
        )
        .filter(
            Q(
                flags__andnz=UserMessage.flags.mentioned
                | UserMessage.flags.stream_wildcard_mentioned
                | UserMessage.flags.topic_wildcard_mentioned
                | UserMessage.flags.group_mentioned
            )
        )
        .values_list("user_profile_id", flat=True)
    )

    user_ids_having_message_access = event_recipient_ids_for_action_on_messages([message])

    return set(mentioned_user_ids) & user_ids_having_message_access


def update_user_message_flags(
    rendering_result: MessageRenderingResult,
    ums: Iterable[UserMessage],
    topic_participant_user_ids: AbstractSet[int] = set(),
) -> None:
    mentioned_ids = rendering_result.mentions_user_ids
    ids_with_alert_words = rendering_result.user_ids_with_alert_words
    stream_wildcard_mentioned = rendering_result.mentions_stream_wildcard
    changed_ums: set[UserMessage] = set()

    def update_flag(um: UserMessage, should_set: bool, flag: int) -> None:
        if should_set:
            if not (um.flags & flag):
                um.flags |= flag
                changed_ums.add(um)
        else:
            if um.flags & flag:
                um.flags &= ~flag
                changed_ums.add(um)

    for um in ums:
        has_alert_word = um.user_profile_id in ids_with_alert_words
        update_flag(um, has_alert_word, UserMessage.flags.has_alert_word)

        mentioned = um.user_profile_id in mentioned_ids
        update_flag(um, mentioned, UserMessage.flags.mentioned)

        update_flag(um, stream_wildcard_mentioned, UserMessage.flags.stream_wildcard_mentioned)

        topic_wildcard_mentioned = um.user_profile_id in topic_participant_user_ids
        update_flag(um, topic_wildcard_mentioned, UserMessage.flags.topic_wildcard_mentioned)

    for um in changed_ums:
        um.save(update_fields=["flags"])


def do_update_embedded_data(
    user_profile: UserProfile,
    message: Message,
    rendered_content: str | MessageRenderingResult,
    mention_data: MentionData | None = None,
) -> None:
    ums = UserMessage.objects.filter(message=message.id)
    update_fields = ["rendered_content"]
    if isinstance(rendered_content, MessageRenderingResult):
        assert mention_data is not None
        for group_id in rendered_content.mentions_user_group_ids:
            members = mention_data.get_group_members(group_id)
            rendered_content.mentions_user_ids.update(members)
        update_user_message_flags(rendered_content, ums)
        message.rendered_content = rendered_content.rendered_content
        message.rendered_content_version = markdown_version
        update_fields.append("rendered_content_version")
    else:
        message.rendered_content = rendered_content
    message.save(update_fields=update_fields)

    update_message_cache([message])
    event: dict[str, Any] = {
        "type": "update_message",
        "user_id": None,
        "edit_timestamp": datetime_to_timestamp(timezone_now()),
        "message_id": message.id,
        "message_ids": [message.id],
        "content": message.content,
        "rendered_content": message.rendered_content,
        "rendering_only": True,
    }

    users_to_notify = event_recipient_ids_for_action_on_messages([message])
    filtered_ums = [um for um in ums if um.user_profile_id in users_to_notify]

    def user_info(um: UserMessage) -> dict[str, Any]:
        return {
            "id": um.user_profile_id,
            "flags": um.flags_list(),
        }

    send_event_on_commit(user_profile.realm, event, list(map(user_info, filtered_ums)))


def get_visibility_policy_after_merge(
    orig_topic_visibility_policy: int, target_topic_visibility_policy: int
) -> int:
    # This function determines the final visibility_policy after the merge
    # operation, based on the visibility policies of the original and target
    # topics.
    #
    # The algorithm to decide is based on:
    # Whichever of the two policies is most visible is what we keep.
    # The general motivation is to err on the side of showing messages
    # rather than hiding them.
    visibility_policies = {orig_topic_visibility_policy, target_topic_visibility_policy}

    if UserTopic.VisibilityPolicy.FOLLOWED in visibility_policies:
        return UserTopic.VisibilityPolicy.FOLLOWED

    if UserTopic.VisibilityPolicy.UNMUTED in visibility_policies:
        return UserTopic.VisibilityPolicy.UNMUTED

    if UserTopic.VisibilityPolicy.INHERIT in visibility_policies:
        return UserTopic.VisibilityPolicy.INHERIT

    return UserTopic.VisibilityPolicy.MUTED


def update_message_content(
    user_profile: UserProfile,
    target_message: Message,
    content: str,
    rendering_result: MessageRenderingResult,
    prior_mention_user_ids: set[int],
    mention_data: MentionData,
    event: dict[str, Any],
    edit_history_event: EditHistoryEvent,
    stream_topic: StreamTopicTarget | None,
) -> None:
    realm = user_profile.realm

    ums = UserMessage.objects.filter(message=target_message.id)

    # add data from group mentions to mentions_user_ids.
    for group_id in rendering_result.mentions_user_group_ids:
        members = mention_data.get_group_members(group_id)
        rendering_result.mentions_user_ids.update(members)

    # One could imagine checking realm.message_edit_history_visibility_policy here and
    # modifying the events based on that setting, but doing so
    # doesn't really make sense.  We need to send the edit event
    # to clients regardless, and a client already had access to
    # the original/pre-edit content of the message anyway.  That
    # setting must be enforced on the client side, and making a
    # change here simply complicates the logic for clients parsing
    # edit history events.
    edit_history_event["prev_content"] = target_message.content
    edit_history_event["prev_rendered_content"] = target_message.rendered_content
    edit_history_event["prev_rendered_content_version"] = target_message.rendered_content_version

    event["orig_content"] = target_message.content
    event["orig_rendered_content"] = target_message.rendered_content
    event["content"] = content
    event["rendered_content"] = rendering_result.rendered_content
    event["is_me_message"] = Message.is_status_message(content, rendering_result.rendered_content)

    target_message.content = content
    target_message.rendered_content = rendering_result.rendered_content
    target_message.rendered_content_version = markdown_version

    info = get_recipient_info(
        realm_id=realm.id,
        recipient=target_message.recipient,
        sender_id=target_message.sender_id,
        stream_topic=stream_topic,
        possible_topic_wildcard_mention=mention_data.message_has_topic_wildcards(),
        possible_stream_wildcard_mention=mention_data.message_has_stream_wildcards(),
    )

    event["online_push_user_ids"] = list(info.online_push_user_ids)
    event["dm_mention_push_disabled_user_ids"] = list(info.dm_mention_push_disabled_user_ids)
    event["dm_mention_email_disabled_user_ids"] = list(info.dm_mention_email_disabled_user_ids)
    event["stream_push_user_ids"] = list(info.stream_push_user_ids)
    event["stream_email_user_ids"] = list(info.stream_email_user_ids)
    event["followed_topic_push_user_ids"] = list(info.followed_topic_push_user_ids)
    event["followed_topic_email_user_ids"] = list(info.followed_topic_email_user_ids)
    event["muted_sender_user_ids"] = list(info.muted_sender_user_ids)
    event["prior_mention_user_ids"] = list(prior_mention_user_ids)
    event["presence_idle_user_ids"] = filter_presence_idle_user_ids(info.active_user_ids)
    event["all_bot_user_ids"] = list(info.all_bot_user_ids)
    event["push_device_registered_user_ids"] = list(info.push_device_registered_user_ids)
    if rendering_result.mentions_stream_wildcard:
        event["stream_wildcard_mention_user_ids"] = list(info.stream_wildcard_mention_user_ids)
        event["stream_wildcard_mention_in_followed_topic_user_ids"] = list(
            info.stream_wildcard_mention_in_followed_topic_user_ids
        )
    else:
        event["stream_wildcard_mention_user_ids"] = []
        event["stream_wildcard_mention_in_followed_topic_user_ids"] = []

    if rendering_result.mentions_topic_wildcard:
        event["topic_wildcard_mention_user_ids"] = list(info.topic_wildcard_mention_user_ids)
        event["topic_wildcard_mention_in_followed_topic_user_ids"] = list(
            info.topic_wildcard_mention_in_followed_topic_user_ids
        )
        topic_participant_user_ids = info.topic_participant_user_ids
    else:
        event["topic_wildcard_mention_user_ids"] = []
        event["topic_wildcard_mention_in_followed_topic_user_ids"] = []
        topic_participant_user_ids = set()

    update_user_message_flags(rendering_result, ums, topic_participant_user_ids)

    do_update_mobile_push_notification(
        target_message,
        prior_mention_user_ids,
        rendering_result.mentions_user_ids,
        info.stream_push_user_ids,
    )


def apply_automatic_unmute_follow_topics_policy(
    user_profile: UserProfile,
    target_stream: Stream,
    target_topic_name: str,
) -> None:
    if (
        user_profile.automatically_follow_topics_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION
    ):
        bulk_do_set_user_topic_visibility_policy(
            [user_profile],
            target_stream,
            target_topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
    elif (
        user_profile.automatically_unmute_topics_in_muted_streams_policy
        == UserProfile.AUTOMATICALLY_CHANGE_VISIBILITY_POLICY_ON_INITIATION
    ):
        subscription = Subscription.objects.filter(
            recipient=target_stream.recipient,
            user_profile=user_profile,
            active=True,
            is_user_active=True,
        ).first()

        if subscription is not None and subscription.is_muted:
            bulk_do_set_user_topic_visibility_policy(
                [user_profile],
                target_stream,
                target_topic_name,
                visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
            )


# This must be called already in a transaction, with a write lock on
# the target_message.
@transaction.atomic(savepoint=False)
def do_update_message(
    user_profile: UserProfile,
    target_message: Message,
    message_edit_request: StreamMessageEditRequest | DirectMessageEditRequest,
    send_notification_to_old_thread: bool,
    send_notification_to_new_thread: bool,
    rendering_result: MessageRenderingResult | None,
    prior_mention_user_ids: set[int],
    mention_data: MentionData | None = None,
) -> UpdateMessageResult:
    """
    The main function for message editing.  A message edit event can
    modify:
    * the message's content (in which case the caller will have set
      both content and rendered_content in message_edit_request object),
    * the topic, in which case the caller will have set target_topic_name
      field with the new topic name in message_edit_request object
    * or both message's content and the topic
    * or stream and/or topic, in which case the caller will have set
      target_stream and/or target_topic_name to their new values in
      message_edit_request object.

    With topic edits, propagate_mode field in message_edit_request
    determines whether other message also have their topics edited.
    """
    timestamp = timezone_now()
    target_message.last_edit_time = timestamp

    event: dict[str, Any] = {
        "type": "update_message",
        "user_id": user_profile.id,
        "edit_timestamp": datetime_to_timestamp(timestamp),
        "message_id": target_message.id,
        "rendering_only": False,
    }

    edit_history_event: EditHistoryEvent = {
        "user_id": user_profile.id,
        "timestamp": event["edit_timestamp"],
    }

    realm = user_profile.realm
    attachment_reference_change = AttachmentChangeResult(False, [])

    ums = UserMessage.objects.filter(message=target_message.id)

    def user_info(um: UserMessage) -> dict[str, Any]:
        return {
            "id": um.user_profile_id,
            "flags": um.flags_list(),
        }

    if message_edit_request.is_content_edited:
        assert rendering_result is not None

        # mention_data is required if there's a content edit.
        assert mention_data is not None

        if isinstance(message_edit_request, StreamMessageEditRequest):
            # We do not allow changing content and stream together,
            # so we use ID of orig_stream.
            stream_topic: StreamTopicTarget | None = StreamTopicTarget(
                stream_id=message_edit_request.orig_stream.id,
                topic_name=message_edit_request.target_topic_name,
            )
        else:
            stream_topic = None

        update_message_content(
            user_profile,
            target_message,
            message_edit_request.content,
            rendering_result,
            prior_mention_user_ids,
            mention_data,
            event,
            edit_history_event,
            stream_topic,
        )

        # target_message.has_image and target_message.has_link will have been
        # already updated by Markdown rendering in the caller.
        attachment_reference_change = check_attachment_reference_change(
            target_message, rendering_result
        )
        target_message.has_attachment = attachment_reference_change.did_attachment_change

        if isinstance(message_edit_request, DirectMessageEditRequest):
            update_edit_history(target_message, timestamp, edit_history_event)

            # This does message.save(update_fields=[...])
            save_message_for_edit_use_case(message=target_message)

            event["message_ids"] = sorted(update_message_cache([target_message]))
            users_to_be_notified = list(map(user_info, ums))
            send_event_on_commit(user_profile.realm, event, users_to_be_notified)

            changed_messages_count = 1
            return UpdateMessageResult(
                changed_messages_count, attachment_reference_change.detached_attachments
            )

    assert isinstance(message_edit_request, StreamMessageEditRequest)

    stream_being_edited = message_edit_request.orig_stream
    orig_topic_name = message_edit_request.orig_topic_name

    event["stream_name"] = stream_being_edited.name
    event["stream_id"] = stream_being_edited.id

    if message_edit_request.is_message_moved:
        event["propagate_mode"] = message_edit_request.propagate_mode

    users_losing_access = UserProfile.objects.none()
    user_ids_gaining_usermessages: list[int] = []
    if message_edit_request.is_stream_edited:
        new_stream = message_edit_request.target_stream

        edit_history_event["prev_stream"] = stream_being_edited.id
        edit_history_event["stream"] = new_stream.id
        event[ORIG_TOPIC] = orig_topic_name
        assert new_stream.recipient_id is not None
        target_message.recipient_id = new_stream.recipient_id

        event["new_stream_id"] = new_stream.id
        event["propagate_mode"] = message_edit_request.propagate_mode

        # When messages are moved from one stream to another, some
        # users may lose access to those messages, including guest
        # users and users not subscribed to the new stream (if it is a
        # private stream).  For those users, their experience is as
        # though the messages were deleted, and we should send a
        # delete_message event to them instead.

        # We select _all_ current subscriptions, not just active ones,
        # for the current stream, since there may be users who were
        # previously subscribed when the message was sent, but are no
        # longer, who should also lose their UserMessage rows.
        old_stream_all_users = UserProfile.objects.filter(
            id__in=Subscription.objects.filter(
                recipient__type=Recipient.STREAM,
                recipient__type_id=stream_being_edited.id,
            ).values_list("user_profile_id")
        ).only("id")

        new_stream_current_users = UserProfile.objects.filter(
            id__in=get_active_subscriptions_for_stream_id(
                new_stream.id, include_deactivated_users=True
            ).values_list("user_profile_id")
        ).only("id")

        users_losing_usermessages = old_stream_all_users.difference(new_stream_current_users)
        if new_stream.is_public():
            # Only guest users are losing access, if it's moving to a public stream
            users_losing_access = old_stream_all_users.filter(
                role=UserProfile.ROLE_GUEST
            ).difference(new_stream_current_users)
        else:
            # If it's moving to a private stream, all non-subscribed users are losing access
            users_losing_access = users_losing_usermessages

        unmodified_user_messages = ums.exclude(user_profile__in=users_losing_usermessages)

        if not new_stream.is_history_public_to_subscribers():
            # We need to guarantee that every currently-subscribed
            # user of the new stream has a UserMessage row, since
            # being a member when the message is moved is always
            # enough to have access.  We cannot reduce that set by
            # removing either active or all subscribers from the old
            # stream, since neither set guarantees that the user was
            # subscribed when these messages were sent -- in fact, it
            # may not be consistent across the messages.
            #
            # There may be current users of the new stream who already
            # have a usermessage row -- we handle this via `ON
            # CONFLICT DO NOTHING` during insert.
            user_ids_gaining_usermessages = list(
                new_stream_current_users.values_list("id", flat=True)
            )
    else:
        # If we're not moving the topic to another stream, we don't
        # modify the original set of UserMessage objects queried.
        unmodified_user_messages = ums

    if message_edit_request.is_topic_edited:
        topic_name = message_edit_request.target_topic_name
        target_message.set_topic_name(topic_name)

        # These fields have legacy field names.
        event[ORIG_TOPIC] = orig_topic_name
        event[TOPIC_NAME] = topic_name
        event[TOPIC_LINKS] = topic_links(target_message.realm_id, topic_name)
        edit_history_event["prev_topic"] = orig_topic_name
        edit_history_event["topic"] = topic_name

    update_edit_history(target_message, timestamp, edit_history_event)

    # 'target_topic_has_messages', 'target_stream', and 'target_topic'
    # will be used while migrating user_topic records later in this function.
    #
    # We need to calculate 'target_topic_has_messages' here,
    # as we are moving the messages in the next step.
    if message_edit_request.is_message_moved:
        target_stream = message_edit_request.target_stream
        target_topic_name = message_edit_request.target_topic_name

        assert target_stream.recipient_id is not None
        target_topic_has_messages = messages_for_topic(
            realm.id, target_stream.recipient_id, target_topic_name
        ).exists()

    changed_messages = Message.objects.filter(id=target_message.id)
    changed_message_ids = [target_message.id]
    changed_messages_count = 1
    save_changes_for_propagation_mode = lambda: Message.objects.filter(
        id=target_message.id
    ).select_related(*Message.DEFAULT_SELECT_RELATED)
    if message_edit_request.propagate_mode in ["change_later", "change_all"]:
        # Other messages should only get topic/stream fields in their edit history.
        topic_only_edit_history_event: EditHistoryEvent = {
            "user_id": edit_history_event["user_id"],
            "timestamp": edit_history_event["timestamp"],
        }
        if message_edit_request.is_topic_edited:
            topic_only_edit_history_event["prev_topic"] = edit_history_event["prev_topic"]
            topic_only_edit_history_event["topic"] = edit_history_event["topic"]
        if message_edit_request.is_stream_edited:
            topic_only_edit_history_event["prev_stream"] = edit_history_event["prev_stream"]
            topic_only_edit_history_event["stream"] = edit_history_event["stream"]

        later_messages, save_changes_for_propagation_mode = update_messages_for_topic_edit(
            acting_user=user_profile,
            edited_message=target_message,
            message_edit_request=message_edit_request,
            edit_history_event=topic_only_edit_history_event,
            last_edit_time=timestamp,
        )
        changed_messages |= later_messages
        changed_message_ids = list(changed_messages.values_list("id", flat=True))
        changed_messages_count = len(changed_message_ids)

    if message_edit_request.is_stream_edited:
        # The fact that the user didn't have a UserMessage
        # originally means we can infer that the user was not
        # mentioned in the original message (even if mention
        # syntax was present, it would not take effect for a user
        # who was not subscribed). If we were editing the
        # message's content, we would rerender the message and
        # then use the new stream's data to determine whether this
        # is a mention of a subscriber; but as we are not doing
        # so, we choose to preserve the "was this mention syntax
        # an actual mention" decision made during the original
        # rendering for implementation simplicity. As a result,
        # the only flag to consider applying here is read.
        bulk_insert_all_ums(
            user_ids_gaining_usermessages, changed_message_ids, UserMessage.flags.read
        )

        # Delete UserMessage objects for users who will no
        # longer have access to these messages.  Note: This could be
        # very expensive, since it's N guest users x M messages.
        UserMessage.objects.filter(
            user_profile__in=users_losing_usermessages,
            message__in=changed_messages,
        ).delete()

        delete_event: DeleteMessagesEvent = {
            "type": "delete_message",
            "message_ids": changed_message_ids,
            "message_type": "stream",
            "stream_id": stream_being_edited.id,
            "topic": orig_topic_name,
        }
        send_event_on_commit(
            user_profile.realm, delete_event, [user.id for user in users_losing_access]
        )

        # Reset the Attachment.is_*_public caches for all messages
        # moved to another stream with different access permissions.
        if message_edit_request.target_stream.invite_only != stream_being_edited.invite_only:
            Attachment.objects.filter(messages__in=changed_messages.values("id")).update(
                is_realm_public=None,
            )
            ArchivedAttachment.objects.filter(messages__in=changed_messages.values("id")).update(
                is_realm_public=None,
            )

        if message_edit_request.target_stream.is_web_public != stream_being_edited.is_web_public:
            Attachment.objects.filter(messages__in=changed_messages.values("id")).update(
                is_web_public=None,
            )
            ArchivedAttachment.objects.filter(messages__in=changed_messages.values("id")).update(
                is_web_public=None,
            )

    # This does message.save(update_fields=[...])
    save_message_for_edit_use_case(message=target_message)

    # This updates any later messages, if any.  It returns the
    # freshly-fetched-from-the-database changed messages.
    changed_messages = save_changes_for_propagation_mode()

    realm_id = target_message.realm_id
    event["message_ids"] = sorted(update_message_cache(changed_messages, realm_id))

    # The following blocks arranges that users who are subscribed to a
    # stream and can see history from before they subscribed get
    # live-update when old messages are edited (e.g. if the user does
    # a topic edit themself).
    #
    # We still don't send an update event to users who are not
    # subscribed to this stream and don't have a UserMessage row. This
    # means if a non-subscriber is viewing the narrow, they won't get
    # a real-time updates. This is a balance between sending
    # message-edit notifications for every public stream to every user
    # in the organization (too expansive, and also not what we do for
    # newly sent messages anyway) and having magical live-updates
    # where possible.
    users_to_be_notified = list(map(user_info, unmodified_user_messages))
    if stream_being_edited.is_history_public_to_subscribers():
        subscriptions = get_active_subscriptions_for_stream_id(
            message_edit_request.target_stream.id, include_deactivated_users=False
        )

        def exclude_duplicates_from_subscription(
            subs: QuerySet[Subscription],
        ) -> QuerySet[Subscription]:
            # We exclude long-term idle users, since they by
            # definition have no active clients.
            subs = subs.exclude(user_profile__long_term_idle=True)
            # Remove duplicates by excluding the id of users already
            # in users_to_be_notified list.  This is the case where a
            # user both has a UserMessage row and is a current
            # Subscriber
            subs = subs.exclude(
                user_profile_id__in=[um.user_profile_id for um in unmodified_user_messages]
            )

            if message_edit_request.is_stream_edited:
                subs = subs.exclude(user_profile__in=users_losing_access)

            return subs

        old_stream_subs_not_in_new_stream = set()
        if message_edit_request.is_stream_edited:
            # We also need to include users who are not subscribed to new stream
            # but are subscribed to the old stream.
            old_stream_subscriptions = get_active_subscriptions_for_stream_id(
                stream_being_edited.id, include_deactivated_users=False
            )
            old_stream_subscriptions = exclude_duplicates_from_subscription(
                old_stream_subscriptions
            )
            old_stream_subscriber_ids = set(
                old_stream_subscriptions.values_list("user_profile_id", flat=True)
            )
            new_stream_subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))
            old_stream_subs_not_in_new_stream = old_stream_subscriber_ids.difference(
                new_stream_subscriber_ids
            )

        subscriptions = exclude_duplicates_from_subscription(subscriptions)
        if message_edit_request.is_stream_edited:
            # TODO: Guest users don't see the new moved topic
            # unless breadcrumb message for new stream is
            # enabled. Excluding these users from receiving this
            # event helps us avoid a error traceback for our
            # clients. We should figure out a way to inform the
            # guest users of this new topic if sending a 'message'
            # event for these messages is not an option.
            #
            # Don't send this event to guest subs who are not
            # subscribers of the old stream but are subscribed to
            # the new stream; clients will be confused.
            old_stream_current_users = UserProfile.objects.filter(
                id__in=get_active_subscriptions_for_stream_id(
                    stream_being_edited.id, include_deactivated_users=True
                ).values_list("user_profile_id", flat=True)
            ).only("id")
            subscriptions = subscriptions.exclude(
                user_profile__in=new_stream_current_users.filter(
                    role=UserProfile.ROLE_GUEST
                ).difference(old_stream_current_users)
            )

        subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))
        notifiable_ids = subscriber_ids.union(old_stream_subs_not_in_new_stream)
        users_to_be_notified += map(subscriber_info, sorted(notifiable_ids))

    # UserTopic updates and the content of notifications depend on
    # whether we've moved the entire topic, or just part of it. We
    # make that determination here.
    moved_all_visible_messages = False
    if message_edit_request.is_message_moved:
        if message_edit_request.propagate_mode == "change_all":
            moved_all_visible_messages = True
        else:
            # With other propagate modes, if the user in fact moved
            # all messages in the stream, we want to explain it was a
            # full-topic move.
            #
            # For security model reasons, we don't want to allow a
            # user to take any action (e.g. post a message about
            # having not moved the whole topic) that would leak
            # information about older messages they cannot access
            # (e.g. there were earlier inaccessible messages in the
            # topic, in a stream without shared history). The
            # bulk_access_stream_messages_query call below addresses
            # that concern.
            assert stream_being_edited.recipient_id is not None
            unmoved_messages = messages_for_topic(
                realm.id,
                stream_being_edited.recipient_id,
                orig_topic_name,
            )
            visible_unmoved_messages = bulk_access_stream_messages_query(
                user_profile, unmoved_messages, stream_being_edited
            )
            moved_all_visible_messages = not visible_unmoved_messages.exists()

    # Migrate 'topic with visibility_policy' configuration in the following
    # circumstances:
    #
    # * If propagate_mode is change_all, do so unconditionally.
    #
    # * If propagate_mode is change_later or change_one, do so when
    #   the acting user has moved the entire topic (as visible to them).
    #
    # This rule corresponds to checking moved_all_visible_messages.
    if moved_all_visible_messages:
        stream_inaccessible_to_user_profiles: list[UserProfile] = []
        orig_topic_user_profile_to_visibility_policy: dict[UserProfile, int] = {}
        target_topic_user_profile_to_visibility_policy: dict[UserProfile, int] = {}
        user_ids_losing_access = {user.id for user in users_losing_access}
        for user_topic in get_users_with_user_topic_visibility_policy(
            stream_being_edited.id, orig_topic_name
        ):
            if (
                message_edit_request.is_stream_edited
                and user_topic.user_profile_id in user_ids_losing_access
            ):
                stream_inaccessible_to_user_profiles.append(user_topic.user_profile)
            else:
                orig_topic_user_profile_to_visibility_policy[user_topic.user_profile] = (
                    user_topic.visibility_policy
                )

        for user_topic in get_users_with_user_topic_visibility_policy(
            target_stream.id, target_topic_name
        ):
            target_topic_user_profile_to_visibility_policy[user_topic.user_profile] = (
                user_topic.visibility_policy
            )

        # User profiles having any of the visibility policies set for either the original or target topic.
        user_profiles_having_visibility_policy: set[UserProfile] = set(
            itertools.chain(
                orig_topic_user_profile_to_visibility_policy.keys(),
                target_topic_user_profile_to_visibility_policy.keys(),
            )
        )

        user_profiles_for_visibility_policy_pair: dict[tuple[int, int], list[UserProfile]] = (
            defaultdict(list)
        )
        for user_profile_with_policy in user_profiles_having_visibility_policy:
            if user_profile_with_policy not in target_topic_user_profile_to_visibility_policy:
                target_topic_user_profile_to_visibility_policy[user_profile_with_policy] = (
                    UserTopic.VisibilityPolicy.INHERIT
                )
            elif user_profile_with_policy not in orig_topic_user_profile_to_visibility_policy:
                orig_topic_user_profile_to_visibility_policy[user_profile_with_policy] = (
                    UserTopic.VisibilityPolicy.INHERIT
                )

            orig_topic_visibility_policy = orig_topic_user_profile_to_visibility_policy[
                user_profile_with_policy
            ]
            target_topic_visibility_policy = target_topic_user_profile_to_visibility_policy[
                user_profile_with_policy
            ]
            user_profiles_for_visibility_policy_pair[
                (orig_topic_visibility_policy, target_topic_visibility_policy)
            ].append(user_profile_with_policy)

        # If the messages are being moved to a stream the user
        # cannot access, then we treat this as the
        # messages/topic being deleted for this user. This is
        # important for security reasons; we don't want to
        # give users a UserTopic row in a stream they cannot
        # access. Remove the user topic rows for such users.
        bulk_do_set_user_topic_visibility_policy(
            stream_inaccessible_to_user_profiles,
            stream_being_edited,
            orig_topic_name,
            visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
        )

        # If the messages are being moved to a stream the user _can_
        # access, we move the user topic records, by removing the old
        # topic visibility_policy and creating a new one.
        #
        # Algorithm used for the 'merge userTopic states' case:
        # Using the 'user_profiles_for_visibility_policy_pair' dictionary,
        # we have 'orig_topic_visibility_policy', 'target_topic_visibility_policy',
        # and a list of 'user_profiles' having the mentioned visibility policies.
        #
        # For every 'orig_topic_visibility_policy and target_topic_visibility_policy' pair,
        # we determine the final visibility_policy that should be after the merge.
        # Update the visibility_policy for the concerned set of user_profiles.
        for (
            visibility_policy_pair,
            user_profiles,
        ) in user_profiles_for_visibility_policy_pair.items():
            orig_topic_visibility_policy, target_topic_visibility_policy = visibility_policy_pair

            if orig_topic_visibility_policy != UserTopic.VisibilityPolicy.INHERIT:
                bulk_do_set_user_topic_visibility_policy(
                    user_profiles,
                    stream_being_edited,
                    orig_topic_name,
                    visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
                    # bulk_do_set_user_topic_visibility_policy with visibility_policy
                    # set to 'new_visibility_policy' will send an updated muted topic
                    # event, which contains the full set of muted
                    # topics, just after this.
                    skip_muted_topics_event=True,
                )

            new_visibility_policy = orig_topic_visibility_policy

            if target_topic_has_messages:
                # Here, we handle the complex case when target_topic already has
                # some messages. We determine the resultant visibility_policy
                # based on the visibility_policy of the orig_topic + target_topic.
                # Finally, bulk_update the user_topic rows with the new visibility_policy.
                new_visibility_policy = get_visibility_policy_after_merge(
                    orig_topic_visibility_policy, target_topic_visibility_policy
                )
                if new_visibility_policy == target_topic_visibility_policy:
                    continue
                bulk_do_set_user_topic_visibility_policy(
                    user_profiles,
                    target_stream,
                    target_topic_name,
                    visibility_policy=new_visibility_policy,
                )
            else:
                # This corresponds to the case when messages are moved
                # to a stream-topic pair that didn't exist. There can
                # still be UserTopic rows for the stream-topic pair
                # that didn't exist if the messages in that topic had
                # been deleted.
                if new_visibility_policy == target_topic_visibility_policy:
                    # This avoids unnecessary db operations and INFO logs.
                    continue
                bulk_do_set_user_topic_visibility_policy(
                    user_profiles,
                    target_stream,
                    target_topic_name,
                    visibility_policy=new_visibility_policy,
                )

    elif message_edit_request.is_stream_edited or message_edit_request.is_topic_edited:
        sender = target_message.sender

        target_stream = message_edit_request.target_stream
        target_topic = message_edit_request.target_topic_name

        assert target_stream.recipient_id is not None

        messages_in_target_topic = messages_for_topic(
            realm.id, target_stream.recipient_id, target_topic
        ).exclude(id__in=[*changed_message_ids])

        # All behavior in channels with protected history depends on
        # the permissions of users who might glean information about
        # whether the topic previously existed. So we need to look at
        # whether this message is becoming the first message in the
        # target topic, as seen by the user who we might change topic
        # visibility policy for in this code path.
        first_message_in_target_topic = bulk_access_stream_messages_query(
            sender, messages_in_target_topic, target_stream
        ).first()

        is_target_message_first = False
        # the target_message would be the first message in the moved topic
        # either if the moved topic doesn't have any messages, or if the
        # target_message is sent before the first message in the moved
        # topic.
        if (
            first_message_in_target_topic is None
            or target_message.id < first_message_in_target_topic.id
        ):
            is_target_message_first = True

        if not sender.is_bot and sender not in users_losing_access and is_target_message_first:
            apply_automatic_unmute_follow_topics_policy(sender, target_stream, target_topic)

    send_event_on_commit(user_profile.realm, event, users_to_be_notified)

    resolved_topic_message_id = None
    # We calculate the users for which the resolved-topic notification
    # should be marked as unread using the topic visibility policy and
    # the `resolved_topic_notice_auto_read_policy` user setting.
    users_following_original_topic = None
    if moved_all_visible_messages:
        users_following_original_topic = {
            user
            for user, visibility_policy in orig_topic_user_profile_to_visibility_policy.items()
            if visibility_policy == UserTopic.VisibilityPolicy.FOLLOWED
        }

    if (
        message_edit_request.is_topic_edited
        and not message_edit_request.is_content_edited
        and not message_edit_request.is_stream_edited
    ):
        resolved_topic_message_id, _resolved_topic_message_deleted = (
            maybe_send_resolve_topic_notifications(
                user_profile=user_profile,
                message_edit_request=message_edit_request,
                users_following_topic=users_following_original_topic,
            )
        )

    if message_edit_request.is_message_moved:
        # Notify users that the topic was moved.
        old_thread_notification_string = None
        if send_notification_to_old_thread:
            if moved_all_visible_messages:
                old_thread_notification_string = gettext_lazy(
                    "This topic was moved to {new_location} by {user}."
                )
            elif changed_messages_count == 1:
                old_thread_notification_string = gettext_lazy(
                    "A message was moved from this topic to {new_location} by {user}."
                )
            else:
                old_thread_notification_string = gettext_lazy(
                    "{changed_messages_count} messages were moved from this topic to {new_location} by {user}."
                )

        # The new thread notification code path is a bit subtle. We
        # don't want every resolve-topic action to also annoyingly
        # send an extra notification that the topic was moved!
        new_thread_notification_string = None
        if send_notification_to_new_thread and (
            # The stream changed -> eligible to notify.
            message_edit_request.is_stream_edited
            # The topic changed -> eligible to notify.
            or (
                message_edit_request.is_topic_edited
                and not message_edit_request.topic_resolved
                and not message_edit_request.topic_unresolved
            )
        ):
            stream_for_new_topic = message_edit_request.target_stream
            assert stream_for_new_topic.recipient_id is not None

            new_topic_name = message_edit_request.target_topic_name

            # We calculate whether the user moved the entire topic
            # using that user's own permissions, which is important to
            # avoid leaking information about whether there are
            # messages in the destination topic's deeper history that
            # the acting user does not have permission to access.
            preexisting_topic_messages = messages_for_topic(
                realm.id, stream_for_new_topic.recipient_id, new_topic_name
            ).exclude(id__in=[*changed_message_ids, resolved_topic_message_id])

            visible_preexisting_messages = bulk_access_stream_messages_query(
                user_profile, preexisting_topic_messages, stream_for_new_topic
            )

            no_visible_preexisting_messages = not visible_preexisting_messages.exists()

            if no_visible_preexisting_messages and moved_all_visible_messages:
                new_thread_notification_string = gettext_lazy(
                    "This topic was moved here from {old_location} by {user}."
                )
            else:
                if changed_messages_count == 1:
                    new_thread_notification_string = gettext_lazy(
                        "[A message]({message_link}) was moved here from {old_location} by {user}."
                    )
                else:
                    new_thread_notification_string = gettext_lazy(
                        "{changed_messages_count} messages were moved here from {old_location} by {user}."
                    )

        send_message_moved_breadcrumbs(
            target_message,
            user_profile,
            message_edit_request,
            old_thread_notification_string,
            new_thread_notification_string,
            changed_messages_count,
        )

    return UpdateMessageResult(
        changed_messages_count, attachment_reference_change.detached_attachments
    )


def check_time_limit_for_change_all_propagate_mode(
    message: Message,
    user_profile: UserProfile,
    topic_name: str | None = None,
    stream_id: int | None = None,
) -> None:
    realm = user_profile.realm
    message_move_limit_buffer = 20

    topic_edit_deadline_seconds = None
    if topic_name is not None and realm.move_messages_within_stream_limit_seconds is not None:
        # We set topic_edit_deadline_seconds only if topic is actually
        # changed and there is some time limit to edit topic.
        topic_edit_deadline_seconds = (
            realm.move_messages_within_stream_limit_seconds + message_move_limit_buffer
        )

    stream_edit_deadline_seconds = None
    if stream_id is not None and realm.move_messages_between_streams_limit_seconds is not None:
        # We set stream_edit_deadline_seconds only if stream is
        # actually changed and there is some time limit to edit
        # stream.
        stream_edit_deadline_seconds = (
            realm.move_messages_between_streams_limit_seconds + message_move_limit_buffer
        )

    # Calculate whichever of the applicable topic and stream moving
    # limits is stricter, and use that.
    if topic_edit_deadline_seconds is not None and stream_edit_deadline_seconds is not None:
        # When both stream and topic are changed, we consider the
        # minimum of the two limits to make sure that we raise the
        # error even when user cannot change one of topic or stream.
        message_move_deadline_seconds = min(
            topic_edit_deadline_seconds, stream_edit_deadline_seconds
        )
    elif topic_edit_deadline_seconds is not None:
        message_move_deadline_seconds = topic_edit_deadline_seconds
    elif stream_edit_deadline_seconds is not None:
        message_move_deadline_seconds = stream_edit_deadline_seconds
    else:
        # There is no applicable time limit for this move request, so
        # approve it.
        return

    stream = get_stream_by_id_in_realm(message.recipient.type_id, realm)

    if not can_access_stream_history(user_profile, stream):
        # If the user doesn't have full access to the stream's
        # history, check if the user can move the entire portion that
        # they do have access to.
        accessible_messages_in_topic = UserMessage.objects.filter(
            user_profile=user_profile,
            message__recipient_id=message.recipient_id,
            message__subject__iexact=message.topic_name(),
            message__is_channel_message=True,
        ).values_list("message_id", flat=True)
        messages_allowed_to_move: list[int] = list(
            Message.objects.filter(
                # Uses index: zerver_message_pkey
                id__in=accessible_messages_in_topic,
                date_sent__gt=timezone_now() - timedelta(seconds=message_move_deadline_seconds),
            )
            .order_by("date_sent")
            .values_list("id", flat=True)
        )
        total_messages_requested_to_move = len(accessible_messages_in_topic)
    else:
        all_messages_in_topic = (
            messages_for_topic(message.realm_id, message.recipient_id, message.topic_name())
            .order_by("id")
            .values_list("id", "date_sent")
        )
        oldest_allowed_message_date = timezone_now() - timedelta(
            seconds=message_move_deadline_seconds
        )
        messages_allowed_to_move = [
            message[0]
            for message in all_messages_in_topic
            if message[1] > oldest_allowed_message_date
        ]
        total_messages_requested_to_move = len(all_messages_in_topic)

    if total_messages_requested_to_move == len(messages_allowed_to_move):
        # We return if all messages are allowed to move.
        return

    raise MessageMoveError(
        first_message_id_allowed_to_move=messages_allowed_to_move[0],
        total_messages_in_topic=total_messages_requested_to_move,
        total_messages_allowed_to_move=len(messages_allowed_to_move),
    )


def build_message_edit_request(
    *,
    message: Message,
    user_profile: UserProfile,
    propagate_mode: str,
    stream_id: int | None = None,
    topic_name: str | None = None,
    content: str | None = None,
) -> StreamMessageEditRequest | DirectMessageEditRequest:
    is_content_edited = False
    new_content = message.content
    if content is not None:
        is_content_edited = True
        if content.rstrip() == "":
            content = "(deleted)"
        new_content = normalize_body(content)

    if not message.is_channel_message:
        # We have already validated that at least one of content, topic, or stream
        # must be modified, and for DMs, only the content can be edited.
        return DirectMessageEditRequest(
            content=new_content,
            orig_content=message.content,
            is_content_edited=True,
        )

    is_topic_edited = False
    topic_resolved = False
    topic_unresolved = False
    old_topic_name = message.topic_name()
    target_topic_name = old_topic_name

    if topic_name is not None:
        is_topic_edited = True
        pre_truncation_target_topic_name = topic_name
        target_topic_name = truncate_topic(topic_name)

        resolved_prefix_len = len(RESOLVED_TOPIC_PREFIX)
        topic_resolved = (
            target_topic_name.startswith(RESOLVED_TOPIC_PREFIX)
            and not old_topic_name.startswith(RESOLVED_TOPIC_PREFIX)
            and pre_truncation_target_topic_name[resolved_prefix_len:] == old_topic_name
        )
        topic_unresolved = (
            old_topic_name.startswith(RESOLVED_TOPIC_PREFIX)
            and not target_topic_name.startswith(RESOLVED_TOPIC_PREFIX)
            and old_topic_name.lstrip(RESOLVED_TOPIC_PREFIX) == target_topic_name
        )

    orig_stream_id = message.recipient.type_id
    # We call get_stream_by_id_for_sending_message instead of
    # get_stream_by_id_in_realm here so that "can_create_topic_group" is
    # fetched using select_related and we can save a couple of DB queries.
    orig_stream = get_stream_by_id_for_sending_message(orig_stream_id, message.realm)

    is_stream_edited = False
    target_stream = orig_stream
    if stream_id is not None:
        target_stream = access_stream_by_id_for_message(user_profile, stream_id)[0]
        is_stream_edited = True

    topics_policy = get_stream_topics_policy(message.realm, target_stream)
    empty_topic_display_name = get_topic_display_name("", user_profile.default_language)
    target_topic_empty = target_topic_name in ("(no topic)", "")
    if (
        target_topic_empty
        and (is_topic_edited or is_stream_edited)
        and topics_policy == StreamTopicsPolicyEnum.disable_empty_topic.value
    ):
        raise MessagesNotAllowedInEmptyTopicError(empty_topic_display_name)

    if topics_policy == StreamTopicsPolicyEnum.empty_topic_only.value and not target_topic_empty:
        raise TopicsNotAllowedError(empty_topic_display_name)

    return StreamMessageEditRequest(
        is_content_edited=is_content_edited,
        content=new_content,
        is_topic_edited=is_topic_edited,
        target_topic_name=target_topic_name,
        is_stream_edited=is_stream_edited,
        topic_resolved=topic_resolved,
        topic_unresolved=topic_unresolved,
        orig_content=message.content,
        orig_topic_name=old_topic_name,
        orig_stream=orig_stream,
        propagate_mode=propagate_mode,
        target_stream=target_stream,
        is_message_moved=is_stream_edited or is_topic_edited,
    )


@transaction.atomic(durable=True)
def check_update_message(
    user_profile: UserProfile,
    message_id: int,
    stream_id: int | None = None,
    topic_name: str | None = None,
    propagate_mode: str = "change_one",
    send_notification_to_old_thread: bool = True,
    send_notification_to_new_thread: bool = True,
    content: str | None = None,
    prev_content_sha256: str | None = None,
) -> UpdateMessageResult:
    """This will update a message given the message id and user profile.
    It checks whether the user profile has the permission to edit the message
    and raises a JsonableError if otherwise.
    It returns the number changed.
    """
    message = access_message(user_profile, message_id, lock_message=True, is_modifying_message=True)

    # If there is a change to the content, check that it hasn't been too long
    # Allow an extra 20 seconds since we potentially allow editing 15 seconds
    # past the limit, and in case there are network issues, etc. The 15 comes
    # from (min_seconds_to_edit + seconds_left_buffer) in message_edit.ts; if
    # you change this value also change those two parameters in message_edit.ts.
    edit_limit_buffer = 20
    if content is not None:
        validate_user_can_edit_message(user_profile, message, edit_limit_buffer)

    if topic_name is not None:
        # The zerver/views/message_edit.py call point already strips this
        # via OptionalTopic; so we can delete this line if we arrange a
        # contract where future callers in the embedded bots system strip
        # use OptionalTopic as well (or otherwise are guaranteed to strip input).
        topic_name = topic_name.strip()
        topic_name = maybe_rename_general_chat_to_empty_topic(topic_name)
        if topic_name == message.topic_name():
            topic_name = None

    validate_message_edit_payload(
        message, stream_id, topic_name, propagate_mode, content, prev_content_sha256
    )

    message_edit_request = build_message_edit_request(
        message=message,
        user_profile=user_profile,
        propagate_mode=propagate_mode,
        stream_id=stream_id,
        topic_name=topic_name,
        content=content,
    )

    if (
        isinstance(message_edit_request, StreamMessageEditRequest)
        and message_edit_request.is_topic_edited
    ):
        if message_edit_request.topic_resolved or message_edit_request.topic_unresolved:
            if not can_resolve_topics(
                user_profile, message_edit_request.orig_stream, message_edit_request.target_stream
            ):
                raise JsonableError(
                    _("You don't have permission to resolve topics in this channel.")
                )
        else:
            if not can_edit_topic(
                user_profile, message_edit_request.orig_stream, message_edit_request.target_stream
            ):
                raise JsonableError(_("You don't have permission to edit this message"))

            # If there is a change to the topic, check that the user is allowed to
            # edit it and that it has not been too long. If user is not admin or moderator,
            # and the time limit for editing topics is passed, raise an error.
            if (
                user_profile.realm.move_messages_within_stream_limit_seconds is not None
                and not user_profile.is_moderator
            ):
                deadline_seconds = (
                    user_profile.realm.move_messages_within_stream_limit_seconds + edit_limit_buffer
                )
                if (timezone_now() - message.date_sent) > timedelta(seconds=deadline_seconds):
                    raise JsonableError(
                        _("The time limit for editing this message's topic has passed.")
                    )

    rendering_result = None
    links_for_embed: set[str] = set()
    prior_mention_user_ids: set[int] = set()
    mention_data: MentionData | None = None
    if message_edit_request.is_content_edited:
        mention_backend = MentionBackend(user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=message_edit_request.content,
            message_sender=message.sender,
        )
        prior_mention_user_ids = get_mentions_for_message_updates(message)

        # We render the message using the current user's realm; since
        # the cross-realm bots never edit messages, this should be
        # always correct.
        # Note: If rendering fails, the called code will raise a JsonableError.
        rendering_result = render_incoming_message(
            message,
            message_edit_request.content,
            user_profile.realm,
            mention_data=mention_data,
        )
        links_for_embed |= rendering_result.links_for_preview

        if message.is_channel_message and rendering_result.mentions_stream_wildcard:
            stream = access_stream_by_id(user_profile, message.recipient.type_id)[0]
            if not stream_wildcard_mention_allowed(message.sender, stream, message.realm):
                raise StreamWildcardMentionNotAllowedError

        if message.is_channel_message and rendering_result.mentions_topic_wildcard:
            topic_participant_count = len(
                participants_for_topic(message.realm.id, message.recipient.id, message.topic_name())
            )
            if not topic_wildcard_mention_allowed(
                message.sender, topic_participant_count, message.realm
            ):
                raise TopicWildcardMentionNotAllowedError

        if rendering_result.mentions_user_group_ids:
            mentioned_group_ids = list(rendering_result.mentions_user_group_ids)
            check_user_group_mention_allowed(user_profile, mentioned_group_ids)

    if isinstance(message_edit_request, StreamMessageEditRequest):
        if message_edit_request.is_stream_edited:
            assert message.is_channel_message
            if not can_move_messages_out_of_channel(user_profile, message_edit_request.orig_stream):
                raise JsonableError(_("You don't have permission to move this message"))

            check_stream_access_based_on_can_send_message_group(
                user_profile, message_edit_request.target_stream
            )

            if (
                user_profile.realm.move_messages_between_streams_limit_seconds is not None
                and not user_profile.is_moderator
            ):
                deadline_seconds = (
                    user_profile.realm.move_messages_between_streams_limit_seconds
                    + edit_limit_buffer
                )
                if (timezone_now() - message.date_sent) > timedelta(seconds=deadline_seconds):
                    raise JsonableError(
                        _("The time limit for editing this message's channel has passed")
                    )

        if (
            propagate_mode == "change_all"
            and not user_profile.is_moderator
            and message_edit_request.is_message_moved
            and not message_edit_request.topic_resolved
            and not message_edit_request.topic_unresolved
        ):
            check_time_limit_for_change_all_propagate_mode(
                message, user_profile, topic_name, stream_id
            )

        if (
            message_edit_request.is_message_moved
            and not message_edit_request.topic_resolved
            and not message_edit_request.topic_unresolved
        ):
            check_for_can_create_topic_group_violation(
                user_profile,
                message_edit_request.target_stream,
                message_edit_request.target_topic_name,
            )

    updated_message_result = do_update_message(
        user_profile,
        message,
        message_edit_request,
        send_notification_to_old_thread,
        send_notification_to_new_thread,
        rendering_result,
        prior_mention_user_ids,
        mention_data,
    )

    if links_for_embed:
        event_data = {
            "message_id": message.id,
            "message_content": message.content,
            # The choice of `user_profile.realm_id` rather than
            # `sender.realm_id` must match the decision made in the
            # `render_incoming_message` call earlier in this function.
            "message_realm_id": user_profile.realm_id,
            "urls": list(links_for_embed),
        }
        queue_event_on_commit("embed_links", event_data)

    # Update stream active status after we have successfully moved the
    # messages. We only update the new stream here and let the daily
    # cron job handle updating the old stream. User might still want
    # to interact with the old stream and keeping it placed in the same
    # position in the left sidebar might help user.
    if (
        isinstance(message_edit_request, StreamMessageEditRequest)
        and message_edit_request.is_stream_edited
        and not message_edit_request.target_stream.is_recently_active
    ):
        date_days_ago = timezone_now() - timedelta(days=Stream.LAST_ACTIVITY_DAYS_BEFORE_FOR_ACTIVE)
        new_stream = message_edit_request.target_stream
        is_stream_active = Message.objects.filter(
            date_sent__gte=date_days_ago,
            recipient__type=Recipient.STREAM,
            realm=user_profile.realm,
            recipient__type_id=new_stream.id,
        ).exists()

        if is_stream_active != new_stream.is_recently_active:
            new_stream.is_recently_active = is_stream_active
            new_stream.save(update_fields=["is_recently_active"])
            notify_stream_is_recently_active_update(new_stream, is_stream_active)

    return updated_message_result


@transaction.atomic(durable=True)
def re_thumbnail(
    message_class: type[Message] | type[ArchivedMessage], message_id: int, enqueue: bool
) -> None:
    message = message_class.objects.select_for_update().get(id=message_id)
    assert message.rendered_content is not None
    image_metadata = manifest_and_get_user_upload_previews(
        message.realm_id,
        message.rendered_content,
        enqueue=enqueue,
        lock=True,
    ).image_metadata

    new_content, _ = rewrite_thumbnailed_images(
        message.rendered_content,
        image_metadata,
    )

    if new_content is None:
        pass
    elif isinstance(message, Message):
        do_update_embedded_data(message.sender, message, new_content)
    else:
        assert isinstance(message, ArchivedMessage)
        message.rendered_content = new_content
        message.save(update_fields=["rendered_content"])
