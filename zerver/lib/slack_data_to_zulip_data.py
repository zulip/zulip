import os
import json
import hashlib
import sys
import argparse
import shutil
import subprocess
import re

from django.utils.timezone import now as timezone_now
from typing import Any, Dict, List, Tuple
from zerver.models import UserProfile, Realm, Stream, UserMessage, \
    Subscription, Message, Recipient, DefaultStream, Attachment
from zerver.forms import check_subdomain_available
from zerver.lib.slack_message_conversion import convert_to_zulip_markdown, \
    get_user_full_name

# stubs
ZerverFieldsT = Dict[str, Any]
AddedUsersT = Dict[str, int]
AddedChannelsT = Dict[str, int]
AddedRecipientsT = Dict[str, int]

def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

def get_model_id(model: Any, table_name: str, sequence_increase_factor: int) -> int:
    """
    Increases the sequence number for a given table by the amount of objects being
    imported into that table. Hence, this gives a reserved range of ids to import the converted
    slack objects into the tables.
    """
    if model.objects.all().last():
        start_id_sequence = model.objects.all().last().id + 1
    else:
        start_id_sequence = 1

    restart_sequence_id = start_id_sequence + sequence_increase_factor
    sequence_name = table_name + '_id_Seq'
    increment_id_command = "ALTER SEQUENCE %s RESTART WITH %s" % (sequence_name,
                                                                  str(restart_sequence_id))

    os.system('echo %s | ./manage.py dbshell' % (increment_id_command))
    return start_id_sequence

