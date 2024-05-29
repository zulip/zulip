import logging
import os
import random
import shutil
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)

import orjson
import requests
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now
from typing_extensions import TypeAlias

from zerver.data_import.sequencer import NEXT_ID
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.partial import partial
from zerver.lib.stream_color import STREAM_ASSIGNMENT_COLORS as STREAM_COLORS
from zerver.models import (
    Attachment,
    Huddle,
    Message,
    Realm,
    RealmEmoji,
    Recipient,
    Stream,
    Subscription,
    UserProfile,
)
from zproject.backends import all_default_backend_names

# stubs
ZerverFieldsT: TypeAlias = Dict[str, Any]


class SubscriberHandler:
    def __init__(self) -> None:
        self.stream_info: Dict[int, Set[int]] = {}
        self.huddle_info: Dict[int, Set[int]] = {}

    def set_info(
        self,
        users: Set[int],
        stream_id: Optional[int] = None,
        huddle_id: Optional[int] = None,
    ) -> None:
        if stream_id is not None:
            self.stream_info[stream_id] = users
        elif huddle_id is not None:
            self.huddle_info[huddle_id] = users
        else:
            raise AssertionError("stream_id or huddle_id is required")

    def get_users(
        self, stream_id: Optional[int] = None, huddle_id: Optional[int] = None
    ) -> Set[int]:
        if stream_id is not None:
            return self.stream_info[stream_id]
        elif huddle_id is not None:
            return self.huddle_info[huddle_id]
        else:
            raise AssertionError("stream_id or huddle_id is required")


def build_zerver_realm(
    realm_id: int, realm_subdomain: str, time: float, other_product: str
) -> List[ZerverFieldsT]:
    realm = Realm(
        id=realm_id,
        name=realm_subdomain,
        string_id=realm_subdomain,
        description=f"Organization imported from {other_product}!",
    )
    realm_dict = model_to_dict(realm)
    realm_dict["date_created"] = time
    # These fields are supposed to be generated upon import.
    del realm_dict["uuid"]
    del realm_dict["uuid_owner_secret"]

    return [realm_dict]


def build_user_profile(
    avatar_source: str,
    date_joined: Any,
    delivery_email: str,
    email: str,
    full_name: str,
    id: int,
    is_active: bool,
    role: int,
    is_mirror_dummy: bool,
    realm_id: int,
    short_name: str,
    timezone: str,
    is_bot: bool = False,
    bot_type: Optional[int] = None,
) -> ZerverFieldsT:
    obj = UserProfile(
        avatar_source=avatar_source,
        date_joined=date_joined,
        delivery_email=delivery_email,
        email=email,
        full_name=full_name,
        id=id,
        is_mirror_dummy=is_mirror_dummy,
        is_active=is_active,
        role=role,
        realm_id=realm_id,
        timezone=timezone,
        is_bot=is_bot,
        bot_type=bot_type,
    )
    dct = model_to_dict(obj)

    """
    Even though short_name is no longer in the Zulip
    UserProfile, it's helpful to have it in our import
    dictionaries for legacy reasons.
    """
    dct["short_name"] = short_name
    return dct


def build_avatar(
    zulip_user_id: int,
    realm_id: int,
    email: str,
    avatar_url: str,
    timestamp: Any,
    avatar_list: List[ZerverFieldsT],
) -> None:
    avatar = dict(
        path=avatar_url,  # Save original avatar URL here, which is downloaded later
        realm_id=realm_id,
        content_type=None,
        user_profile_id=zulip_user_id,
        last_modified=timestamp,
        user_profile_email=email,
        s3_path="",
        size="",
    )
    avatar_list.append(avatar)


def make_subscriber_map(zerver_subscription: List[ZerverFieldsT]) -> Dict[int, Set[int]]:
    """
    This can be convenient for building up UserMessage
    rows.
    """
    subscriber_map: Dict[int, Set[int]] = {}
    for sub in zerver_subscription:
        user_id = sub["user_profile"]
        recipient_id = sub["recipient"]
        if recipient_id not in subscriber_map:
            subscriber_map[recipient_id] = set()
        subscriber_map[recipient_id].add(user_id)

    return subscriber_map


