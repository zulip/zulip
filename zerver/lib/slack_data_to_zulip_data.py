import os
import json
import ujson
import hashlib
import sys
import argparse
import shutil
import subprocess
import re
import logging
import random
import requests
import random

from django.conf import settings
from django.db import connection
from django.utils.timezone import now as timezone_now
from django.forms.models import model_to_dict
from typing import Any, Dict, List, Optional, Tuple
from zerver.forms import check_subdomain_available
from zerver.models import Reaction, RealmEmoji, Realm
from zerver.lib.slack_message_conversion import convert_to_zulip_markdown, \
    get_user_full_name
from zerver.lib.parallel import run_parallel
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.actions import STREAM_ASSIGNMENT_COLORS as stream_colors
from zerver.lib.upload import random_name, sanitize_name
from zerver.lib.emoji import NAME_TO_CODEPOINT_PATH

# stubs
ZerverFieldsT = Dict[str, Any]
AddedUsersT = Dict[str, int]
AddedChannelsT = Dict[str, Tuple[str, int]]
AddedRecipientsT = Dict[str, int]

def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

def slack_workspace_to_realm(domain_name: str, realm_id: int, user_list: List[ZerverFieldsT],
                             realm_subdomain: str, slack_data_dir: str,
                             custom_emoji_list: ZerverFieldsT)-> Tuple[ZerverFieldsT, AddedUsersT,
                                                                       AddedRecipientsT,
                                                                       AddedChannelsT,
                                                                       List[ZerverFieldsT],
                                                                       ZerverFieldsT]:
    """
    Returns:
    1. realm, Converted Realm data
    2. added_users, which is a dictionary to map from slack user id to zulip user id
    3. added_recipient, which is a dictionary to map from channel name to zulip recipient_id
    4. added_channels, which is a dictionary to map from channel name to channel id, zulip stream_id
    5. avatars, which is list to map avatars to zulip avatar records.json
    6. emoji_url_map, which is maps emoji name to its slack url
    """
    NOW = float(timezone_now().timestamp())

    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW)

    realm = dict(zerver_client=[{"name": "populate_db", "id": 1},
                                {"name": "website", "id": 2},
                                {"name": "API", "id": 3}],
                 zerver_userpresence=[],  # shows last logged in data, which is not available in slack
                 zerver_userprofile_mirrordummy=[],
                 zerver_realmdomain=[{"realm": realm_id,
                                      "allow_subdomains": False,
                                      "domain": domain_name,
                                      "id": realm_id}],
                 zerver_useractivity=[],
                 zerver_realm=zerver_realm,
                 zerver_huddle=[],
                 zerver_userprofile_crossrealm=[],
                 zerver_useractivityinterval=[],
                 zerver_realmfilter=[])

    zerver_userprofile, avatars, added_users, zerver_customprofilefield, \
        zerver_customprofilefield_value = users_to_zerver_userprofile(slack_data_dir, user_list,
                                                                      realm_id, int(NOW), domain_name)
    channels_to_zerver_stream_fields = channels_to_zerver_stream(slack_data_dir,
                                                                 realm_id,
                                                                 added_users,
                                                                 zerver_userprofile)
    zerver_realmemoji, emoji_url_map = build_realmemoji(custom_emoji_list, realm_id)
    realm['zerver_realmemoji'] = zerver_realmemoji

    # See https://zulipchat.com/help/set-default-streams-for-new-users
    # for documentation on zerver_defaultstream
    realm['zerver_userprofile'] = zerver_userprofile

    # Custom profile fields
    realm['zerver_customprofilefield'] = zerver_customprofilefield
    realm['zerver_customprofilefield_value'] = zerver_customprofilefield_value

    realm['zerver_defaultstream'] = channels_to_zerver_stream_fields[0]
    realm['zerver_stream'] = channels_to_zerver_stream_fields[1]
    realm['zerver_subscription'] = channels_to_zerver_stream_fields[3]
    realm['zerver_recipient'] = channels_to_zerver_stream_fields[4]
    added_channels = channels_to_zerver_stream_fields[2]
    added_recipient = channels_to_zerver_stream_fields[5]

    return realm, added_users, added_recipient, added_channels, avatars, emoji_url_map

def build_zerver_realm(realm_id: int, realm_subdomain: str,
                       time: float) -> List[ZerverFieldsT]:
    realm = Realm(id=realm_id, date_created=time,
                  name=realm_subdomain, string_id=realm_subdomain,
                  description="Organization imported from Slack!")
    auth_methods = [[flag[0], flag[1]] for flag in realm.authentication_methods]
    realm_dict = model_to_dict(realm, exclude='authentication_methods')
    realm_dict['authentication_methods'] = auth_methods
    return[realm_dict]

