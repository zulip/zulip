"""
spec:
https://docs.mattermost.com/administration/bulk-export.html
"""

import logging
import os
import random
import re
import secrets
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Set, Tuple

import orjson
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    SubscriberHandler,
    ZerverFieldsT,
    build_attachment,
    build_huddle,
    build_huddle_subscriptions,
    build_message,
    build_personal_subscriptions,
    build_realm,
    build_realm_emoji,
    build_recipients,
    build_stream,
    build_stream_subscriptions,
    build_user_profile,
    build_zerver_realm,
    create_converted_data_files,
    make_subscriber_map,
    make_user_messages,
)
from zerver.data_import.sequencer import NEXT_ID, IdMapper
from zerver.data_import.user_handler import UserHandler
from zerver.lib.emoji import name_to_codepoint
from zerver.lib.markdown import IMAGE_EXTENSIONS
from zerver.lib.upload.base import sanitize_name
from zerver.lib.utils import process_list_in_batches
from zerver.models import Reaction, RealmEmoji, Recipient, UserProfile


def make_realm(realm_id: int, team: Dict[str, Any]) -> ZerverFieldsT:
    # set correct realm details
    NOW = float(timezone_now().timestamp())
    domain_name = settings.EXTERNAL_HOST
    realm_subdomain = team["name"]

    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW, "Mattermost")
    realm = build_realm(zerver_realm, realm_id, domain_name)

    # We may override these later.
    realm["zerver_defaultstream"] = []

    return realm


def process_user(
    user_dict: Dict[str, Any], realm_id: int, team_name: str, user_id_mapper: IdMapper
) -> ZerverFieldsT:
    def is_team_admin(user_dict: Dict[str, Any]) -> bool:
        if user_dict["teams"] is None:
            return False
        return any(
            team["name"] == team_name and "team_admin" in team["roles"]
            for team in user_dict["teams"]
        )

    def is_team_guest(user_dict: Dict[str, Any]) -> bool:
        if user_dict["teams"] is None:
            return False
        for team in user_dict["teams"]:
            if team["name"] == team_name and "team_guest" in team["roles"]:
                return True
        return False

    def get_full_name(user_dict: Dict[str, Any]) -> str:
        full_name = "{} {}".format(user_dict["first_name"], user_dict["last_name"])
        if full_name.strip():
            return full_name
        return user_dict["username"]

    avatar_source = "G"
    full_name = get_full_name(user_dict)
    id = user_id_mapper.get(user_dict["username"])
    delivery_email = user_dict["email"]
    email = user_dict["email"]
    short_name = user_dict["username"]
    date_joined = int(timezone_now().timestamp())
    timezone = "UTC"

    if is_team_admin(user_dict):
        role = UserProfile.ROLE_REALM_OWNER
    elif is_team_guest(user_dict):
        role = UserProfile.ROLE_GUEST
    else:
        role = UserProfile.ROLE_MEMBER

    if user_dict["is_mirror_dummy"]:
        is_active = False
        is_mirror_dummy = True
    else:
        is_active = True
        is_mirror_dummy = False

    return build_user_profile(
        avatar_source=avatar_source,
        date_joined=date_joined,
        delivery_email=delivery_email,
        email=email,
        full_name=full_name,
        id=id,
        is_active=is_active,
        role=role,
        is_mirror_dummy=is_mirror_dummy,
        realm_id=realm_id,
        short_name=short_name,
        timezone=timezone,
    )


def convert_user_data(
    user_handler: UserHandler,
    user_id_mapper: IdMapper,
    user_data_map: Dict[str, Dict[str, Any]],
    realm_id: int,
    team_name: str,
) -> None:
    user_data_list = []
    for username in user_data_map:
        user = user_data_map[username]
        if check_user_in_team(user, team_name) or user["is_mirror_dummy"]:
            user_data_list.append(user)

    for raw_item in user_data_list:
        user = process_user(raw_item, realm_id, team_name, user_id_mapper)
        user_handler.add_user(user)