def make_user_messages(
    zerver_message: List[ZerverFieldsT],
    subscriber_map: Dict[int, Set[int]],
    is_pm_data: bool,
    mention_map: Dict[int, Set[int]],
    wildcard_mention_map: Mapping[int, bool] = {},
) -> List[ZerverFieldsT]:
    zerver_usermessage = []

    for message in zerver_message:
        message_id = message["id"]
        recipient_id = message["recipient"]
        sender_id = message["sender"]
        mention_user_ids = mention_map[message_id]
        wildcard_mention = wildcard_mention_map.get(message_id, False)
        subscriber_ids = subscriber_map.get(recipient_id, set())
        user_ids = subscriber_ids | {sender_id}

        for user_id in user_ids:
            is_mentioned = user_id in mention_user_ids
            user_message = build_user_message(
                user_id=user_id,
                message_id=message_id,
                is_private=is_pm_data,
                is_mentioned=is_mentioned,
                wildcard_mention=wildcard_mention,
            )
            zerver_usermessage.append(user_message)

    return zerver_usermessage


def build_subscription(recipient_id: int, user_id: int, subscription_id: int) -> ZerverFieldsT:
    subscription = Subscription(color=random.choice(STREAM_COLORS), id=subscription_id)
    subscription_dict = model_to_dict(subscription, exclude=["user_profile", "recipient_id"])
    subscription_dict["user_profile"] = user_id
    subscription_dict["recipient"] = recipient_id
    return subscription_dict


class GetUsers(Protocol):
    def __call__(self, stream_id: int = ..., huddle_id: int = ...) -> Set[int]: ...


