import functools
import re
from collections import defaultdict
from dataclasses import dataclass
from re import Match
from typing import Literal

from django.conf import settings
from django.db.models import Q
from django_stubs_ext import StrPromise

from zerver.lib.streams import get_content_access_streams
from zerver.lib.topic import get_first_message_for_user_in_topic
from zerver.lib.types import UserDisplayRecipient
from zerver.lib.user_groups import (
    UserGroupMembershipDetails,
    get_root_id_annotated_recursive_subgroups_for_groups,
    user_has_permission_for_group_setting,
)
from zerver.lib.users import get_inaccessible_user_ids
from zerver.models import NamedUserGroup, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.streams import Stream
from zerver.models.users import is_cross_realm_bot_email

BEFORE_MENTION_ALLOWED_REGEX = r"(?<![^\s\'\"\(\{\[\/<])"

# Match multi-word string between @** ** or match any one-word
# sequences after @
MENTIONS_RE = re.compile(
    rf"{BEFORE_MENTION_ALLOWED_REGEX}@(?P<silent>_?)(\*\*(?P<match>[^\*]+)\*\*)"
)
USER_GROUP_MENTIONS_RE = re.compile(
    rf"{BEFORE_MENTION_ALLOWED_REGEX}@(?P<silent>_?)(\*(?P<match>[^\*]+)\*)"
)

topic_wildcards = frozenset(["topic"])
stream_wildcards = frozenset(["all", "everyone", "stream", "channel"])


@dataclass
class FullNameInfo:
    id: int
    full_name: str
    is_active: bool


@dataclass
class UserFilter:
    id: int | None
    full_name: str | None

    def Q(self) -> Q:
        if self.full_name is not None and self.id is not None:
            return Q(full_name__iexact=self.full_name, id=self.id)
        elif self.id is not None:
            return Q(id=self.id)
        elif self.full_name is not None:
            return Q(full_name__iexact=self.full_name)
        else:
            raise AssertionError("totally empty filter makes no sense")


@dataclass
class MentionText:
    text: str | None
    is_topic_wildcard: bool
    is_stream_wildcard: bool


@dataclass
class PossibleMentions:
    mention_texts: set[str]
    message_has_topic_wildcards: bool
    message_has_stream_wildcards: bool


@dataclass(frozen=True)
class ChannelTopicInfo:
    channel_name: str
    topic_name: str


@dataclass
class ChannelInfo:
    channel_id: int
    recipient_id: int
    history_public_to_subscribers: bool
    # TODO: Track whether the current user has only metadata access or
    # content access, so that we can allow mentioning channels with
    # only metadata access, while still enforcing content access to
    # mention topics or messages within channels.