def convert_channel_data(
    channel_data: List[ZerverFieldsT],
    user_data_map: Dict[str, Dict[str, Any]],
    subscriber_handler: SubscriberHandler,
    stream_id_mapper: IdMapper,
    user_id_mapper: IdMapper,
    realm_id: int,
    team_name: str,
) -> List[ZerverFieldsT]:
    channel_data_list = [d for d in channel_data if d["team"] == team_name]

    channel_members_map: Dict[str, List[str]] = {}
    channel_admins_map: Dict[str, List[str]] = {}

    def initialize_stream_membership_dicts() -> None:
        for channel in channel_data:
            channel_name = channel["name"]
            channel_members_map[channel_name] = []
            channel_admins_map[channel_name] = []

        for username in user_data_map:
            user_dict = user_data_map[username]
            teams = user_dict["teams"]
            if user_dict["teams"] is None:
                continue

            for team in teams:
                if team["name"] != team_name:
                    continue
                for channel in team["channels"]:
                    channel_roles = channel["roles"]
                    channel_name = channel["name"]
                    if "channel_admin" in channel_roles:
                        channel_admins_map[channel_name].append(username)
                    elif "channel_user" in channel_roles:
                        channel_members_map[channel_name].append(username)

    def get_invite_only_value_from_channel_type(channel_type: str) -> bool:
        # Channel can have two types in Mattermost
        # "O" for a public channel.
        # "P" for a private channel.
        if channel_type == "O":
            return False
        elif channel_type == "P":
            return True
        else:  # nocoverage
            raise Exception("unexpected value")

    streams = []
    initialize_stream_membership_dicts()

    for channel_dict in channel_data_list:
        now = int(timezone_now().timestamp())
        stream_id = stream_id_mapper.get(channel_dict["name"])
        stream_name = channel_dict["name"]
        invite_only = get_invite_only_value_from_channel_type(channel_dict["type"])

        stream = build_stream(
            date_created=now,
            realm_id=realm_id,
            name=channel_dict["display_name"],
            # Purpose describes how the channel should be used. It is similar to
            # stream description and is shown in channel list to help others decide
            # whether to join.
            # Header text always appears right next to channel name in channel header.
            # Can be used for advertising the purpose of stream, making announcements as
            # well as including frequently used links. So probably not a bad idea to use
            # this as description if the channel purpose is empty.
            description=channel_dict["purpose"] or channel_dict["header"],
            stream_id=stream_id,
            # Mattermost export don't include data of archived(~ deactivated) channels.
            deactivated=False,
            invite_only=invite_only,
        )

        channel_users = set()
        for username in channel_admins_map[stream_name]:
            channel_users.add(user_id_mapper.get(username))

        for username in channel_members_map[stream_name]:
            channel_users.add(user_id_mapper.get(username))

        subscriber_handler.set_info(
            users=channel_users,
            stream_id=stream_id,
        )
        streams.append(stream)
    return streams


def generate_huddle_name(huddle_members: List[str]) -> str:
    # Simple hash function to generate a unique hash key for the
    # members of a huddle.  Needs to be consistent only within the
    # lifetime of export tool run, as it doesn't appear in the output.
    import hashlib

    return hashlib.md5("".join(sorted(huddle_members)).encode()).hexdigest()


def convert_huddle_data(
    huddle_data: List[ZerverFieldsT],
    user_data_map: Dict[str, Dict[str, Any]],
    subscriber_handler: SubscriberHandler,
    huddle_id_mapper: IdMapper,
    user_id_mapper: IdMapper,
    realm_id: int,
    team_name: str,
) -> List[ZerverFieldsT]:
    zerver_huddle = []
    for huddle in huddle_data:
        if len(huddle["members"]) > 2:
            huddle_name = generate_huddle_name(huddle["members"])
            huddle_id = huddle_id_mapper.get(huddle_name)
            huddle_dict = build_huddle(huddle_id)
            huddle_user_ids = set()
            for username in huddle["members"]:
                huddle_user_ids.add(user_id_mapper.get(username))
            subscriber_handler.set_info(
                users=huddle_user_ids,
                huddle_id=huddle_id,
            )
            zerver_huddle.append(huddle_dict)
    return zerver_huddle


