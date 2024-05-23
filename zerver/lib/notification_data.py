import math
from dataclasses import dataclass
from typing import Any, Collection, Dict, List, Optional, Set

from zerver.lib.mention import MentionData
from zerver.lib.user_groups import get_user_group_member_ids
from zerver.models import NamedUserGroup, UserProfile, UserTopic
from zerver.models.scheduled_jobs import NotificationTriggers


@dataclass
class UserMessageNotificationsData:
    user_id: int
    online_push_enabled: bool
    dm_email_notify: bool
    dm_push_notify: bool
    mention_email_notify: bool
    mention_push_notify: bool
    topic_wildcard_mention_email_notify: bool
    topic_wildcard_mention_push_notify: bool
    stream_wildcard_mention_email_notify: bool
    stream_wildcard_mention_push_notify: bool
    stream_push_notify: bool
    stream_email_notify: bool
    followed_topic_push_notify: bool
    followed_topic_email_notify: bool
    topic_wildcard_mention_in_followed_topic_push_notify: bool
    topic_wildcard_mention_in_followed_topic_email_notify: bool
    stream_wildcard_mention_in_followed_topic_push_notify: bool
    stream_wildcard_mention_in_followed_topic_email_notify: bool
    sender_is_muted: bool
    disable_external_notifications: bool

    def __post_init__(self) -> None:
        # Check that there's no dubious data.
        if self.dm_email_notify or self.dm_push_notify:
            assert not (
                self.stream_email_notify
                or self.stream_push_notify
                or self.followed_topic_email_notify
                or self.followed_topic_push_notify
            )

        if (
            self.stream_email_notify
            or self.stream_push_notify
            or self.followed_topic_email_notify
            or self.followed_topic_push_notify
        ):
            assert not (self.dm_email_notify or self.dm_push_notify)

    @classmethod
    def from_user_id_sets(
        cls,
        *,
        user_id: int,
        flags: Collection[str],
        private_message: bool,
        disable_external_notifications: bool,
        online_push_user_ids: Set[int],
        dm_mention_push_disabled_user_ids: Set[int],
        dm_mention_email_disabled_user_ids: Set[int],
        stream_push_user_ids: Set[int],
        stream_email_user_ids: Set[int],
        topic_wildcard_mention_user_ids: Set[int],
        stream_wildcard_mention_user_ids: Set[int],
        followed_topic_push_user_ids: Set[int],
        followed_topic_email_user_ids: Set[int],
        topic_wildcard_mention_in_followed_topic_user_ids: Set[int],
        stream_wildcard_mention_in_followed_topic_user_ids: Set[int],
        muted_sender_user_ids: Set[int],
        all_bot_user_ids: Set[int],
    ) -> "UserMessageNotificationsData":
        if user_id in all_bot_user_ids:
            # Don't send any notifications to bots
            return cls(
                user_id=user_id,
                dm_email_notify=False,
                mention_email_notify=False,
                topic_wildcard_mention_email_notify=False,
                stream_wildcard_mention_email_notify=False,
                dm_push_notify=False,
                mention_push_notify=False,
                topic_wildcard_mention_push_notify=False,
                stream_wildcard_mention_push_notify=False,
                online_push_enabled=False,
                stream_push_notify=False,
                stream_email_notify=False,
                followed_topic_push_notify=False,
                followed_topic_email_notify=False,
                topic_wildcard_mention_in_followed_topic_push_notify=False,
                topic_wildcard_mention_in_followed_topic_email_notify=False,
                stream_wildcard_mention_in_followed_topic_push_notify=False,
                stream_wildcard_mention_in_followed_topic_email_notify=False,
                sender_is_muted=False,
                disable_external_notifications=False,
            )

        # `stream_wildcard_mention_user_ids`, `topic_wildcard_mention_user_ids`,
        # `stream_wildcard_mention_in_followed_topic_user_ids` and `topic_wildcard_mention_in_followed_topic_user_ids`
        # are those user IDs for whom stream or topic wildcard mentions should obey notification
        # settings for personal mentions. Hence, it isn't an independent notification setting and acts as a wrapper.
        dm_email_notify = user_id not in dm_mention_email_disabled_user_ids and private_message
        mention_email_notify = (
            user_id not in dm_mention_email_disabled_user_ids and "mentioned" in flags
        )
        topic_wildcard_mention_email_notify = (
            user_id in topic_wildcard_mention_user_ids
            and user_id not in dm_mention_email_disabled_user_ids
            and "topic_wildcard_mentioned" in flags
        )
        stream_wildcard_mention_email_notify = (
            user_id in stream_wildcard_mention_user_ids
            and user_id not in dm_mention_email_disabled_user_ids
            and "stream_wildcard_mentioned" in flags
        )
        topic_wildcard_mention_in_followed_topic_email_notify = (
            user_id in topic_wildcard_mention_in_followed_topic_user_ids
            and user_id not in dm_mention_email_disabled_user_ids
            and "topic_wildcard_mentioned" in flags
        )
        stream_wildcard_mention_in_followed_topic_email_notify = (
            user_id in stream_wildcard_mention_in_followed_topic_user_ids
            and user_id not in dm_mention_email_disabled_user_ids
            and "stream_wildcard_mentioned" in flags
        )

        dm_push_notify = user_id not in dm_mention_push_disabled_user_ids and private_message
        mention_push_notify = (
            user_id not in dm_mention_push_disabled_user_ids and "mentioned" in flags
        )
        topic_wildcard_mention_push_notify = (
            user_id in topic_wildcard_mention_user_ids
            and user_id not in dm_mention_push_disabled_user_ids
            and "topic_wildcard_mentioned" in flags
        )
        stream_wildcard_mention_push_notify = (
            user_id in stream_wildcard_mention_user_ids
            and user_id not in dm_mention_push_disabled_user_ids
            and "stream_wildcard_mentioned" in flags
        )
        topic_wildcard_mention_in_followed_topic_push_notify = (
            user_id in topic_wildcard_mention_in_followed_topic_user_ids
            and user_id not in dm_mention_push_disabled_user_ids
            and "topic_wildcard_mentioned" in flags
        )
        stream_wildcard_mention_in_followed_topic_push_notify = (
            user_id in stream_wildcard_mention_in_followed_topic_user_ids
            and user_id not in dm_mention_push_disabled_user_ids
            and "stream_wildcard_mentioned" in flags
        )
        return cls(
            user_id=user_id,
            dm_email_notify=dm_email_notify,
            mention_email_notify=mention_email_notify,
            topic_wildcard_mention_email_notify=topic_wildcard_mention_email_notify,
            stream_wildcard_mention_email_notify=stream_wildcard_mention_email_notify,
            dm_push_notify=dm_push_notify,
            mention_push_notify=mention_push_notify,
            topic_wildcard_mention_push_notify=topic_wildcard_mention_push_notify,
            stream_wildcard_mention_push_notify=stream_wildcard_mention_push_notify,
            online_push_enabled=user_id in online_push_user_ids,
            stream_push_notify=user_id in stream_push_user_ids,
            stream_email_notify=user_id in stream_email_user_ids,
            followed_topic_push_notify=user_id in followed_topic_push_user_ids,
            followed_topic_email_notify=user_id in followed_topic_email_user_ids,
            topic_wildcard_mention_in_followed_topic_push_notify=topic_wildcard_mention_in_followed_topic_push_notify,
            topic_wildcard_mention_in_followed_topic_email_notify=topic_wildcard_mention_in_followed_topic_email_notify,
            stream_wildcard_mention_in_followed_topic_push_notify=stream_wildcard_mention_in_followed_topic_push_notify,
            stream_wildcard_mention_in_followed_topic_email_notify=stream_wildcard_mention_in_followed_topic_email_notify,
            sender_is_muted=user_id in muted_sender_user_ids,
            disable_external_notifications=disable_external_notifications,
        )

    # For these functions, acting_user_id is the user sent a message
    # (or edited a message) triggering the event for which we need to
    # determine notifiability.
    def trivially_should_not_notify(self, acting_user_id: int) -> bool:
        """Common check for reasons not to trigger a notification that arex
        independent of users' notification settings and thus don't
        depend on what type of notification (email/push) it is.
        """
        if self.user_id == acting_user_id:
            return True

        if self.sender_is_muted:
            return True

        if self.disable_external_notifications:
            return True

        return False

    def is_notifiable(self, acting_user_id: int, idle: bool) -> bool:
        return self.is_email_notifiable(acting_user_id, idle) or self.is_push_notifiable(
            acting_user_id, idle
        )

    def is_push_notifiable(self, acting_user_id: int, idle: bool) -> bool:
        return self.get_push_notification_trigger(acting_user_id, idle) is not None

    def get_push_notification_trigger(self, acting_user_id: int, idle: bool) -> Optional[str]:
        if not idle and not self.online_push_enabled:
            return None

        if self.trivially_should_not_notify(acting_user_id):
            return None

        # The order here is important. If, for example, both
        # `mention_push_notify` and `stream_push_notify` are True, we
        # want to classify it as a mention, since that's more salient.
        if self.dm_push_notify:
            return NotificationTriggers.DIRECT_MESSAGE
        elif self.mention_push_notify:
            return NotificationTriggers.MENTION
        elif self.topic_wildcard_mention_in_followed_topic_push_notify:
            return NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        elif self.stream_wildcard_mention_in_followed_topic_push_notify:
            return NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        elif self.topic_wildcard_mention_push_notify:
            return NotificationTriggers.TOPIC_WILDCARD_MENTION
        elif self.stream_wildcard_mention_push_notify:
            return NotificationTriggers.STREAM_WILDCARD_MENTION
        elif self.followed_topic_push_notify:
            return NotificationTriggers.FOLLOWED_TOPIC_PUSH
        elif self.stream_push_notify:
            return NotificationTriggers.STREAM_PUSH
        else:
            return None

    def is_email_notifiable(self, acting_user_id: int, idle: bool) -> bool:
        return self.get_email_notification_trigger(acting_user_id, idle) is not None

    def get_email_notification_trigger(self, acting_user_id: int, idle: bool) -> Optional[str]:
        if not idle:
            return None

        if self.trivially_should_not_notify(acting_user_id):
            return None

        # The order here is important. If, for example, both
        # `mention_email_notify` and `stream_email_notify` are True, we
        # want to classify it as a mention, since that's more salient.
        if self.dm_email_notify:
            return NotificationTriggers.DIRECT_MESSAGE
        elif self.mention_email_notify:
            return NotificationTriggers.MENTION
        elif self.topic_wildcard_mention_in_followed_topic_email_notify:
            return NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        elif self.stream_wildcard_mention_in_followed_topic_email_notify:
            return NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        elif self.topic_wildcard_mention_email_notify:
            return NotificationTriggers.TOPIC_WILDCARD_MENTION
        elif self.stream_wildcard_mention_email_notify:
            return NotificationTriggers.STREAM_WILDCARD_MENTION
        elif self.followed_topic_email_notify:
            return NotificationTriggers.FOLLOWED_TOPIC_EMAIL
        elif self.stream_email_notify:
            return NotificationTriggers.STREAM_EMAIL
        else:
            return None


