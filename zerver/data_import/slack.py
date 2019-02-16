import os
import ujson
import shutil
import subprocess
import logging
import random
import requests

from collections import defaultdict

from django.conf import settings
from django.utils.timezone import now as timezone_now
from django.forms.models import model_to_dict
from typing import Any, Dict, List, Optional, Tuple, Set, Iterator
from zerver.models import Reaction, RealmEmoji, UserProfile, Recipient, \
    CustomProfileField, CustomProfileFieldValue
from zerver.data_import.slack_message_conversion import convert_to_zulip_markdown, \
    get_user_full_name
from zerver.data_import.import_util import ZerverFieldsT, build_zerver_realm, \
    build_avatar, build_subscription, build_recipient, build_usermessages, \
    build_defaultstream, build_attachment, process_avatars, process_uploads, \
    process_emojis, build_realm, build_stream, build_message, \
    create_converted_data_files, make_subscriber_map
from zerver.data_import.sequencer import NEXT_ID
from zerver.lib.upload import random_name, sanitize_name
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.lib.emoji import NAME_TO_CODEPOINT_PATH

# stubs
AddedUsersT = Dict[str, int]
AddedChannelsT = Dict[str, Tuple[str, int]]
AddedRecipientsT = Dict[str, int]

def rm_tree(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)

def slack_workspace_to_realm(domain_name: str, realm_id: int, user_list: List[ZerverFieldsT],
                             realm_subdomain: str, slack_data_dir: str,
                             custom_emoji_list: ZerverFieldsT) -> Tuple[ZerverFieldsT, AddedUsersT,
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

    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW, 'Slack')  # type: List[ZerverFieldsT]
    realm = build_realm(zerver_realm, realm_id, domain_name)

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
    realm['zerver_customprofilefieldvalue'] = zerver_customprofilefield_value

    realm['zerver_defaultstream'] = channels_to_zerver_stream_fields[0]
    realm['zerver_stream'] = channels_to_zerver_stream_fields[1]
    realm['zerver_subscription'] = channels_to_zerver_stream_fields[3]
    realm['zerver_recipient'] = channels_to_zerver_stream_fields[4]
    added_channels = channels_to_zerver_stream_fields[2]
    added_recipient = channels_to_zerver_stream_fields[5]

    return realm, added_users, added_recipient, added_channels, avatars, emoji_url_map

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
    slack_user_custom_field_map = {}  # type: ZerverFieldsT
    # To store custom fields corresponding to their ids
    custom_field_map = {}  # type: ZerverFieldsT

    for user in slack_data_file_user_list:
        process_slack_custom_fields(user, slack_user_custom_field_map)

    # We have only one primary owner in slack, see link
    # https://get.slack.help/hc/en-us/articles/201912948-Owners-and-Administrators
    # This is to import the primary owner first from all the users
    user_id_count = custom_field_id_count = customprofilefield_id = 0
    primary_owner_id = user_id_count
    user_id_count += 1

    for user in users:
        slack_user_id = user['id']

        if user.get('is_primary_owner', False):
            user_id = primary_owner_id
        else:
            user_id = user_id_count

        # email
        email = get_user_email(user, domain_name)

        # avatar
        # ref: https://chat.zulip.org/help/set-your-avatar
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

        userprofile = UserProfile(
            full_name=get_user_full_name(user),
            short_name=user['name'],
            is_active=not user['deleted'],
            id=user_id,
            email=email,
            delivery_email=email,
            avatar_source='U',
            is_bot=user.get('is_bot', False),
            pointer=-1,
            is_realm_admin=realm_admin,
            bot_type=1 if user.get('is_bot', False) else None,
            date_joined=timestamp,
            timezone=timezone,
            last_login=timestamp)
        userprofile_dict = model_to_dict(userprofile)
        # Set realm id separately as the corresponding realm is not yet a Realm model instance
        userprofile_dict['realm'] = realm_id

        zerver_userprofile.append(userprofile_dict)
        added_users[slack_user_id] = user_id
        if not user.get('is_primary_owner', False):
            user_id_count += 1

        logging.info(u"{} -> {}".format(user['name'], userprofile_dict['email']))

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
            slack_custom_fields = ['phone', 'skype']
            if field in slack_custom_fields:
                field_name = field
            else:
                field_name = ("slack custom field %s" % str(customprofilefield_id + 1))
            customprofilefield = CustomProfileField(
                id=customprofilefield_id,
                name=field_name,
                field_type=1  # For now this is defaulted to 'SHORT_TEXT'
                              # Processing is done in the function 'process_customprofilefields'
            )

            customprofilefield_dict = model_to_dict(customprofilefield,
                                                    exclude=['realm'])
            customprofilefield_dict['realm'] = realm_id

            custom_field_map[field] = customprofilefield_id
            customprofilefield_id += 1
            customprofile_field.append(customprofilefield_dict)
    return custom_field_map, customprofilefield_id

