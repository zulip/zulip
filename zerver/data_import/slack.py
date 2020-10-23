import logging
import os
import random
import secrets
import shutil
import subprocess
from collections import defaultdict
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple
from urllib.parse import urlencode

import orjson
import requests
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_attachment,
    build_avatar,
    build_defaultstream,
    build_huddle,
    build_message,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_usermessages,
    build_zerver_realm,
    create_converted_data_files,
    make_subscriber_map,
    process_avatars,
    process_emojis,
    process_uploads,
)
from zerver.data_import.sequencer import NEXT_ID
from zerver.data_import.slack_message_conversion import (
    convert_to_zulip_markdown,
    get_user_full_name,
)
from zerver.lib.emoji import name_to_codepoint
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.lib.upload import resize_logo, sanitize_name
from zerver.models import (
    CustomProfileField,
    CustomProfileFieldValue,
    Reaction,
    Realm,
    RealmEmoji,
    Recipient,
    UserProfile,
)

SlackToZulipUserIDT = Dict[str, int]
AddedChannelsT = Dict[str, Tuple[str, int]]
AddedMPIMsT = Dict[str, Tuple[str, int]]
DMMembersT = Dict[str, Tuple[str, str]]
SlackToZulipRecipientT = Dict[str, int]

def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

def slack_workspace_to_realm(domain_name: str, realm_id: int, user_list: List[ZerverFieldsT],
                             realm_subdomain: str, slack_data_dir: str,
                             custom_emoji_list: ZerverFieldsT) -> Tuple[ZerverFieldsT,
                                                                        SlackToZulipUserIDT,
                                                                        SlackToZulipRecipientT,
                                                                        AddedChannelsT,
                                                                        AddedMPIMsT,
                                                                        DMMembersT,
                                                                        List[ZerverFieldsT],
                                                                        ZerverFieldsT]:
    """
    Returns:
    1. realm, converted realm data
    2. slack_user_id_to_zulip_user_id, which is a dictionary to map from Slack user id to Zulip user id
    3. slack_recipient_name_to_zulip_recipient_id, which is a dictionary to map from Slack recipient
       name(channel names, mpim names, usernames, etc) to Zulip recipient id
    4. added_channels, which is a dictionary to map from channel name to channel id, Zulip stream_id
    5. added_mpims, which is a dictionary to map from MPIM name to MPIM id, Zulip huddle_id
    6. dm_members, which is a dictionary to map from DM id to tuple of DM participants.
    7. avatars, which is list to map avatars to Zulip avatar records.json
    8. emoji_url_map, which is maps emoji name to its Slack URL
    """
    NOW = float(timezone_now().timestamp())

    zerver_realm: List[ZerverFieldsT] = build_zerver_realm(realm_id, realm_subdomain, NOW, 'Slack')
    realm = build_realm(zerver_realm, realm_id, domain_name)

    zerver_userprofile, avatars, slack_user_id_to_zulip_user_id, zerver_customprofilefield, \
        zerver_customprofilefield_value = users_to_zerver_userprofile(slack_data_dir, user_list,
                                                                      realm_id, int(NOW), domain_name)
    realm, added_channels, added_mpims, dm_members, slack_recipient_name_to_zulip_recipient_id = \
        channels_to_zerver_stream(slack_data_dir, realm_id, realm, slack_user_id_to_zulip_user_id,
                                  zerver_userprofile)

    zerver_realmemoji, emoji_url_map = build_realmemoji(custom_emoji_list, realm_id)
    realm['zerver_realmemoji'] = zerver_realmemoji

    # See https://zulip.com/help/set-default-streams-for-new-users
    # for documentation on zerver_defaultstream
    realm['zerver_userprofile'] = zerver_userprofile

    realm['zerver_customprofilefield'] = zerver_customprofilefield
    realm['zerver_customprofilefieldvalue'] = zerver_customprofilefield_value

    return realm, slack_user_id_to_zulip_user_id, slack_recipient_name_to_zulip_recipient_id, \
        added_channels, added_mpims, dm_members, avatars, emoji_url_map

def build_realmemoji(custom_emoji_list: ZerverFieldsT,
                     realm_id: int) -> Tuple[List[ZerverFieldsT],
                                             ZerverFieldsT]:
    zerver_realmemoji = []
    emoji_url_map = {}
    emoji_id = 0
    for emoji_name, url in custom_emoji_list.items():
        if 'emoji.slack-edge.com' in url:
            # Some of the emojis we get from the API have invalid links
            # this is to prevent errors related to them
            realmemoji = RealmEmoji(
                name=emoji_name,
                id=emoji_id,
                file_name=os.path.basename(url),
                deactivated=False)

            realmemoji_dict = model_to_dict(realmemoji, exclude=['realm', 'author'])
            realmemoji_dict['author'] = None
            realmemoji_dict['realm'] = realm_id

            emoji_url_map[emoji_name] = url
            zerver_realmemoji.append(realmemoji_dict)
            emoji_id += 1
    return zerver_realmemoji, emoji_url_map

