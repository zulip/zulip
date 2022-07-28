import datetime
from typing import Any, Dict, Iterable, List, Optional, Set

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.utils.translation import override as override_language
from django_stubs_ext import StrPromise

from zerver.actions.message_delete import DeleteMessagesEvent
from zerver.actions.message_flags import do_update_mobile_push_notification
from zerver.actions.message_send import (
    filter_presence_idle_user_ids,
    get_recipient_info,
    internal_send_stream_message,
    render_incoming_message,
)
from zerver.actions.uploads import check_attachment_reference_change
from zerver.actions.user_topics import do_mute_topic, do_unmute_topic
from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import MessageRenderingResult, topic_links
from zerver.lib.markdown import version as markdown_version
from zerver.lib.mention import MentionBackend, MentionData, silent_mention_syntax_for_user
from zerver.lib.message import (
    access_message,
    bulk_access_messages,
    normalize_body,
    truncate_topic,
    update_to_dict_cache,
    wildcard_mention_allowed,
)
from zerver.lib.queue import queue_json_publish
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.streams import access_stream_by_id, check_stream_access_based_on_stream_post_policy
from zerver.lib.string_validation import check_stream_topic
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import (
    ORIG_TOPIC,
    RESOLVED_TOPIC_PREFIX,
    TOPIC_LINKS,
    TOPIC_NAME,
    messages_for_topic,
    save_message_for_edit_use_case,
    update_edit_history,
    update_messages_for_topic_edit,
)
from zerver.lib.types import EditHistoryEvent
from zerver.lib.user_message import UserMessageLite, bulk_insert_ums
from zerver.lib.user_topics import get_users_muting_topic
from zerver.lib.widget import is_widget_message
from zerver.models import (
    ArchivedAttachment,
    Attachment,
    Message,
    Reaction,
    Realm,
    Stream,
    UserMessage,
    UserProfile,
    get_stream_by_id_in_realm,
    get_system_bot,
)
from zerver.tornado.django_api import send_event


def subscriber_info(user_id: int) -> Dict[str, Any]:
    return {"id": user_id, "flags": ["read"]}


def validate_message_edit_payload(
    message: Message,
    stream_id: Optional[int],
    topic_name: Optional[str],
    propagate_mode: Optional[str],
    content: Optional[str],
) -> None:
    """
    Checks that the data sent is well-formed. Does not handle editability, permissions etc.
    """
    if topic_name is None and content is None and stream_id is None:
        raise JsonableError(_("Nothing to change"))

    if not message.is_stream_message():
        if stream_id is not None:
            raise JsonableError(_("Private messages cannot be moved to streams."))
        if topic_name is not None:
            raise JsonableError(_("Private messages cannot have topics."))

    if propagate_mode != "change_one" and topic_name is None and stream_id is None:
        raise JsonableError(_("Invalid propagate_mode without topic edit"))

    if topic_name is not None:
        check_stream_topic(topic_name)

    if stream_id is not None and content is not None:
        raise JsonableError(_("Cannot change message content while changing stream"))

    # Right now, we prevent users from editing widgets.
    if content is not None and is_widget_message(message):
        raise JsonableError(_("Widgets cannot be edited."))


def can_edit_topic(
    user_profile: UserProfile,
    is_no_topic_msg: bool,
) -> bool:
    # We allow anyone to edit (no topic) messages to help tend them.
    if is_no_topic_msg:
        return True

    # The can_edit_topic_of_any_message helper returns whether the user can edit the topic
    # or not based on edit_topic_policy setting and the user's role.
    if user_profile.can_edit_topic_of_any_message():
        return True

    return False


