import os
import json
import hashlib
import sys
import argparse
import shutil
import subprocess
import re
import logging
import requests

from django.conf import settings
from django.db import connection
from django.utils.timezone import now as timezone_now
from typing import Any, Dict, List, Tuple
from zerver.models import UserProfile, Realm, Stream, UserMessage, \
    Subscription, Message, Recipient, DefaultStream
from zerver.forms import check_subdomain_available
from zerver.lib.slack_message_conversion import convert_to_zulip_markdown, \
    get_user_full_name
from zerver.lib.avatar_hash import user_avatar_path_from_ids

# stubs
ZerverFieldsT = Dict[str, Any]
AddedUsersT = Dict[str, int]
AddedChannelsT = Dict[str, int]
AddedRecipientsT = Dict[str, int]

def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

def idseq(model_class: Any) -> str:
    return '{}_id_seq'.format(model_class._meta.db_table)

def allocate_ids(model_class: Any, count: int) -> List[int]:
    """
    Increases the sequence number for a given table by the amount of objects being
    imported into that table. Hence, this gives a reserved range of ids to import the converted
    slack objects into the tables.
    """
    conn = connection.cursor()
    sequence = idseq(model_class)
    conn.execute("select nextval('%s') from generate_series(1,%s)" %
                 (sequence, str(count)))
    query = conn.fetchall()  # Each element in the result is a tuple like (5,)
    conn.close()
    # convert List[Tuple[int]] to List[int]
    return [item[0] for item in query]

def slack_workspace_to_realm(domain_name: str, realm_id: int, user_list: List[ZerverFieldsT],
                             realm_subdomain: str, fixtures_path: str,
                             slack_data_dir: str) -> Tuple[ZerverFieldsT, AddedUsersT,
                                                           AddedRecipientsT, AddedChannelsT,
                                                           List[ZerverFieldsT]]:
    """
    Returns:
    1. realm, Converted Realm data
    2. added_users, which is a dictionary to map from slack user id to zulip user id
    3. added_recipient, which is a dictionary to map from channel name to zulip recipient_id
    4. added_channels, which is a dictionary to map from channel name to zulip stream_id
    5. avatars, which is list to map avatars to zulip avatar records.json
    """
    NOW = float(timezone_now().timestamp())

    zerver_realm = build_zerver_realm(fixtures_path, realm_id, realm_subdomain, NOW)

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
                 zerver_realmfilter=[],
                 zerver_realmemoji=[])

    zerver_userprofile, avatars, added_users = users_to_zerver_userprofile(
        slack_data_dir, user_list, realm_id, int(NOW), domain_name)
    channels_to_zerver_stream_fields = channels_to_zerver_stream(slack_data_dir,
                                                                 realm_id,
                                                                 added_users,
                                                                 zerver_userprofile)
    # See https://zulipchat.com/help/set-default-streams-for-new-users
    # for documentation on zerver_defaultstream
    realm['zerver_userprofile'] = zerver_userprofile

    realm['zerver_defaultstream'] = channels_to_zerver_stream_fields[0]
    realm['zerver_stream'] = channels_to_zerver_stream_fields[1]
    realm['zerver_subscription'] = channels_to_zerver_stream_fields[3]
    realm['zerver_recipient'] = channels_to_zerver_stream_fields[4]
    added_channels = channels_to_zerver_stream_fields[2]
    added_recipient = channels_to_zerver_stream_fields[5]

    return realm, added_users, added_recipient, added_channels, avatars

def build_zerver_realm(fixtures_path: str, realm_id: int, realm_subdomain: str,
                       time: float) -> List[ZerverFieldsT]:

    zerver_realm_skeleton = get_data_file(fixtures_path + 'zerver_realm_skeleton.json')

    zerver_realm_skeleton[0]['id'] = realm_id
    zerver_realm_skeleton[0]['string_id'] = realm_subdomain  # subdomain / short_name of realm
    zerver_realm_skeleton[0]['name'] = realm_subdomain
    zerver_realm_skeleton[0]['date_created'] = time

    return zerver_realm_skeleton