def users_to_zerver_userprofile(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                timestamp: Any, domain_name: str) -> Tuple[List[ZerverFieldsT],
                                                                           List[ZerverFieldsT],
                                                                           SlackToZulipUserIDT,
                                                                           List[ZerverFieldsT],
                                                                           List[ZerverFieldsT]]:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. avatar_list, which is list to map avatars to Zulip avatard records.json
    3. slack_user_id_to_zulip_user_id, which is a dictionary to map from Slack user ID to Zulip
       user id
    4. zerver_customprofilefield, which is a list of all custom profile fields
    5. zerver_customprofilefield_values, which is a list of user profile fields
    """
    logging.info('######### IMPORTING USERS STARTED #########\n')
    zerver_userprofile = []
    zerver_customprofilefield: List[ZerverFieldsT] = []
    zerver_customprofilefield_values: List[ZerverFieldsT] = []
    avatar_list: List[ZerverFieldsT] = []
    slack_user_id_to_zulip_user_id = {}

    # The user data we get from the Slack API does not contain custom profile data
    # Hence we get it from the Slack zip file
    slack_data_file_user_list = get_data_file(slack_data_dir + '/users.json')

    slack_user_id_to_custom_profile_fields: ZerverFieldsT = {}
    slack_custom_field_name_to_zulip_custom_field_id: ZerverFieldsT = {}

    for user in slack_data_file_user_list:
        process_slack_custom_fields(user, slack_user_id_to_custom_profile_fields)

    # We have only one primary owner in Slack, see link
    # https://get.slack.help/hc/en-us/articles/201912948-Owners-and-Administrators
    # This is to import the primary owner first from all the users
    user_id_count = custom_profile_field_value_id_count = custom_profile_field_id_count = 0
    primary_owner_id = user_id_count
    user_id_count += 1

    for user in users:
        slack_user_id = user['id']

        if user.get('is_primary_owner', False):
            user_id = primary_owner_id
        else:
            user_id = user_id_count

        email = get_user_email(user, domain_name)
        # ref: https://chat.zulip.org/help/change-your-profile-picture
        avatar_url = build_avatar_url(slack_user_id, user['team_id'],
                                      user['profile']['avatar_hash'])
        build_avatar(user_id, realm_id, email, avatar_url, timestamp, avatar_list)
        role = UserProfile.ROLE_MEMBER
        if get_owner(user):
            role = UserProfile.ROLE_REALM_OWNER
        elif get_admin(user):
            role = UserProfile.ROLE_REALM_ADMINISTRATOR
        if get_guest(user):
            role = UserProfile.ROLE_GUEST
        timezone = get_user_timezone(user)

        if slack_user_id in slack_user_id_to_custom_profile_fields:
            slack_custom_field_name_to_zulip_custom_field_id, custom_profile_field_id_count = \
                build_customprofile_field(zerver_customprofilefield,
                                          slack_user_id_to_custom_profile_fields[slack_user_id],
                                          custom_profile_field_id_count, realm_id,
                                          slack_custom_field_name_to_zulip_custom_field_id)
            custom_profile_field_value_id_count = build_customprofilefields_values(
                slack_custom_field_name_to_zulip_custom_field_id,
                slack_user_id_to_custom_profile_fields[slack_user_id], user_id,
                custom_profile_field_value_id_count, zerver_customprofilefield_values)

        userprofile = UserProfile(
            full_name=get_user_full_name(user),
            is_active=not user.get('deleted', False) and not user["is_mirror_dummy"],
            is_mirror_dummy=user["is_mirror_dummy"],
            id=user_id,
            email=email,
            delivery_email=email,
            avatar_source='U',
            is_bot=user.get('is_bot', False),
            role=role,
            bot_type=1 if user.get('is_bot', False) else None,
            date_joined=timestamp,
            timezone=timezone,
            last_login=timestamp)
        userprofile_dict = model_to_dict(userprofile)
        # Set realm id separately as the corresponding realm is not yet a Realm model instance
        userprofile_dict['realm'] = realm_id

        zerver_userprofile.append(userprofile_dict)
        slack_user_id_to_zulip_user_id[slack_user_id] = user_id
        if not user.get('is_primary_owner', False):
            user_id_count += 1

        logging.info("%s -> %s", user['name'], userprofile_dict['email'])

    process_customprofilefields(zerver_customprofilefield, zerver_customprofilefield_values)
    logging.info('######### IMPORTING USERS FINISHED #########\n')
    return zerver_userprofile, avatar_list, slack_user_id_to_zulip_user_id, zerver_customprofilefield, \
        zerver_customprofilefield_values

def build_customprofile_field(customprofile_field: List[ZerverFieldsT], fields: ZerverFieldsT,
                              custom_profile_field_id: int, realm_id: int,
                              slack_custom_field_name_to_zulip_custom_field_id: ZerverFieldsT) \
        -> Tuple[ZerverFieldsT, int]:
    # The name of the custom profile field is not provided in the Slack data
    # Hash keys of the fields are provided
    # Reference: https://api.slack.com/methods/users.profile.set
    for field, value in fields.items():
        if field not in slack_custom_field_name_to_zulip_custom_field_id:
            slack_custom_fields = ['phone', 'skype']
            if field in slack_custom_fields:
                field_name = field
            else:
                field_name = f"Slack custom field {str(custom_profile_field_id + 1)}"
            customprofilefield = CustomProfileField(
                id=custom_profile_field_id,
                name=field_name,
                field_type=1,  # For now this is defaulted to 'SHORT_TEXT'
                               # Processing is done in the function 'process_customprofilefields'
            )

            customprofilefield_dict = model_to_dict(customprofilefield,
                                                    exclude=['realm'])
            customprofilefield_dict['realm'] = realm_id

            slack_custom_field_name_to_zulip_custom_field_id[field] = custom_profile_field_id
            custom_profile_field_id += 1
            customprofile_field.append(customprofilefield_dict)
    return slack_custom_field_name_to_zulip_custom_field_id, custom_profile_field_id

def process_slack_custom_fields(user: ZerverFieldsT,
                                slack_user_id_to_custom_profile_fields: ZerverFieldsT) -> None:
    slack_user_id_to_custom_profile_fields[user['id']] = {}
    if user['profile'].get('fields'):
        slack_user_id_to_custom_profile_fields[user['id']] = user['profile']['fields']

    slack_custom_fields = ['phone', 'skype']
    for field in slack_custom_fields:
        if field in user['profile']:
            slack_user_id_to_custom_profile_fields[user['id']][field] = {'value': user['profile'][field]}

def build_customprofilefields_values(slack_custom_field_name_to_zulip_custom_field_id: ZerverFieldsT,
                                     fields: ZerverFieldsT, user_id: int, custom_field_id: int,
                                     custom_field_values: List[ZerverFieldsT]) -> int:
    for field, value in fields.items():
        if value['value'] == "":
            continue
        custom_field_value = CustomProfileFieldValue(
            id=custom_field_id,
            value=value['value'])

        custom_field_value_dict = model_to_dict(custom_field_value,
                                                exclude=['user_profile', 'field'])
        custom_field_value_dict['user_profile'] = user_id
        custom_field_value_dict['field'] = slack_custom_field_name_to_zulip_custom_field_id[field]

        custom_field_values.append(custom_field_value_dict)
        custom_field_id += 1
    return custom_field_id

def process_customprofilefields(customprofilefield: List[ZerverFieldsT],
                                customprofilefield_value: List[ZerverFieldsT]) -> None:
    for field in customprofilefield:
        for field_value in customprofilefield_value:
            if field_value['field'] == field['id'] and len(field_value['value']) > 50:
                field['field_type'] = 2  # corresponding to Long text
                break

def get_user_email(user: ZerverFieldsT, domain_name: str) -> str:
    if 'email' in user['profile']:
        return user['profile']['email']
    if user['is_mirror_dummy']:
        return "{}@{}.slack.com".format(user["name"], user["team_domain"])
    if 'bot_id' in user['profile']:
        if 'real_name_normalized' in user['profile']:
            slack_bot_name = user['profile']['real_name_normalized']
        elif 'first_name' in user['profile']:
            slack_bot_name = user['profile']['first_name']
        else:
            raise AssertionError("Could not identify bot type")
        return slack_bot_name.replace("Bot", "").replace(" ", "") + f"-bot@{domain_name}"
    if get_user_full_name(user).lower() == "slackbot":
        return f"imported-slackbot-bot@{domain_name}"
    raise AssertionError(f"Could not find email address for Slack user {user}")

def build_avatar_url(slack_user_id: str, team_id: str, avatar_hash: str) -> str:
    avatar_url = f"https://ca.slack-edge.com/{team_id}-{slack_user_id}-{avatar_hash}"
    return avatar_url

def get_owner(user: ZerverFieldsT) -> bool:
    owner = user.get('is_owner', False)
    primary_owner = user.get('is_primary_owner', False)

    return primary_owner or owner

def get_admin(user: ZerverFieldsT) -> bool:
    admin = user.get('is_admin', False)
    return admin

def get_guest(user: ZerverFieldsT) -> bool:
    restricted_user = user.get('is_restricted', False)
    ultra_restricted_user = user.get('is_ultra_restricted', False)

    # Slack's Single channel and multi channel guests both have
    # is_restricted set to True.  So assuming Slack doesn't change their
    # data model, it would also be correct to just check whether
    # is_restricted is set to True.
    return restricted_user or ultra_restricted_user

def get_user_timezone(user: ZerverFieldsT) -> str:
    _default_timezone = "America/New_York"
    timezone = user.get("tz", _default_timezone)
    if timezone is None or '/' not in timezone:
        timezone = _default_timezone
    return timezone

def channels_to_zerver_stream(slack_data_dir: str, realm_id: int,
                              realm: Dict[str, Any],
                              slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
                              zerver_userprofile: List[ZerverFieldsT]) \
        -> Tuple[Dict[str, List[ZerverFieldsT]], AddedChannelsT, AddedMPIMsT,
                 DMMembersT, SlackToZulipRecipientT]:
    """
    Returns:
    1. realm, converted realm data
    2. added_channels, which is a dictionary to map from channel name to channel id, Zulip stream_id
    3. added_mpims, which is a dictionary to map from MPIM(multiparty IM) name to MPIM id, Zulip huddle_id
    4. dm_members, which is a dictionary to map from DM id to tuple of DM participants.
    5. slack_recipient_name_to_zulip_recipient_id, which is a dictionary to map from Slack recipient
       name(channel names, mpim names, usernames etc) to Zulip recipient_id
    """
    logging.info('######### IMPORTING CHANNELS STARTED #########\n')

    added_channels = {}
    added_mpims = {}
    dm_members = {}
    slack_recipient_name_to_zulip_recipient_id = {}

    realm["zerver_stream"] = []
    realm["zerver_huddle"] = []
    realm["zerver_subscription"] = []
    realm["zerver_recipient"] = []
    realm["zerver_defaultstream"] = []

    subscription_id_count = recipient_id_count = 0
    stream_id_count = defaultstream_id = 0
    huddle_id_count = 0

    def process_channels(channels: List[Dict[str, Any]], invite_only: bool=False) -> None:
        nonlocal stream_id_count
        nonlocal recipient_id_count
        nonlocal defaultstream_id
        nonlocal subscription_id_count

        for channel in channels:
            # map Slack's topic and purpose content into Zulip's stream description.
            # WARN This mapping is lossy since the topic.creator, topic.last_set,
            # purpose.creator, purpose.last_set fields are not preserved.
            description = channel["purpose"]["value"]
            stream_id = stream_id_count
            recipient_id = recipient_id_count

            stream = build_stream(float(channel["created"]), realm_id, channel["name"],
                                  description, stream_id, channel["is_archived"], invite_only)
            realm["zerver_stream"].append(stream)

            slack_default_channels = ['general', 'random']
            if channel['name'] in slack_default_channels and not stream['deactivated']:
                defaultstream = build_defaultstream(realm_id, stream_id,
                                                    defaultstream_id)
                realm["zerver_defaultstream"].append(defaultstream)
                defaultstream_id += 1

            added_channels[stream['name']] = (channel['id'], stream_id)

            recipient = build_recipient(stream_id, recipient_id, Recipient.STREAM)
            realm["zerver_recipient"].append(recipient)
            slack_recipient_name_to_zulip_recipient_id[stream['name']] = recipient_id

            subscription_id_count = get_subscription(channel['members'], realm["zerver_subscription"],
                                                     recipient_id, slack_user_id_to_zulip_user_id,
                                                     subscription_id_count)

            stream_id_count += 1
            recipient_id_count += 1
            logging.info("%s -> created", channel['name'])

            # TODO map Slack's pins to Zulip's stars
            # There is the security model that Slack's pins are known to the team owner
            # as evident from where it is stored at (channels)
            # "pins": [
            #         {
            #             "id": "1444755381.000003",
            #             "type": "C",
            #             "user": "U061A5N1G",
            #             "owner": "U061A5N1G",
            #             "created": "1444755463"
            #         }
            #         ],

    public_channels = get_data_file(slack_data_dir + '/channels.json')
    process_channels(public_channels)

    try:
        private_channels = get_data_file(slack_data_dir + '/groups.json')
    except FileNotFoundError:
        private_channels = []
    process_channels(private_channels, True)

    # mpim is the Slack equivalent of huddle.
    def process_mpims(mpims: List[Dict[str, Any]]) -> None:
        nonlocal huddle_id_count
        nonlocal recipient_id_count
        nonlocal subscription_id_count

        for mpim in mpims:
            huddle = build_huddle(huddle_id_count)
            realm["zerver_huddle"].append(huddle)

            added_mpims[mpim['name']] = (mpim['id'], huddle_id_count)

            recipient = build_recipient(huddle_id_count, recipient_id_count, Recipient.HUDDLE)
            realm["zerver_recipient"].append(recipient)
            slack_recipient_name_to_zulip_recipient_id[mpim['name']] = recipient_id_count

            subscription_id_count = get_subscription(mpim['members'], realm["zerver_subscription"],
                                                     recipient_id_count, slack_user_id_to_zulip_user_id,
                                                     subscription_id_count)

            huddle_id_count += 1
            recipient_id_count += 1
            logging.info("%s -> created", mpim['name'])

    try:
        mpims = get_data_file(slack_data_dir + '/mpims.json')
    except FileNotFoundError:
        mpims = []
    process_mpims(mpims)

    for slack_user_id, zulip_user_id in slack_user_id_to_zulip_user_id.items():
        recipient = build_recipient(zulip_user_id, recipient_id_count, Recipient.PERSONAL)
        slack_recipient_name_to_zulip_recipient_id[slack_user_id] = recipient_id_count
        sub = build_subscription(recipient_id_count, zulip_user_id, subscription_id_count)
        realm["zerver_recipient"].append(recipient)
        realm["zerver_subscription"].append(sub)
        recipient_id_count += 1
        subscription_id_count += 1

    def process_dms(dms: List[Dict[str, Any]]) -> None:
        for dm in dms:
            user_a = dm["members"][0]
            user_b = dm["members"][1]
            dm_members[dm["id"]] = (user_a, user_b)

    try:
        dms = get_data_file(slack_data_dir + '/dms.json')
    except FileNotFoundError:
        dms = []
    process_dms(dms)

    logging.info('######### IMPORTING STREAMS FINISHED #########\n')
    return realm, added_channels, added_mpims, dm_members, slack_recipient_name_to_zulip_recipient_id

def get_subscription(channel_members: List[str], zerver_subscription: List[ZerverFieldsT],
                     recipient_id: int, slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
                     subscription_id: int) -> int:
    for slack_user_id in channel_members:
        sub = build_subscription(recipient_id, slack_user_id_to_zulip_user_id[slack_user_id],
                                 subscription_id)
        zerver_subscription.append(sub)
        subscription_id += 1
    return subscription_id

def process_long_term_idle_users(slack_data_dir: str, users: List[ZerverFieldsT],
                                 slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
                                 added_channels: AddedChannelsT,
                                 added_mpims: AddedMPIMsT, dm_members: DMMembersT,
                                 zerver_userprofile: List[ZerverFieldsT]) -> Set[int]:
    """Algorithmically, we treat users who have sent at least 10 messages
    or have sent a message within the last 60 days as active.
    Everyone else is treated as long-term idle, which means they will
    have a slightly slower first page load when coming back to
    Zulip.
    """
    all_messages = get_messages_iterator(slack_data_dir, added_channels, added_mpims, dm_members)

    sender_counts: Dict[str, int] = defaultdict(int)
    recent_senders: Set[str] = set()
    NOW = float(timezone_now().timestamp())
    for message in all_messages:
        timestamp = float(message['ts'])
        slack_user_id = get_message_sending_user(message)
        if not slack_user_id:
            continue

        if slack_user_id in recent_senders:
            continue

        if NOW - timestamp < 60:
            recent_senders.add(slack_user_id)

        sender_counts[slack_user_id] += 1
    for (slack_sender_id, count) in sender_counts.items():
        if count > 10:
            recent_senders.add(slack_sender_id)

    long_term_idle = set()

    for slack_user in users:
        if slack_user["id"] in recent_senders:
            continue
        zulip_user_id = slack_user_id_to_zulip_user_id[slack_user['id']]
        long_term_idle.add(zulip_user_id)

    for user_profile_row in zerver_userprofile:
        if user_profile_row['id'] in long_term_idle:
            user_profile_row['long_term_idle'] = True
            # Setting last_active_message_id to 1 means the user, if
            # imported, will get the full message history for the
            # streams they were on.
            user_profile_row['last_active_message_id'] = 1

    return long_term_idle

def convert_slack_workspace_messages(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                     slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
                                     slack_recipient_name_to_zulip_recipient_id: SlackToZulipRecipientT,
                                     added_channels: AddedChannelsT,
                                     added_mpims: AddedMPIMsT,
                                     dm_members: DMMembersT,
                                     realm: ZerverFieldsT,
                                     zerver_userprofile: List[ZerverFieldsT],
                                     zerver_realmemoji: List[ZerverFieldsT], domain_name: str,
                                     output_dir: str,
                                     chunk_size: int=MESSAGE_BATCH_CHUNK_SIZE) -> Tuple[List[ZerverFieldsT],
                                                                                        List[ZerverFieldsT],
                                                                                        List[ZerverFieldsT]]:
    """
    Returns:
    1. reactions, which is a list of the reactions
    2. uploads, which is a list of uploads to be mapped in uploads records.json
    3. attachment, which is a list of the attachments
    """

    long_term_idle = process_long_term_idle_users(slack_data_dir, users, slack_user_id_to_zulip_user_id,
                                                  added_channels, added_mpims, dm_members,
                                                  zerver_userprofile)

    all_messages = get_messages_iterator(slack_data_dir, added_channels, added_mpims, dm_members)
    logging.info('######### IMPORTING MESSAGES STARTED #########\n')

    total_reactions: List[ZerverFieldsT] = []
    total_attachments: List[ZerverFieldsT] = []
    total_uploads: List[ZerverFieldsT] = []

    dump_file_id = 1

    subscriber_map = make_subscriber_map(
        zerver_subscription=realm['zerver_subscription'],
    )

    while True:
        message_data = []
        _counter = 0
        for msg in all_messages:
            _counter += 1
            message_data.append(msg)
            if _counter == chunk_size:
                break
        if len(message_data) == 0:
            break

        zerver_message, zerver_usermessage, attachment, uploads, reactions = \
            channel_message_to_zerver_message(
                realm_id, users, slack_user_id_to_zulip_user_id, slack_recipient_name_to_zulip_recipient_id,
                message_data, zerver_realmemoji, subscriber_map, added_channels, dm_members,
                domain_name, long_term_idle)

        message_json = dict(
            zerver_message=zerver_message,
            zerver_usermessage=zerver_usermessage)

        message_file = f"/messages-{dump_file_id:06}.json"
        logging.info("Writing Messages to %s\n", output_dir + message_file)
        create_converted_data_files(message_json, output_dir, message_file)

        total_reactions += reactions
        total_attachments += attachment
        total_uploads += uploads

        dump_file_id += 1

    logging.info('######### IMPORTING MESSAGES FINISHED #########\n')
    return total_reactions, total_uploads, total_attachments

def get_messages_iterator(slack_data_dir: str, added_channels: Dict[str, Any],
                          added_mpims: AddedMPIMsT, dm_members: DMMembersT) -> Iterator[ZerverFieldsT]:
    """This function is an iterator that returns all the messages across
       all Slack channels, in order by timestamp.  It's important to
       not read all the messages into memory at once, because for
       large imports that can OOM kill."""

    dir_names = list(added_channels.keys()) + list(added_mpims.keys()) + list(dm_members.keys())
    all_json_names: Dict[str, List[str]] = defaultdict(list)
    for dir_name in dir_names:
        dir_path = os.path.join(slack_data_dir, dir_name)
        json_names = os.listdir(dir_path)
        for json_name in json_names:
            all_json_names[json_name].append(dir_path)

    # Sort json_name by date
    for json_name in sorted(all_json_names.keys()):
        messages_for_one_day: List[ZerverFieldsT] = []
        for dir_path in all_json_names[json_name]:
            message_dir = os.path.join(dir_path, json_name)
            dir_name = os.path.basename(dir_path)
            messages = []
            for message in get_data_file(message_dir):
                if message.get('user') == 'U00':
                    # Skip messages involving the the "U00" user,
                    # which is apparently used in some channel rename
                    # messages.  It's likely just the result of some
                    # bug in Slack's export system.  Arguably we could
                    # change this to point to slackbot instead, but
                    # skipping those messages is simpler.
                    continue
                if dir_name in added_channels:
                    message['channel_name'] = dir_name
                elif dir_name in added_mpims:
                    message['mpim_name'] = dir_name
                elif dir_name in dm_members:
                    message['pm_name'] = dir_name
                messages.append(message)
            messages_for_one_day += messages

        # we sort the messages according to the timestamp to show messages with
        # the proper date order
        yield from sorted(messages_for_one_day, key=lambda m: m['ts'])

def channel_message_to_zerver_message(realm_id: int,
                                      users: List[ZerverFieldsT],
                                      slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
                                      slack_recipient_name_to_zulip_recipient_id: SlackToZulipRecipientT,
                                      all_messages: List[ZerverFieldsT],
                                      zerver_realmemoji: List[ZerverFieldsT],
                                      subscriber_map: Dict[int, Set[int]],
                                      added_channels: AddedChannelsT,
                                      dm_members: DMMembersT,
                                      domain_name: str,
                                      long_term_idle: Set[int]) -> Tuple[List[ZerverFieldsT],
                                                                         List[ZerverFieldsT],
                                                                         List[ZerverFieldsT],
                                                                         List[ZerverFieldsT],
                                                                         List[ZerverFieldsT]]:
    """
    Returns:
    1. zerver_message, which is a list of the messages
    2. zerver_usermessage, which is a list of the usermessages
    3. zerver_attachment, which is a list of the attachments
    4. uploads_list, which is a list of uploads to be mapped in uploads records.json
    5. reaction_list, which is a list of all user reactions
    """
    zerver_message = []
    zerver_usermessage: List[ZerverFieldsT] = []
    uploads_list: List[ZerverFieldsT] = []
    zerver_attachment: List[ZerverFieldsT] = []
    reaction_list: List[ZerverFieldsT] = []

    total_user_messages = 0
    total_skipped_user_messages = 0
    for message in all_messages:
        slack_user_id = get_message_sending_user(message)
        if not slack_user_id:
            # Ignore messages without slack_user_id
            # These are Sometimes produced by Slack
            continue

        subtype = message.get('subtype', False)
        if subtype in [
                # Zulip doesn't have a pinned_item concept
                "pinned_item",
                "unpinned_item",
                # Slack's channel join/leave notices are spammy
                "channel_join",
                "channel_leave",
                "channel_name",
        ]:
            continue

        try:
            content, mentioned_user_ids, has_link = convert_to_zulip_markdown(
                message['text'], users, added_channels, slack_user_id_to_zulip_user_id)
        except Exception:
            print("Slack message unexpectedly missing text representation:")
            print(orjson.dumps(message, option=orjson.OPT_INDENT_2).decode())
            continue
        rendered_content = None

        if "channel_name" in message:
            is_private = False
            recipient_id = slack_recipient_name_to_zulip_recipient_id[message['channel_name']]
        elif "mpim_name" in message:
            is_private = True
            recipient_id = slack_recipient_name_to_zulip_recipient_id[message['mpim_name']]
        elif "pm_name" in message:
            is_private = True
            sender = get_message_sending_user(message)
            members = dm_members[message['pm_name']]
            if sender == members[0]:
                recipient_id = slack_recipient_name_to_zulip_recipient_id[members[1]]
                sender_recipient_id = slack_recipient_name_to_zulip_recipient_id[members[0]]
            else:
                recipient_id = slack_recipient_name_to_zulip_recipient_id[members[0]]
                sender_recipient_id = slack_recipient_name_to_zulip_recipient_id[members[1]]

        message_id = NEXT_ID('message')

        if 'reactions' in message.keys():
            build_reactions(reaction_list, message['reactions'], slack_user_id_to_zulip_user_id,
                            message_id, zerver_realmemoji)

        # Process different subtypes of slack messages

        # Subtypes which have only the action in the message should
        # be rendered with '/me' in the content initially
        # For example "sh_room_created" has the message 'started a call'
        # which should be displayed as '/me started a call'
        if subtype in ["bot_add", "sh_room_created", "me_message"]:
            content = f'/me {content}'
        if subtype == 'file_comment':
            # The file_comment message type only indicates the
            # responsible user in a subfield.
            message['user'] = message['comment']['user']

        file_info = process_message_files(
            message=message,
            domain_name=domain_name,
            realm_id=realm_id,
            message_id=message_id,
            slack_user_id=slack_user_id,
            users=users,
            slack_user_id_to_zulip_user_id=slack_user_id_to_zulip_user_id,
            zerver_attachment=zerver_attachment,
            uploads_list=uploads_list,
        )

        content += file_info['content']
        has_link = has_link or file_info['has_link']

        has_attachment = file_info['has_attachment']
        has_image = file_info['has_image']

        topic_name = 'imported from Slack'

        zulip_message = build_message(topic_name, float(message['ts']), message_id, content,
                                      rendered_content, slack_user_id_to_zulip_user_id[slack_user_id],
                                      recipient_id, has_image, has_link, has_attachment)
        zerver_message.append(zulip_message)

        (num_created, num_skipped) = build_usermessages(
            zerver_usermessage=zerver_usermessage,
            subscriber_map=subscriber_map,
            recipient_id=recipient_id,
            mentioned_user_ids=mentioned_user_ids,
            message_id=message_id,
            is_private=is_private,
            long_term_idle=long_term_idle,
        )
        total_user_messages += num_created
        total_skipped_user_messages += num_skipped

        if "pm_name" in message and recipient_id != sender_recipient_id:
            (num_created, num_skipped) = build_usermessages(
                zerver_usermessage=zerver_usermessage,
                subscriber_map=subscriber_map,
                recipient_id=sender_recipient_id,
                mentioned_user_ids=mentioned_user_ids,
                message_id=message_id,
                is_private=is_private,
                long_term_idle=long_term_idle,
            )
            total_user_messages += num_created
            total_skipped_user_messages += num_skipped

    logging.debug(
        "Created %s UserMessages; deferred %s due to long-term idle",
        total_user_messages, total_skipped_user_messages,
    )
    return zerver_message, zerver_usermessage, zerver_attachment, uploads_list, \
        reaction_list

def process_message_files(message: ZerverFieldsT,
                          domain_name: str,
                          realm_id: int,
                          message_id: int,
                          slack_user_id: str,
                          users: List[ZerverFieldsT],
                          slack_user_id_to_zulip_user_id: SlackToZulipUserIDT,
                          zerver_attachment: List[ZerverFieldsT],
                          uploads_list: List[ZerverFieldsT]) -> Dict[str, Any]:
    has_attachment = False
    has_image = False
    has_link = False

    files = message.get('files', [])

    subtype = message.get('subtype')

    if subtype == 'file_share':
        # In Slack messages, uploads can either have the subtype as 'file_share' or
        # have the upload information in 'files' keyword
        files = [message['file']]

    markdown_links = []

    for fileinfo in files:
        if fileinfo.get('mode', '') in ['tombstone', 'hidden_by_limit']:
            # Slack sometimes includes tombstone mode files with no
            # real data on the actual file (presumably in cases where
            # the file was deleted). hidden_by_limit mode is for files
            # that are hidden because of 10k cap in free plan.
            continue

        url = fileinfo['url_private']

        if 'files.slack.com' in url:
            # For attachments with Slack download link
            has_attachment = True
            has_link = True
            has_image = True if 'image' in fileinfo['mimetype'] else False

            file_user = [iterate_user for iterate_user in users if message['user'] == iterate_user['id']]
            file_user_email = get_user_email(file_user[0], domain_name)

            s3_path, content_for_link = get_attachment_path_and_content(fileinfo, realm_id)
            markdown_links.append(content_for_link)

            build_uploads(slack_user_id_to_zulip_user_id[slack_user_id], realm_id, file_user_email,
                          fileinfo, s3_path, uploads_list)

            build_attachment(realm_id, {message_id}, slack_user_id_to_zulip_user_id[slack_user_id],
                             fileinfo, s3_path, zerver_attachment)
        else:
            # For attachments with link not from Slack
            # Example: Google drive integration
            has_link = True
            if 'title' in fileinfo:
                file_name = fileinfo['title']
            else:
                file_name = fileinfo['name']
            markdown_links.append('[{}]({})'.format(file_name, fileinfo['url_private']))

    content = '\n'.join(markdown_links)

    return dict(
        content=content,
        has_attachment=has_attachment,
        has_image=has_image,
        has_link=has_link,
    )

def get_attachment_path_and_content(fileinfo: ZerverFieldsT, realm_id: int) -> Tuple[str,
                                                                                     str]:
    # Should be kept in sync with its equivalent in zerver/lib/uploads in the function
    # 'upload_message_file'
    s3_path = "/".join([
        str(realm_id),
        'SlackImportAttachment',  # This is a special placeholder which should be kept
                                  # in sync with 'exports.py' function 'import_message_data'
        format(random.randint(0, 255), 'x'),
        secrets.token_urlsafe(18),
        sanitize_name(fileinfo['name']),
    ])
    attachment_path = f'/user_uploads/{s3_path}'
    content = '[{}]({})'.format(fileinfo['title'], attachment_path)

    return s3_path, content

def build_reactions(reaction_list: List[ZerverFieldsT], reactions: List[ZerverFieldsT],
                    slack_user_id_to_zulip_user_id: SlackToZulipUserIDT, message_id: int,
                    zerver_realmemoji: List[ZerverFieldsT]) -> None:
    realmemoji = {}
    for realm_emoji in zerver_realmemoji:
        realmemoji[realm_emoji['name']] = realm_emoji['id']

    # For the Unicode emoji codes, we use equivalent of
    # function 'emoji_name_to_emoji_code' in 'zerver/lib/emoji' here
    for slack_reaction in reactions:
        emoji_name = slack_reaction['name']
        if emoji_name in name_to_codepoint:
            emoji_code = name_to_codepoint[emoji_name]
            reaction_type = Reaction.UNICODE_EMOJI
        elif emoji_name in realmemoji:
            emoji_code = realmemoji[emoji_name]
            reaction_type = Reaction.REALM_EMOJI
        else:
            continue

        for slack_user_id in slack_reaction['users']:
            reaction_id = NEXT_ID('reaction')
            reaction = Reaction(
                id=reaction_id,
                emoji_code=emoji_code,
                emoji_name=emoji_name,
                reaction_type=reaction_type)

            reaction_dict = model_to_dict(reaction,
                                          exclude=['message', 'user_profile'])
            reaction_dict['message'] = message_id
            reaction_dict['user_profile'] = slack_user_id_to_zulip_user_id[slack_user_id]

            reaction_list.append(reaction_dict)

def build_uploads(user_id: int, realm_id: int, email: str, fileinfo: ZerverFieldsT, s3_path: str,
                  uploads_list: List[ZerverFieldsT]) -> None:
    upload = dict(
        path=fileinfo['url_private'],  # Save Slack's URL here, which is used later while processing
        realm_id=realm_id,
        content_type=None,
        user_profile_id=user_id,
        last_modified=fileinfo['timestamp'],
        user_profile_email=email,
        s3_path=s3_path,
        size=fileinfo['size'])
    uploads_list.append(upload)

def get_message_sending_user(message: ZerverFieldsT) -> Optional[str]:
    if 'user' in message:
        return message['user']
    if message.get('file'):
        return message['file'].get('user')
    return None

def fetch_shared_channel_users(user_list: List[ZerverFieldsT], slack_data_dir: str, token: str) -> None:
    normal_user_ids = set()
    mirror_dummy_user_ids = set()
    added_channels = {}
    team_id_to_domain: Dict[str, str] = {}
    for user in user_list:
        user["is_mirror_dummy"] = False
        normal_user_ids.add(user["id"])

    public_channels = get_data_file(slack_data_dir + '/channels.json')
    try:
        private_channels = get_data_file(slack_data_dir + '/groups.json')
    except FileNotFoundError:
        private_channels = []
    for channel in public_channels + private_channels:
        added_channels[channel["name"]] = True
        for user_id in channel["members"]:
            if user_id not in normal_user_ids:
                mirror_dummy_user_ids.add(user_id)

    all_messages = get_messages_iterator(slack_data_dir, added_channels, {}, {})
    for message in all_messages:
        user_id = get_message_sending_user(message)
        if user_id is None or user_id in normal_user_ids:
            continue
        mirror_dummy_user_ids.add(user_id)

    # Fetch data on the mirror_dummy_user_ids from the Slack API (it's
    # not included in the data export file).
    for user_id in mirror_dummy_user_ids:
        user = get_slack_api_data("https://slack.com/api/users.info", "user", token=token, user=user_id)
        team_id = user["team_id"]
        if team_id not in team_id_to_domain:
            team = get_slack_api_data("https://slack.com/api/team.info", "team", token=token, team=team_id)
            team_id_to_domain[team_id] = team["domain"]
        user["team_domain"] = team_id_to_domain[team_id]
        user["is_mirror_dummy"] = True
        user_list.append(user)

def fetch_team_icons(zerver_realm: Dict[str, Any], team_info_dict: Dict[str, Any],
                     output_dir: str) -> List[Dict[str, Any]]:
    records = []

    team_icons_dict = team_info_dict["icon"]
    if "image_default" in team_icons_dict and team_icons_dict["image_default"]:
        return []

    icon_url = team_icons_dict.get("image_original", None) or team_icons_dict.get("image_230", None) or \
        team_icons_dict.get("image_132", None) or team_icons_dict.get("image_102", None)
    if icon_url is None:
        return []

    response = requests.get(icon_url, stream=True)
    response_raw = response.raw

    realm_id = zerver_realm["id"]
    os.makedirs(os.path.join(output_dir, str(realm_id)), exist_ok=True)

    original_icon_output_path = os.path.join(output_dir, str(realm_id), "icon.original")
    with open(original_icon_output_path, 'wb') as output_file:
        shutil.copyfileobj(response_raw, output_file)
    records.append({
        "realm_id": realm_id,
        "path": os.path.join(str(realm_id), "icon.original"),
        "s3_path": os.path.join(str(realm_id), "icon.original"),
    })

    resized_icon_output_path = os.path.join(output_dir, str(realm_id), "icon.png")
    with open(resized_icon_output_path, 'wb') as output_file:
        with open(original_icon_output_path, 'rb') as original_file:
            resized_data = resize_logo(original_file.read())
            output_file.write(resized_data)
    records.append({
        "realm_id": realm_id,
        "path": os.path.join(str(realm_id), "icon.png"),
        "s3_path": os.path.join(str(realm_id), "icon.png"),
    })

    zerver_realm["icon_source"] = Realm.ICON_UPLOADED

    return records

def do_convert_data(slack_zip_file: str, output_dir: str, token: str, threads: int=6) -> None:
    # Subdomain is set by the user while running the import command
    realm_subdomain = ""
    realm_id = 0
    domain_name = settings.EXTERNAL_HOST

    log_token_warning(token)

    slack_data_dir = slack_zip_file.replace('.zip', '')
    if not os.path.exists(slack_data_dir):
        os.makedirs(slack_data_dir)

    os.makedirs(output_dir, exist_ok=True)
    if os.listdir(output_dir):
        raise Exception('Output directory should be empty!')

    subprocess.check_call(['unzip', '-q', slack_zip_file, '-d', slack_data_dir])

    # We get the user data from the legacy token method of Slack API, which is depreciated
    # but we use it as the user email data is provided only in this method
    user_list = get_slack_api_data("https://slack.com/api/users.list", "members", token=token)
    fetch_shared_channel_users(user_list, slack_data_dir, token)

    custom_emoji_list = get_slack_api_data("https://slack.com/api/emoji.list", "emoji", token=token)

    realm, slack_user_id_to_zulip_user_id, slack_recipient_name_to_zulip_recipient_id, \
        added_channels, added_mpims, dm_members, avatar_list, \
        emoji_url_map = slack_workspace_to_realm(domain_name, realm_id, user_list,
                                                 realm_subdomain, slack_data_dir,
                                                 custom_emoji_list)

    reactions, uploads_list, zerver_attachment = convert_slack_workspace_messages(
        slack_data_dir, user_list, realm_id, slack_user_id_to_zulip_user_id,
        slack_recipient_name_to_zulip_recipient_id, added_channels, added_mpims, dm_members, realm,
        realm['zerver_userprofile'], realm['zerver_realmemoji'], domain_name, output_dir)

    # Move zerver_reactions to realm.json file
    realm['zerver_reaction'] = reactions

    emoji_folder = os.path.join(output_dir, 'emoji')
    os.makedirs(emoji_folder, exist_ok=True)
    emoji_records = process_emojis(realm['zerver_realmemoji'], emoji_folder, emoji_url_map, threads)

    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)
    avatar_records = process_avatars(avatar_list, avatar_folder, realm_id, threads, size_url_suffix='-512')

    uploads_folder = os.path.join(output_dir, 'uploads')
    os.makedirs(os.path.join(uploads_folder, str(realm_id)), exist_ok=True)
    uploads_records = process_uploads(uploads_list, uploads_folder, threads)
    attachment = {"zerver_attachment": zerver_attachment}

    team_info_dict = get_slack_api_data("https://slack.com/api/team.info", "team", token=token)
    realm_icons_folder = os.path.join(output_dir, 'realm_icons')
    realm_icon_records = fetch_team_icons(realm["zerver_realm"][0], team_info_dict, realm_icons_folder)

    create_converted_data_files(realm, output_dir, '/realm.json')
    create_converted_data_files(emoji_records, output_dir, '/emoji/records.json')
    create_converted_data_files(avatar_records, output_dir, '/avatars/records.json')
    create_converted_data_files(uploads_records, output_dir, '/uploads/records.json')
    create_converted_data_files(attachment, output_dir, '/attachment.json')
    create_converted_data_files(realm_icon_records, output_dir, '/realm_icons/records.json')

    rm_tree(slack_data_dir)
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

    logging.info('######### DATA CONVERSION FINISHED #########\n')
    logging.info("Zulip data dump created at %s", output_dir)

def get_data_file(path: str) -> Any:
    with open(path, "rb") as fp:
        data = orjson.loads(fp.read())
        return data

def log_token_warning(token: str) -> None:
    if not token.startswith("xoxp-"):
        logging.info('Not a Slack legacy token.\n'
                     '  This token might not have all the needed scopes. We need the following scopes:\n'
                     '  - emoji:read\n  - users:read\n  - users:read.email\n  - team:read')


def get_slack_api_data(slack_api_url: str, get_param: str, **kwargs: Any) -> Any:
    if not kwargs.get("token"):
        raise AssertionError("Slack token missing in kwargs")
    data = requests.get(f"{slack_api_url}?{urlencode(kwargs)}")

    if data.status_code == requests.codes.ok:
        result = data.json()
        if not result['ok']:
            raise Exception('Error accessing Slack API: {}'.format(result['error']))
        return result[get_param]

    raise Exception('HTTP error accessing the Slack API.')