def build_reactions(
    realm_id: int,
    total_reactions: List[ZerverFieldsT],
    reactions: List[ZerverFieldsT],
    message_id: int,
    user_id_mapper: IdMapper,
    zerver_realmemoji: List[ZerverFieldsT],
) -> None:
    realmemoji = {}
    for realm_emoji in zerver_realmemoji:
        realmemoji[realm_emoji["name"]] = realm_emoji["id"]

    # For the Unicode emoji codes, we use equivalent of
    # function 'get_emoji_data' in 'zerver/lib/emoji' here
    for mattermost_reaction in reactions:
        emoji_name = mattermost_reaction["emoji_name"]
        username = mattermost_reaction["user"]
        # Check in Unicode emoji
        if emoji_name in name_to_codepoint:
            emoji_code = name_to_codepoint[emoji_name]
            reaction_type = Reaction.UNICODE_EMOJI
        # Check in realm emoji
        elif emoji_name in realmemoji:
            emoji_code = realmemoji[emoji_name]
            reaction_type = Reaction.REALM_EMOJI
        else:  # nocoverage
            continue

        if not user_id_mapper.has(username):
            continue

        reaction_id = NEXT_ID("reaction")
        reaction = Reaction(
            id=reaction_id,
            emoji_code=emoji_code,
            emoji_name=emoji_name,
            reaction_type=reaction_type,
        )

        reaction_dict = model_to_dict(reaction, exclude=["message", "user_profile"])
        reaction_dict["message"] = message_id
        reaction_dict["user_profile"] = user_id_mapper.get(username)
        total_reactions.append(reaction_dict)


def get_mentioned_user_ids(raw_message: Dict[str, Any], user_id_mapper: IdMapper) -> Set[int]:
    user_ids = set()
    content = raw_message["content"]

    # usernames can be of the form user.name, user_name, username., username_, user.name_ etc
    matches = re.findall(r"(?<=^|(?<=[^a-zA-Z0-9-_.]))@(([A-Za-z0-9]+[_.]?)+)", content)

    for match in matches:
        possible_username = match[0]
        if user_id_mapper.has(possible_username):
            user_ids.add(user_id_mapper.get(possible_username))
    return user_ids


def process_message_attachments(
    attachments: List[Dict[str, Any]],
    realm_id: int,
    message_id: int,
    user_id: int,
    user_handler: UserHandler,
    zerver_attachment: List[ZerverFieldsT],
    uploads_list: List[ZerverFieldsT],
    mattermost_data_dir: str,
    output_dir: str,
) -> Tuple[str, bool]:
    has_image = False

    markdown_links = []

    for attachment in attachments:
        attachment_path = attachment["path"]
        attachment_full_path = os.path.join(mattermost_data_dir, "data", attachment_path)

        file_name = attachment_path.split("/")[-1]
        file_ext = f'.{file_name.split(".")[-1]}'

        if file_ext.lower() in IMAGE_EXTENSIONS:
            has_image = True

        s3_path = "/".join(
            [
                str(realm_id),
                format(random.randint(0, 255), "x"),
                secrets.token_urlsafe(18),
                sanitize_name(file_name),
            ]
        )
        content_for_link = f"[{file_name}](/user_uploads/{s3_path})"

        markdown_links.append(content_for_link)

        fileinfo = {
            "name": file_name,
            "size": os.path.getsize(attachment_full_path),
            "created": os.path.getmtime(attachment_full_path),
        }

        upload = dict(
            path=s3_path,
            realm_id=realm_id,
            content_type=None,
            user_profile_id=user_id,
            last_modified=fileinfo["created"],
            user_profile_email=user_handler.get_user(user_id=user_id)["email"],
            s3_path=s3_path,
            size=fileinfo["size"],
        )
        uploads_list.append(upload)

        build_attachment(
            realm_id=realm_id,
            message_ids={message_id},
            user_id=user_id,
            fileinfo=fileinfo,
            s3_path=s3_path,
            zerver_attachment=zerver_attachment,
        )

        # Copy the attachment file to output_dir
        attachment_out_path = os.path.join(output_dir, "uploads", s3_path)
        os.makedirs(os.path.dirname(attachment_out_path), exist_ok=True)
        shutil.copyfile(attachment_full_path, attachment_out_path)

    content = "\n".join(markdown_links)

    return content, has_image