def users_to_zerver_userprofile(slack_data_dir: str, realm_id: int, timestamp: Any,
                                domain_name: str) -> Tuple[List[ZerverFieldsT], AddedUsersT]:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. added_users, which is a dictionary to map from slack user id to zulip
       user id
    """
    print('######### IMPORTING USERS STARTED #########\n')
    users = json.load(open(slack_data_dir + '/users.json'))
    total_users = len(users)
    zerver_userprofile = []
    added_users = {}

    user_id_count = get_model_id(UserProfile, 'zerver_userprofile', total_users)
    for user in users:
        slack_user_id = user['id']
        profile = user['profile']
        DESKTOP_NOTIFICATION = True

        # email
        if 'email' not in profile:
            email = (hashlib.sha256(user['real_name'].encode()).hexdigest() +
                     "@%s" % (domain_name))
        else:
            email = profile['email']

        # avatar
        # ref: https://chat.zulip.org/help/change-your-avatar
        avatar_source = 'U'
        if 'gravatar.com' in profile['image_32']:
            # use the avatar from gravatar
            avatar_source = 'G'

        # timezone
        _default_timezone = "America/New_York"
        timezone = user.get("tz", _default_timezone)
        if timezone is None or '/' not in timezone:
            timezone = _default_timezone

        # userprofile's quota is hardcoded as per
        # https://github.com/zulip/zulip/blob/e1498988d9094961e6f9988fb308b3e7310a8e74/zerver/migrations/0059_userprofile_quota.py#L18
        userprofile = dict(
            enable_desktop_notifications=DESKTOP_NOTIFICATION,
            is_staff=user.get('is_admin', False),
            avatar_source=avatar_source,
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
            is_realm_admin=user.get('is_owner', False),
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
            quota=1073741824,
            # invites_used=0,  # TODO
            id=user_id_count)

        # TODO map the avatar
        # zerver auto-infer the url from Gravatar instead of from a specified
        # url; zerver.lib.avatar needs to be patched
        # profile['image_32'], Slack has 24, 32, 48, 72, 192, 512 size range

        zerver_userprofile.append(userprofile)
        added_users[slack_user_id] = user_id_count
        user_id_count += 1
        print(u"{} -> {}\nCreated\n".format(user['name'], userprofile['email']))
    print('######### IMPORTING USERS FINISHED #########\n')
    return zerver_userprofile, added_users

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
    """
    print('######### IMPORTING CHANNELS STARTED #########\n')
    channels = json.load(open(slack_data_dir + '/channels.json'))

    added_channels = {}
    added_recipient = {}

    zerver_stream = []
    zerver_subscription = []
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

    stream_id_count = get_model_id(Stream, 'zerver_stream', total_users)
    subscription_id_count = get_model_id(Subscription, 'zerver_subscription', total_subscription)
    recipient_id_count = get_model_id(Recipient, 'zerver_recipient', total_recipients)

    for channel in channels:
        # slack_channel_id = channel['id']

        # map Slack's topic and purpose content into Zulip's stream description.
        # WARN This mapping is lossy since the topic.creator, topic.last_set,
        # purpose.creator, purpose.last_set fields are not preserved.
        description = "topic: {}\npurpose: {}".format(channel["topic"]["value"],
                                                      channel["purpose"]["value"])

        # construct the stream object and append it to zerver_stream
        stream = dict(
            realm=realm_id,
            name=channel["name"],
            deactivated=channel["is_archived"],
            description=description,
            invite_only=not channel["is_general"],
            date_created=float(channel["created"]),
            id=stream_id_count)

        if channel["name"] == "general":
            defaultstream = dict(
                stream=stream_id_count,
                realm=realm_id,
                id=get_model_id(DefaultStream, 'zerver_defaultstream', 1))
            zerver_defaultstream.append(defaultstream)

        zerver_stream.append(stream)
        added_channels[stream['name']] = stream_id_count

        # construct the recipient object and append it to zerver_recipient
        # type 1: private
        # type 2: stream
        # type 3: huddle
        recipient = dict(
            type_id=stream_id_count,
            id=recipient_id_count,
            type=2)
        zerver_recipient.append(recipient)
        added_recipient[stream['name']] = recipient_id_count
        # TOODO add recipients for private message and huddles

        # construct the subscription object and append it to zerver_subscription
        for member in channel['members']:
            sub = dict(
                recipient=recipient_id_count,
                notifications=False,
                color="#c2c2c2",
                desktop_notifications=True,
                pin_to_top=False,
                in_home_view=True,
                active=True,
                user_profile=added_users[member],
                id=subscription_id_count)
            # The recipient is a stream for stream-readable message.
            # proof :  https://github.com/zulip/zulip/blob/master/zerver/views/messages.py#L240 &
            # https://github.com/zulip/zulip/blob/master/zerver/views/messages.py#L324
            zerver_subscription.append(sub)
            subscription_id_count += 1
            # TOODO add zerver_subscription which correspond to
            # huddles type recipient
            # For huddles:
            # sub['recipient']=recipient['id'] where recipient['type_id']=added_users[member]

            # TOODO do private message subscriptions between each users have to
            # be generated from scratch?

        stream_id_count += 1
        recipient_id_count += 1
        print(u"{} -> created\n".format(channel['name']))

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

        recipient = dict(
            type_id=zulip_user_id,
            id=recipient_id_count,
            type=1)
        zerver_recipient.append(recipient)

        sub = dict(
            recipient=recipient_id_count,
            notifications=False,
            color="#c2c2c2",
            desktop_notifications=True,
            pin_to_top=False,
            in_home_view=True,
            active=True,
            user_profile=zulip_user_id,
            id=subscription_id_count)

        zerver_subscription.append(sub)
        subscription_id_count += 1
        recipient_id_count += 1

    print('######### IMPORTING STREAMS FINISHED #########\n')
    return zerver_defaultstream, zerver_stream, added_channels, zerver_subscription, \
        zerver_recipient, added_recipient

def get_total_messages_and_attachments(slack_data_dir: str, channel: str,
                                       zerver_userprofile: List[ZerverFieldsT],
                                       zerver_subscription: List[ZerverFieldsT],
                                       added_recipient: AddedRecipientsT) -> Tuple[int,
                                                                                   int,
                                                                                   int]:
    """
    Returns:
    1. message_id, which is total number of messages
    2. usermessage_id, which is total number of usermessages
    3. attachment_id, which is total number of attachments
    """
    json_names = os.listdir(slack_data_dir + '/' + channel)
    total_messages = 0
    total_usermessages = 0
    total_attachments = 0

    for json_name in json_names:
        messages = json.load(open(slack_data_dir + '/%s/%s' % (channel, json_name)))
        for message in messages:
            if 'subtype' in message.keys():
                subtype = message['subtype']
                if subtype in ["channel_join", "channel_leave", "channel_name"]:
                    continue
                elif subtype == "file_share":
                    total_attachments += 1

            for subscription in zerver_subscription:
                if subscription['recipient'] == added_recipient[channel]:
                    total_usermessages += 1
            total_messages += 1

    return total_messages, total_usermessages, total_attachments

