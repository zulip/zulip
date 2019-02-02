import os
import dateutil.parser
import logging
import subprocess
import ujson

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now
from typing import Any, Dict, List, Set, Tuple

from zerver.models import UserProfile, Recipient
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.data_import.import_util import ZerverFieldsT, build_zerver_realm, \
    build_avatar, build_subscription, build_recipient, build_usermessages, \
    build_defaultstream, process_avatars, build_realm, build_stream, \
    build_message, create_converted_data_files, make_subscriber_map

# stubs
GitterDataT = List[Dict[str, Any]]

realm_id = 0

def gitter_workspace_to_realm(domain_name: str, gitter_data: GitterDataT,
                              realm_subdomain: str) -> Tuple[ZerverFieldsT,
                                                             List[ZerverFieldsT],
                                                             Dict[str, int]]:
    """
    Returns:
    1. realm, Converted Realm data
    2. avatars, which is list to map avatars to zulip avatar records.json
    3. user_map, which is a dictionary to map from gitter user id to zulip user id
    """
    NOW = float(timezone_now().timestamp())
    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW, 'Gitter')  # type: List[ZerverFieldsT]
    realm = build_realm(zerver_realm, realm_id, domain_name)

    zerver_userprofile, avatars, user_map = build_userprofile(int(NOW), domain_name, gitter_data)
    zerver_stream, zerver_defaultstream = build_stream_and_defaultstream(int(NOW))
    zerver_recipient, zerver_subscription = build_recipient_and_subscription(
        zerver_userprofile, zerver_stream)

    realm['zerver_userprofile'] = zerver_userprofile
    realm['zerver_stream'] = zerver_stream
    realm['zerver_defaultstream'] = zerver_defaultstream
    realm['zerver_recipient'] = zerver_recipient
    realm['zerver_subscription'] = zerver_subscription

    return realm, avatars, user_map