def process_raw_message_batch(
    realm_id: int,
    raw_messages: List[Dict[str, Any]],
    subscriber_map: Dict[int, Set[int]],
    user_id_mapper: IdMapper,
    user_handler: UserHandler,
    get_recipient_id_from_receiver_name: Callable[[str, int], int],
    is_pm_data: bool,
    output_dir: str,
    zerver_realmemoji: List[Dict[str, Any]],
    total_reactions: List[Dict[str, Any]],
    uploads_list: List[ZerverFieldsT],
    zerver_attachment: List[ZerverFieldsT],
    mattermost_data_dir: str,
) -> None:
    def fix_mentions(content: str, mention_user_ids: Set[int]) -> str:
        for user_id in mention_user_ids:
            user = user_handler.get_user(user_id=user_id)
            mattermost_mention = "@{short_name}".format(**user)
            zulip_mention = "@**{full_name}**".format(**user)
            content = content.replace(mattermost_mention, zulip_mention)

        content = content.replace("@channel", "@**all**")
        content = content.replace("@all", "@**all**")
        # We don't have an equivalent for Mattermost's @here mention which mentions all users
        # online in the channel.
        content = content.replace("@here", "@**all**")
        return content

    mention_map: Dict[int, Set[int]] = {}
    zerver_message = []

    pm_members = {}

    for raw_message in raw_messages:
        message_id = NEXT_ID("message")
        mention_user_ids = get_mentioned_user_ids(raw_message, user_id_mapper)
        mention_map[message_id] = mention_user_ids

        content = fix_mentions(
            content=raw_message["content"],
            mention_user_ids=mention_user_ids,
        )

        # html2text is GPL licensed, so run it as a subprocess.
        content = subprocess.check_output(["html2text"], input=content, text=True)

        if len(content) > 10000:  # nocoverage
            logging.info("skipping too-long message of length %s", len(content))
            continue

        date_sent = raw_message["date_sent"]
        sender_user_id = raw_message["sender_id"]
        if "channel_name" in raw_message:
            recipient_id = get_recipient_id_from_receiver_name(
                raw_message["channel_name"], Recipient.STREAM
            )
        elif "huddle_name" in raw_message:
            recipient_id = get_recipient_id_from_receiver_name(
                raw_message["huddle_name"], Recipient.DIRECT_MESSAGE_GROUP
            )
        elif "pm_members" in raw_message:
            members = raw_message["pm_members"]
            member_ids = {user_id_mapper.get(member) for member in members}
            pm_members[message_id] = member_ids
            if sender_user_id == user_id_mapper.get(members[0]):
                recipient_id = get_recipient_id_from_receiver_name(members[1], Recipient.PERSONAL)
            else:
                recipient_id = get_recipient_id_from_receiver_name(members[0], Recipient.PERSONAL)
        else:
            raise AssertionError("raw_message without channel_name, huddle_name or pm_members key")

        rendered_content = None

        has_attachment = False
        has_image = False
        has_link = False
        if "attachments" in raw_message:
            has_attachment = True
            has_link = True

            attachment_markdown, has_image = process_message_attachments(
                attachments=raw_message["attachments"],
                realm_id=realm_id,
                message_id=message_id,
                user_id=sender_user_id,
                user_handler=user_handler,
                zerver_attachment=zerver_attachment,
                uploads_list=uploads_list,
                mattermost_data_dir=mattermost_data_dir,
                output_dir=output_dir,
            )

            content += attachment_markdown

        topic_name = "imported from mattermost"

        message = build_message(
            content=content,
            message_id=message_id,
            date_sent=date_sent,
            recipient_id=recipient_id,
            realm_id=realm_id,
            rendered_content=rendered_content,
            topic_name=topic_name,
            user_id=sender_user_id,
            has_image=has_image,
            has_link=has_link,
            has_attachment=has_attachment,
        )
        zerver_message.append(message)
        build_reactions(
            realm_id,
            total_reactions,
            raw_message["reactions"],
            message_id,
            user_id_mapper,
            zerver_realmemoji,
        )

    zerver_usermessage = make_user_messages(
        zerver_message=zerver_message,
        subscriber_map=subscriber_map,
        is_pm_data=is_pm_data,
        mention_map=mention_map,
    )

    message_json = dict(
        zerver_message=zerver_message,
        zerver_usermessage=zerver_usermessage,
    )

    dump_file_id = NEXT_ID("dump_file_id" + str(realm_id))
    message_file = f"/messages-{dump_file_id:06}.json"
    create_converted_data_files(message_json, output_dir, message_file)