def process_slack_custom_fields(user: ZerverFieldsT,
                                slack_user_custom_field_map: ZerverFieldsT) -> None:
    slack_user_custom_field_map[user['id']] = {}
    if user['profile'].get('fields'):
        slack_user_custom_field_map[user['id']] = user['profile']['fields']

    slack_custom_fields = ['phone', 'skype']
    for field in slack_custom_fields:
        if field in user['profile']:
            slack_user_custom_field_map[user['id']][field] = {'value': user['profile'][field]}

def build_customprofilefields_values(custom_field_map: ZerverFieldsT, fields: ZerverFieldsT,
                                     user_id: int, custom_field_id: int,
                                     custom_field_values: List[ZerverFieldsT]) -> int:
    for field, value in fields.items():
        if value['value'] == "":
            # Skip writing entries for fields with an empty value
            continue
        custom_field_value = CustomProfileFieldValue(
            id=custom_field_id,
            value=value['value'])

        custom_field_value_dict = model_to_dict(custom_field_value,
                                                exclude=['user_profile', 'field'])
        custom_field_value_dict['user_profile'] = user_id
        custom_field_value_dict['field'] = custom_field_map[field]

        custom_field_values.append(custom_field_value_dict)
        custom_field_id += 1
    return custom_field_id

def process_customprofilefields(customprofilefield: List[ZerverFieldsT],
                                customprofilefield_value: List[ZerverFieldsT]) -> None:
    # Process the field types by checking all field values
    for field in customprofilefield:
        for field_value in customprofilefield_value:
            if field_value['field'] == field['id'] and len(field_value['value']) > 50:
                field['field_type'] = 2  # corresponding to Long text
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
    if get_user_full_name(user).lower() == "slackbot":
        return "imported-slackbot-bot@%s" % (domain_name,)
    raise AssertionError("Could not find email address for Slack user %s" % (user,))

def build_avatar_url(slack_user_id: str, team_id: str, avatar_hash: str) -> str:
    avatar_url = "https://ca.slack-edge.com/{}-{}-{}".format(team_id, slack_user_id,
                                                             avatar_hash)
    return avatar_url

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
        stream = build_stream(float(channel["created"]), realm_id, channel["name"],
                              description, stream_id, channel["is_archived"])
        zerver_stream.append(stream)

        # construct defaultstream object
        # slack has the default channel 'general' and 'random'
        # where every user is subscribed
        default_channels = ['general', 'random']  # Slack specific
        if channel['name'] in default_channels:
            defaultstream = build_defaultstream(realm_id, stream_id,
                                                defaultstream_id)
            zerver_defaultstream.append(defaultstream)
            defaultstream_id += 1

        added_channels[stream['name']] = (channel['id'], stream_id)

        recipient = build_recipient(stream_id, recipient_id, Recipient.STREAM)
        zerver_recipient.append(recipient)
        added_recipient[stream['name']] = recipient_id
        # TODO add recipients for private message and huddles

        # construct the subscription object and append it to zerver_subscription
        subscription_id_count = get_subscription(channel['members'], zerver_subscription,
                                                 recipient_id, added_users,
                                                 subscription_id_count)
        # TODO add zerver_subscription which correspond to
        # huddles type recipient
        # For huddles:
        # sub['recipient']=recipient['id'] where recipient['type_id']=added_users[member]

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
        # this maps the recipients and subscriptions
        # related to private messages
        recipient = build_recipient(user['id'], recipient_id_count, Recipient.PERSONAL)
        sub = build_subscription(recipient_id_count, user['id'], subscription_id_count)

        zerver_recipient.append(recipient)
        zerver_subscription.append(sub)

        subscription_id_count += 1
        recipient_id_count += 1

    logging.info('######### IMPORTING STREAMS FINISHED #########\n')
    return zerver_defaultstream, zerver_stream, added_channels, zerver_subscription, \
        zerver_recipient, added_recipient