def maybe_send_resolve_topic_notifications(
    *,
    user_profile: UserProfile,
    stream: Stream,
    old_topic: str,
    new_topic: str,
    changed_messages: List[Message],
) -> bool:
    """Returns True if resolve topic notifications were in fact sent."""
    # Note that topics will have already been stripped in check_update_message.
    #
    # This logic is designed to treat removing a weird "✔ ✔✔ "
    # prefix as unresolving the topic.
    topic_resolved: bool = new_topic.startswith(RESOLVED_TOPIC_PREFIX) and not old_topic.startswith(
        RESOLVED_TOPIC_PREFIX
    )
    topic_unresolved: bool = old_topic.startswith(
        RESOLVED_TOPIC_PREFIX
    ) and not new_topic.startswith(RESOLVED_TOPIC_PREFIX)

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
        # administrator can the messages in between. We consider this
        # to be a fundamental risk of irresponsible message deletion,
        # not a bug with the "resolve topics" feature.
        return False

    # Compute the users who either sent or reacted to messages that
    # were moved via the "resolve topic' action. Only those users
    # should be eligible for this message being managed as unread.
    affected_participant_ids = {message.sender_id for message in changed_messages} | set(
        Reaction.objects.filter(message__in=changed_messages).values_list(
            "user_profile_id", flat=True
        )
    )
    sender = get_system_bot(settings.NOTIFICATION_BOT, user_profile.realm_id)
    user_mention = silent_mention_syntax_for_user(user_profile)
    with override_language(stream.realm.default_language):
        if topic_resolved:
            notification_string = _("{user} has marked this topic as resolved.")
        elif topic_unresolved:
            notification_string = _("{user} has marked this topic as unresolved.")

        internal_send_stream_message(
            sender,
            stream,
            new_topic,
            notification_string.format(
                user=user_mention,
            ),
            limit_unread_user_ids=affected_participant_ids,
        )

    return True


def send_message_moved_breadcrumbs(
    user_profile: UserProfile,
    old_stream: Stream,
    old_topic: str,
    old_thread_notification_string: Optional[StrPromise],
    new_stream: Stream,
    new_topic: Optional[str],
    new_thread_notification_string: Optional[StrPromise],
    changed_messages_count: int,
) -> None:
    # Since moving content between streams is highly disruptive,
    # it's worth adding a couple tombstone messages showing what
    # happened.
    sender = get_system_bot(settings.NOTIFICATION_BOT, old_stream.realm_id)

    if new_topic is None:
        new_topic = old_topic

    user_mention = silent_mention_syntax_for_user(user_profile)
    old_topic_link = f"#**{old_stream.name}>{old_topic}**"
    new_topic_link = f"#**{new_stream.name}>{new_topic}**"

    if new_thread_notification_string is not None:
        with override_language(new_stream.realm.default_language):
            internal_send_stream_message(
                sender,
                new_stream,
                new_topic,
                new_thread_notification_string.format(
                    old_location=old_topic_link,
                    user=user_mention,
                    changed_messages_count=changed_messages_count,
                ),
            )

    if old_thread_notification_string is not None:
        with override_language(old_stream.realm.default_language):
            # Send a notification to the old stream that the topic was moved.
            internal_send_stream_message(
                sender,
                old_stream,
                old_topic,
                old_thread_notification_string.format(
                    user=user_mention,
                    new_location=new_topic_link,
                    changed_messages_count=changed_messages_count,
                ),
            )


def get_mentions_for_message_updates(message_id: int) -> Set[int]:
    # We exclude UserMessage.flags.historical rows since those
    # users did not receive the message originally, and thus
    # probably are not relevant for reprocessed alert_words,
    # mentions and similar rendering features.  This may be a
    # decision we change in the future.
    mentioned_user_ids = (
        UserMessage.objects.filter(
            message=message_id,
            flags=~UserMessage.flags.historical,
        )
        .filter(
            Q(flags__andnz=(UserMessage.flags.mentioned | UserMessage.flags.wildcard_mentioned))
        )
        .values_list("user_profile_id", flat=True)
    )
    return set(mentioned_user_ids)


def update_user_message_flags(
    rendering_result: MessageRenderingResult, ums: Iterable[UserMessage]
) -> None:
    wildcard = rendering_result.mentions_wildcard
    mentioned_ids = rendering_result.mentions_user_ids
    ids_with_alert_words = rendering_result.user_ids_with_alert_words
    changed_ums: Set[UserMessage] = set()

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

        update_flag(um, wildcard, UserMessage.flags.wildcard_mentioned)

    for um in changed_ums:
        um.save(update_fields=["flags"])