def process_posts(
    num_teams: int,
    team_name: str,
    realm_id: int,
    post_data: List[Dict[str, Any]],
    get_recipient_id_from_receiver_name: Callable[[str, int], int],
    subscriber_map: Dict[int, Set[int]],
    output_dir: str,
    is_pm_data: bool,
    masking_content: bool,
    user_id_mapper: IdMapper,
    user_handler: UserHandler,
    zerver_realmemoji: List[Dict[str, Any]],
    total_reactions: List[Dict[str, Any]],
    uploads_list: List[ZerverFieldsT],
    zerver_attachment: List[ZerverFieldsT],
    mattermost_data_dir: str,
) -> None:
    post_data_list = []
    for post in post_data:
        if "team" not in post:
            # Mattermost doesn't specify a team for direct messages
            # in its export format.  This line of code requires that
            # we only be importing data from a single team (checked
            # elsewhere) -- we just assume it's the target team.
            post_team = team_name
        else:
            post_team = post["team"]
        if post_team == team_name:
            post_data_list.append(post)

    def message_to_dict(post_dict: Dict[str, Any]) -> Dict[str, Any]:
        sender_username = post_dict["user"]
        sender_id = user_id_mapper.get(sender_username)
        content = post_dict["message"]

        if masking_content:
            content = re.sub(r"[a-z]", "x", content)
            content = re.sub(r"[A-Z]", "X", content)

        if "reactions" in post_dict:
            reactions = post_dict["reactions"] or []
        else:
            reactions = []

        message_dict = dict(
            sender_id=sender_id,
            content=content,
            date_sent=int(post_dict["create_at"] / 1000),
            reactions=reactions,
        )
        if "channel" in post_dict:
            message_dict["channel_name"] = post_dict["channel"]
        elif "channel_members" in post_dict:
            # This case is for handling posts from direct messages and huddles,
            # not channels. Direct messages and huddles are known as direct_channels
            # in Slack and hence the name channel_members.
            channel_members = post_dict["channel_members"]
            if len(channel_members) > 2:
                message_dict["huddle_name"] = generate_huddle_name(channel_members)
            elif len(channel_members) == 2:
                message_dict["pm_members"] = channel_members
        else:
            raise AssertionError("Post without channel or channel_members key.")

        if post_dict.get("attachments"):
            message_dict["attachments"] = post_dict["attachments"]

        return message_dict

    raw_messages = []
    for post_dict in post_data_list:
        raw_messages.append(message_to_dict(post_dict))
        message_replies = post_dict["replies"]
        # Replies to a message in Mattermost are stored in the main message object.
        # For now, we just append the replies immediately after the original message.
        if message_replies is not None:
            for reply in message_replies:
                if "channel" in post_dict:
                    reply["channel"] = post_dict["channel"]
                else:  # nocoverage
                    reply["channel_members"] = post_dict["channel_members"]
                raw_messages.append(message_to_dict(reply))

    def process_batch(lst: List[Dict[str, Any]]) -> None:
        process_raw_message_batch(
            realm_id=realm_id,
            raw_messages=lst,
            subscriber_map=subscriber_map,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
            get_recipient_id_from_receiver_name=get_recipient_id_from_receiver_name,
            is_pm_data=is_pm_data,
            output_dir=output_dir,
            zerver_realmemoji=zerver_realmemoji,
            total_reactions=total_reactions,
            uploads_list=uploads_list,
            zerver_attachment=zerver_attachment,
            mattermost_data_dir=mattermost_data_dir,
        )

    chunk_size = 1000

    process_list_in_batches(
        lst=raw_messages,
        chunk_size=chunk_size,
        process_batch=process_batch,
    )