class MentionBackend:
    # Be careful about reuse: MentionBackend contains caches which are
    # designed to only have the lifespan of a sender user (typically a
    # single request).
    #
    # In particular, user_cache is not robust to message_sender
    # within the lifetime of a single MentionBackend lifetime.

    def __init__(self, realm_id: int) -> None:
        self.realm_id = realm_id
        self.user_cache: dict[tuple[int, str], FullNameInfo] = {}
        self.stream_cache: dict[str, ChannelInfo] = {}
        self.topic_cache: dict[ChannelTopicInfo, int | None] = {}

    def get_full_name_info_list(
        self, user_filters: list[UserFilter], message_sender: UserProfile | None
    ) -> list[FullNameInfo]:
        result: list[FullNameInfo] = []
        unseen_user_filters: list[UserFilter] = []

        # Try to get messages from the user_cache first.
        # This loop populates two lists:
        #  - results are the objects we pull from cache
        #  - unseen_user_filters are filters where need to hit the DB
        for user_filter in user_filters:
            # We expect callers who take advantage of our user_cache to supply both
            # id and full_name in the user mentions in their messages.
            if user_filter.id is not None and user_filter.full_name is not None:
                user = self.user_cache.get((user_filter.id, user_filter.full_name), None)
                if user is not None:
                    result.append(user)
                    continue

            # BOO! We have to go the database.
            unseen_user_filters.append(user_filter)

        # Most of the time, we have to go to the database to get user info,
        # unless our last loop found everything in the cache.
        if unseen_user_filters:
            q_list = [user_filter.Q() for user_filter in unseen_user_filters]

            rows = (
                UserProfile.objects.filter(
                    Q(realm_id=self.realm_id) | Q(email__in=settings.CROSS_REALM_BOT_EMAILS),
                )
                .filter(
                    functools.reduce(lambda a, b: a | b, q_list),
                )
                .only(
                    "id",
                    "full_name",
                    "is_active",
                )
            )

            possible_mention_user_ids = [row.id for row in rows]
            inaccessible_user_ids = get_inaccessible_user_ids(
                possible_mention_user_ids, message_sender
            )

            user_list = [
                FullNameInfo(id=row.id, full_name=row.full_name, is_active=row.is_active)
                for row in rows
                if row.id not in inaccessible_user_ids
            ]

            # We expect callers who take advantage of our cache to supply both
            # id and full_name in the user mentions in their messages.
            for user in user_list:
                self.user_cache[(user.id, user.full_name)] = user

            result += user_list

        return result

    def get_stream_name_map(
        self, stream_names: set[str], acting_user: UserProfile | None
    ) -> dict[str, int]:
        if not stream_names:
            return {}

        result: dict[str, int] = {}
        unseen_stream_names: list[str] = []

        for stream_name in stream_names:
            if stream_name in self.stream_cache:
                result[stream_name] = self.stream_cache[stream_name].channel_id
            else:
                unseen_stream_names.append(stream_name)

        if not unseen_stream_names:
            return result

        q_list = {Q(name=name) for name in unseen_stream_names}
        if acting_user is None:
            rows = (
                Stream.objects.filter(
                    realm_id=self.realm_id,
                )
                .filter(
                    functools.reduce(lambda a, b: a | b, q_list),
                )
                .values(
                    "id",
                    "name",
                    "recipient_id",
                    "history_public_to_subscribers",
                )
            )
            for row in rows:
                self.stream_cache[row["name"]] = ChannelInfo(
                    row["id"], row["recipient_id"], row["history_public_to_subscribers"]
                )
                result[row["name"]] = row["id"]
        else:
            content_access_streams = get_content_access_streams(
                acting_user,
                list(
                    Stream.objects.filter(
                        realm_id=self.realm_id,
                    ).filter(
                        functools.reduce(lambda a, b: a | b, q_list),
                    )
                ),
                user_group_membership_details=UserGroupMembershipDetails(
                    user_recursive_group_ids=None
                ),
            )
            for stream in content_access_streams:
                assert stream.recipient_id is not None
                self.stream_cache[stream.name] = ChannelInfo(
                    stream.id, stream.recipient_id, stream.history_public_to_subscribers
                )
                result[stream.name] = stream.id

        return result

    def get_topic_info_map(
        self, channel_topics: set[ChannelTopicInfo], acting_user: UserProfile | None
    ) -> dict[ChannelTopicInfo, int | None]:
        if not channel_topics:
            return {}

        result: dict[ChannelTopicInfo, int | None] = {}
        unseen_channel_topic: list[ChannelTopicInfo] = []

        for channel_topic in channel_topics:
            if channel_topic in self.topic_cache:
                result[channel_topic] = self.topic_cache[channel_topic]
            else:
                unseen_channel_topic.append(channel_topic)

        for channel_topic in unseen_channel_topic:
            channel_info = self.stream_cache.get(channel_topic.channel_name)

            if channel_info is None:
                # The acting user does not have access to content in this channel.
                continue

            recipient_id = channel_info.recipient_id
            topic_name = channel_topic.topic_name
            history_public_to_subscribers = channel_info.history_public_to_subscribers

            topic_latest_message = get_first_message_for_user_in_topic(
                self.realm_id,
                acting_user,
                recipient_id,
                topic_name,
                history_public_to_subscribers,
                acting_user_has_channel_content_access=True,
            )

            self.topic_cache[channel_topic] = topic_latest_message
            result[channel_topic] = topic_latest_message

        return result


