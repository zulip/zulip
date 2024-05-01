import functools
import re
from dataclasses import dataclass
from typing import Dict, List, Match, Optional, Set, Tuple

from django.conf import settings
from django.db.models import Q

from zerver.lib.users import get_inaccessible_user_ids
from zerver.models import NamedUserGroup, UserProfile
from zerver.models.streams import get_linkable_streams

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
    id: Optional[int]
    full_name: Optional[str]

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
    text: Optional[str]
    is_topic_wildcard: bool
    is_stream_wildcard: bool


@dataclass
class PossibleMentions:
    mention_texts: Set[str]
    message_has_topic_wildcards: bool
    message_has_stream_wildcards: bool


class MentionBackend:
    # Be careful about reuse: MentionBackend contains caches which are
    # designed to only have the lifespan of a sender user (typically a
    # single request).
    #
    # In particular, user_cache is not robust to message_sender
    # within the lifetime of a single MentionBackend lifetime.

    def __init__(self, realm_id: int) -> None:
        self.realm_id = realm_id
        self.user_cache: Dict[Tuple[int, str], FullNameInfo] = {}
        self.stream_cache: Dict[str, int] = {}

    def get_full_name_info_list(
        self, user_filters: List[UserFilter], message_sender: Optional[UserProfile]
    ) -> List[FullNameInfo]:
        result: List[FullNameInfo] = []
        unseen_user_filters: List[UserFilter] = []

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

    def get_stream_name_map(self, stream_names: Set[str]) -> Dict[str, int]:
        if not stream_names:
            return {}

        result: Dict[str, int] = {}
        unseen_stream_names: List[str] = []

        for stream_name in stream_names:
            if stream_name in self.stream_cache:
                result[stream_name] = self.stream_cache[stream_name]
            else:
                unseen_stream_names.append(stream_name)

        if unseen_stream_names:
            q_list = {Q(name=name) for name in unseen_stream_names}

            rows = (
                get_linkable_streams(
                    realm_id=self.realm_id,
                )
                .filter(
                    functools.reduce(lambda a, b: a | b, q_list),
                )
                .values(
                    "id",
                    "name",
                )
            )

            for row in rows:
                self.stream_cache[row["name"]] = row["id"]
                result[row["name"]] = row["id"]

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


def possible_user_group_mentions(content: str) -> Set[str]:
    return {m.group("match") for m in USER_GROUP_MENTIONS_RE.finditer(content)}


def get_possible_mentions_info(
    mention_backend: MentionBackend, mention_texts: Set[str], message_sender: Optional[UserProfile]
) -> List[FullNameInfo]:
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
        self, mention_backend: MentionBackend, content: str, message_sender: Optional[UserProfile]
    ) -> None:
        self.mention_backend = mention_backend
        realm_id = mention_backend.realm_id
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
        self.user_group_name_info: Dict[str, NamedUserGroup] = {}
        self.user_group_members: Dict[int, List[int]] = {}
        user_group_names = possible_user_group_mentions(content)
        if user_group_names:
            for group in NamedUserGroup.objects.filter(
                realm_id=realm_id, name__in=user_group_names, is_system_group=False
            ).prefetch_related("direct_members"):
                self.user_group_name_info[group.name.lower()] = group
                self.user_group_members[group.id] = [m.id for m in group.direct_members.all()]

    def get_user_by_name(self, name: str) -> Optional[FullNameInfo]:
        # warning: get_user_by_name is not dependable if two
        # users of the same full name are mentioned. Use
        # get_user_by_id where possible.
        return self.full_name_info.get(name.lower(), None)

    def get_user_by_id(self, id: int) -> Optional[FullNameInfo]:
        return self.user_id_info.get(id, None)

    def get_user_ids(self) -> Set[int]:
        """
        Returns the user IDs that might have been mentioned by this
        content.  Note that because this data structure has not parsed
        the message and does not know about escaping/code blocks, this
        will overestimate the list of user ids.
        """
        return set(self.user_id_info.keys())

    def get_user_group(self, name: str) -> Optional[NamedUserGroup]:
        return self.user_group_name_info.get(name.lower(), None)

    def get_group_members(self, user_group_id: int) -> List[int]:
        return self.user_group_members.get(user_group_id, [])

    def get_stream_name_map(self, stream_names: Set[str]) -> Dict[str, int]:
        return self.mention_backend.get_stream_name_map(stream_names)


def silent_mention_syntax_for_user(user_profile: UserProfile) -> str:
    return f"@_**{user_profile.full_name}|{user_profile.id}**"