def write_message_data(
    num_teams: int,
    team_name: str,
    realm_id: int,
    post_data: Dict[str, List[Dict[str, Any]]],
    zerver_recipient: List[ZerverFieldsT],
    subscriber_map: Dict[int, Set[int]],
    output_dir: str,
    masking_content: bool,
    stream_id_mapper: IdMapper,
    huddle_id_mapper: IdMapper,
    user_id_mapper: IdMapper,
    user_handler: UserHandler,
    zerver_realmemoji: List[Dict[str, Any]],
    total_reactions: List[Dict[str, Any]],
    uploads_list: List[ZerverFieldsT],
    zerver_attachment: List[ZerverFieldsT],
    mattermost_data_dir: str,
) -> None:
    stream_id_to_recipient_id = {}
    huddle_id_to_recipient_id = {}
    user_id_to_recipient_id = {}

    for d in zerver_recipient:
        if d["type"] == Recipient.STREAM:
            stream_id_to_recipient_id[d["type_id"]] = d["id"]
        elif d["type"] == Recipient.DIRECT_MESSAGE_GROUP:
            huddle_id_to_recipient_id[d["type_id"]] = d["id"]
        if d["type"] == Recipient.PERSONAL:
            user_id_to_recipient_id[d["type_id"]] = d["id"]

    def get_recipient_id_from_receiver_name(receiver_name: str, recipient_type: int) -> int:
        if recipient_type == Recipient.STREAM:
            receiver_id = stream_id_mapper.get(receiver_name)
            recipient_id = stream_id_to_recipient_id[receiver_id]
        elif recipient_type == Recipient.DIRECT_MESSAGE_GROUP:
            receiver_id = huddle_id_mapper.get(receiver_name)
            recipient_id = huddle_id_to_recipient_id[receiver_id]
        elif recipient_type == Recipient.PERSONAL:
            receiver_id = user_id_mapper.get(receiver_name)
            recipient_id = user_id_to_recipient_id[receiver_id]
        else:
            raise AssertionError("Invalid recipient_type")
        return recipient_id

    if num_teams == 1:
        post_types = ["channel_post", "direct_post"]
    else:
        post_types = ["channel_post"]
        logging.warning(
            "Skipping importing huddles and DMs since there are multiple teams in the export"
        )

    for post_type in post_types:
        process_posts(
            num_teams=num_teams,
            team_name=team_name,
            realm_id=realm_id,
            post_data=post_data[post_type],
            get_recipient_id_from_receiver_name=get_recipient_id_from_receiver_name,
            subscriber_map=subscriber_map,
            output_dir=output_dir,
            is_pm_data=post_type == "direct_post",
            masking_content=masking_content,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
            zerver_realmemoji=zerver_realmemoji,
            total_reactions=total_reactions,
            uploads_list=uploads_list,
            zerver_attachment=zerver_attachment,
            mattermost_data_dir=mattermost_data_dir,
        )


def write_emoticon_data(
    realm_id: int, custom_emoji_data: List[Dict[str, Any]], data_dir: str, output_dir: str
) -> List[ZerverFieldsT]:
    """
    This function does most of the work for processing emoticons, the bulk
    of which is copying files.  We also write a json file with metadata.
    Finally, we return a list of RealmEmoji dicts to our caller.

    In our data_dir we have a pretty simple setup:

        The exported JSON file will have emoji rows if it contains any custom emoji
            {
                "type": "emoji",
                "emoji": {"name": "peerdium", "image": "exported_emoji/h15ni7kf1bnj7jeua4qhmctsdo/image"}
            }
            {
                "type": "emoji",
                "emoji": {"name": "tick", "image": "exported_emoji/7u7x8ytgp78q8jir81o9ejwwnr/image"}
            }

        exported_emoji/ - contains a bunch of image files:
            exported_emoji/7u7x8ytgp78q8jir81o9ejwwnr/image
            exported_emoji/h15ni7kf1bnj7jeua4qhmctsdo/image

    We move all the relevant files to Zulip's more nested
    directory structure.
    """

    logging.info("Starting to process emoticons")

    flat_data = [
        dict(
            path=d["image"],
            name=d["name"],
        )
        for d in custom_emoji_data
    ]

    emoji_folder = os.path.join(output_dir, "emoji")
    os.makedirs(emoji_folder, exist_ok=True)

    def process(data: ZerverFieldsT) -> ZerverFieldsT:
        source_sub_path = data["path"]
        source_path = os.path.join(data_dir, source_sub_path)

        target_fn = data["name"]
        target_sub_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=realm_id,
            emoji_file_name=target_fn,
        )
        target_path = os.path.join(emoji_folder, target_sub_path)

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        source_path = os.path.abspath(source_path)
        target_path = os.path.abspath(target_path)

        shutil.copyfile(source_path, target_path)

        return dict(
            path=target_path,
            s3_path=target_path,
            file_name=target_fn,
            realm_id=realm_id,
            name=data["name"],
        )

    emoji_records = list(map(process, flat_data))
    create_converted_data_files(emoji_records, output_dir, "/emoji/records.json")

    realmemoji = [
        build_realm_emoji(
            realm_id=realm_id,
            name=rec["name"],
            id=NEXT_ID("realmemoji"),
            file_name=rec["file_name"],
        )
        for rec in emoji_records
    ]
    logging.info("Done processing emoticons")

    return realmemoji