def build_userprofile(timestamp: Any, domain_name: str,
                      gitter_data: GitterDataT) -> Tuple[List[ZerverFieldsT],
                                                         List[ZerverFieldsT],
                                                         Dict[str, int]]:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. avatar_list, which is list to map avatars to zulip avatard records.json
    3. added_users, which is a dictionary to map from gitter user id to zulip id
    """
    logging.info('######### IMPORTING USERS STARTED #########\n')
    zerver_userprofile = []
    avatar_list = []  # type: List[ZerverFieldsT]
    user_map = {}  # type: Dict[str, int]
    user_id = 0

    for data in gitter_data:
        if data['fromUser']['id'] not in user_map:
            user_data = data['fromUser']
            user_map[user_data['id']] = user_id

            email = get_user_email(user_data, domain_name)
            build_avatar(user_id, realm_id, email, user_data['avatarUrl'],
                         timestamp, avatar_list)

            # Build userprofile object
            userprofile = UserProfile(
                full_name=user_data['displayName'],
                short_name=user_data['username'],
                id=user_id,
                email=email,
                delivery_email=email,
                avatar_source='U',
                pointer=-1,
                date_joined=timestamp,
                last_login=timestamp)
            userprofile_dict = model_to_dict(userprofile)
            # Set realm id separately as the corresponding realm is not yet a Realm model
            # instance
            userprofile_dict['realm'] = realm_id
            zerver_userprofile.append(userprofile_dict)
            user_id += 1
    logging.info('######### IMPORTING USERS FINISHED #########\n')
    return zerver_userprofile, avatar_list, user_map

def get_user_email(user_data: ZerverFieldsT, domain_name: str) -> str:
    # TODO Get user email from github
    email = ("%s@users.noreply.github.com" % user_data['username'])
    return email

def build_stream_and_defaultstream(timestamp: Any) -> Tuple[List[ZerverFieldsT],
                                                            List[ZerverFieldsT]]:
    logging.info('######### IMPORTING STREAM STARTED #########\n')
    # We have only one stream for gitter export
    stream_name = 'from gitter'
    stream_description = "Imported from gitter"
    stream_id = 0
    stream = build_stream(timestamp, realm_id, stream_name, stream_description,
                          stream_id)

    defaultstream = build_defaultstream(realm_id=realm_id, stream_id=stream_id,
                                        defaultstream_id=0)
    logging.info('######### IMPORTING STREAMS FINISHED #########\n')
    return [stream], [defaultstream]

def build_recipient_and_subscription(
    zerver_userprofile: List[ZerverFieldsT],
    zerver_stream: List[ZerverFieldsT]) -> Tuple[List[ZerverFieldsT],
                                                 List[ZerverFieldsT]]:
    """
    Returns:
    1. zerver_recipient, which is a list of mapped recipient
    2. zerver_subscription, which is a list of mapped subscription
    """
    zerver_recipient = []
    zerver_subscription = []
    recipient_id = subscription_id = 0

    # For stream

    # We have only one recipient, because we have only one stream
    # Hence 'recipient_id'=0 corresponds to 'stream_id'=0
    recipient = build_recipient(0, recipient_id, Recipient.STREAM)
    zerver_recipient.append(recipient)

    for user in zerver_userprofile:
        subscription = build_subscription(recipient_id, user['id'], subscription_id)
        zerver_subscription.append(subscription)
        subscription_id += 1
    recipient_id += 1

    # For users
    for user in zerver_userprofile:
        recipient = build_recipient(user['id'], recipient_id, Recipient.PERSONAL)
        subscription = build_subscription(recipient_id, user['id'], subscription_id)
        zerver_recipient.append(recipient)
        zerver_subscription.append(subscription)
        recipient_id += 1
        subscription_id += 1

    return zerver_recipient, zerver_subscription

def convert_gitter_workspace_messages(gitter_data: GitterDataT, output_dir: str,
                                      subscriber_map: Dict[int, Set[int]],
                                      user_map: Dict[str, int],
                                      user_short_name_to_full_name: Dict[str, str],
                                      chunk_size: int=MESSAGE_BATCH_CHUNK_SIZE) -> None:
    """
    Messages are stored in batches
    """
    logging.info('######### IMPORTING MESSAGES STARTED #########\n')
    message_id = 0
    recipient_id = 0  # Corresponding to stream "gitter"

    low_index = 0
    upper_index = low_index + chunk_size
    dump_file_id = 1

    while True:
        message_json = {}
        zerver_message = []
        zerver_usermessage = []  # type: List[ZerverFieldsT]
        message_data = gitter_data[low_index: upper_index]
        if len(message_data) == 0:
            break
        for message in message_data:
            message_time = dateutil.parser.parse(message['sent']).timestamp()
            mentioned_user_ids = get_usermentions(message, user_map,
                                                  user_short_name_to_full_name)
            rendered_content = None
            topic_name = 'imported from gitter'
            user_id = user_map[message['fromUser']['id']]

            zulip_message = build_message(topic_name, float(message_time), message_id, message['text'],
                                          rendered_content, user_id, recipient_id)
            zerver_message.append(zulip_message)

            build_usermessages(
                zerver_usermessage=zerver_usermessage,
                subscriber_map=subscriber_map,
                recipient_id=recipient_id,
                mentioned_user_ids=mentioned_user_ids,
                message_id=message_id,
            )

            message_id += 1

        message_json['zerver_message'] = zerver_message
        message_json['zerver_usermessage'] = zerver_usermessage
        message_filename = os.path.join(output_dir, "messages-%06d.json" % (dump_file_id,))
        logging.info("Writing Messages to %s\n" % (message_filename,))
        write_data_to_file(os.path.join(message_filename), message_json)

        low_index = upper_index
        upper_index = chunk_size + low_index
        dump_file_id += 1

    logging.info('######### IMPORTING MESSAGES FINISHED #########\n')

def get_usermentions(message: Dict[str, Any], user_map: Dict[str, int],
                     user_short_name_to_full_name: Dict[str, str]) -> List[int]:
    mentioned_user_ids = []
    if 'mentions' in message:
        for mention in message['mentions']:
            if mention.get('userId') in user_map:
                gitter_mention = '@%s' % (mention['screenName'])
                if mention['screenName'] not in user_short_name_to_full_name:
                    logging.info("Mentioned user %s never sent any messages, so has no full name data" %
                                 mention['screenName'])
                    full_name = mention['screenName']
                else:
                    full_name = user_short_name_to_full_name[mention['screenName']]
                zulip_mention = ('@**%s**' % (full_name,))
                message['text'] = message['text'].replace(gitter_mention, zulip_mention)

                mentioned_user_ids.append(user_map[mention['userId']])
    return mentioned_user_ids

def do_convert_data(gitter_data_file: str, output_dir: str, threads: int=6) -> None:
    #  Subdomain is set by the user while running the import commands
    realm_subdomain = ""
    domain_name = settings.EXTERNAL_HOST

    os.makedirs(output_dir, exist_ok=True)
    # output directory should be empty initially
    if os.listdir(output_dir):
        raise Exception("Output directory should be empty!")

    # Read data from the gitter file
    with open(gitter_data_file, "r") as fp:
        gitter_data = ujson.load(fp)

    realm, avatar_list, user_map = gitter_workspace_to_realm(
        domain_name, gitter_data, realm_subdomain)

    subscriber_map = make_subscriber_map(
        zerver_subscription=realm['zerver_subscription'],
    )

    # For user mentions
    user_short_name_to_full_name = {}
    for userprofile in realm['zerver_userprofile']:
        user_short_name_to_full_name[userprofile['short_name']] = userprofile['full_name']

    convert_gitter_workspace_messages(
        gitter_data, output_dir, subscriber_map, user_map,
        user_short_name_to_full_name)

    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)
    avatar_records = process_avatars(avatar_list, avatar_folder, realm_id, threads)

    attachment = {"zerver_attachment": []}  # type: Dict[str, List[Any]]

    # IO realm.json
    create_converted_data_files(realm, output_dir, '/realm.json')
    # IO emoji records
    create_converted_data_files([], output_dir, '/emoji/records.json')
    # IO avatar records
    create_converted_data_files(avatar_records, output_dir, '/avatars/records.json')
    # IO uploads records
    create_converted_data_files([], output_dir, '/uploads/records.json')
    # IO attachments records
    create_converted_data_files(attachment, output_dir, '/attachment.json')

    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

    logging.info('######### DATA CONVERSION FINISHED #########\n')
    logging.info("Zulip data dump created at %s" % (output_dir))

def write_data_to_file(output_file: str, data: Any) -> None:
    with open(output_file, "w") as f:
        f.write(ujson.dumps(data, indent=4))
