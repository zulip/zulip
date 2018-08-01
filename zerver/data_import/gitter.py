import os
import ujson
import dateutil.parser
import random
import requests
import json
import logging
import shutil
import subprocess

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now
from typing import Any, Dict, List, Tuple

from zerver.models import Realm, UserProfile, Recipient
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.parallel import run_parallel
from zerver.data_import.import_util import ZerverFieldsT, build_zerver_realm, \
    build_avatar, build_subscription, build_recipient

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

    realm = dict(zerver_client=[{"name": "populate_db", "id": 1},
                                {"name": "website", "id": 2},
                                {"name": "API", "id": 3}],
                 zerver_customprofilefield=[],
                 zerver_customprofilefieldvalue=[],
                 zerver_userpresence=[],  # shows last logged in data, which is not available in gitter
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
                 zerver_reaction=[],
                 zerver_realmemoji=[],
                 zerver_realmfilter=[])

    zerver_userprofile, avatars, user_map = build_userprofile(int(NOW), domain_name, gitter_data)
    zerver_stream, zerver_defaultstream = build_stream(int(NOW))
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

def build_stream(timestamp: Any) -> Tuple[List[ZerverFieldsT],
                                          List[ZerverFieldsT]]:
    logging.info('######### IMPORTING STREAM STARTED #########\n')
    # We have only one stream for gitter export
    stream = dict(
        realm=realm_id,
        name="from gitter",
        deactivated=False,
        description="Imported from gitter",
        invite_only=False,
        date_created=timestamp,
        id=0)

    defaultstream = dict(
        stream=0,
        realm=realm_id,
        id=0)
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
                                      zerver_subscription: List[ZerverFieldsT],
                                      user_map: Dict[str, int],
                                      user_short_name_to_full_name: Dict[str, str],
                                      chunk_size: int=MESSAGE_BATCH_CHUNK_SIZE) -> None:
    """
    Messages are stored in batches
    """
    logging.info('######### IMPORTING MESSAGES STARTED #########\n')
    message_id = usermessage_id = 0
    recipient_id = 0  # Corresponding to stream "gitter"

    low_index = 0
    upper_index = low_index + chunk_size
    dump_file_id = 1

    while True:
        message_json = {}
        zerver_message = []
        zerver_usermessage = []
        message_data = gitter_data[low_index: upper_index]
        if len(message_data) == 0:
            break
        for message in message_data:
            message_time = dateutil.parser.parse(message['sent']).timestamp()
            mentioned_user_ids = get_usermentions(message, user_map,
                                                  user_short_name_to_full_name)
            rendered_content = None

            zulip_message = dict(
                sending_client=1,
                rendered_content_version=1,  # This is Zulip-specific
                has_image=False,
                subject='imported from gitter',
                pub_date=float(message_time),
                id=message_id,
                has_attachment=False,
                edit_history=None,
                sender=user_map[message['fromUser']['id']],
                content=message['text'],
                rendered_content=rendered_content,
                recipient=recipient_id,
                last_edit_time=None,
                has_link=False)
            zerver_message.append(zulip_message)

            for subscription in zerver_subscription:
                if subscription['recipient'] == recipient_id:
                    flags_mask = 1  # For read
                    if subscription['user_profile'] in mentioned_user_ids:
                        flags_mask = 9  # For read and mentioned

                    usermessage = dict(
                        user_profile=subscription['user_profile'],
                        id=usermessage_id,
                        flags_mask=flags_mask,
                        message=message_id)
                    usermessage_id += 1
                    zerver_usermessage.append(usermessage)
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
                zulip_mention = ('@**%s**' %
                                 (user_short_name_to_full_name[mention['screenName']]))
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
    gitter_data = json.load(open(gitter_data_file))

    realm, avatar_list, user_map = gitter_workspace_to_realm(
        domain_name, gitter_data, realm_subdomain)

    # For user mentions
    user_short_name_to_full_name = {}
    for userprofile in realm['zerver_userprofile']:
        user_short_name_to_full_name[userprofile['short_name']] = userprofile['full_name']

    convert_gitter_workspace_messages(
        gitter_data, output_dir, realm['zerver_subscription'], user_map,
        user_short_name_to_full_name)

    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)
    avatar_records = process_avatars(avatar_list, avatar_folder, threads)

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

def process_avatars(avatar_list: List[ZerverFieldsT], avatar_dir: str,
                    threads: int) -> List[ZerverFieldsT]:
    """
    This function gets the gitter avatar of the user and saves it in the
    user's avatar directory with both the extensions '.png' and '.original'
    """
    def get_avatar(avatar_upload_list: List[str]) -> int:
        gitter_avatar_url = avatar_upload_list[0]
        image_path = avatar_upload_list[1]
        original_image_path = avatar_upload_list[2]
        response = requests.get(gitter_avatar_url, stream=True)
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
        gitter_avatar_url = avatar['path']
        avatar_original = dict(avatar)

        image_path = ('%s/%s.png' % (avatar_dir, avatar_hash))
        original_image_path = ('%s/%s.original' % (avatar_dir, avatar_hash))

        avatar_upload_list.append([gitter_avatar_url, image_path, original_image_path])
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

def create_converted_data_files(data: Any, output_dir: str, file_path: str) -> None:
    output_file = output_dir + file_path
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    json.dump(data, open(output_file, 'w'), indent=4)

def write_data_to_file(output_file: str, data: Any) -> None:
    with open(output_file, "w") as f:
        f.write(ujson.dumps(data, indent=4))