def get_subscription(channel_members: List[str], zerver_subscription: List[ZerverFieldsT],
                     recipient_id: int, added_users: AddedUsersT,
                     subscription_id: int) -> int:
    for member in channel_members:
        sub = build_subscription(recipient_id, added_users[member], subscription_id)
        # The recipient corresponds to a stream for stream-readable message.
        zerver_subscription.append(sub)
        subscription_id += 1
    return subscription_id

def process_long_term_idle_users(slack_data_dir: str, users: List[ZerverFieldsT],
                                 added_users: AddedUsersT, added_channels: AddedChannelsT,
                                 zerver_userprofile: List[ZerverFieldsT]) -> Set[int]:
    """Algorithmically, we treat users who have sent at least 10 messages
    or have sent a message within the last 60 days as active.
    Everyone else is treated as long-term idle, which means they will
    have a slighly slower first page load when coming back to
    Zulip.
    """
    all_messages = get_messages_iterator(slack_data_dir, added_channels)

    sender_counts = defaultdict(int)  # type: Dict[str, int]
    recent_senders = set()  # type: Set[str]
    NOW = float(timezone_now().timestamp())
    for message in all_messages:
        timestamp = float(message['ts'])
        slack_user_id = get_message_sending_user(message)
        if not slack_user_id:
            # Ignore messages without user names
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
        zulip_user_id = added_users[slack_user['id']]
        long_term_idle.add(zulip_user_id)

    # Record long-term idle status in zerver_userprofile
    for user_profile_row in zerver_userprofile:
        if user_profile_row['id'] in long_term_idle:
            user_profile_row['long_term_idle'] = True
            # Setting last_active_message_id to 1 means the user, if
            # imported, will get the full message history for the
            # streams they were on.
            user_profile_row['last_active_message_id'] = 1

    return long_term_idle

def convert_slack_workspace_messages(slack_data_dir: str, users: List[ZerverFieldsT], realm_id: int,
                                     added_users: AddedUsersT, added_recipient: AddedRecipientsT,
                                     added_channels: AddedChannelsT, realm: ZerverFieldsT,
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

    long_term_idle = process_long_term_idle_users(slack_data_dir, users, added_users,
                                                  added_channels, zerver_userprofile)

    # Now, we actually import the messages.
    all_messages = get_messages_iterator(slack_data_dir, added_channels)
    logging.info('######### IMPORTING MESSAGES STARTED #########\n')

    total_reactions = []  # type: List[ZerverFieldsT]
    total_attachments = []  # type: List[ZerverFieldsT]
    total_uploads = []  # type: List[ZerverFieldsT]

    # The messages are stored in batches
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
                realm_id, users, added_users, added_recipient, message_data,
                zerver_realmemoji, subscriber_map, added_channels,
                domain_name, long_term_idle)

        message_json = dict(
            zerver_message=zerver_message,
            zerver_usermessage=zerver_usermessage)

        message_file = "/messages-%06d.json" % (dump_file_id,)
        logging.info("Writing Messages to %s\n" % (output_dir + message_file))
        create_converted_data_files(message_json, output_dir, message_file)

        total_reactions += reactions
        total_attachments += attachment
        total_uploads += uploads

        dump_file_id += 1

    logging.info('######### IMPORTING MESSAGES FINISHED #########\n')
    return total_reactions, total_uploads, total_attachments