def create_username_to_user_mapping(
    user_data_list: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    username_to_user = {}
    for user in user_data_list:
        username_to_user[user["username"]] = user
    return username_to_user


def check_user_in_team(user: Dict[str, Any], team_name: str) -> bool:
    if user["teams"] is None:
        # This is null for users not on any team
        return False
    return any(team["name"] == team_name for team in user["teams"])


def label_mirror_dummy_users(
    num_teams: int,
    team_name: str,
    mattermost_data: Dict[str, Any],
    username_to_user: Dict[str, Dict[str, Any]],
) -> None:
    # This function might looks like a great place to label admin users. But
    # that won't be fully correct since we are iterating only though posts and
    # it covers only users that have sent at least one message.
    for post in mattermost_data["post"]["channel_post"]:
        post_team = post["team"]
        if post_team == team_name:
            user = username_to_user[post["user"]]
            if not check_user_in_team(user, team_name):
                user["is_mirror_dummy"] = True

    if num_teams == 1:
        for post in mattermost_data["post"]["direct_post"]:
            assert "team" not in post
            user = username_to_user[post["user"]]
            if not check_user_in_team(user, team_name):
                user["is_mirror_dummy"] = True


def reset_mirror_dummy_users(username_to_user: Dict[str, Dict[str, Any]]) -> None:
    for username in username_to_user:
        user = username_to_user[username]
        user["is_mirror_dummy"] = False


def mattermost_data_file_to_dict(mattermost_data_file: str) -> Dict[str, Any]:
    mattermost_data: Dict[str, Any] = {}
    mattermost_data["version"] = []
    mattermost_data["team"] = []
    mattermost_data["channel"] = []
    mattermost_data["user"] = []
    mattermost_data["post"] = {"channel_post": [], "direct_post": []}
    mattermost_data["emoji"] = []
    mattermost_data["direct_channel"] = []

    with open(mattermost_data_file, "rb") as fp:
        for line in fp:
            row = orjson.loads(line)
            data_type = row["type"]
            if data_type == "post":
                mattermost_data["post"]["channel_post"].append(row["post"])
            elif data_type == "direct_post":
                mattermost_data["post"]["direct_post"].append(row["direct_post"])
            else:
                mattermost_data[data_type].append(row[data_type])
    return mattermost_data


def do_convert_data(mattermost_data_dir: str, output_dir: str, masking_content: bool) -> None:
    username_to_user: Dict[str, Dict[str, Any]] = {}

    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):  # nocoverage
        raise Exception("Output directory should be empty!")

    mattermost_data_file = os.path.join(mattermost_data_dir, "export.json")
    mattermost_data = mattermost_data_file_to_dict(mattermost_data_file)

    username_to_user = create_username_to_user_mapping(mattermost_data["user"])

    for team in mattermost_data["team"]:
        realm_id = NEXT_ID("realm_id")
        team_name = team["name"]

        user_handler = UserHandler()
        subscriber_handler = SubscriberHandler()
        user_id_mapper = IdMapper()
        stream_id_mapper = IdMapper()
        huddle_id_mapper = IdMapper()

        print("Generating data for", team_name)
        realm = make_realm(realm_id, team)
        realm_output_dir = os.path.join(output_dir, team_name)

        reset_mirror_dummy_users(username_to_user)
        label_mirror_dummy_users(
            len(mattermost_data["team"]), team_name, mattermost_data, username_to_user
        )

        convert_user_data(
            user_handler=user_handler,
            user_id_mapper=user_id_mapper,
            user_data_map=username_to_user,
            realm_id=realm_id,
            team_name=team_name,
        )

        zerver_stream = convert_channel_data(
            channel_data=mattermost_data["channel"],
            user_data_map=username_to_user,
            subscriber_handler=subscriber_handler,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            realm_id=realm_id,
            team_name=team_name,
        )
        realm["zerver_stream"] = zerver_stream

        zerver_huddle: List[ZerverFieldsT] = []
        if len(mattermost_data["team"]) == 1:
            zerver_huddle = convert_huddle_data(
                huddle_data=mattermost_data["direct_channel"],
                user_data_map=username_to_user,
                subscriber_handler=subscriber_handler,
                huddle_id_mapper=huddle_id_mapper,
                user_id_mapper=user_id_mapper,
                realm_id=realm_id,
                team_name=team_name,
            )
            realm["zerver_huddle"] = zerver_huddle

        all_users = user_handler.get_all_users()

        zerver_recipient = build_recipients(
            zerver_userprofile=all_users,
            zerver_stream=zerver_stream,
            zerver_huddle=zerver_huddle,
        )
        realm["zerver_recipient"] = zerver_recipient

        stream_subscriptions = build_stream_subscriptions(
            get_users=subscriber_handler.get_users,
            zerver_recipient=zerver_recipient,
            zerver_stream=zerver_stream,
        )

        huddle_subscriptions = build_huddle_subscriptions(
            get_users=subscriber_handler.get_users,
            zerver_recipient=zerver_recipient,
            zerver_huddle=zerver_huddle,
        )

        personal_subscriptions = build_personal_subscriptions(
            zerver_recipient=zerver_recipient,
        )

        # Mattermost currently supports only exporting messages from channels.
        # Personal messages and huddles are not exported.
        zerver_subscription = personal_subscriptions + stream_subscriptions + huddle_subscriptions
        realm["zerver_subscription"] = zerver_subscription

        zerver_realmemoji = write_emoticon_data(
            realm_id=realm_id,
            custom_emoji_data=mattermost_data["emoji"],
            data_dir=mattermost_data_dir,
            output_dir=realm_output_dir,
        )
        realm["zerver_realmemoji"] = zerver_realmemoji

        subscriber_map = make_subscriber_map(
            zerver_subscription=zerver_subscription,
        )

        total_reactions: List[Dict[str, Any]] = []
        uploads_list: List[ZerverFieldsT] = []
        zerver_attachment: List[ZerverFieldsT] = []

        write_message_data(
            num_teams=len(mattermost_data["team"]),
            team_name=team_name,
            realm_id=realm_id,
            post_data=mattermost_data["post"],
            zerver_recipient=zerver_recipient,
            subscriber_map=subscriber_map,
            output_dir=realm_output_dir,
            masking_content=masking_content,
            stream_id_mapper=stream_id_mapper,
            huddle_id_mapper=huddle_id_mapper,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
            zerver_realmemoji=zerver_realmemoji,
            total_reactions=total_reactions,
            uploads_list=uploads_list,
            zerver_attachment=zerver_attachment,
            mattermost_data_dir=mattermost_data_dir,
        )
        realm["zerver_reaction"] = total_reactions
        realm["zerver_userprofile"] = user_handler.get_all_users()
        realm["sort_by_date"] = True

        create_converted_data_files(realm, realm_output_dir, "/realm.json")
        # Mattermost currently doesn't support exporting avatars
        create_converted_data_files([], realm_output_dir, "/avatars/records.json")

        # Export message attachments
        attachment: Dict[str, List[Any]] = {"zerver_attachment": zerver_attachment}
        create_converted_data_files(uploads_list, realm_output_dir, "/uploads/records.json")
        create_converted_data_files(attachment, realm_output_dir, "/attachment.json")