def users_to_zerver_userprofile(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                timestamp: Any, domain_name: str) -> Tuple[List[ZerverFieldsT],
                                                                           List[ZerverFieldsT],
                                                                           AddedUsersT]:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. avatar_list, which is list to map avatars to zulip avatard records.json
    3. added_users, which is a dictionary to map from slack user id to zulip
       user id
    """
    logging.info('######### IMPORTING USERS STARTED #########\n')
    total_users = len(users)
    zerver_userprofile = []
    avatar_list = []  # type: List[ZerverFieldsT]
    added_users = {}

    user_id_list = allocate_ids(UserProfile, total_users)

    # We have only one primary owner in slack, see link
    # https://get.slack.help/hc/en-us/articles/201912948-Owners-and-Administrators
    # This is to import the primary owner first from all the users
    user_id_count = 0
    primary_owner_id = user_id_count
    user_id_count += 1

    for user in users:
        slack_user_id = user['id']
        DESKTOP_NOTIFICATION = True

        if user.get('is_primary_owner', False):
            user_id = user_id_list[primary_owner_id]
        else:
            user_id = user_id_list[user_id_count]

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
    logging.info('######### IMPORTING USERS FINISHED #########\n')
    return zerver_userprofile, avatar_list, added_users

def get_user_email(user: ZerverFieldsT, domain_name: str) -> str:
    if 'email' not in user['profile']:
        email = (hashlib.sha256(user['real_name'].encode()).hexdigest() +
                 "@%s" % (domain_name))
    else:
        email = user['profile']['email']
    return email

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
    3. added_channels, which is a dictionary to map from channel name to zulip stream_id
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

    # Pre-compute all the total number of ids to fastword the ids in active db
    total_channels = len(channels)
    total_users = len(zerver_userprofile)
    total_recipients = total_channels + total_users
    total_subscription = total_users
    for channel in channels:
        for member in channel['members']:
            total_subscription += 1

    stream_id_list = allocate_ids(Stream, total_channels)
    subscription_id_list = allocate_ids(Subscription, total_subscription)
    recipient_id_list = allocate_ids(Recipient, total_recipients)
    # corresponding to channels 'general' and 'random' which are slack specific
    defaultstream_id_list = allocate_ids(DefaultStream, 2)

    stream_id_count = subscription_id_count = recipient_id_count = defaultstream_id = 0

    for channel in channels:
        # slack_channel_id = channel['id']

        # map Slack's topic and purpose content into Zulip's stream description.
        # WARN This mapping is lossy since the topic.creator, topic.last_set,
        # purpose.creator, purpose.last_set fields are not preserved.
        description = "topic: {}\npurpose: {}".format(channel["topic"]["value"],
                                                      channel["purpose"]["value"])
        stream_id = stream_id_list[stream_id_count]
        recipient_id = recipient_id_list[recipient_id_count]

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
                                                defaultstream_id_list[defaultstream_id])
            zerver_defaultstream.append(defaultstream)
            defaultstream_id += 1

        zerver_stream.append(stream)
        added_channels[stream['name']] = stream_id

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
                                                   subscription_id_list, subscription_id_count)
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
        recipient_id = recipient_id_list[recipient_id_count]
        subscription_id = subscription_id_list[subscription_id_count]

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
        color="#c2c2c2",
        desktop_notifications=True,
        pin_to_top=False,
        in_home_view=True,
        active=True,
        user_profile=zulip_user_id,
        id=subscription_id)

    return recipient, sub

def build_subscription(channel_members: List[str], zerver_subscription: List[ZerverFieldsT],
                       recipient_id: int, added_users: AddedUsersT,
                       subscription_id_list: List[int], subscription_id_count: int) -> int:
    for member in channel_members:
        subscription_id = subscription_id_list[subscription_id_count]
        sub = dict(
            recipient=recipient_id,
            notifications=False,
            color="#c2c2c2",
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
        subscription_id_count += 1
    return subscription_id_count

def convert_slack_workspace_messages(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                     added_users: AddedUsersT, added_recipient: AddedRecipientsT,
                                     added_channels: AddedChannelsT,
                                     realm: ZerverFieldsT) -> ZerverFieldsT:
    """
    Returns:
    1. message.json, Converted messages
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

    # To pre-compute the total number of messages and usermessages
    total_messages, total_usermessages = get_total_messages_and_usermessages(
        realm['zerver_subscription'], added_recipient, all_messages)

    message_id_list = allocate_ids(Message, total_messages)
    usermessage_id_list = allocate_ids(UserMessage, total_usermessages)

    id_list = [message_id_list, usermessage_id_list]
    zerver_message, zerver_usermessage = channel_message_to_zerver_message(
        realm_id, users, added_users, added_recipient, all_messages,
        realm['zerver_subscription'], id_list)

    logging.info('######### IMPORTING MESSAGES FINISHED #########\n')

    message_json['zerver_message'] = zerver_message
    message_json['zerver_usermessage'] = zerver_usermessage

    return message_json

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