def get_messages_iterator(slack_data_dir: str, added_channels: AddedChannelsT) -> Iterator[ZerverFieldsT]:
    """This function is an iterator that returns all the messages across
       all Slack channels, in order by timestamp.  It's important to
       not read all the messages into memory at once, because for
       large imports that can OOM kill."""
    all_json_names = defaultdict(list)  # type: Dict[str, List[str]]
    for channel_name in added_channels.keys():
        channel_dir = os.path.join(slack_data_dir, channel_name)
        json_names = os.listdir(channel_dir)
        for json_name in json_names:
            all_json_names[json_name].append(channel_dir)

    # Sort json_name by date
    for json_name in sorted(all_json_names.keys()):
        messages_for_one_day = []  # type: List[ZerverFieldsT]
        for channel_dir in all_json_names[json_name]:
            message_dir = os.path.join(channel_dir, json_name)
            messages = get_data_file(message_dir)
            channel_name = os.path.basename(channel_dir)
            for message in messages:
                # To give every message the channel information
                message['channel_name'] = channel_name
            messages_for_one_day += messages

        # we sort the messages according to the timestamp to show messages with
        # the proper date order
        for message in sorted(messages_for_one_day, key=lambda m: m['ts']):
            yield message

def channel_message_to_zerver_message(realm_id: int,
                                      users: List[ZerverFieldsT],
                                      added_users: AddedUsersT,
                                      added_recipient: AddedRecipientsT,
                                      all_messages: List[ZerverFieldsT],
                                      zerver_realmemoji: List[ZerverFieldsT],
                                      subscriber_map: Dict[int, Set[int]],
                                      added_channels: AddedChannelsT,
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
    zerver_usermessage = []  # type: List[ZerverFieldsT]
    uploads_list = []  # type: List[ZerverFieldsT]
    zerver_attachment = []  # type: List[ZerverFieldsT]
    reaction_list = []  # type: List[ZerverFieldsT]

    # For unicode emoji
    with open(NAME_TO_CODEPOINT_PATH) as fp:
        name_to_codepoint = ujson.load(fp)

    total_user_messages = 0
    total_skipped_user_messages = 0
    for message in all_messages:
        user = get_message_sending_user(message)
        if not user:
            # Ignore messages without user names
            # These are Sometimes produced by slack
            continue

        subtype = message.get('subtype', False)
        if subtype in [
                # Zulip doesn't have a pinned_item concept
                "pinned_item",
                "unpinned_item",
                # Slack's channel join/leave notices are spammy
                "channel_join",
                "channel_leave",
                "channel_name"
        ]:
            continue

        try:
            content, mentioned_user_ids, has_link = convert_to_zulip_markdown(
                message['text'], users, added_channels, added_users)
        except Exception:
            print("Slack message unexpectedly missing text representation:")
            print(ujson.dumps(message, indent=4))
            continue
        rendered_content = None

        recipient_id = added_recipient[message['channel_name']]
        message_id = NEXT_ID('message')

        # Process message reactions
        if 'reactions' in message.keys():
            build_reactions(reaction_list, message['reactions'], added_users,
                            message_id, name_to_codepoint,
                            zerver_realmemoji)

        # Process different subtypes of slack messages

        # Subtypes which have only the action in the message should
        # be rendered with '/me' in the content initially
        # For example "sh_room_created" has the message 'started a call'
        # which should be displayed as '/me started a call'
        if subtype in ["bot_add", "sh_room_created", "me_message"]:
            content = ('/me %s' % (content))
        if subtype == 'file_comment':
            # The file_comment message type only indicates the
            # responsible user in a subfield.
            message['user'] = message['comment']['user']

        file_info = process_message_files(
            message=message,
            domain_name=domain_name,
            realm_id=realm_id,
            message_id=message_id,
            user=user,
            users=users,
            added_users=added_users,
            zerver_attachment=zerver_attachment,
            uploads_list=uploads_list,
        )

        content += file_info['content']
        has_link = has_link or file_info['has_link']

        has_attachment = file_info['has_attachment']
        has_image = file_info['has_image']

        # construct message
        topic_name = 'imported from slack'

        zulip_message = build_message(topic_name, float(message['ts']), message_id, content,
                                      rendered_content, added_users[user], recipient_id,
                                      has_image, has_link, has_attachment)
        zerver_message.append(zulip_message)

        # construct usermessages
        (num_created, num_skipped) = build_usermessages(
            zerver_usermessage=zerver_usermessage,
            subscriber_map=subscriber_map,
            recipient_id=recipient_id,
            mentioned_user_ids=mentioned_user_ids,
            message_id=message_id,
            long_term_idle=long_term_idle,
        )
        total_user_messages += num_created
        total_skipped_user_messages += num_skipped

    logging.debug("Created %s UserMessages; deferred %s due to long-term idle" % (
        total_user_messages, total_skipped_user_messages))
    return zerver_message, zerver_usermessage, zerver_attachment, uploads_list, \
        reaction_list

def process_message_files(message: ZerverFieldsT,
                          domain_name: str,
                          realm_id: int,
                          message_id: int,
                          user: str,
                          users: List[ZerverFieldsT],
                          added_users: AddedUsersT,
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
        url = fileinfo['url_private']

        if 'files.slack.com' in url:
            # For attachments with slack download link
            has_attachment = True
            has_link = True
            has_image = True if 'image' in fileinfo['mimetype'] else False

            file_user = [iterate_user for iterate_user in users if message['user'] == iterate_user['id']]
            file_user_email = get_user_email(file_user[0], domain_name)

            s3_path, content_for_link = get_attachment_path_and_content(fileinfo, realm_id)
            markdown_links.append(content_for_link)

            # construct attachments
            build_uploads(added_users[user], realm_id, file_user_email, fileinfo, s3_path,
                          uploads_list)

            build_attachment(realm_id, {message_id}, added_users[user],
                             fileinfo, s3_path, zerver_attachment)
        else:
            # For attachments with link not from slack
            # Example: Google drive integration
            has_link = True
            if 'title' in fileinfo:
                file_name = fileinfo['title']
            else:
                file_name = fileinfo['name']
            markdown_links.append('[%s](%s)' % (file_name, fileinfo['url_private']))

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
        random_name(18),
        sanitize_name(fileinfo['name'])
    ])
    attachment_path = ('/user_uploads/%s' % (s3_path))
    content = '[%s](%s)' % (fileinfo['title'], attachment_path)

    return s3_path, content