def user_allows_notifications_in_StreamTopic(
    stream_is_muted: bool,
    visibility_policy: int,
    stream_specific_setting: Optional[bool],
    global_setting: bool,
) -> bool:
    """
    Captures the hierarchy of notification settings, where visibility policy is considered first,
    followed by stream-specific settings, and the global-setting in the UserProfile is the fallback.
    """
    if stream_is_muted and visibility_policy != UserTopic.VisibilityPolicy.UNMUTED:
        return False

    if visibility_policy == UserTopic.VisibilityPolicy.MUTED:
        return False

    if stream_specific_setting is not None:
        return stream_specific_setting

    return global_setting


def get_user_group_mentions_data(
    mentioned_user_ids: Set[int], mentioned_user_group_ids: List[int], mention_data: MentionData
) -> Dict[int, int]:
    # Maps user_id -> mentioned user_group_id
    mentioned_user_groups_map: Dict[int, int] = dict()

    # Add members of the mentioned user groups into `mentions_user_ids`.
    for group_id in mentioned_user_group_ids:
        member_ids = mention_data.get_group_members(group_id)
        for member_id in member_ids:
            if member_id in mentioned_user_ids:
                # If a user is also mentioned personally, we use that as a trigger
                # for notifications.
                continue

            if member_id in mentioned_user_groups_map:
                # If multiple user groups are mentioned, we prefer the
                # user group with the least members for email/mobile
                # notifications.
                previous_group_id = mentioned_user_groups_map[member_id]
                previous_group_member_ids = mention_data.get_group_members(previous_group_id)

                if len(previous_group_member_ids) > len(member_ids):
                    mentioned_user_groups_map[member_id] = group_id
            else:
                mentioned_user_groups_map[member_id] = group_id

    return mentioned_user_groups_map


