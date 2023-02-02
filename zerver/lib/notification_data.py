import math
from dataclasses import dataclass
from typing import Any, Collection, Dict, List, Optional, Set

from zerver.lib.mention import MentionData
from zerver.lib.user_groups import get_user_group_direct_member_ids
from zerver.models import NotificationTriggers, UserGroup, UserProfile


@dataclass
class UserMessageNotificationsData:
    user_id: int
    online_push_enabled: bool
    pm_email_notify: bool
    pm_push_notify: bool
    mention_email_notify: bool
    mention_push_notify: bool
    wildcard_mention_email_notify: bool
    wildcard_mention_push_notify: bool
    stream_push_notify: bool
    stream_email_notify: bool
    sender_is_muted: bool

    def __post_init__(self) -> None:
        # Check that there's no dubious data.
        if self.pm_email_notify or self.pm_push_notify:
            assert not (self.stream_email_notify or self.stream_push_notify)

        if self.stream_email_notify or self.stream_push_notify:
            assert not (self.pm_email_notify or self.pm_push_notify)

    @classmethod
    def from_user_id_sets(
        cls,
        *,
        user_id: int,
        flags: Collection[str],
        private_message: bool,
        online_push_user_ids: Set[int],
        pm_mention_push_disabled_user_ids: Set[int],
        pm_mention_email_disabled_user_ids: Set[int],
        stream_push_user_ids: Set[int],
        stream_email_user_ids: Set[int],
        wildcard_mention_user_ids: Set[int],
        muted_sender_user_ids: Set[int],
        all_bot_user_ids: Set[int],
    ) -> "UserMessageNotificationsData":
        if user_id in all_bot_user_ids:
            # Don't send any notifications to bots
            return cls(
                user_id=user_id,
                pm_email_notify=False,
                mention_email_notify=False,
                wildcard_mention_email_notify=False,
                pm_push_notify=False,
                mention_push_notify=False,
                wildcard_mention_push_notify=False,
                online_push_enabled=False,
                stream_push_notify=False,
                stream_email_notify=False,
                sender_is_muted=False,
            )

        # `wildcard_mention_user_ids` are those user IDs for whom wildcard mentions should
        # obey notification settings of personal mentions. Hence, it isn't an independent
        # notification setting and acts as a wrapper.
        pm_email_notify = user_id not in pm_mention_email_disabled_user_ids and private_message
        mention_email_notify = (
            user_id not in pm_mention_email_disabled_user_ids and "mentioned" in flags
        )
        wildcard_mention_email_notify = (
            user_id in wildcard_mention_user_ids
            and user_id not in pm_mention_email_disabled_user_ids
            and "wildcard_mentioned" in flags
        )

        pm_push_notify = user_id not in pm_mention_push_disabled_user_ids and private_message
        mention_push_notify = (
            user_id not in pm_mention_push_disabled_user_ids and "mentioned" in flags
        )
        wildcard_mention_push_notify = (
            user_id in wildcard_mention_user_ids
            and user_id not in pm_mention_push_disabled_user_ids
            and "wildcard_mentioned" in flags
        )
        return cls(
            user_id=user_id,
            pm_email_notify=pm_email_notify,
            mention_email_notify=mention_email_notify,
            wildcard_mention_email_notify=wildcard_mention_email_notify,
            pm_push_notify=pm_push_notify,
            mention_push_notify=mention_push_notify,
            wildcard_mention_push_notify=wildcard_mention_push_notify,
            online_push_enabled=(user_id in online_push_user_ids),
            stream_push_notify=(user_id in stream_push_user_ids),
            stream_email_notify=(user_id in stream_email_user_ids),
            sender_is_muted=(user_id in muted_sender_user_ids),
        )

    # For these functions, acting_user_id is the user sent a message
    # (or edited a message) triggering the event for which we need to
    # determine notifiability.
    def is_notifiable(self, acting_user_id: int, idle: bool) -> bool:
        return self.is_email_notifiable(acting_user_id, idle) or self.is_push_notifiable(
            acting_user_id, idle
        )

    def is_push_notifiable(self, acting_user_id: int, idle: bool) -> bool:
        return self.get_push_notification_trigger(acting_user_id, idle) is not None

    def get_push_notification_trigger(self, acting_user_id: int, idle: bool) -> Optional[str]:
        if not idle and not self.online_push_enabled:
            return None

        if self.user_id == acting_user_id:
            return None

        if self.sender_is_muted:
            return None

        # The order here is important. If, for example, both
        # `mention_push_notify` and `stream_push_notify` are True, we
        # want to classify it as a mention, since that's more salient.
        if self.pm_push_notify:
            return NotificationTriggers.PRIVATE_MESSAGE
        elif self.mention_push_notify:
            return NotificationTriggers.MENTION
        elif self.wildcard_mention_push_notify:
            return NotificationTriggers.WILDCARD_MENTION
        elif self.stream_push_notify:
            return NotificationTriggers.STREAM_PUSH
        else:
            return None

    def is_email_notifiable(self, acting_user_id: int, idle: bool) -> bool:
        return self.get_email_notification_trigger(acting_user_id, idle) is not None

    def get_email_notification_trigger(self, acting_user_id: int, idle: bool) -> Optional[str]:
        if not idle:
            return None

        if self.user_id == acting_user_id:
            return None

        if self.sender_is_muted:
            return None

        # The order here is important. If, for example, both
        # `mention_email_notify` and `stream_email_notify` are True, we
        # want to classify it as a mention, since that's more salient.
        if self.pm_email_notify:
            return NotificationTriggers.PRIVATE_MESSAGE
        elif self.mention_email_notify:
            return NotificationTriggers.MENTION
        elif self.wildcard_mention_email_notify:
            return NotificationTriggers.WILDCARD_MENTION
        elif self.stream_email_notify:
            return NotificationTriggers.STREAM_EMAIL
        else:
            return None


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


def get_mentioned_user_group_name(
    messages: List[Dict[str, Any]], user_profile: UserProfile
) -> Optional[str]:
    """Returns the user group name to display in the email notification
    if user group(s) are mentioned.

    This implements the same algorithm as get_user_group_mentions_data
    in zerver/lib/notification_data.py, but we're passed a list of
    messages instead.
    """
    for message in messages:
        if message["mentioned_user_group_id"] is None and message["trigger"] == "mentioned":
            # The user has also been personally mentioned, so that gets prioritized.
            return None

    # These IDs are those of the smallest user groups mentioned in each message.
    mentioned_user_group_ids = [
        message["mentioned_user_group_id"]
        for message in messages
        if message["mentioned_user_group_id"] is not None
    ]

    # We now want to calculate the name of the smallest user group mentioned among
    # all these messages.
    smallest_user_group_size = math.inf
    smallest_user_group_name = None
    for user_group_id in mentioned_user_group_ids:
        current_user_group = UserGroup.objects.get(id=user_group_id, realm=user_profile.realm)
        current_user_group_size = len(get_user_group_direct_member_ids(current_user_group))

        if current_user_group_size < smallest_user_group_size:
            # If multiple user groups are mentioned, we prefer the
            # user group with the least members.
            smallest_user_group_size = current_user_group_size
            smallest_user_group_name = current_user_group.name

    return smallest_user_group_name