def get_total_messages_and_usermessages(zerver_subscription: List[ZerverFieldsT],
                                        added_recipient: AddedRecipientsT,
                                        all_messages: List[ZerverFieldsT]) -> Tuple[int, int]:
    """
    Returns:
    1. message_id, which is total number of messages
    2. usermessage_id, which is total number of usermessages
    """
    total_messages = 0
    total_usermessages = 0

    for message in all_messages:
        if 'subtype' in message.keys():
            subtype = message['subtype']
            if subtype in ["channel_join", "channel_leave", "channel_name"]:
                continue

        for subscription in zerver_subscription:
            if subscription['recipient'] == added_recipient[message['channel_name']]:
                total_usermessages += 1
        total_messages += 1

    return total_messages, total_usermessages

def channel_message_to_zerver_message(realm_id: int, users: List[ZerverFieldsT],
                                      added_users: AddedUsersT,
                                      added_recipient: AddedRecipientsT,
                                      all_messages: List[ZerverFieldsT],
                                      zerver_subscription: List[ZerverFieldsT],
                                      ids: List[Any]) -> Tuple[List[ZerverFieldsT],
                                                               List[ZerverFieldsT]]:
    """
    Returns:
    1. zerver_message, which is a list of the messages
    2. zerver_usermessage, which is a list of the usermessages
    """
    message_id_count = usermessage_id_count = 0
    message_id_list, usermessage_id_list = ids
    zerver_message = []
    zerver_usermessage = []  # type: List[ZerverFieldsT]

    for message in all_messages:
        user = get_message_sending_user(message)
        if not user:
            # Ignore messages without user names
            # These are Sometimes produced by slack
            continue

        has_attachment = False
        content, mentioned_users_id, has_link = convert_to_zulip_markdown(message['text'],
                                                                          users,
                                                                          added_users)
        rendered_content = None
        if 'subtype' in message.keys():
            subtype = message['subtype']
            if subtype in ["channel_join", "channel_leave", "channel_name"]:
                continue

        recipient_id = added_recipient[message['channel_name']]
        message_id = message_id_list[message_id_count]
        # construct message
        zulip_message = dict(
            sending_client=1,
            rendered_content_version=1,  # This is Zulip-specific
            has_image=message.get('has_image', False),
            subject='from slack',  # This is Zulip-specific
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
            zerver_usermessage, usermessage_id_count, usermessage_id_list,
            zerver_subscription, recipient_id, mentioned_users_id, message_id)

        message_id_count += 1
    return zerver_message, zerver_usermessage

def get_message_sending_user(message: ZerverFieldsT) -> str:
    try:
        user = message.get('user', message['file']['user'])
    except KeyError:
        user = message.get('user')
    return user

def build_zerver_usermessage(zerver_usermessage: List[ZerverFieldsT], usermessage_id_count: int,
                             usermessage_id_list: List[int],
                             zerver_subscription: List[ZerverFieldsT], recipient_id: int,
                             mentioned_users_id: List[int], message_id: int) -> int:
    for subscription in zerver_subscription:
        if subscription['recipient'] == recipient_id:
            flags_mask = 1  # For read
            if subscription['user_profile'] in mentioned_users_id:
                flags_mask = 9  # For read and mentioned

            usermessage = dict(
                user_profile=subscription['user_profile'],
                id=usermessage_id_list[usermessage_id_count],
                flags_mask=flags_mask,
                message=message_id)
            usermessage_id_count += 1
            zerver_usermessage.append(usermessage)
    return usermessage_id_count