@dataclass
class MentionedUserGroup:
    id: int
    name: str
    members_count: int


def get_mentioned_user_group(
    messages: List[Dict[str, Any]], user_profile: UserProfile
) -> Optional[MentionedUserGroup]:
    """Returns the user group name to display in the email notification
    if user group(s) are mentioned.

    This implements the same algorithm as get_user_group_mentions_data
    in zerver/lib/notification_data.py, but we're passed a list of
    messages instead.
    """
    for message in messages:
        if (
            message.get("mentioned_user_group_id") is None
            and message["trigger"] == NotificationTriggers.MENTION
        ):
            # The user has also been personally mentioned, so that gets prioritized.
            return None

    # These IDs are those of the smallest user groups mentioned in each message.
    mentioned_user_group_ids = [
        message["mentioned_user_group_id"]
        for message in messages
        if message.get("mentioned_user_group_id") is not None
    ]

    if len(mentioned_user_group_ids) == 0:
        return None

    # We now want to calculate the name of the smallest user group mentioned among
    # all these messages.
    smallest_user_group_size = math.inf
    for user_group_id in mentioned_user_group_ids:
        current_user_group = NamedUserGroup.objects.get(id=user_group_id, realm=user_profile.realm)
        current_mentioned_user_group = MentionedUserGroup(
            id=current_user_group.id,
            name=current_user_group.name,
            members_count=len(get_user_group_member_ids(current_user_group)),
        )

        if current_mentioned_user_group.members_count < smallest_user_group_size:
            # If multiple user groups are mentioned, we prefer the
            # user group with the least members.
            smallest_user_group_size = current_mentioned_user_group.members_count
            smallest_mentioned_user_group = current_mentioned_user_group

    return smallest_mentioned_user_group