def build_stream_subscriptions(
    get_users: GetUsers,
    zerver_recipient: List[ZerverFieldsT],
    zerver_stream: List[ZerverFieldsT],
) -> List[ZerverFieldsT]:
    subscriptions: List[ZerverFieldsT] = []

    stream_ids = {stream["id"] for stream in zerver_stream}

    recipient_map = {
        recipient["id"]: recipient["type_id"]  # recipient_id -> stream_id
        for recipient in zerver_recipient
        if recipient["type"] == Recipient.STREAM and recipient["type_id"] in stream_ids
    }

    for recipient_id, stream_id in recipient_map.items():
        user_ids = get_users(stream_id=stream_id)
        for user_id in user_ids:
            subscription = build_subscription(
                recipient_id=recipient_id,
                user_id=user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            subscriptions.append(subscription)

    return subscriptions


def build_huddle_subscriptions(
    get_users: GetUsers,
    zerver_recipient: List[ZerverFieldsT],
    zerver_huddle: List[ZerverFieldsT],
) -> List[ZerverFieldsT]:
    subscriptions: List[ZerverFieldsT] = []

    huddle_ids = {huddle["id"] for huddle in zerver_huddle}

    recipient_map = {
        recipient["id"]: recipient["type_id"]  # recipient_id -> stream_id
        for recipient in zerver_recipient
        if recipient["type"] == Recipient.DIRECT_MESSAGE_GROUP
        and recipient["type_id"] in huddle_ids
    }

    for recipient_id, huddle_id in recipient_map.items():
        user_ids = get_users(huddle_id=huddle_id)
        for user_id in user_ids:
            subscription = build_subscription(
                recipient_id=recipient_id,
                user_id=user_id,
                subscription_id=NEXT_ID("subscription"),
            )
            subscriptions.append(subscription)

    return subscriptions


def build_personal_subscriptions(zerver_recipient: List[ZerverFieldsT]) -> List[ZerverFieldsT]:
    subscriptions: List[ZerverFieldsT] = []

    personal_recipients = [
        recipient for recipient in zerver_recipient if recipient["type"] == Recipient.PERSONAL
    ]

    for recipient in personal_recipients:
        recipient_id = recipient["id"]
        user_id = recipient["type_id"]
        subscription = build_subscription(
            recipient_id=recipient_id,
            user_id=user_id,
            subscription_id=NEXT_ID("subscription"),
        )
        subscriptions.append(subscription)

    return subscriptions


def build_recipient(type_id: int, recipient_id: int, type: int) -> ZerverFieldsT:
    recipient = Recipient(
        type_id=type_id,  # stream id
        id=recipient_id,
        type=type,
    )
    recipient_dict = model_to_dict(recipient)
    return recipient_dict


def build_recipients(
    zerver_userprofile: Iterable[ZerverFieldsT],
    zerver_stream: Iterable[ZerverFieldsT],
    zerver_huddle: Iterable[ZerverFieldsT] = [],
) -> List[ZerverFieldsT]:
    """
    This function was only used HipChat import, this function may be
    required for future conversions. The Slack conversions do it more
    tightly integrated with creating other objects.
    """

    recipients = []

    for user in zerver_userprofile:
        type_id = user["id"]
        type = Recipient.PERSONAL
        recipient = Recipient(
            type_id=type_id,
            id=NEXT_ID("recipient"),
            type=type,
        )
        recipient_dict = model_to_dict(recipient)
        recipients.append(recipient_dict)

    for stream in zerver_stream:
        type_id = stream["id"]
        type = Recipient.STREAM
        recipient = Recipient(
            type_id=type_id,
            id=NEXT_ID("recipient"),
            type=type,
        )
        recipient_dict = model_to_dict(recipient)
        recipients.append(recipient_dict)

    for huddle in zerver_huddle:
        type_id = huddle["id"]
        type = Recipient.DIRECT_MESSAGE_GROUP
        recipient = Recipient(
            type_id=type_id,
            id=NEXT_ID("recipient"),
            type=type,
        )
        recipient_dict = model_to_dict(recipient)
        recipients.append(recipient_dict)
    return recipients


def build_realm(
    zerver_realm: List[ZerverFieldsT], realm_id: int, domain_name: str
) -> ZerverFieldsT:
    realm = dict(
        zerver_client=[
            {"name": "populate_db", "id": 1},
            {"name": "website", "id": 2},
            {"name": "API", "id": 3},
        ],
        zerver_customprofilefield=[],
        zerver_customprofilefieldvalue=[],
        zerver_userpresence=[],  # shows last logged in data, which is not available
        zerver_userprofile_mirrordummy=[],
        zerver_realmdomain=[
            {"realm": realm_id, "allow_subdomains": False, "domain": domain_name, "id": realm_id}
        ],
        zerver_useractivity=[],
        zerver_realm=zerver_realm,
        zerver_huddle=[],
        zerver_userprofile_crossrealm=[],
        zerver_useractivityinterval=[],
        zerver_reaction=[],
        zerver_realmemoji=[],
        zerver_realmfilter=[],
        zerver_realmplayground=[],
        zerver_realmauthenticationmethod=[
            {"realm": realm_id, "name": name, "id": i}
            for i, name in enumerate(all_default_backend_names(), start=1)
        ],
    )
    return realm


def build_usermessages(
    zerver_usermessage: List[ZerverFieldsT],
    subscriber_map: Dict[int, Set[int]],
    recipient_id: int,
    mentioned_user_ids: List[int],
    message_id: int,
    is_private: bool,
    long_term_idle: AbstractSet[int] = set(),
) -> Tuple[int, int]:
    user_ids = subscriber_map.get(recipient_id, set())

    user_messages_created = 0
    user_messages_skipped = 0
    if user_ids:
        for user_id in sorted(user_ids):
            is_mentioned = user_id in mentioned_user_ids

            if not is_mentioned and not is_private and user_id in long_term_idle:
                # these users are long-term idle
                user_messages_skipped += 1
                continue
            user_messages_created += 1

            usermessage = build_user_message(
                user_id=user_id,
                message_id=message_id,
                is_private=is_private,
                is_mentioned=is_mentioned,
            )

            zerver_usermessage.append(usermessage)
    return (user_messages_created, user_messages_skipped)


def build_user_message(
    user_id: int,
    message_id: int,
    is_private: bool,
    is_mentioned: bool,
    wildcard_mention: bool = False,
) -> ZerverFieldsT:
    flags_mask = 1  # For read
    if is_mentioned:
        flags_mask += 8  # For mentioned
    if wildcard_mention:
        flags_mask += 16
    if is_private:
        flags_mask += 2048  # For is_private

    id = NEXT_ID("user_message")

    usermessage = dict(
        id=id,
        user_profile=user_id,
        message=message_id,
        flags_mask=flags_mask,
    )
    return usermessage


def build_defaultstream(realm_id: int, stream_id: int, defaultstream_id: int) -> ZerverFieldsT:
    defaultstream = dict(stream=stream_id, realm=realm_id, id=defaultstream_id)
    return defaultstream


def build_stream(
    date_created: Any,
    realm_id: int,
    name: str,
    description: str,
    stream_id: int,
    deactivated: bool = False,
    invite_only: bool = False,
    stream_post_policy: int = 1,
) -> ZerverFieldsT:
    # Other applications don't have the distinction of "private stream with public history"
    # vs "private stream with hidden history" - and we've traditionally imported private "streams"
    # of other products as private streams with hidden history.
    # So we can set the history_public_to_subscribers value based on the invite_only flag.
    history_public_to_subscribers = not invite_only

    stream = Stream(
        name=name,
        deactivated=deactivated,
        description=description.replace("\n", " "),
        # We don't set rendered_description here; it'll be added on import
        date_created=date_created,
        invite_only=invite_only,
        id=stream_id,
        stream_post_policy=stream_post_policy,
        history_public_to_subscribers=history_public_to_subscribers,
    )
    stream_dict = model_to_dict(stream, exclude=["realm"])
    stream_dict["realm"] = realm_id
    return stream_dict


def build_huddle(huddle_id: int) -> ZerverFieldsT:
    huddle = Huddle(
        id=huddle_id,
    )
    return model_to_dict(huddle)


def build_message(
    *,
    topic_name: str,
    date_sent: float,
    message_id: int,
    content: str,
    rendered_content: Optional[str],
    user_id: int,
    recipient_id: int,
    realm_id: int,
    has_image: bool = False,
    has_link: bool = False,
    has_attachment: bool = True,
) -> ZerverFieldsT:
    zulip_message = Message(
        rendered_content_version=1,  # this is Zulip specific
        id=message_id,
        content=content,
        rendered_content=rendered_content,
        has_image=has_image,
        has_attachment=has_attachment,
        has_link=has_link,
    )
    zulip_message.set_topic_name(topic_name)
    zulip_message_dict = model_to_dict(
        zulip_message, exclude=["recipient", "sender", "sending_client"]
    )
    zulip_message_dict["sender"] = user_id
    zulip_message_dict["sending_client"] = 1
    zulip_message_dict["recipient"] = recipient_id
    zulip_message_dict["date_sent"] = date_sent

    return zulip_message_dict


def build_attachment(
    realm_id: int,
    message_ids: Set[int],
    user_id: int,
    fileinfo: ZerverFieldsT,
    s3_path: str,
    zerver_attachment: List[ZerverFieldsT],
) -> None:
    """
    This function should be passed a 'fileinfo' dictionary, which contains
    information about 'size', 'created' (created time) and ['name'] (filename).
    """
    attachment_id = NEXT_ID("attachment")

    attachment = Attachment(
        id=attachment_id,
        size=fileinfo["size"],
        create_time=fileinfo["created"],
        is_realm_public=True,
        path_id=s3_path,
        file_name=fileinfo["name"],
    )

    attachment_dict = model_to_dict(attachment, exclude=["owner", "messages", "realm"])
    attachment_dict["owner"] = user_id
    attachment_dict["messages"] = list(message_ids)
    attachment_dict["realm"] = realm_id

    zerver_attachment.append(attachment_dict)


def get_avatar(avatar_dir: str, size_url_suffix: str, avatar_upload_item: List[str]) -> None:
    avatar_url = avatar_upload_item[0]

    image_path = os.path.join(avatar_dir, avatar_upload_item[1])
    original_image_path = os.path.join(avatar_dir, avatar_upload_item[2])

    response = requests.get(avatar_url + size_url_suffix, stream=True)
    with open(image_path, "wb") as image_file:
        shutil.copyfileobj(response.raw, image_file)
    shutil.copy(image_path, original_image_path)


def process_avatars(
    avatar_list: List[ZerverFieldsT],
    avatar_dir: str,
    realm_id: int,
    threads: int,
    size_url_suffix: str = "",
) -> List[ZerverFieldsT]:
    """
    This function gets the avatar of the user and saves it in the
    user's avatar directory with both the extensions '.png' and '.original'
    Required parameters:

    1. avatar_list: List of avatars to be mapped in avatars records.json file
    2. avatar_dir: Folder where the downloaded avatars are saved
    3. realm_id: Realm ID.

    We use this for Slack conversions, where avatars need to be
    downloaded.  For simpler conversions see write_avatar_png.
    """

    logging.info("######### GETTING AVATARS #########\n")
    logging.info("DOWNLOADING AVATARS .......\n")
    avatar_original_list = []
    avatar_upload_list = []
    for avatar in avatar_list:
        avatar_hash = user_avatar_path_from_ids(avatar["user_profile_id"], realm_id)
        avatar_url = avatar["path"]
        avatar_original = dict(avatar)

        image_path = f"{avatar_hash}.png"
        original_image_path = f"{avatar_hash}.original"

        avatar_upload_list.append([avatar_url, image_path, original_image_path])
        # We don't add the size field here in avatar's records.json,
        # since the metadata is not needed on the import end, and we
        # don't have it until we've downloaded the files anyway.
        avatar["path"] = image_path
        avatar["s3_path"] = image_path

        avatar_original["path"] = original_image_path
        avatar_original["s3_path"] = original_image_path
        avatar_original_list.append(avatar_original)

    # Run downloads in parallel
    run_parallel_wrapper(
        partial(get_avatar, avatar_dir, size_url_suffix), avatar_upload_list, threads=threads
    )

    logging.info("######### GETTING AVATARS FINISHED #########\n")
    return avatar_list + avatar_original_list


ListJobData = TypeVar("ListJobData")


def wrapping_function(f: Callable[[ListJobData], None], item: ListJobData) -> None:
    try:
        f(item)
    except Exception:
        logging.exception("Error processing item: %s", item, stack_info=True)


def run_parallel_wrapper(
    f: Callable[[ListJobData], None], full_items: List[ListJobData], threads: int = 6
) -> None:
    logging.info("Distributing %s items across %s threads", len(full_items), threads)

    with ProcessPoolExecutor(max_workers=threads) as executor:
        for count, future in enumerate(
            as_completed(executor.submit(wrapping_function, f, item) for item in full_items), 1
        ):
            future.result()
            if count % 1000 == 0:
                logging.info("Finished %s items", count)


def get_uploads(upload_dir: str, upload: List[str]) -> None:
    upload_url = upload[0]
    upload_path = upload[1]
    upload_path = os.path.join(upload_dir, upload_path)

    response = requests.get(upload_url, stream=True)
    os.makedirs(os.path.dirname(upload_path), exist_ok=True)
    with open(upload_path, "wb") as upload_file:
        shutil.copyfileobj(response.raw, upload_file)


def process_uploads(
    upload_list: List[ZerverFieldsT], upload_dir: str, threads: int
) -> List[ZerverFieldsT]:
    """
    This function downloads the uploads and saves it in the realm's upload directory.
    Required parameters:

    1. upload_list: List of uploads to be mapped in uploads records.json file
    2. upload_dir: Folder where the downloaded uploads are saved
    """
    logging.info("######### GETTING ATTACHMENTS #########\n")
    logging.info("DOWNLOADING ATTACHMENTS .......\n")
    upload_url_list = []
    for upload in upload_list:
        upload_url = upload["path"]
        upload_s3_path = upload["s3_path"]
        upload_url_list.append([upload_url, upload_s3_path])
        upload["path"] = upload_s3_path

    # Run downloads in parallel
    run_parallel_wrapper(partial(get_uploads, upload_dir), upload_url_list, threads=threads)

    logging.info("######### GETTING ATTACHMENTS FINISHED #########\n")
    return upload_list


def build_realm_emoji(realm_id: int, name: str, id: int, file_name: str) -> ZerverFieldsT:
    return model_to_dict(
        RealmEmoji(
            realm_id=realm_id,
            name=name,
            id=id,
            file_name=file_name,
        ),
    )


def get_emojis(emoji_dir: str, upload: List[str]) -> None:
    emoji_url = upload[0]
    emoji_path = upload[1]
    upload_emoji_path = os.path.join(emoji_dir, emoji_path)

    response = requests.get(emoji_url, stream=True)
    os.makedirs(os.path.dirname(upload_emoji_path), exist_ok=True)
    with open(upload_emoji_path, "wb") as emoji_file:
        shutil.copyfileobj(response.raw, emoji_file)


def process_emojis(
    zerver_realmemoji: List[ZerverFieldsT],
    emoji_dir: str,
    emoji_url_map: ZerverFieldsT,
    threads: int,
) -> List[ZerverFieldsT]:
    """
    This function downloads the custom emojis and saves in the output emoji folder.
    Required parameters:

    1. zerver_realmemoji: List of all RealmEmoji objects to be imported
    2. emoji_dir: Folder where the downloaded emojis are saved
    3. emoji_url_map: Maps emoji name to its url
    """
    emoji_records = []
    upload_emoji_list = []
    logging.info("######### GETTING EMOJIS #########\n")
    logging.info("DOWNLOADING EMOJIS .......\n")
    for emoji in zerver_realmemoji:
        emoji_url = emoji_url_map[emoji["name"]]
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=emoji["realm"], emoji_file_name=emoji["name"]
        )

        upload_emoji_list.append([emoji_url, emoji_path])

        emoji_record = dict(emoji)
        emoji_record["path"] = emoji_path
        emoji_record["s3_path"] = emoji_path
        emoji_record["realm_id"] = emoji_record["realm"]
        emoji_record.pop("realm")

        emoji_records.append(emoji_record)

    # Run downloads in parallel
    run_parallel_wrapper(partial(get_emojis, emoji_dir), upload_emoji_list, threads=threads)

    logging.info("######### GETTING EMOJIS FINISHED #########\n")
    return emoji_records