def channel_message_to_zerver_message(constants: List[Any], channel: str,
                                      added_users: AddedUsersT, added_recipient: AddedRecipientsT,
                                      zerver_userprofile: List[ZerverFieldsT],
                                      zerver_subscription: List[ZerverFieldsT],
                                      ids: List[int]) -> Tuple[List[ZerverFieldsT],
                                                               List[ZerverFieldsT],
                                                               List[ZerverFieldsT]]:
    """
    Returns:
    1. zerver_message, which is a list of the messages
    2. zerver_usermessage, which is a list of the usermessages
    """
    slack_data_dir, REALM_ID = constants
    message_id, usermessage_id, attachment_id = ids
    json_names = os.listdir(slack_data_dir + '/' + channel)
    users = json.load(open(slack_data_dir + '/users.json'))
    zerver_message = []
    zerver_usermessage = []
    zerver_attachment = []

    for json_name in json_names:
        messages = json.load(open(slack_data_dir + '/%s/%s' % (channel, json_name)))
        for message in messages:
            has_attachment = False
            url_private = None
            content, mentioned_users_id, has_link = convert_to_zulip_markdown(message['text'],
                                                                              users,
                                                                              added_users)
            rendered_content = None
            try:
                user = message.get('user', message['file']['user'])
            except KeyError:
                user = message['user']
            if 'subtype' in message.keys():
                subtype = message['subtype']
                if subtype in ["channel_join", "channel_leave", "channel_name"]:
                    continue
                elif subtype == "file_share":
                    has_attachment = True
                    fileinfo = message['file']
                    url_private = fileinfo['url_private']
                    zerver_attachment.append(dict(
                        owner=added_users[user],
                        messages=[message_id],
                        id=attachment_id,
                        size=fileinfo['size'],
                        create_time=fileinfo['created'],
                        is_realm_public=True,  # is always strue for stream message
                        path_id="",  # TODO
                        realm=1,
                        file_name=fileinfo['name']
                    ))
                    attachment_id += 1

            recipient_id = added_recipient[channel]
            # construct message
            zulip_message = dict(
                sending_client=1,
                rendered_content_version=1,  # This is Zulip-specific
                has_image=message.get('has_image', False),
                subject=channel,  # This is Zulip-specific
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
            for subscription in zerver_subscription:
                if subscription['recipient'] == recipient_id:
                    flags_mask = 1  # For read
                    if subscription['user_profile'] in mentioned_users_id:
                        flags_mask = 9  # For read and mentioned

                    usermessage = dict(
                        user_profile=subscription['user_profile'],
                        id=usermessage_id,
                        flags_mask=flags_mask,
                        message=zulip_message['id'])
                    usermessage_id += 1
                    zerver_usermessage.append(usermessage)
            message_id += 1
    return zerver_message, zerver_usermessage

def do_convert_data(slack_zip_file: str, realm_subdomain: str, output_dir: str) -> None:
    check_subdomain_available(realm_subdomain)
    slack_data_dir = slack_zip_file.replace('.zip', '')
    if not os.path.exists(slack_data_dir):
        os.makedirs(slack_data_dir)
    subprocess.check_call(['unzip', '-q', slack_zip_file, '-d', slack_data_dir])
    # with zipfile.ZipFile(slack_zip_file, 'r') as zip_ref:
    #     zip_ref.extractall(slack_data_dir)

    # TODO fetch realm config from zulip config
    DOMAIN_NAME = "zulipchat.com"

    REALM_ID = get_model_id(Realm, 'zerver_realm', 1)
    NOW = float(timezone_now().timestamp())

    script_path = os.path.dirname(os.path.abspath(__file__)) + '/'
    fixtures_path = script_path + '../fixtures/'
    zerver_realm_skeleton = json.load(open(fixtures_path + 'zerver_realm_skeleton.json'))
    zerver_realm_skeleton[0]['id'] = REALM_ID

    zerver_realm_skeleton[0]['string_id'] = realm_subdomain  # subdomain / short_name of realm
    zerver_realm_skeleton[0]['name'] = realm_subdomain
    zerver_realm_skeleton[0]['date_created'] = NOW

    realm = dict(zerver_client=[{"name": "populate_db", "id": 1},
                                {"name": "website", "id": 2},
                                {"name": "API", "id": 3}],
                 zerver_userpresence=[],  # shows last logged in data, which is not available in slack
                 zerver_userprofile_mirrordummy=[],
                 zerver_realmdomain=[{"realm": REALM_ID,
                                      "allow_subdomains": False,
                                      "domain": DOMAIN_NAME,
                                      "id": REALM_ID}],
                 zerver_useractivity=[],
                 zerver_realm=zerver_realm_skeleton,
                 zerver_huddle=[],
                 zerver_userprofile_crossrealm=[],
                 zerver_useractivityinterval=[],
                 zerver_realmfilter=[],
                 zerver_realmemoji=[])

    zerver_userprofile, added_users = users_to_zerver_userprofile(slack_data_dir,
                                                                  REALM_ID,
                                                                  int(NOW),
                                                                  DOMAIN_NAME)
    realm['zerver_userprofile'] = zerver_userprofile

    channels_to_zerver_stream_fields = channels_to_zerver_stream(slack_data_dir,
                                                                 REALM_ID,
                                                                 added_users,
                                                                 zerver_userprofile)
    # See https://zulipchat.com/help/set-default-streams-for-new-users
    # for documentation on zerver_defaultstream
    realm['zerver_defaultstream'] = channels_to_zerver_stream_fields[0]
    realm['zerver_stream'] = channels_to_zerver_stream_fields[1]
    realm['zerver_subscription'] = channels_to_zerver_stream_fields[3]
    realm['zerver_recipient'] = channels_to_zerver_stream_fields[4]
    added_channels = channels_to_zerver_stream_fields[2]
    added_recipient = channels_to_zerver_stream_fields[5]

    # IO realm.json
    realm_file = output_dir + '/realm.json'
    json.dump(realm, open(realm_file, 'w'))

    # now for message.json
    message_json = {}
    zerver_message = []  # type: List[ZerverFieldsT]
    zerver_usermessage = []  # type: List[ZerverFieldsT]
    zerver_attachment = []  # type: List[ZerverFieldsT]

    print('######### IMPORTING MESSAGES STARTED #########\n')
    # To pre-compute the total number of messages and usermessages
    total_messages = 0
    total_usermessages = 0
    total_attachments = 0
    for channel in added_channels.keys():
        tm, tum, ta = get_total_messages_and_attachments(
            slack_data_dir, channel, zerver_userprofile,
            realm['zerver_subscription'], added_recipient)
        total_messages += tm
        total_usermessages += tum
        total_attachments += ta
    message_id_count = get_model_id(Message, 'zerver_message', total_messages)
    usermessage_id_count = get_model_id(UserMessage, 'zerver_usermessage', total_usermessages)
    attachment_id_count = get_model_id(Attachment, 'zerver_attachment', total_attachments)

    constants = [slack_data_dir, REALM_ID]
    for channel in added_channels.keys():
        message_id = len(zerver_message) + message_id_count  # For the id of the messages
        usermessage_id = len(zerver_usermessage) + usermessage_id_count
        attachment_id = len(zerver_attachment) + attachment_id_count
        id_list = [message_id, usermessage_id, attachment_id]
        zm, zum, za = channel_message_to_zerver_message(
            constants, channel, added_users, added_recipient,
            zerver_userprofile, realm['zerver_subscription'], id_list)
        zerver_message += zm
        zerver_usermessage += zum
        zerver_attachment += za
    print('######### IMPORTING MESSAGES FINISHED #########\n')

    message_json['zerver_message'] = zerver_message
    message_json['zerver_usermessage'] = zerver_usermessage
    # IO message.json
    message_file = output_dir + '/messages-000001.json'
    json.dump(message_json, open(message_file, 'w'))

    # IO avatar records
    avatar_records_file = output_dir + '/avatars/records.json'
    os.makedirs(output_dir + '/avatars', exist_ok=True)
    json.dump([], open(avatar_records_file, 'w'))

    # IO uploads TODO
    uploads_records_file = output_dir + '/uploads/records.json'
    os.makedirs(output_dir + '/uploads', exist_ok=True)
    json.dump([], open(uploads_records_file, 'w'))

    # IO attachments
    attachment_file = output_dir + '/attachment.json'
    attachment = {"zerver_attachment": zerver_attachment}
    json.dump(attachment, open(attachment_file, 'w'))

    # remove slack dir
    rm_tree(slack_data_dir)
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

    print('######### DATA CONVERSION FINISHED #########\n')
    print("Zulip data dump created at %s" % (output_dir))
    sys.exit(0)