def user_mention_matches_topic_wildcard(mention: str) -> bool:
    return mention in topic_wildcards


def user_mention_matches_stream_wildcard(mention: str) -> bool:
    return mention in stream_wildcards


def extract_mention_text(m: Match[str]) -> MentionText:
    text = m.group("match")
    if text in topic_wildcards:
        return MentionText(text=None, is_topic_wildcard=True, is_stream_wildcard=False)
    if text in stream_wildcards:
        return MentionText(text=None, is_topic_wildcard=False, is_stream_wildcard=True)
    return MentionText(text=text, is_topic_wildcard=False, is_stream_wildcard=False)


def possible_mentions(content: str) -> PossibleMentions:
    # mention texts can either be names, or an extended name|id syntax.
    texts = set()
    message_has_topic_wildcards = False
    message_has_stream_wildcards = False
    for m in MENTIONS_RE.finditer(content):
        mention_text = extract_mention_text(m)
        text = mention_text.text
        if text:
            texts.add(text)
        if mention_text.is_topic_wildcard:
            message_has_topic_wildcards = True
        if mention_text.is_stream_wildcard:
            message_has_stream_wildcards = True
    return PossibleMentions(
        mention_texts=texts,
        message_has_topic_wildcards=message_has_topic_wildcards,
        message_has_stream_wildcards=message_has_stream_wildcards,
    )


def possible_user_group_mentions(content: str) -> dict[str, Literal["silent", "non-silent"]]:
    # maps each group name to its mention type, silent or non-silent.
    mentions: dict[str, Literal["silent", "non-silent"]] = {}

    for mention in USER_GROUP_MENTIONS_RE.finditer(content):
        group_mention = mention.group("match")

        # non-silent mention can override silent.
        if not mention.group("silent"):
            mentions[group_mention] = "non-silent"

        # silent mention should NOT override non-silent.
        if mention.group("silent") and group_mention not in mentions:
            mentions[group_mention] = "silent"

    return mentions


def get_possible_mentions_info(
    mention_backend: MentionBackend, mention_texts: set[str], message_sender: UserProfile | None
) -> list[FullNameInfo]:
    if not mention_texts:
        return []

    user_filters = list()

    name_re = r"(?P<full_name>.+)?\|(?P<mention_id>\d+)$"
    for mention_text in mention_texts:
        name_syntax_match = re.match(name_re, mention_text)
        if name_syntax_match:
            full_name = name_syntax_match.group("full_name")
            mention_id = name_syntax_match.group("mention_id")
            if full_name:
                # For **name|id** mentions as mention_id
                # cannot be null inside this block.
                user_filters.append(UserFilter(full_name=full_name, id=int(mention_id)))
            else:
                # For **|id** syntax.
                user_filters.append(UserFilter(full_name=None, id=int(mention_id)))
        else:
            # For **name** syntax.
            user_filters.append(UserFilter(full_name=mention_text, id=None))

    return mention_backend.get_full_name_info_list(user_filters, message_sender)