def do_update_embedded_data(
    user_profile: UserProfile,
    message: Message,
    content: Optional[str],
    rendering_result: MessageRenderingResult,
) -> None:
    timestamp = timezone_now()
    event: Dict[str, Any] = {
        "type": "update_message",
        "user_id": None,
        "edit_timestamp": datetime_to_timestamp(timestamp),
        "message_id": message.id,
        "rendering_only": True,
    }
    changed_messages = [message]
    rendered_content: Optional[str] = None

    ums = UserMessage.objects.filter(message=message.id)

    if content is not None:
        update_user_message_flags(rendering_result, ums)
        rendered_content = rendering_result.rendered_content
        message.rendered_content = rendered_content
        message.rendered_content_version = markdown_version
        event["content"] = content
        event["rendered_content"] = rendered_content

    message.save(update_fields=["content", "rendered_content"])

    event["message_ids"] = update_to_dict_cache(changed_messages)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            "id": um.user_profile_id,
            "flags": um.flags_list(),
        }

    send_event(user_profile.realm, event, list(map(user_info, ums)))


# We use transaction.atomic to support select_for_update in the attachment codepath.
@transaction.atomic(savepoint=False)
def do_update_message(
    user_profile: UserProfile,
    target_message: Message,
    new_stream: Optional[Stream],
    topic_name: Optional[str],
    propagate_mode: Optional[str],
    send_notification_to_old_thread: bool,
    send_notification_to_new_thread: bool,
    content: Optional[str],
    rendering_result: Optional[MessageRenderingResult],
    prior_mention_user_ids: Set[int],
    mention_data: Optional[MentionData] = None,
) -> int:
    """
    The main function for message editing.  A message edit event can
    modify:
    * the message's content (in which case the caller will have
      set both content and rendered_content),
    * the topic, in which case the caller will have set topic_name
    * or both message's content and the topic
    * or stream and/or topic, in which case the caller will have set
        new_stream and/or topic_name.

    With topic edits, propagate_mode determines whether other message
    also have their topics edited.
    """
    timestamp = timezone_now()
    target_message.last_edit_time = timestamp

    event: Dict[str, Any] = {
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

    changed_messages = [target_message]

    realm = user_profile.realm

    stream_being_edited = None
    if target_message.is_stream_message():
        stream_id = target_message.recipient.type_id
        stream_being_edited = get_stream_by_id_in_realm(stream_id, realm)
        event["stream_name"] = stream_being_edited.name
        event["stream_id"] = stream_being_edited.id

    ums = UserMessage.objects.filter(message=target_message.id)

    if content is not None:
        assert rendering_result is not None

        # mention_data is required if there's a content edit.
        assert mention_data is not None

        # add data from group mentions to mentions_user_ids.
        for group_id in rendering_result.mentions_user_group_ids:
            members = mention_data.get_group_members(group_id)
            rendering_result.mentions_user_ids.update(members)

        update_user_message_flags(rendering_result, ums)

        # One could imagine checking realm.allow_edit_history here and
        # modifying the events based on that setting, but doing so
        # doesn't really make sense.  We need to send the edit event
        # to clients regardless, and a client already had access to
        # the original/pre-edit content of the message anyway.  That
        # setting must be enforced on the client side, and making a
        # change here simply complicates the logic for clients parsing
        # edit history events.
        event["orig_content"] = target_message.content
        event["orig_rendered_content"] = target_message.rendered_content
        edit_history_event["prev_content"] = target_message.content
        edit_history_event["prev_rendered_content"] = target_message.rendered_content
        edit_history_event[
            "prev_rendered_content_version"
        ] = target_message.rendered_content_version
        target_message.content = content
        target_message.rendered_content = rendering_result.rendered_content
        target_message.rendered_content_version = markdown_version
        event["content"] = content
        event["rendered_content"] = rendering_result.rendered_content
        event["prev_rendered_content_version"] = target_message.rendered_content_version
        event["is_me_message"] = Message.is_status_message(
            content, rendering_result.rendered_content
        )

        # target_message.has_image and target_message.has_link will have been
        # already updated by Markdown rendering in the caller.
        target_message.has_attachment = check_attachment_reference_change(
            target_message, rendering_result
        )

        if target_message.is_stream_message():
            if topic_name is not None:
                new_topic_name = topic_name
            else:
                new_topic_name = target_message.topic_name()

            stream_topic: Optional[StreamTopicTarget] = StreamTopicTarget(
                stream_id=stream_id,
                topic_name=new_topic_name,
            )
        else:
            stream_topic = None

        info = get_recipient_info(
            realm_id=realm.id,
            recipient=target_message.recipient,
            sender_id=target_message.sender_id,
            stream_topic=stream_topic,
            possible_wildcard_mention=mention_data.message_has_wildcards(),
        )

        event["online_push_user_ids"] = list(info["online_push_user_ids"])
        event["pm_mention_push_disabled_user_ids"] = list(info["pm_mention_push_disabled_user_ids"])
        event["pm_mention_email_disabled_user_ids"] = list(
            info["pm_mention_email_disabled_user_ids"]
        )
        event["stream_push_user_ids"] = list(info["stream_push_user_ids"])
        event["stream_email_user_ids"] = list(info["stream_email_user_ids"])
        event["muted_sender_user_ids"] = list(info["muted_sender_user_ids"])
        event["prior_mention_user_ids"] = list(prior_mention_user_ids)
        event["presence_idle_user_ids"] = filter_presence_idle_user_ids(info["active_user_ids"])
        event["all_bot_user_ids"] = list(info["all_bot_user_ids"])
        if rendering_result.mentions_wildcard:
            event["wildcard_mention_user_ids"] = list(info["wildcard_mention_user_ids"])
        else:
            event["wildcard_mention_user_ids"] = []

        do_update_mobile_push_notification(
            target_message,
            prior_mention_user_ids,
            rendering_result.mentions_user_ids,
            info["stream_push_user_ids"],
        )

    if topic_name is not None or new_stream is not None:
        assert propagate_mode is not None
        orig_topic_name = target_message.topic_name()
        event["propagate_mode"] = propagate_mode

    if new_stream is not None:
        assert content is None
        assert target_message.is_stream_message()
        assert stream_being_edited is not None

        edit_history_event["prev_stream"] = stream_being_edited.id
        edit_history_event["stream"] = new_stream.id
        event[ORIG_TOPIC] = orig_topic_name
        assert new_stream.recipient_id is not None
        target_message.recipient_id = new_stream.recipient_id

        event["new_stream_id"] = new_stream.id
        event["propagate_mode"] = propagate_mode

        # When messages are moved from one stream to another, some
        # users may lose access to those messages, including guest
        # users and users not subscribed to the new stream (if it is a
        # private stream).  For those users, their experience is as
        # though the messages were deleted, and we should send a
        # delete_message event to them instead.

        subs_to_old_stream = get_active_subscriptions_for_stream_id(
            stream_id, include_deactivated_users=True
        ).select_related("user_profile")
        subs_to_new_stream = list(
            get_active_subscriptions_for_stream_id(
                new_stream.id, include_deactivated_users=True
            ).select_related("user_profile")
        )

        old_stream_sub_ids = [user.user_profile_id for user in subs_to_old_stream]
        new_stream_sub_ids = [user.user_profile_id for user in subs_to_new_stream]

        # Get users who aren't subscribed to the new_stream.
        subs_losing_usermessages = [
            sub for sub in subs_to_old_stream if sub.user_profile_id not in new_stream_sub_ids
        ]
        # Users who can longer access the message without some action
        # from administrators.
        subs_losing_access = [
            sub
            for sub in subs_losing_usermessages
            if sub.user_profile.is_guest or not new_stream.is_public()
        ]
        ums = ums.exclude(
            user_profile_id__in=[sub.user_profile_id for sub in subs_losing_usermessages]
        )

        subs_gaining_usermessages = []
        if not new_stream.is_history_public_to_subscribers():
            # For private streams, with history not public to subscribers,
            # We find out users who are not present in the msgs' old stream
            # and create new UserMessage for these users so that they can
            # access this message.
            subs_gaining_usermessages += [
                user_id for user_id in new_stream_sub_ids if user_id not in old_stream_sub_ids
            ]

    # We save the full topic name so that checks that require comparison
    # between the original topic and the topic name passed into this function
    # will not be affected by the potential truncation of topic_name below.
    pre_truncation_topic_name = topic_name
    if topic_name is not None:
        topic_name = truncate_topic(topic_name)
        target_message.set_topic_name(topic_name)

        # These fields have legacy field names.
        event[ORIG_TOPIC] = orig_topic_name
        event[TOPIC_NAME] = topic_name
        event[TOPIC_LINKS] = topic_links(target_message.sender.realm_id, topic_name)
        edit_history_event["prev_topic"] = orig_topic_name
        edit_history_event["topic"] = topic_name

    update_edit_history(target_message, timestamp, edit_history_event)

    delete_event_notify_user_ids: List[int] = []
    if propagate_mode in ["change_later", "change_all"]:
        assert topic_name is not None or new_stream is not None
        assert stream_being_edited is not None

        # Other messages should only get topic/stream fields in their edit history.
        topic_only_edit_history_event: EditHistoryEvent = {
            "user_id": edit_history_event["user_id"],
            "timestamp": edit_history_event["timestamp"],
        }
        if topic_name is not None:
            topic_only_edit_history_event["prev_topic"] = edit_history_event["prev_topic"]
            topic_only_edit_history_event["topic"] = edit_history_event["topic"]
        if new_stream is not None:
            topic_only_edit_history_event["prev_stream"] = edit_history_event["prev_stream"]
            topic_only_edit_history_event["stream"] = edit_history_event["stream"]

        messages_list = update_messages_for_topic_edit(
            acting_user=user_profile,
            edited_message=target_message,
            propagate_mode=propagate_mode,
            orig_topic_name=orig_topic_name,
            topic_name=topic_name,
            new_stream=new_stream,
            old_stream=stream_being_edited,
            edit_history_event=topic_only_edit_history_event,
            last_edit_time=timestamp,
        )
        changed_messages += messages_list

        if new_stream is not None:
            assert stream_being_edited is not None
            changed_message_ids = [msg.id for msg in changed_messages]

            if subs_gaining_usermessages:
                ums_to_create = []
                for message_id in changed_message_ids:
                    for user_profile_id in subs_gaining_usermessages:
                        # The fact that the user didn't have a UserMessage originally means we can infer that the user
                        # was not mentioned in the original message (even if mention syntax was present, it would not
                        # take effect for a user who was not subscribed). If we were editing the message's content, we
                        # would rerender the message and then use the new stream's data to determine whether this is
                        # a mention of a subscriber; but as we are not doing so, we choose to preserve the "was this
                        # mention syntax an actual mention" decision made during the original rendering for implementation
                        # simplicity. As a result, the only flag to consider applying here is read.
                        um = UserMessageLite(
                            user_profile_id=user_profile_id,
                            message_id=message_id,
                            flags=UserMessage.flags.read,
                        )
                        ums_to_create.append(um)
                bulk_insert_ums(ums_to_create)

            # Delete UserMessage objects for users who will no
            # longer have access to these messages.  Note: This could be
            # very expensive, since it's N guest users x M messages.
            UserMessage.objects.filter(
                user_profile_id__in=[sub.user_profile_id for sub in subs_losing_usermessages],
                message_id__in=changed_message_ids,
            ).delete()

            delete_event: DeleteMessagesEvent = {
                "type": "delete_message",
                "message_ids": changed_message_ids,
                "message_type": "stream",
                "stream_id": stream_being_edited.id,
                "topic": orig_topic_name,
            }
            delete_event_notify_user_ids = [sub.user_profile_id for sub in subs_losing_access]
            send_event(user_profile.realm, delete_event, delete_event_notify_user_ids)

            # Reset the Attachment.is_*_public caches for all messages
            # moved to another stream with different access permissions.
            if new_stream.invite_only != stream_being_edited.invite_only:
                Attachment.objects.filter(messages__in=changed_message_ids).update(
                    is_realm_public=None,
                )
                ArchivedAttachment.objects.filter(messages__in=changed_message_ids).update(
                    is_realm_public=None,
                )

            if new_stream.is_web_public != stream_being_edited.is_web_public:
                Attachment.objects.filter(messages__in=changed_message_ids).update(
                    is_web_public=None,
                )
                ArchivedAttachment.objects.filter(messages__in=changed_message_ids).update(
                    is_web_public=None,
                )

    # This does message.save(update_fields=[...])
    save_message_for_edit_use_case(message=target_message)

    realm_id: Optional[int] = None
    if stream_being_edited is not None:
        realm_id = stream_being_edited.realm_id

    event["message_ids"] = update_to_dict_cache(changed_messages, realm_id)

    def user_info(um: UserMessage) -> Dict[str, Any]:
        return {
            "id": um.user_profile_id,
            "flags": um.flags_list(),
        }

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
    users_to_be_notified = list(map(user_info, ums))
    if stream_being_edited is not None:
        if stream_being_edited.is_history_public_to_subscribers():
            subscriptions = get_active_subscriptions_for_stream_id(
                stream_id, include_deactivated_users=False
            )
            # We exclude long-term idle users, since they by
            # definition have no active clients.
            subscriptions = subscriptions.exclude(user_profile__long_term_idle=True)
            # Remove duplicates by excluding the id of users already
            # in users_to_be_notified list.  This is the case where a
            # user both has a UserMessage row and is a current
            # Subscriber
            subscriptions = subscriptions.exclude(
                user_profile_id__in=[um.user_profile_id for um in ums]
            )

            if new_stream is not None:
                assert delete_event_notify_user_ids is not None
                subscriptions = subscriptions.exclude(
                    user_profile_id__in=delete_event_notify_user_ids
                )

            # All users that are subscribed to the stream must be
            # notified when a message is edited
            subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))

            if new_stream is not None:
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
                old_stream_unsubbed_guests = [
                    sub
                    for sub in subs_to_new_stream
                    if sub.user_profile.is_guest and sub.user_profile_id not in subscriber_ids
                ]
                subscriptions = subscriptions.exclude(
                    user_profile_id__in=[sub.user_profile_id for sub in old_stream_unsubbed_guests]
                )
                subscriber_ids = set(subscriptions.values_list("user_profile_id", flat=True))

            users_to_be_notified += list(map(subscriber_info, sorted(subscriber_ids)))

    # UserTopic updates and the content of notifications depend on
    # whether we've moved the entire topic, or just part of it. We
    # make that determination here.
    moved_all_visible_messages = False
    if topic_name is not None or new_stream is not None:
        assert stream_being_edited is not None

        if propagate_mode == "change_all":
            moved_all_visible_messages = True
        else:
            # With other propagate modes, if the user in fact moved
            # all messages in the stream, we want to explain it was a
            # full-topic move.
            #
            # For security model reasons, we don't want to allow a
            # user to take any action that would leak information
            # about older messages they cannot access (E.g. the only
            # remaining messages are in a stream without shared
            # history). The bulk_access_messages call below addresses
            # that concern.
            #
            # bulk_access_messages is inefficient for this task, since
            # we just want to do the exists() version of this
            # query. But it's nice to reuse code, and this bulk
            # operation is likely cheaper than a `GET /messages`
            # unless the topic has thousands of messages of history.
            assert stream_being_edited.recipient_id is not None
            unmoved_messages = messages_for_topic(
                stream_being_edited.recipient_id,
                orig_topic_name,
            )
            visible_unmoved_messages = bulk_access_messages(
                user_profile, unmoved_messages, stream=stream_being_edited
            )
            moved_all_visible_messages = len(visible_unmoved_messages) == 0

    # Migrate muted topic configuration in the following circumstances:
    #
    # * If propagate_mode is change_all, do so unconditionally.
    #
    # * If propagate_mode is change_later or change_one, do so when
    #   the acting user has moved the entire topic (as visible to them).
    #
    # This rule corresponds to checking moved_all_visible_messages.
    #
    # We may want more complex behavior in cases where one appears to
    # be merging topics (E.g. there are existing messages in the
    # target topic).
    if moved_all_visible_messages:
        assert stream_being_edited is not None
        assert topic_name is not None or new_stream is not None

        for muting_user in get_users_muting_topic(stream_being_edited.id, orig_topic_name):
            # TODO: Ideally, this would be a bulk update operation,
            # because we are doing database operations in a loop here.
            #
            # This loop is only acceptable in production because it is
            # rare for more than a few users to have muted an
            # individual topic that is being moved; as of this
            # writing, no individual topic in Zulip Cloud had been
            # muted by more than 100 users.

            if new_stream is not None and muting_user.id in delete_event_notify_user_ids:
                # If the messages are being moved to a stream the user
                # cannot access, then we treat this as the
                # messages/topic being deleted for this user. This is
                # important for security reasons; we don't want to
                # give users a UserTopic row in a stream they cannot
                # access.  Unmute the topic for such users.
                do_unmute_topic(muting_user, stream_being_edited, orig_topic_name)
            else:
                # Otherwise, we move the muted topic record for the
                # user, but removing the old topic mute and then
                # creating a new one.
                do_unmute_topic(
                    muting_user,
                    stream_being_edited,
                    orig_topic_name,
                    # do_mute_topic will send an updated muted topic
                    # event, which contains the full set of muted
                    # topics, just after this.
                    skip_muted_topics_event=True,
                )

                do_mute_topic(
                    muting_user,
                    new_stream if new_stream is not None else stream_being_edited,
                    topic_name if topic_name is not None else orig_topic_name,
                    ignore_duplicate=True,
                )

    send_event(user_profile.realm, event, users_to_be_notified)

    sent_resolve_topic_notification = False
    if (
        topic_name is not None
        and new_stream is None
        and content is None
        and len(changed_messages) > 0
    ):
        assert stream_being_edited is not None
        sent_resolve_topic_notification = maybe_send_resolve_topic_notifications(
            user_profile=user_profile,
            stream=stream_being_edited,
            old_topic=orig_topic_name,
            new_topic=topic_name,
            changed_messages=changed_messages,
        )

    if (
        len(changed_messages) > 0
        and (new_stream is not None or topic_name is not None)
        and stream_being_edited is not None
    ):
        # Notify users that the topic was moved.
        changed_messages_count = len(changed_messages)

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
        #
        # Since one can resolve/unresolve a topic at the same time
        # you're moving it, we need to carefully treat the resolve
        # topic notification as satisfying our obligation to send a
        # notification to the new topic only if the only thing this
        # request did is mark the topic as resolved.
        new_thread_notification_string = None
        if send_notification_to_new_thread and (
            new_stream is not None
            or not sent_resolve_topic_notification
            or (
                pre_truncation_topic_name is not None
                and orig_topic_name.lstrip(RESOLVED_TOPIC_PREFIX)
                != pre_truncation_topic_name.lstrip(RESOLVED_TOPIC_PREFIX)
            )
        ):
            if moved_all_visible_messages:
                new_thread_notification_string = gettext_lazy(
                    "This topic was moved here from {old_location} by {user}."
                )
            elif changed_messages_count == 1:
                new_thread_notification_string = gettext_lazy(
                    "A message was moved here from {old_location} by {user}."
                )
            else:
                new_thread_notification_string = gettext_lazy(
                    "{changed_messages_count} messages were moved here from {old_location} by {user}."
                )

        send_message_moved_breadcrumbs(
            user_profile,
            stream_being_edited,
            orig_topic_name,
            old_thread_notification_string,
            new_stream if new_stream is not None else stream_being_edited,
            topic_name,
            new_thread_notification_string,
            changed_messages_count,
        )

    return len(changed_messages)