def build_reactions(reaction_list: List[ZerverFieldsT], reactions: List[ZerverFieldsT],
                    added_users: AddedUsersT, message_id: int,
                    name_to_codepoint: ZerverFieldsT,
                    zerver_realmemoji: List[ZerverFieldsT]) -> None:
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
            reaction_id = NEXT_ID('reaction')
            reaction = Reaction(
                id=reaction_id,
                emoji_code=emoji_code,
                emoji_name=emoji_name,
                reaction_type=reaction_type)

            reaction_dict = model_to_dict(reaction,
                                          exclude=['message', 'user_profile'])
            reaction_dict['message'] = message_id
            reaction_dict['user_profile'] = added_users[user]

            reaction_list.append(reaction_dict)

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

def get_message_sending_user(message: ZerverFieldsT) -> Optional[str]:
    if 'user' in message:
        return message['user']
    if message.get('file'):
        return message['file'].get('user')
    return None

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

    reactions, uploads_list, zerver_attachment = convert_slack_workspace_messages(
        slack_data_dir, user_list, realm_id, added_users, added_recipient, added_channels,
        realm, realm['zerver_userprofile'], realm['zerver_realmemoji'], domain_name, output_dir)

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

    # IO realm.json
    create_converted_data_files(realm, output_dir, '/realm.json')
    # IO emoji records
    create_converted_data_files(emoji_records, output_dir, '/emoji/records.json')
    # IO avatar records
    create_converted_data_files(avatar_records, output_dir, '/avatars/records.json')
    # IO uploads records
    create_converted_data_files(uploads_records, output_dir, '/uploads/records.json')
    # IO attachments records
    create_converted_data_files(attachment, output_dir, '/attachment.json')

    # remove slack dir
    rm_tree(slack_data_dir)
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

    logging.info('######### DATA CONVERSION FINISHED #########\n')
    logging.info("Zulip data dump created at %s" % (output_dir))

def get_data_file(path: str) -> Any:
    with open(path, "r") as fp:
        data = ujson.load(fp)
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