class MentionData:
    def __init__(
        self, mention_backend: MentionBackend, content: str, message_sender: UserProfile | None
    ) -> None:
        self.mention_backend = mention_backend
        realm_id = mention_backend.realm_id
        self.message_sender = message_sender
        mentions = possible_mentions(content)
        possible_mentions_info = get_possible_mentions_info(
            mention_backend, mentions.mention_texts, message_sender
        )
        self.full_name_info = {row.full_name.lower(): row for row in possible_mentions_info}
        self.user_id_info = {row.id: row for row in possible_mentions_info}
        self.init_user_group_data(realm_id=realm_id, content=content)
        self.has_stream_wildcards = mentions.message_has_stream_wildcards
        self.has_topic_wildcards = mentions.message_has_topic_wildcards

    def message_has_stream_wildcards(self) -> bool:
        return self.has_stream_wildcards

    def message_has_topic_wildcards(self) -> bool:
        return self.has_topic_wildcards

    def init_user_group_data(self, realm_id: int, content: str) -> None:
        self.user_group_name_info: dict[str, NamedUserGroup] = {}
        self.user_group_members: dict[int, set[int]] = defaultdict(set)
        user_group_names_mentions = possible_user_group_mentions(content)
        if user_group_names_mentions:
            named_user_groups = NamedUserGroup.objects.filter(
                realm_id=realm_id, name__in=user_group_names_mentions
            )

            # No filter here as we need user_group_name_info for all groups mentions.
            self.user_group_name_info = {group.name.lower(): group for group in named_user_groups}

            # We only fetch group membership mentions that can
            # possibly trigger notifications.
            filtered_group_ids = [
                group.id
                for group in named_user_groups
                if not group.deactivated
                and user_group_names_mentions.get(group.name) == "non-silent"
            ]

            # Avoid doing a database query if there's nothing to fetch.
            #
            # This isn't quite optimal -- we've not checked our user
            # has permission to mention the group yet.
            if len(filtered_group_ids) == 0:
                return

            # Fetch membership for the groups filtered above in a
            # single, efficient bulk query, mapping each group to its
            # direct and indirect members.
            for group_root_id, member_id in (
                get_root_id_annotated_recursive_subgroups_for_groups(filtered_group_ids, realm_id)
                .filter(direct_members__is_active=True)
                .values_list("root_id", "direct_members")  # type: ignore[misc]  # root_id is an annotated field.
            ):
                self.user_group_members[group_root_id].add(member_id)

    def get_user_by_name(self, name: str) -> FullNameInfo | None:
        # warning: get_user_by_name is not dependable if two
        # users of the same full name are mentioned. Use
        # get_user_by_id where possible.
        return self.full_name_info.get(name.lower(), None)

    def get_user_by_id(self, id: int) -> FullNameInfo | None:
        return self.user_id_info.get(id, None)

    def get_user_ids(self) -> set[int]:
        """
        Returns the user IDs that might have been mentioned by this
        content.  Note that because this data structure has not parsed
        the message and does not know about escaping/code blocks, this
        will overestimate the list of user ids.
        """
        return set(self.user_id_info.keys())

    def get_user_group(self, name: str) -> NamedUserGroup | None:
        return self.user_group_name_info.get(name.lower(), None)

    def get_group_members(self, user_group_id: int) -> set[int]:
        return self.user_group_members.get(user_group_id, set())

    def get_stream_name_map(
        self, stream_names: set[str], acting_user: UserProfile | None
    ) -> dict[str, int]:
        return self.mention_backend.get_stream_name_map(stream_names, acting_user=acting_user)

    def get_topic_info_map(
        self, channel_topics: set[ChannelTopicInfo], acting_user: UserProfile | None
    ) -> dict[ChannelTopicInfo, int | None]:
        return self.mention_backend.get_topic_info_map(channel_topics, acting_user=acting_user)


def silent_mention_syntax_for_user(user_profile: UserProfile | UserDisplayRecipient) -> str:
    if isinstance(user_profile, UserProfile):
        return f"@_**{user_profile.full_name}|{user_profile.id}**"
    else:
        return f"@_**{user_profile['full_name']}|{user_profile['id']}**"


def silent_mention_syntax_for_user_group(user_group: NamedUserGroup) -> str:
    return f"@_*{user_group.name}*"


def get_user_group_mention_display_name(user_group: NamedUserGroup) -> StrPromise | str:
    if user_group.is_system_group:
        return SystemGroups.GROUP_DISPLAY_NAME_MAP[user_group.name]

    return user_group.name


def sender_can_mention_group(sender: UserProfile | None, named_group: NamedUserGroup) -> bool:
    can_mention_group = named_group.can_mention_group

    if (
        hasattr(can_mention_group, "named_user_group")
        and can_mention_group.named_user_group.name == SystemGroups.EVERYONE
    ):
        return True

    assert sender is not None

    if is_cross_realm_bot_email(sender.delivery_email):
        return False

    return user_has_permission_for_group_setting(
        can_mention_group.id,
        sender,
        NamedUserGroup.GROUP_PERMISSION_SETTINGS["can_mention_group"],
        direct_member_only=False,
    )