def build_realmemoji(custom_emoji_list: ZerverFieldsT,
                     realm_id: int) -> Tuple[List[ZerverFieldsT],
                                             ZerverFieldsT]:
    zerver_realmemoji = []
    emoji_url_map = {}
    emoji_id = 0
    for emoji_name, url in custom_emoji_list.items():
        if 'emoji.slack-edge.com' in url:
            # Some of the emojis we get from the api have invalid links
            # this is to prevent errors related to them
            realmemoji = dict(
                name=emoji_name,
                id=emoji_id,
                author=None,
                realm=realm_id,
                file_name=os.path.basename(url),
                deactivated=False)
            emoji_url_map[emoji_name] = url
            zerver_realmemoji.append(realmemoji)
            emoji_id += 1
    return zerver_realmemoji, emoji_url_map

def users_to_zerver_userprofile(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                timestamp: Any, domain_name: str) -> Tuple[List[ZerverFieldsT],
                                                                           List[ZerverFieldsT],
                                                                           AddedUsersT,
                                                                           List[ZerverFieldsT],
                                                                           List[ZerverFieldsT]]:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. avatar_list, which is list to map avatars to zulip avatard records.json
    3. added_users, which is a dictionary to map from slack user id to zulip
       user id
    4. zerver_customprofilefield, which is a list of all custom profile fields
    5. zerver_customprofilefield_values, which is a list of user profile fields
    """
    logging.info('######### IMPORTING USERS STARTED #########\n')
    zerver_userprofile = []
    zerver_customprofilefield = []  # type: List[ZerverFieldsT]
    zerver_customprofilefield_values = []  # type: List[ZerverFieldsT]
    avatar_list = []  # type: List[ZerverFieldsT]
    added_users = {}

    # The user data we get from the slack api does not contain custom profile data
    # Hence we get it from the slack zip file
    slack_data_file_user_list = get_data_file(slack_data_dir + '/users.json')

    # To map user id with the custom profile fields of the corresponding user
    slack_user_custom_field_map = {}
    # To store custom fields corresponding to their ids
    custom_field_map = {}  # type: ZerverFieldsT

    for user in slack_data_file_user_list:
        if 'fields' in user['profile']:
            # Make sure the content of fields is not 'None'
            if user['profile']['fields']:
                slack_user_custom_field_map[user['id']] = user['profile']['fields']

    # We have only one primary owner in slack, see link
    # https://get.slack.help/hc/en-us/articles/201912948-Owners-and-Administrators
    # This is to import the primary owner first from all the users
    user_id_count = custom_field_id_count = customprofilefield_id = 0
    primary_owner_id = user_id_count
    user_id_count += 1

    for user in users:
        slack_user_id = user['id']
        DESKTOP_NOTIFICATION = True

        if user.get('is_primary_owner', False):
            user_id = primary_owner_id
        else:
            user_id = user_id_count

        # email
        email = get_user_email(user, domain_name)

        # avatar
        # ref: https://chat.zulip.org/help/change-your-avatar
        avatar_url = build_avatar_url(slack_user_id, user['team_id'],
                                      user['profile']['avatar_hash'])
        build_avatar(user_id, realm_id, email, avatar_url, timestamp, avatar_list)

        # check if user is the admin
        realm_admin = get_admin(user)

        # timezone
        timezone = get_user_timezone(user)

        # Check for custom profile fields
        if slack_user_id in slack_user_custom_field_map:
            # For processing the fields
            custom_field_map, customprofilefield_id = build_customprofile_field(
                zerver_customprofilefield, slack_user_custom_field_map[slack_user_id],
                customprofilefield_id, realm_id, custom_field_map)
            # Store the custom field values for the corresponding user
            custom_field_id_count = build_customprofilefields_values(
                custom_field_map, slack_user_custom_field_map[slack_user_id], user_id,
                custom_field_id_count, zerver_customprofilefield_values)

        userprofile = dict(
            enable_desktop_notifications=DESKTOP_NOTIFICATION,
            is_staff=False,  # 'staff' is for server administrators, which don't exist in Slack.
            avatar_source='U',
            is_bot=user.get('is_bot', False),
            avatar_version=1,
            default_desktop_notifications=True,
            timezone=timezone,
            default_sending_stream=None,
            enable_offline_email_notifications=True,
            user_permissions=[],  # This is Zulip-specific
            is_mirror_dummy=False,
            pointer=-1,
            default_events_register_stream=None,
            is_realm_admin=realm_admin,
            # invites_granted=0,  # TODO
            enter_sends=True,
            bot_type=1 if user.get('is_bot', False) else None,
            enable_stream_sounds=False,
            is_api_super_user=False,
            rate_limits="",
            last_login=timestamp,
            tos_version=None,
            default_all_public_streams=False,
            full_name=get_user_full_name(user),
            twenty_four_hour_time=False,
            groups=[],  # This is Zulip-specific
            enable_online_push_notifications=False,
            alert_words="[]",
            bot_owner=None,  # This is Zulip-specific
            short_name=user['name'],
            enable_offline_push_notifications=True,
            left_side_userlist=False,
            enable_stream_desktop_notifications=False,
            enable_digest_emails=True,
            last_pointer_updater="",
            last_active_message_id=None,
            email=email,
            realm_name_in_notifications=False,
            date_joined=timestamp,
            last_reminder=timestamp,
            is_superuser=False,
            tutorial_status="T",
            default_language="en",
            enable_sounds=True,
            pm_content_in_desktop_notifications=True,
            is_active=not user['deleted'],
            onboarding_steps="[]",
            emojiset="google",
            realm=realm_id,
            # invites_used=0,  # TODO
            id=user_id)

        # TODO map the avatar
        # zerver auto-infer the url from Gravatar instead of from a specified
        # url; zerver.lib.avatar needs to be patched
        # profile['image_32'], Slack has 24, 32, 48, 72, 192, 512 size range

        zerver_userprofile.append(userprofile)
        added_users[slack_user_id] = user_id
        if not user.get('is_primary_owner', False):
            user_id_count += 1

        logging.info(u"{} -> {}".format(user['name'], userprofile['email']))

    process_customprofilefields(zerver_customprofilefield, zerver_customprofilefield_values)
    logging.info('######### IMPORTING USERS FINISHED #########\n')
    return zerver_userprofile, avatar_list, added_users, zerver_customprofilefield, \
        zerver_customprofilefield_values

def build_customprofile_field(customprofile_field: List[ZerverFieldsT], fields: ZerverFieldsT,
                              customprofilefield_id: int, realm_id: int,
                              custom_field_map: ZerverFieldsT) -> Tuple[ZerverFieldsT, int]:
    # The name of the custom profile field is not provided in the slack data
    # Hash keys of the fields are provided
    # Reference: https://api.slack.com/methods/users.profile.set
    for field, value in fields.items():
        if field not in custom_field_map:
            field_name = ("slack custom field %s" % str(customprofilefield_id + 1))
            customprofilefield = dict(
                id=customprofilefield_id,
                realm=realm_id,
                name=field_name,
                field_type=1  # For now this is defaulted to 'SHORT_TEXT'
                              # Processing is done in the function 'process_customprofilefields'
            )
            custom_field_map[field] = customprofilefield_id
            customprofilefield_id += 1
            customprofile_field.append(customprofilefield)
    return custom_field_map, customprofilefield_id

def build_customprofilefields_values(custom_field_map: ZerverFieldsT, fields: ZerverFieldsT,
                                     user_id: int, custom_field_id: int,
                                     custom_field_values: List[ZerverFieldsT]) -> int:
    for field, value in fields.items():
        custom_field_value = dict(
            id=custom_field_id,
            user_profile=user_id,
            field=custom_field_map[field],
            value=value['value'])
        custom_field_values.append(custom_field_value)
        custom_field_id += 1
    return custom_field_id

def process_customprofilefields(customprofilefield: List[ZerverFieldsT],
                                customprofilefield_value: List[ZerverFieldsT]) -> None:
    # Process the field types by checking all field values
    for field in customprofilefield:
        for field_value in customprofilefield_value:
            if field_value['field'] == field['id'] and len(field_value['value']) > 50:
                field['field_type'] = 2  # corresponding to Long Text
                break

def get_user_email(user: ZerverFieldsT, domain_name: str) -> str:
    if 'email' in user['profile']:
        return user['profile']['email']
    if 'bot_id' in user['profile']:
        if 'real_name_normalized' in user['profile']:
            slack_bot_name = user['profile']['real_name_normalized']
        elif 'first_name' in user['profile']:
            slack_bot_name = user['profile']['first_name']
        else:
            raise AssertionError("Could not identify bot type")
        return slack_bot_name.replace("Bot", "").replace(" ", "") + "-bot@%s" % (domain_name,)
    # TODO: Do we need this fallback case at all?
    return (hashlib.sha256(user['real_name'].encode()).hexdigest() +
            "@%s" % (domain_name,))

def build_avatar_url(slack_user_id: str, team_id: str, avatar_hash: str) -> str:
    avatar_url = "https://ca.slack-edge.com/{}-{}-{}".format(team_id, slack_user_id,
                                                             avatar_hash)
    return avatar_url

def build_avatar(zulip_user_id: int, realm_id: int, email: str, avatar_url: str,
                 timestamp: Any, avatar_list: List[ZerverFieldsT]) -> None:
    avatar = dict(
        path=avatar_url,  # Save slack's url here, which is used later while processing
        realm_id=realm_id,
        content_type=None,
        user_profile_id=zulip_user_id,
        last_modified=timestamp,
        user_profile_email=email,
        s3_path="",
        size="")
    avatar_list.append(avatar)

def get_admin(user: ZerverFieldsT) -> bool:
    admin = user.get('is_admin', False)
    owner = user.get('is_owner', False)
    primary_owner = user.get('is_primary_owner', False)

    if admin or owner or primary_owner:
        return True
    return False

def get_user_timezone(user: ZerverFieldsT) -> str:
    _default_timezone = "America/New_York"
    timezone = user.get("tz", _default_timezone)
    if timezone is None or '/' not in timezone:
        timezone = _default_timezone
    return timezone

def channels_to_zerver_stream(slack_data_dir: str, realm_id: int, added_users: AddedUsersT,
                              zerver_userprofile: List[ZerverFieldsT]) -> Tuple[List[ZerverFieldsT],
                                                                                List[ZerverFieldsT],
                                                                                AddedChannelsT,
                                                                                List[ZerverFieldsT],
                                                                                List[ZerverFieldsT],
                                                                                AddedRecipientsT]:
    """
    Returns:
    1. zerver_defaultstream, which is a list of the default streams
    2. zerver_stream, while is a list of all streams
    3. added_channels, which is a dictionary to map from channel name to channel id, zulip stream_id
    4. zerver_subscription, which is a list of the subscriptions
    5. zerver_recipient, which is a list of the recipients
    6. added_recipient, which is a dictionary to map from channel name to zulip recipient_id
    """
    logging.info('######### IMPORTING CHANNELS STARTED #########\n')
    channels = get_data_file(slack_data_dir + '/channels.json')

    added_channels = {}
    added_recipient = {}

    zerver_stream = []
    zerver_subscription = []  # type: List[ZerverFieldsT]
    zerver_recipient = []
    zerver_defaultstream = []

    stream_id_count = subscription_id_count = recipient_id_count = defaultstream_id = 0

    for channel in channels:
        # slack_channel_id = channel['id']

        # map Slack's topic and purpose content into Zulip's stream description.
        # WARN This mapping is lossy since the topic.creator, topic.last_set,
        # purpose.creator, purpose.last_set fields are not preserved.
        description = channel["purpose"]["value"]
        stream_id = stream_id_count
        recipient_id = recipient_id_count

        # construct the stream object and append it to zerver_stream
        stream = dict(
            realm=realm_id,
            name=channel["name"],
            deactivated=channel["is_archived"],
            description=description,
            invite_only=False,  # TODO: private channels are not
                                # exported with Slack's standard plan;
                                # so this field is always false
            date_created=float(channel["created"]),
            id=stream_id)

        # construct defaultstream object
        # slack has the default channel 'general' and 'random'
        # where every user is subscribed
        default_channels = ['general', 'random']  # Slack specific
        if channel['name'] in default_channels:
            defaultstream = build_defaultstream(channel['name'], realm_id, stream_id,
                                                defaultstream_id)
            zerver_defaultstream.append(defaultstream)
            defaultstream_id += 1

        zerver_stream.append(stream)
        added_channels[stream['name']] = (channel['id'], stream_id)

        # construct the recipient object and append it to zerver_recipient
        # type 1: private
        # type 2: stream
        # type 3: huddle
        recipient = dict(
            type_id=stream_id,
            id=recipient_id,
            type=2)
        zerver_recipient.append(recipient)
        added_recipient[stream['name']] = recipient_id
        # TOODO add recipients for private message and huddles

        # construct the subscription object and append it to zerver_subscription
        subscription_id_count = build_subscription(channel['members'], zerver_subscription,
                                                   recipient_id, added_users,
                                                   subscription_id_count)
        # TOODO add zerver_subscription which correspond to
        # huddles type recipient
        # For huddles:
        # sub['recipient']=recipient['id'] where recipient['type_id']=added_users[member]

        # TOODO do private message subscriptions between each users have to
        # be generated from scratch?

        stream_id_count += 1
        recipient_id_count += 1
        logging.info(u"{} -> created".format(channel['name']))

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

    for user in zerver_userprofile:
        zulip_user_id = user['id']
        # this maps the recipients and subscriptions
        # related to private messages
        recipient_id = recipient_id_count
        subscription_id = subscription_id_count

        recipient, sub = build_pm_recipient_sub_from_user(zulip_user_id, recipient_id,
                                                          subscription_id)
        zerver_recipient.append(recipient)
        zerver_subscription.append(sub)
        subscription_id_count += 1
        recipient_id_count += 1

    logging.info('######### IMPORTING STREAMS FINISHED #########\n')
    return zerver_defaultstream, zerver_stream, added_channels, zerver_subscription, \
        zerver_recipient, added_recipient

def build_defaultstream(channel_name: str, realm_id: int, stream_id: int,
                        defaultstream_id: int) -> ZerverFieldsT:
    defaultstream = dict(
        stream=stream_id,
        realm=realm_id,
        id=defaultstream_id)
    return defaultstream

def build_pm_recipient_sub_from_user(zulip_user_id: int, recipient_id: int,
                                     subscription_id: int) -> Tuple[ZerverFieldsT,
                                                                    ZerverFieldsT]:
    recipient = dict(
        type_id=zulip_user_id,
        id=recipient_id,
        type=1)

    sub = dict(
        recipient=recipient_id,
        notifications=False,
        color=random.choice(stream_colors),
        desktop_notifications=True,
        pin_to_top=False,
        in_home_view=True,
        active=True,
        user_profile=zulip_user_id,
        id=subscription_id)

    return recipient, sub

def build_subscription(channel_members: List[str], zerver_subscription: List[ZerverFieldsT],
                       recipient_id: int, added_users: AddedUsersT,
                       subscription_id: int) -> int:
    for member in channel_members:
        sub = dict(
            recipient=recipient_id,
            notifications=False,
            color=random.choice(stream_colors),
            desktop_notifications=True,
            pin_to_top=False,
            in_home_view=True,
            active=True,
            user_profile=added_users[member],
            id=subscription_id)
        # The recipient is a stream for stream-readable message.
        # proof :  https://github.com/zulip/zulip/blob/master/zerver/views/messages.py#L240 &
        # https://github.com/zulip/zulip/blob/master/zerver/views/messages.py#L324
        zerver_subscription.append(sub)
        subscription_id += 1
    return subscription_id

def convert_slack_workspace_messages(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                     added_users: AddedUsersT, added_recipient: AddedRecipientsT,
                                     added_channels: AddedChannelsT, realm: ZerverFieldsT,
                                     zerver_realmemoji: List[ZerverFieldsT],
                                     domain_name: str) -> Tuple[ZerverFieldsT,
                                                                List[ZerverFieldsT],
                                                                List[ZerverFieldsT]]:
    """
    Returns:
    1. message.json, Converted messages
    2. uploads, which is a list of uploads to be mapped in uploads records.json
    3. attachment, which is a list of the attachments
    """
    # now for message.json
    message_json = {}
    zerver_message = []  # type: List[ZerverFieldsT]
    zerver_usermessage = []  # type: List[ZerverFieldsT]
    all_messages = get_all_messages(slack_data_dir, added_channels)

    # we sort the messages according to the timestamp to show messages with
    # the proper date order
    all_messages = sorted(all_messages, key=lambda message: message['ts'])

    logging.info('######### IMPORTING MESSAGES STARTED #########\n')

    zerver_message, zerver_usermessage, attachment, uploads, \
        reactions = channel_message_to_zerver_message(realm_id, users, added_users,
                                                      added_recipient, all_messages,
                                                      zerver_realmemoji,
                                                      realm['zerver_subscription'],
                                                      added_channels,
                                                      domain_name)

    logging.info('######### IMPORTING MESSAGES FINISHED #########\n')

    message_json['zerver_message'] = zerver_message
    message_json['zerver_usermessage'] = zerver_usermessage
    message_json['zerver_reaction'] = reactions

    return message_json, uploads, attachment

def get_all_messages(slack_data_dir: str, added_channels: AddedChannelsT) -> List[ZerverFieldsT]:
    all_messages = []  # type: List[ZerverFieldsT]
    for channel_name in added_channels.keys():
        channel_dir = os.path.join(slack_data_dir, channel_name)
        json_names = os.listdir(channel_dir)
        for json_name in json_names:
            message_dir = os.path.join(channel_dir, json_name)
            messages = get_data_file(message_dir)
            for message in messages:
                # To give every message the channel information
                message['channel_name'] = channel_name
            all_messages += messages
    return all_messages

def channel_message_to_zerver_message(realm_id: int, users: List[ZerverFieldsT],
                                      added_users: AddedUsersT,
                                      added_recipient: AddedRecipientsT,
                                      all_messages: List[ZerverFieldsT],
                                      zerver_realmemoji: List[ZerverFieldsT],
                                      zerver_subscription: List[ZerverFieldsT],
                                      added_channels: AddedChannelsT,
                                      domain_name: str) -> Tuple[List[ZerverFieldsT],
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
    message_id_count = usermessage_id_count = attachment_id_count = reaction_id_count = 0
    zerver_message = []
    zerver_usermessage = []  # type: List[ZerverFieldsT]
    uploads_list = []  # type: List[ZerverFieldsT]
    zerver_attachment = []  # type: List[ZerverFieldsT]
    reaction_list = []  # type: List[ZerverFieldsT]

    # For unicode emoji
    with open(NAME_TO_CODEPOINT_PATH) as fp:
        name_to_codepoint = ujson.load(fp)

    for message in all_messages:
        user = get_message_sending_user(message)
        if not user:
            # Ignore messages without user names
            # These are Sometimes produced by slack
            continue
        if message.get('subtype') in [
                # Zulip doesn't have a pinned_item concept
                "pinned_item",
                "unpinned_item",
                # Slack's channel join/leave notices are spammy
                "channel_join",
                "channel_leave",
                "channel_name"
        ]:
            continue

        has_attachment = has_image = False
        try:
            content, mentioned_users_id, has_link = convert_to_zulip_markdown(
                message['text'], users, added_channels, added_users)
        except Exception:
            print("Slack message unexpectedly missing text representation:")
            print(json.dumps(message, indent=4))
            continue
        rendered_content = None

        recipient_id = added_recipient[message['channel_name']]
        message_id = message_id_count

        # Process message reactions
        if 'reactions' in message.keys():
            reaction_id_count = build_reactions(reaction_list, message['reactions'], added_users,
                                                message_id, reaction_id_count, name_to_codepoint,
                                                zerver_realmemoji)

        # Process different subtypes of slack messages
        if 'subtype' in message.keys():
            subtype = message['subtype']
            # Subtypes which have only the action in the message should
            # be rendered with '/me' in the content initially
            # For example "sh_room_created" has the message 'started a call'
            # which should be displayed as '/me started a call'
            if subtype in ["bot_add", "sh_room_created", "me_message"]:
                content = ('/me %s' % (content))

            # For attachments with slack download link
            elif subtype == "file_share" and 'files.slack.com' in message['file']['url_private']:
                fileinfo = message['file']

                has_attachment = has_link = True
                has_image = True if 'image' in fileinfo['mimetype'] else False

                file_user = [iterate_user for iterate_user in users if message['user'] == user]
                file_user_email = get_user_email(file_user[0], domain_name)

                s3_path, content = get_attachment_path_and_content(fileinfo, realm_id)

                # construct attachments
                build_uploads(added_users[user], realm_id, file_user_email, fileinfo, s3_path,
                              uploads_list)

                attachment_id = attachment_id_count
                build_zerver_attachment(realm_id, message_id, attachment_id, added_users[user],
                                        fileinfo, s3_path, zerver_attachment)
                attachment_id_count += 1

            # For attachments with link not from slack
            # Example: Google drive integration
            elif subtype == "file_share":
                fileinfo = message['file']
                has_link = True
                if 'title' in fileinfo:
                    file_name = fileinfo['title']
                else:
                    file_name = fileinfo['name']
                content = '[%s](%s)' % (file_name, fileinfo['url_private'])

        # construct message
        zulip_message = dict(
            sending_client=1,
            rendered_content_version=1,  # This is Zulip-specific
            has_image=has_image,
            subject='imported from slack',  # This is Zulip-specific
            pub_date=float(message['ts']),
            id=message_id,
            has_attachment=has_attachment,  # attachment will be posted in the subsequent message;
                                            # this is how Slack does it, i.e. less like email
            edit_history=None,
            sender=added_users[user],  # map slack id to zulip id
            content=content,
            rendered_content=rendered_content,  # slack doesn't cache this
            recipient=recipient_id,
            last_edit_time=None,
            has_link=has_link)
        zerver_message.append(zulip_message)

        # construct usermessages
        usermessage_id_count = build_zerver_usermessage(
            zerver_usermessage, usermessage_id_count, zerver_subscription,
            recipient_id, mentioned_users_id, message_id)

        message_id_count += 1
    return zerver_message, zerver_usermessage, zerver_attachment, uploads_list, reaction_list

def get_attachment_path_and_content(fileinfo: ZerverFieldsT, realm_id: int) -> Tuple[str,
                                                                                     str]:
    # Should be kept in sync with its equivalent in zerver/lib/uploads in the function
    # 'upload_message_file'
    s3_path = "/".join([
        str(realm_id),
        'SlackImportAttachment',  # This is a special placeholder which should be kept
                                  # in sync with 'exports.py' function 'import_message_data'
        format(random.randint(0, 255), 'x'),
        random_name(18),
        sanitize_name(fileinfo['name'])
    ])
    attachment_path = ('/user_uploads/%s' % (s3_path))
    content = '[%s](%s)' % (fileinfo['title'], attachment_path)

    return s3_path, content

def build_reactions(reaction_list: List[ZerverFieldsT], reactions: List[ZerverFieldsT],
                    added_users: AddedUsersT, message_id: int, reaction_id: int,
                    name_to_codepoint: ZerverFieldsT,
                    zerver_realmemoji: List[ZerverFieldsT]) -> int:
    realmemoji = {}
    for realm_emoji in zerver_realmemoji:
        realmemoji[realm_emoji['name']] = realm_emoji['id']

    # For the unicode emoji codes, we use equivalent of
    # function 'emoji_name_to_emoji_code' in 'zerver/lib/emoji' here
    for slack_reaction in reactions:
        emoji_name = slack_reaction['name']
        # Check in unicode emoji
        if emoji_name in name_to_codepoint:
            emoji_code = name_to_codepoint[emoji_name]
            reaction_type = Reaction.UNICODE_EMOJI
        # Check in realm emoji
        elif emoji_name in realmemoji:
            emoji_code = realmemoji[emoji_name]
            reaction_type = Reaction.REALM_EMOJI
        else:
            continue

        for user in slack_reaction['users']:
            reaction = dict(
                id=reaction_id,
                emoji_code=emoji_code,
                emoji_name=emoji_name,
                message=message_id,
                reaction_type=reaction_type,
                user_profile=added_users[user])
            reaction_id += 1
            reaction_list.append(reaction)
    return reaction_id

def build_uploads(user_id: int, realm_id: int, email: str, fileinfo: ZerverFieldsT, s3_path: str,
                  uploads_list: List[ZerverFieldsT]) -> None:
    upload = dict(
        path=fileinfo['url_private'],  # Save slack's url here, which is used later while processing
        realm_id=realm_id,
        content_type=None,
        user_profile_id=user_id,
        last_modified=fileinfo['timestamp'],
        user_profile_email=email,
        s3_path=s3_path,
        size=fileinfo['size'])
    uploads_list.append(upload)

def build_zerver_attachment(realm_id: int, message_id: int, attachment_id: int,
                            user_id: int, fileinfo: ZerverFieldsT, s3_path: str,
                            zerver_attachment: List[ZerverFieldsT]) -> None:
    attachment = dict(
        owner=user_id,
        messages=[message_id],
        id=attachment_id,
        size=fileinfo['size'],
        create_time=fileinfo['created'],
        is_realm_public=True,  # is always true for stream message
        path_id=s3_path,
        realm=realm_id,
        file_name=fileinfo['name'])
    zerver_attachment.append(attachment)

def get_message_sending_user(message: ZerverFieldsT) -> Optional[str]:
    if 'user' in message:
        return message['user']
    if message.get('file'):
        return message['file'].get('user')
    return None

def build_zerver_usermessage(zerver_usermessage: List[ZerverFieldsT], usermessage_id: int,
                             zerver_subscription: List[ZerverFieldsT], recipient_id: int,
                             mentioned_users_id: List[int], message_id: int) -> int:
    for subscription in zerver_subscription:
        if subscription['recipient'] == recipient_id:
            flags_mask = 1  # For read
            if subscription['user_profile'] in mentioned_users_id:
                flags_mask = 9  # For read and mentioned

            usermessage = dict(
                user_profile=subscription['user_profile'],
                id=usermessage_id,
                flags_mask=flags_mask,
                message=message_id)
            usermessage_id += 1
            zerver_usermessage.append(usermessage)
    return usermessage_id

def do_convert_data(slack_zip_file: str, output_dir: str, token: str, threads: int=6) -> None:
    # Subdomain is set by the user while running the import command
    realm_subdomain = ""
    realm_id = 0
    domain_name = settings.EXTERNAL_HOST

    slack_data_dir = slack_zip_file.replace('.zip', '')
    if not os.path.exists(slack_data_dir):
        os.makedirs(slack_data_dir)

    os.makedirs(output_dir, exist_ok=True)
    # output directory should be empty initially
    if os.listdir(output_dir):
        raise Exception('Output directory should be empty!')

    subprocess.check_call(['unzip', '-q', slack_zip_file, '-d', slack_data_dir])
    # with zipfile.ZipFile(slack_zip_file, 'r') as zip_ref:
    #     zip_ref.extractall(slack_data_dir)

    # We get the user data from the legacy token method of slack api, which is depreciated
    # but we use it as the user email data is provided only in this method
    user_list = get_slack_api_data(token, "https://slack.com/api/users.list", "members")
    # Get custom emoji from slack api
    custom_emoji_list = get_slack_api_data(token, "https://slack.com/api/emoji.list", "emoji")

    realm, added_users, added_recipient, added_channels, avatar_list, \
        emoji_url_map = slack_workspace_to_realm(domain_name, realm_id, user_list,
                                                 realm_subdomain,
                                                 slack_data_dir, custom_emoji_list)

    message_json, uploads_list, zerver_attachment = convert_slack_workspace_messages(
        slack_data_dir, user_list, realm_id, added_users, added_recipient, added_channels,
        realm, realm['zerver_realmemoji'], domain_name)

    emoji_folder = os.path.join(output_dir, 'emoji')
    os.makedirs(emoji_folder, exist_ok=True)
    emoji_records = process_emojis(realm['zerver_realmemoji'], emoji_folder, emoji_url_map, threads)

    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)
    avatar_records = process_avatars(avatar_list, avatar_folder, realm_id, threads)

    uploads_folder = os.path.join(output_dir, 'uploads')
    os.makedirs(os.path.join(uploads_folder, str(realm_id)), exist_ok=True)
    uploads_records = process_uploads(uploads_list, uploads_folder, threads)
    attachment = {"zerver_attachment": zerver_attachment}

    # IO realm.json
    create_converted_data_files(realm, output_dir, '/realm.json')
    # IO message.json
    create_converted_data_files(message_json, output_dir, '/messages-000001.json')
    # IO emoji records
    create_converted_data_files(emoji_records, output_dir, '/emoji/records.json')
    # IO avatar records
    create_converted_data_files(avatar_records, output_dir, '/avatars/records.json')
    # IO uploads TODO
    create_converted_data_files(uploads_records, output_dir, '/uploads/records.json')
    # IO attachments
    create_converted_data_files(attachment, output_dir, '/attachment.json')

    # remove slack dir
    rm_tree(slack_data_dir)
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

    logging.info('######### DATA CONVERSION FINISHED #########\n')
    logging.info("Zulip data dump created at %s" % (output_dir))

def process_emojis(zerver_realmemoji: List[ZerverFieldsT], emoji_dir: str,
                   emoji_url_map: ZerverFieldsT, threads: int) -> List[ZerverFieldsT]:
    """
    This function gets the custom emojis and saves in the output emoji folder
    """
    def get_emojis(upload: List[str]) -> int:
        slack_emoji_url = upload[0]
        emoji_path = upload[1]
        upload_emoji_path = os.path.join(emoji_dir, emoji_path)

        response = requests.get(slack_emoji_url, stream=True)
        os.makedirs(os.path.dirname(upload_emoji_path), exist_ok=True)
        with open(upload_emoji_path, 'wb') as emoji_file:
            shutil.copyfileobj(response.raw, emoji_file)
        return 0

    emoji_records = []
    upload_emoji_list = []
    logging.info('######### GETTING EMOJIS #########\n')
    logging.info('DOWNLOADING EMOJIS .......\n')
    for emoji in zerver_realmemoji:
        slack_emoji_url = emoji_url_map[emoji['name']]
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=emoji['realm'],
            emoji_file_name=emoji['name'])

        upload_emoji_list.append([slack_emoji_url, emoji_path])

        emoji_record = dict(emoji)
        emoji_record['path'] = emoji_path
        emoji_record['s3_path'] = emoji_path
        emoji_record['realm_id'] = emoji_record['realm']
        emoji_record.pop('realm')

        emoji_records.append(emoji_record)

    # Run downloads parallely
    output = []
    for (status, job) in run_parallel(get_emojis, upload_emoji_list, threads=threads):
        output.append(job)

    logging.info('######### GETTING EMOJIS FINISHED #########\n')
    return emoji_records

def process_avatars(avatar_list: List[ZerverFieldsT], avatar_dir: str,
                    realm_id: int, threads: int) -> List[ZerverFieldsT]:
    """
    This function gets the avatar of size 512 px and saves it in the
    user's avatar directory with both the extensions
    '.png' and '.original'
    """
    def get_avatar(avatar_upload_list: List[str]) -> int:
        # get avatar of size 512
        slack_avatar_url = avatar_upload_list[0]
        image_path = avatar_upload_list[1]
        original_image_path = avatar_upload_list[2]
        response = requests.get(slack_avatar_url + '-512', stream=True)
        with open(image_path, 'wb') as image_file:
            shutil.copyfileobj(response.raw, image_file)
        shutil.copy(image_path, original_image_path)
        return 0

    logging.info('######### GETTING AVATARS #########\n')
    logging.info('DOWNLOADING AVATARS .......\n')
    avatar_original_list = []
    avatar_upload_list = []
    for avatar in avatar_list:
        avatar_hash = user_avatar_path_from_ids(avatar['user_profile_id'], realm_id)
        slack_avatar_url = avatar['path']
        avatar_original = dict(avatar)

        image_path = ('%s/%s.png' % (avatar_dir, avatar_hash))
        original_image_path = ('%s/%s.original' % (avatar_dir, avatar_hash))

        avatar_upload_list.append([slack_avatar_url, image_path, original_image_path])

        # We don't add the size field here in avatar's records.json,
        # since the metadata is not needed on the import end, and we
        # don't have it until we've downloaded the files anyway.
        avatar['path'] = image_path
        avatar['s3_path'] = image_path

        avatar_original['path'] = original_image_path
        avatar_original['s3_path'] = original_image_path
        avatar_original_list.append(avatar_original)

    # Run downloads parallely
    output = []
    for (status, job) in run_parallel(get_avatar, avatar_upload_list, threads=threads):
        output.append(job)

    logging.info('######### GETTING AVATARS FINISHED #########\n')
    return avatar_list + avatar_original_list

def process_uploads(upload_list: List[ZerverFieldsT], upload_dir: str,
                    threads: int) -> List[ZerverFieldsT]:
    """
    This function gets the uploads and saves it in the realm's upload directory
    """
    def get_uploads(upload: List[str]) -> int:
        upload_url = upload[0]
        upload_path = upload[1]
        upload_path = os.path.join(upload_dir, upload_path)

        response = requests.get(upload_url, stream=True)
        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        with open(upload_path, 'wb') as upload_file:
            shutil.copyfileobj(response.raw, upload_file)
        return 0

    logging.info('######### GETTING ATTACHMENTS #########\n')
    logging.info('DOWNLOADING ATTACHMENTS .......\n')
    upload_url_list = []
    for upload in upload_list:
        upload_url = upload['path']
        upload_s3_path = upload['s3_path']
        upload_url_list.append([upload_url, upload_s3_path])
        upload['path'] = upload_s3_path

    # Run downloads parallely
    output = []
    for (status, job) in run_parallel(get_uploads, upload_url_list, threads=threads):
        output.append(job)

    logging.info('######### GETTING ATTACHMENTS FINISHED #########\n')
    return upload_list

def get_data_file(path: str) -> Any:
    data = json.load(open(path))
    return data

def get_slack_api_data(token: str, slack_api_url: str, get_param: str) -> Any:
    data = requests.get('%s?token=%s' % (slack_api_url, token))
    if data.status_code == requests.codes.ok:
        if 'error' in data.json():
            raise Exception('Enter a valid token!')
        json_data = data.json()[get_param]
        return json_data
    else:
        raise Exception('Something went wrong. Please try again!')

def create_converted_data_files(data: Any, output_dir: str, file_path: str) -> None:
    output_file = output_dir + file_path
    json.dump(data, open(output_file, 'w'), indent=4)