def create_converted_data_files(data: Any, output_dir: str, file_path: str) -> None:
    output_file = output_dir + file_path
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "wb") as fp:
        fp.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))


# External user-id
ExternalId = TypeVar("ExternalId")


def long_term_idle_helper(
    message_iterator: Iterator[ZerverFieldsT],
    user_from_message: Callable[[ZerverFieldsT], Optional[ExternalId]],
    timestamp_from_message: Callable[[ZerverFieldsT], float],
    zulip_user_id_from_user: Callable[[ExternalId], int],
    all_user_ids_iterator: Iterator[ExternalId],
    zerver_userprofile: List[ZerverFieldsT],
) -> Set[int]:
    """Algorithmically, we treat users who have sent at least 10 messages
    or have sent a message within the last 60 days as active.
    Everyone else is treated as long-term idle, which means they will
    have a slightly slower first page load when coming back to
    Zulip.
    """
    sender_counts: Dict[ExternalId, int] = defaultdict(int)
    recent_senders: Set[ExternalId] = set()
    NOW = float(timezone_now().timestamp())
    for message in message_iterator:
        timestamp = timestamp_from_message(message)
        user = user_from_message(message)
        if user is None:
            continue

        if user in recent_senders:
            continue

        if NOW - timestamp < 60 * 24 * 60 * 60:
            recent_senders.add(user)

        sender_counts[user] += 1
    for user, count in sender_counts.items():
        if count > 10:
            recent_senders.add(user)

    long_term_idle = set()

    for user_id in all_user_ids_iterator:
        if user_id in recent_senders:
            continue
        zulip_user_id = zulip_user_id_from_user(user_id)
        long_term_idle.add(zulip_user_id)

    for user_profile_row in zerver_userprofile:
        if user_profile_row["id"] in long_term_idle:
            user_profile_row["long_term_idle"] = True
            # Setting last_active_message_id to 1 means the user, if
            # imported, will get the full message history for the
            # streams they were on.
            user_profile_row["last_active_message_id"] = 1

    return long_term_idle