def check_update_message(
    user_profile: UserProfile,
    message_id: int,
    stream_id: Optional[int] = None,
    topic_name: Optional[str] = None,
    propagate_mode: str = "change_one",
    send_notification_to_old_thread: bool = True,
    send_notification_to_new_thread: bool = True,
    content: Optional[str] = None,
) -> int:
    """This will update a message given the message id and user profile.
    It checks whether the user profile has the permission to edit the message
    and raises a JsonableError if otherwise.
    It returns the number changed.
    """
    message, ignored_user_message = access_message(user_profile, message_id)

    if content is not None and not user_profile.realm.allow_message_editing:
        raise JsonableError(_("Your organization has turned off message editing"))

    # The zerver/views/message_edit.py call point already strips this
    # via REQ_topic; so we can delete this line if we arrange a
    # contract where future callers in the embedded bots system strip
    # use REQ_topic as well (or otherwise are guaranteed to strip input).
    if topic_name is not None:
        topic_name = topic_name.strip()
        if topic_name == message.topic_name():
            topic_name = None

    validate_message_edit_payload(message, stream_id, topic_name, propagate_mode, content)

    if content is not None:
        # You cannot edit the content of message sent by someone else.
        if message.sender_id != user_profile.id:
            raise JsonableError(_("You don't have permission to edit this message"))

    is_no_topic_msg = message.topic_name() == "(no topic)"

    if topic_name is not None and not can_edit_topic(user_profile, is_no_topic_msg):
        raise JsonableError(_("You don't have permission to edit this message"))

    # If there is a change to the content, check that it hasn't been too long
    # Allow an extra 20 seconds since we potentially allow editing 15 seconds
    # past the limit, and in case there are network issues, etc. The 15 comes
    # from (min_seconds_to_edit + seconds_left_buffer) in message_edit.js; if
    # you change this value also change those two parameters in message_edit.js.
    edit_limit_buffer = 20
    if content is not None and user_profile.realm.message_content_edit_limit_seconds is not None:
        deadline_seconds = user_profile.realm.message_content_edit_limit_seconds + edit_limit_buffer
        if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message has passed"))

    # If there is a change to the topic, check that the user is allowed to
    # edit it and that it has not been too long. If user is not admin or moderator,
    # and the time limit for editing topics is passed, raise an error.
    if (
        topic_name is not None
        and not user_profile.is_realm_admin
        and not user_profile.is_moderator
        and not is_no_topic_msg
    ):
        deadline_seconds = Realm.DEFAULT_COMMUNITY_TOPIC_EDITING_LIMIT_SECONDS + edit_limit_buffer
        if (timezone_now() - message.date_sent) > datetime.timedelta(seconds=deadline_seconds):
            raise JsonableError(_("The time limit for editing this message's topic has passed"))

    rendering_result = None
    links_for_embed: Set[str] = set()
    prior_mention_user_ids: Set[int] = set()
    mention_data: Optional[MentionData] = None
    if content is not None:
        if content.rstrip() == "":
            content = "(deleted)"
        content = normalize_body(content)

        mention_backend = MentionBackend(user_profile.realm_id)
        mention_data = MentionData(
            mention_backend=mention_backend,
            content=content,
        )
        prior_mention_user_ids = get_mentions_for_message_updates(message.id)

        # We render the message using the current user's realm; since
        # the cross-realm bots never edit messages, this should be
        # always correct.
        # Note: If rendering fails, the called code will raise a JsonableError.
        rendering_result = render_incoming_message(
            message,
            content,
            user_profile.realm,
            mention_data=mention_data,
        )
        links_for_embed |= rendering_result.links_for_preview

        if message.is_stream_message() and rendering_result.mentions_wildcard:
            stream = access_stream_by_id(user_profile, message.recipient.type_id)[0]
            if not wildcard_mention_allowed(message.sender, stream):
                raise JsonableError(
                    _("You do not have permission to use wildcard mentions in this stream.")
                )

    new_stream = None
    number_changed = 0

    if stream_id is not None:
        assert message.is_stream_message()
        if not user_profile.can_move_messages_between_streams():
            raise JsonableError(_("You don't have permission to move this message"))
        try:
            access_stream_by_id(user_profile, message.recipient.type_id)
        except JsonableError:
            raise JsonableError(
                _(
                    "You don't have permission to move this message due to missing access to its stream"
                )
            )

        new_stream = access_stream_by_id(user_profile, stream_id, require_active=True)[0]
        check_stream_access_based_on_stream_post_policy(user_profile, new_stream)

    number_changed = do_update_message(
        user_profile,
        message,
        new_stream,
        topic_name,
        propagate_mode,
        send_notification_to_old_thread,
        send_notification_to_new_thread,
        content,
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
        queue_json_publish("embed_links", event_data)

    return number_changed