def do_convert_data(slack_zip_file: str, realm_subdomain: str, output_dir: str, token: str) -> None:
    check_subdomain_available(realm_subdomain)

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

    script_path = os.path.dirname(os.path.abspath(__file__)) + '/'
    fixtures_path = script_path + '../fixtures/'

    realm_id = allocate_ids(Realm, 1)[0]

    user_list = get_user_data(token)
    realm, added_users, added_recipient, added_channels, avatar_list = slack_workspace_to_realm(
        domain_name, realm_id, user_list, realm_subdomain, fixtures_path, slack_data_dir)

    message_json = convert_slack_workspace_messages(slack_data_dir, user_list, realm_id,
                                                    added_users, added_recipient, added_channels,
                                                    realm)

    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))

    os.makedirs(avatar_realm_folder, exist_ok=True)
    avatar_records = process_avatars(avatar_list, avatar_folder, realm_id)

    zerver_attachment = []  # type: List[ZerverFieldsT]
    attachment = {"zerver_attachment": zerver_attachment}

    # IO realm.json
    create_converted_data_files(realm, output_dir, '/realm.json', False)
    # IO message.json
    create_converted_data_files(message_json, output_dir, '/messages-000001.json', False)
    # IO avatar records
    create_converted_data_files(avatar_records, output_dir, '/avatars/records.json', False)
    # IO uploads TODO
    create_converted_data_files([], output_dir, '/uploads/records.json', True)
    # IO attachments
    create_converted_data_files(attachment, output_dir, '/attachment.json', False)

    # remove slack dir
    rm_tree(slack_data_dir)
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

    logging.info('######### DATA CONVERSION FINISHED #########\n')
    logging.info("Zulip data dump created at %s" % (output_dir))

def process_avatars(avatar_list: List[ZerverFieldsT], avatar_dir: str,
                    realm_id: int) -> List[ZerverFieldsT]:
    """
    This function gets the avatar of size 512 px and saves it in the
    user's avatar directory with both the extensions
    '.png' and '.original'
    """
    logging.info('######### GETTING AVATARS #########\n')
    avatar_original_list = []
    for avatar in avatar_list:
        avatar_hash = user_avatar_path_from_ids(avatar['user_profile_id'], realm_id)
        slack_avatar_url = avatar['path']
        avatar_original = dict(avatar)

        image_path = ('%s/%s.png' % (avatar_dir, avatar_hash))
        original_image_path = ('%s/%s.original' % (avatar_dir, avatar_hash))

        # Fetch the avatars from the url
        get_avatar(slack_avatar_url, image_path, original_image_path)
        image_size = os.stat(image_path).st_size

        avatar['path'] = image_path
        avatar['s3_path'] = image_path
        avatar['size'] = image_size

        avatar_original['path'] = original_image_path
        avatar_original['s3_path'] = original_image_path
        avatar_original['size'] = image_size
        avatar_original_list.append(avatar_original)
    logging.info('######### GETTING AVATARS FINISHED #########\n')
    return avatar_list + avatar_original_list

def get_avatar(slack_avatar_url: str, image_path: str, original_image_path: str) -> None:
    # get avatar of size 512
    response = requests.get(slack_avatar_url + '-512', stream=True)
    with open(image_path, 'wb') as image_file:
        shutil.copyfileobj(response.raw, image_file)
    shutil.copy(image_path, original_image_path)

def get_data_file(path: str) -> Any:
    data = json.load(open(path))
    return data

def get_user_data(token: str) -> List[ZerverFieldsT]:
    slack_user_list_url = "https://slack.com/api/users.list"
    user_list = requests.get('%s?token=%s' % (slack_user_list_url, token))
    if user_list.status_code == requests.codes.ok:
        user_list_json = user_list.json()['members']
        return user_list_json
    else:
        raise Exception('Enter a valid token!')

def create_converted_data_files(data: Any, output_dir: str, file_path: str,
                                make_new_dir: bool) -> None:
    output_file = output_dir + file_path
    if make_new_dir:
        new_directory = os.path.dirname(file_path)
        os.makedirs(output_dir + new_directory, exist_ok=True)
    json.dump(data, open(output_file, 'w'))
