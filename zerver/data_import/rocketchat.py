import logging
import os
import random
import re
import subprocess
from typing import Any, Dict, List, Set, Tuple

import bson
import requests
import ujson
from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.data_import.import_util import (
    ZerverFieldsT,
    build_attachment,
    build_avatar,
    build_defaultstream,
    build_message,
    build_realm,
    build_recipient,
    build_stream,
    build_subscription,
    build_user_message,
    build_usermessages,
    build_zerver_realm,
    create_converted_data_files,
    make_subscriber_map,
)
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.export import MESSAGE_BATCH_CHUNK_SIZE
from zerver.lib.upload import random_name, sanitize_name
from zerver.models import Recipient, UserProfile

# stubs
RocketchatDataT = List[Dict[str, Any]]
StreamMapT = Tuple[List[ZerverFieldsT], List[ZerverFieldsT], Dict[str, int],
                   Dict[str, int]]
UserMapT = Tuple[List[ZerverFieldsT], List[ZerverFieldsT], Dict[str, int]]

realm_id = 0


class ListFilter:
    """
    Using list comprehensions in code on a regular base is very ugly and
    unreadable. Since these comprehensions mostly do the same (abstract),
    this class was created to structure the code better.
    """
    def __init__(self, dicts: List[Dict[str, Any]]) -> None:
        self.dicts = dicts

    def get(self, key: str, value: str) -> List[Dict[str, Any]]:
        ret = [x for x in self.dicts if x.get(key) == value]
        return ret

    def add(self, _dict: Dict[str, Any]) -> None:
        self.dicts.append(_dict)


def rocketchat_workspace_to_realm(domain_name: str,
                                  realm_subdomain: str,
                                  ) -> Tuple[ZerverFieldsT,
                                             List[ZerverFieldsT],
                                             Dict[str, Any],
                                             Dict[str, Any],
                                             Dict[str, Any],
                                             List[ZerverFieldsT]]:
    """
    Returns:
    1. realm, Converted Realm data
    2. avatars, which is list to map avatars to zulip avatar records.json
    3. user_map, which is a dictionary to map from rocketchat user id to
       zulip user id
    4. stream_map, which is a dictionary to map from rocketchat rooms to zulip
       stream id
    """
    NOW = float(timezone_now().timestamp())
    zerver_realm: List[ZerverFieldsT] = \
        build_zerver_realm(realm_id, realm_subdomain, NOW, 'Rocketchat')
    realm = build_realm(zerver_realm, realm_id, domain_name)
    zerver_userprofile, avatars, user_map = \
        build_userprofile(int(NOW), domain_name)
    zerver_stream, zerver_defaultstream, stream_map, private_stream_map = \
        build_stream_map(int(NOW))
    zerver_recipient, zerver_subscription = \
        build_recipient_and_subscription(zerver_userprofile, zerver_stream,
                                         stream_map, user_map)
    realm['zerver_userprofile'] = zerver_userprofile
    realm['zerver_stream'] = zerver_stream
    realm['zerver_defaultstream'] = zerver_defaultstream
    realm['zerver_recipient'] = zerver_recipient
    realm['zerver_subscription'] = zerver_subscription
    return realm, avatars, user_map, stream_map, private_stream_map, \
        zerver_recipient


def build_userprofile(timestamp: Any, domain_name: str) -> UserMapT:
    """
    Returns:
    1. zerver_userprofile, which is a list of user profile
    2. avatar_list, which is list to map avatars to zulip avatars records.json
    3. added_users, which is a dictionary to map from rocketchat user id to
       zulip id
    """
    logging.info('######### IMPORTING USERS STARTED #########\n')
    zerver_userprofile = []
    avatar_list: List[ZerverFieldsT] = []
    user_map: Dict[str, Any] = {}
    user_id = 0

    rc_dump = OPTIONS.get('rocketchat_dump')
    with open(f'./{rc_dump}/rocketchat_avatars.bson', 'rb') as fcache:
        avatars = ListFilter(bson.decode_all(fcache.read()))
    with open(f'./{rc_dump}/rocketchat_avatars.files.bson', 'rb') as fcache:
        files = ListFilter(bson.decode_all(fcache.read()))
    with open(f'./{rc_dump}/rocketchat_avatars.chunks.bson', 'rb') as fcache:
        chunks = ListFilter(bson.decode_all(fcache.read()))
    with open(f'./{rc_dump}/users.bson', 'rb') as fcache:
        users = ListFilter(bson.decode_all(fcache.read()))

    # ensure avatar folder exists
    opath = '{}/avatars/{}'.format(OPTIONS['output_dir'], realm_id)
    os.makedirs(opath, exist_ok=True)
    fallback_avatar = requests.get(OPTIONS['fallback_avatar'])

    for data in users.dicts:
        uname = data['username']
        if uname not in user_map:
            user_map[uname] = {'zulip_id': user_id, 'full_name': data['name'],
                               'rooms': data['__rooms']}
            email = data['emails'][0]['address']
            # @TODO: Rework to use the mongodb dump
            avatar = avatars.get('name', uname)
            avatar_hash = user_avatar_path_from_ids(user_id, realm_id)
            if not avatar:
                avatar_filename = os.path.basename(OPTIONS['fallback_avatar'])
                avatar_content_type = avatar_filename.split('.')[-1]
                avatar_data = fallback_avatar.content
            else:
                _avatar = avatar[0]
                fileinfo = files.get('_id', _avatar['_id'])[0]
                chunk = chunks.get('files_id', _avatar['_id'])
                avatar_content_type = fileinfo['contentType'].split('/')[1]
                avatar_data = b''.join([x['data'] for x in chunk])
            avatar_filename = f'{avatar_hash}.{avatar_content_type}'
            print(avatar_filename)
            # save avatar binary data
            avatar_path = '/'.join((os.path.dirname(opath), avatar_filename))
            with open(avatar_path, 'wb') as afile:
                afile.write(avatar_data)
            build_avatar(user_id, realm_id, email,
                         f'{avatar_filename}',
                         timestamp, avatar_list)
            # Build userprofile object
            userprofile = UserProfile(
                full_name=data['name'],
                id=user_id,
                email=email,
                delivery_email=email,
                avatar_source='U',
                date_joined=timestamp,
                last_login=timestamp)
            userprofile_dict = model_to_dict(userprofile)
            # Set realm id separately as the corresponding realm is not yet a
            # Realm model instance
            userprofile_dict['realm'] = realm_id
            # We use this later, even though Zulip doesn't
            # support short_name
            userprofile_dict['short_name'] = uname
            zerver_userprofile.append(userprofile_dict)
            user_id += 1
    logging.info('######### IMPORTING USERS FINISHED #########\n')
    return zerver_userprofile, avatar_list, user_map


def build_stream_map(timestamp: Any) -> StreamMapT:
    """
    Returns:
    1. stream, which is the list of streams
    2. defaultstreams, which is the list of default streams
    3. stream_map, which is a dictionary to map from rocketchat rooms to zulip
       stream id
    """
    logging.info('######### IMPORTING STREAM STARTED #########\n')
    stream_id = 0
    stream: List[ZerverFieldsT] = []

    rc_dump = OPTIONS.get('rocketchat_dump')
    with open(f'./{rc_dump}/rocketchat_room.bson', 'rb') as fcache:
        rooms = ListFilter(bson.decode_all(fcache.read()))

    # Gathering streams from rocketchat_data
    stream_map: Dict[str, Any] = {}
    private_stream_map: Dict[str, Any] = {}
    for room in rooms.dicts:
        invite_only = False
        is_direct = True if room['t'] == 'd' else False
        room_name = room['name'] if room.get('name') else \
            room['fname'] if room.get('fname') else \
            '@{}'.format(':'.join(room['usernames']))
        if room_name.startswith('@'):
            logging.debug(f'Marking {room_name} as private stream.')
            invite_only = True
            # Do not handle private messages as streams
        if is_direct and room_name not in private_stream_map:
            private_stream_map[room_name] = {'zulip_id': stream_id,
                                             'rc_id': room['_id'],
                                             'is_private': is_direct,
                                             'usernames': room['usernames'],
                                             'users_count': room['usersCount']}
        elif not is_direct and room_name not in stream_map:
            stream.append(build_stream(timestamp, realm_id, room_name,
                                       f'{room_name}', stream_id, False,
                                       invite_only))
            stream_map[room_name] = {'zulip_id': stream_id,
                                     'rc_id': room['_id'],
                                     'is_private': is_direct}
            stream_id += 1
    defaultstream = build_defaultstream(realm_id=realm_id,
                                        stream_id=0,
                                        defaultstream_id=0)
    logging.info('######### IMPORTING STREAMS FINISHED #########\n')
    return stream, [defaultstream], stream_map, private_stream_map


def build_recipient_and_subscription(
        zerver_userprofile: List[ZerverFieldsT],
        zerver_stream: List[ZerverFieldsT],
        stream_map: Dict[str, Any],
        user_map: Dict[str, Any]) -> \
        Tuple[List[ZerverFieldsT], List[ZerverFieldsT]]:
    logging.info('######### CALCULATIING SUBSCRIPTIONS STARTED #########\n')
    """
    Assumes that there is at least one stream with 'stream_id' = 0,
    and that this stream is the only defaultstream, with 'defaultstream_id' = 0
    Returns:
    1. zerver_recipient, which is a list of mapped recipient
    2. zerver_subscription, which is a list of mapped subscription
    """
    zerver_recipient = []
    zerver_subscription = []
    recipient_id = subscription_id = 0

    # Initial recipients correspond to intitial streams
    # We enumerate all streams, and build a recipient for each
    # Hence 'recipient_id'=n corresponds to 'stream_id'=n
    for stream in zerver_stream:
        rec = build_recipient(recipient_id, recipient_id, Recipient.STREAM)
        zerver_recipient.append(rec)
        recipient_id += 1

    for user in zerver_userprofile:
        zerver_recipient.append(build_recipient(user['id'],
                                                recipient_id,
                                                Recipient.PERSONAL))
        zerver_subscription.append(build_subscription(recipient_id,
                                                      user['id'],
                                                      subscription_id))
        recipient_id += 1
        subscription_id += 1

    # Iter over all rooms/streams and calculate subscriptions
    for _stream in zerver_stream:
        zulip_sid = _stream['id']
        rocket_sid = [y['rc_id'] for x, y in stream_map.items()
                      if y['zulip_id'] == zulip_sid][0]
        for username, userdict in user_map.items():
            if rocket_sid in userdict['rooms'] or \
                    re.search(username, _stream['name']):
                subscription = build_subscription(zulip_sid,
                                                  userdict['zulip_id'],
                                                  subscription_id)
                zerver_subscription.append(subscription)
                subscription_id += 1
                recipient_id += 1

    logging.info('######### CALCULATIING SUBSCRIPTIONS FINISHED #########\n')
    return zerver_recipient, zerver_subscription


def convert_rocketchat_workspace_messages(
        output_dir: str,
        subscriber_map: Dict[int, Set[int]],
        user_map: Dict[str, Any],
        stream_map: Dict[str, Any],
        private_stream_map: Dict[str, Any],
        zerver_recipient: List[ZerverFieldsT],
        user_short_name_to_full_name: Dict[str, str],
        chunk_size: int = MESSAGE_BATCH_CHUNK_SIZE) \
        -> Tuple[List[ZerverFieldsT], List[ZerverFieldsT]]:
    """
    Convert Rocketchat messages to Zulip messages and write them to files
    in batches
    """
    rc_dump = OPTIONS.get('rocketchat_dump')
    with open(f'./{rc_dump}/rocketchat_uploads.bson', 'rb') as fcache:
        uploads = ListFilter(bson.decode_all(fcache.read()))
    with open(f'./{rc_dump}/rocketchat_uploads.files.bson', 'rb') as fcache:
        files = ListFilter(bson.decode_all(fcache.read()))
    with open(f'./{rc_dump}/rocketchat_uploads.chunks.bson', 'rb') as fcache:
        chunks = ListFilter(bson.decode_all(fcache.read()))
    with open(f'./{rc_dump}/rocketchat_message.bson', 'rb') as fcache:
        messages = ListFilter(bson.decode_all(fcache.read()))

    logging.info('######### IMPORTING MESSAGES STARTED #########\n')
    message_id = 0
    low_index = 0
    upper_index = low_index + chunk_size
    dump_file_id = 1
    skipped_no_room = 0
    skipped_no_user = 0
    zerver_attachment: List[ZerverFieldsT] = []
    attachment_records: List[ZerverFieldsT] = []
    replies = ListFilter([])
    topic_count = 0

    def rc_room_id_to_room(
            rc_id: str,
            stream_map: Dict[str, Any],
            private_stream_map: Dict[str, Any]) \
            -> Dict[str, Any]:
        """ Resolve rocketchat room id to Zulip recipient, which can be either
            a stream or a person (or a huddle)
        """
        room = None
        for stream_name, stream_dict in stream_map.items():
            if stream_dict['rc_id'] == rc_id:
                room = stream_dict
                room['name'] = stream_name
                break
        if not room:
            for stream_name, stream_dict in private_stream_map.items():
                if stream_dict['rc_id'] == rc_id:
                    room = stream_dict
                    room['name'] = stream_name
                    break
        return room

    def get_topic_name(
            is_private: bool,
            message: Dict[str, Any],
            replies: ListFilter,
            topic_count: int) \
            -> str:
        is_reply = True if message.get('tmid') else False
        has_replies = True if message.get('replies') else False
        if is_private:
            return ""
        elif has_replies:
            return f"general-topic-{topic_count}"
        elif is_reply:
            try:
                reply_to = message['tmid']
                # logging.error(replies.dicts)
                topic_count = replies.get('id', reply_to)[0]['topic_count']
                topic_count += 1  # wtf?
                return f"general-topic-{topic_count}"
            except IndexError:
                msg = f'Start message ({reply_to}) for topic not found.'
                logging.error(msg)
                return 'general'
        else:
            return 'general'

    while True:
        message_json = {}
        zerver_message: List[ZerverFieldsT] = []
        zerver_usermessage: List[ZerverFieldsT] = []
        message_data = messages.dicts[low_index: upper_index]
        if len(message_data) == 0:
            break
        for message in message_data:
            _uname = message['u']['username']
            sender = _uname
            room = rc_room_id_to_room(message['rid'], stream_map,
                                      private_stream_map)
            usermessage_ids: Set[int] = set()
            # Messages from non-existing rooms get ignored
            if not room:
                skipped_no_room += 1
                # logging.error(message)
                continue
            room_name = room['name']
            # Messages from user that do not exist as users, are ignored.
            if sender not in user_map:
                logging.debug(message)
                skipped_no_user += 1
                continue
            is_private = room['is_private']
            has_attachment = bool(message.get('attachments'))
            if bool(message.get('replies')):
                replies.add({'id': message['_id'],
                             'topic_count': topic_count})
                topic_count += 1
            # message_time = dateutil.parser.parse(message['ts']).timestamp()
            message_time = message['ts'].timestamp()
            mentioned_user_ids = [] if is_private else \
                get_usermentions(message, user_map,
                                 user_short_name_to_full_name)
            rendered_content = None
            topic_name = get_topic_name(is_private, message, replies, topic_count)
            sender_id = user_map[sender]['zulip_id']
            # Iter over attachments and build_attachment
            if has_attachment:
                records = get_attachments(
                    message, sender_id, usermessage_ids,
                    zerver_attachment, files, chunks, uploads, zerver_message)
                attachment_records += records
            if is_private:
                participants = room['usernames']
                if room['users_count'] == 2 and \
                        len(dict.fromkeys(participants)) == 2:
                    # for private messages, two usermessages need to be
                    # created. One for every user account that was involved in
                    # the direct message exchange
                    for participant in participants:
                        participant_id = user_map[participant]['zulip_id']
                        usermessage = build_user_message(
                            user_id=participant_id,
                            message_id=message_id,
                            is_private=is_private,
                            is_mentioned=False
                        )
                        zerver_usermessage.append(usermessage)
                        usermessage_ids.add(message_id)

                    recipient = [x for x in participants if x != sender][0]
                    recipient_uid = user_map[recipient]['zulip_id']
                    recipient_id = [y['id'] for y in zerver_recipient
                                    if y['type'] == 1
                                    and y['type_id'] == recipient_uid][0]
                    zulip_message = build_message(topic_name,
                                                  float(message_time),
                                                  message_id, message['msg'],
                                                  rendered_content, sender_id,
                                                  recipient_id, has_attachment)
                    zerver_message.append(zulip_message)
                    message_id += 1
                elif room['users_count'] == 1:
                    # Message from users to them self
                    usermessage = build_user_message(
                        user_id=sender_id,
                        message_id=message_id,
                        is_private=is_private,
                        is_mentioned=False
                    )
                    zerver_usermessage.append(usermessage)
                    usermessage_ids.add(message_id)
                    recipient_id = [y['id'] for y in zerver_recipient
                                    if y['type'] == 1
                                    and y['type_id'] == sender_id][0]
                    zulip_message = build_message(topic_name,
                                                  float(message_time),
                                                  message_id, message['msg'],
                                                  rendered_content, sender_id,
                                                  recipient_id, has_attachment)
                    zerver_message.append(zulip_message)
                    message_id += 1
                else:
                    logging.error(room)
                    logging.error(message)
                    continue
            else:
                recipient_id = stream_map[room_name]['zulip_id']
                zulip_message = build_message(topic_name, float(message_time),
                                              message_id, message['msg'],
                                              rendered_content, sender_id,
                                              recipient_id, has_attachment)
                zerver_message.append(zulip_message)

                build_usermessages(
                    zerver_usermessage=zerver_usermessage,
                    subscriber_map=subscriber_map,
                    recipient_id=recipient_id,
                    mentioned_user_ids=mentioned_user_ids,
                    message_id=message_id,
                    is_private=is_private,
                )
                usermessage_ids.add(message_id)
                message_id += 1

        message_json['zerver_message'] = zerver_message
        message_json['zerver_usermessage'] = zerver_usermessage
        file_id = f"messages-{dump_file_id:06}.json"
        message_filename = os.path.join(output_dir, file_id)
        logging.info("Writing Messages to %s\n", message_filename)
        write_data_to_file(os.path.join(message_filename), message_json)

        low_index = upper_index
        upper_index = chunk_size + low_index
        dump_file_id += 1
    logging.info(f"Failed to find room for {skipped_no_room} messages")
    logging.info(f"Failed to find user for {skipped_no_user} messages")
    logging.info('######### IMPORTING MESSAGES FINISHED #########\n')
    return zerver_attachment, attachment_records


def get_attachments(
        message: Dict[str, Any],
        sender_id: int,
        usermessage_ids: Set[int],
        zerver_attachment: RocketchatDataT,
        files: ListFilter,
        chunks: ListFilter,
        uploads: ListFilter,
        zerver_message: List[Dict[str, Any]]) \
        -> RocketchatDataT:
    """ Extract attachments from mongodb chunks and build attachment list """
    ret = []

    def sanitize_contenttype(upload: Dict[str, Any]) -> str:
        fname_components = upload['name'].split('.')
        content_type = upload.get('type', 'image/png').split('/')[-1]
        if len(fname_components) == 1:
            fname = fname_components[0]
        else:
            fname = '.'.join(fname_components[:-1])
        return f'{fname}.{content_type}'

    for attachment in message['attachments']:
        # Identify attachment type and act accordingly. File attachments get
        # extracted and assembled from the mongodb chunks, while text/link
        # based attachments are getting formatted correctly
        if 'text' in attachment:
            # text-ish attachment type
            # Sometime attachment['text'] is None ... :/
            message['msg'] += attachment['text'] if attachment['text'] else ""
        elif 'title' in attachment and 'title_link' in attachment \
                and 'type' not in attachment:
            # text-ish attachment type
            message['msg'] += "[{}]({})".format(attachment['title'],
                                                attachment['title_link'])
        elif 'title' in attachment and 'image_url' in attachment \
                and 'type' not in attachment:
            # text-ish attachment type
            message['msg'] += "[{}]({})".format(attachment['title'],
                                                attachment['image_url'])
        elif 'title_link' in attachment and attachment.get('type') == 'file':
            # file-ish attachments
            attachment_id = attachment['title_link'].split('/')[2]
            attachment_file = files.get('_id', attachment_id)[0]
            upload = uploads.get('_id', attachment_id)[0]
            attachment_chunk = chunks.get('files_id', attachment_id)
            fileinfo = {'size': upload['size'],
                        'created': upload['uploadedAt'],
                        'name': sanitize_contenttype(upload)}
            s3_path = "/".join([
                str(realm_id),
                format(random.randint(0, 255), 'x'),
                random_name(18),
                sanitize_name(fileinfo['name'])
            ])
            message['msg'] += "[{}](/user_uploads/{})".format(upload['name'],
                                                              s3_path)
            build_attachment(realm_id, usermessage_ids, sender_id,
                             fileinfo, s3_path, zerver_attachment)
            # ensure folder exists
            opath = '{}/uploads/{}'.format(OPTIONS['output_dir'], s3_path)
            os.makedirs(os.path.dirname(opath), exist_ok=True)
            # save binary data for filename
            with open(opath, 'wb') as afile:
                afile.write(b''.join([x['data'] for x in attachment_chunk]))
            record = {'realm_id': realm_id,
                      'user_profile_id': sender_id,
                      'user_profile_email': '',
                      's3_path': s3_path,
                      'path': s3_path,
                      'size': fileinfo['size'],
                      'last_modified': fileinfo['created'],
                      'content_type': attachment_file.get('contentType', None)
                      }
            ret.append(record)
        else:
            logging.error(attachment.keys())
            pass
    return ret


def get_usermentions(
        message: Dict[str, Any],
        user_map: Dict[str, Any],
        user_short_name_to_full_name: Dict[str, Any]) \
        -> List[int]:
    mentioned_user_ids = []
    if 'mentions' in message:
        for mention in message['mentions']:
            if mention.get('username') in user_map:
                username = mention['username']
                rocketchat_mention = '@{}'.format(username)
                if mention['username'] not in user_short_name_to_full_name:
                    logging.error("Mentioned user %s never sent any messages,"
                                  "so has no full name data", username)
                    full_name = username
                else:
                    full_name = user_short_name_to_full_name[username]
                zulip_mention = (f'@**{full_name}**')
                message['msg'] = message['msg'].replace(rocketchat_mention,
                                                        zulip_mention)
                user_id = user_map[mention['username']]['zulip_id']
                mentioned_user_ids.append(user_id)
    return mentioned_user_ids


def do_convert_data(output_dir: str, options: Dict[str, Any]) -> None:
    #  Subdomain is set by the user while running the import commands
    realm_subdomain = ""
    global OPTIONS
    OPTIONS = options
    logging.basicConfig(level=getattr(logging, OPTIONS['loglevel'].upper()))
    domain_name = settings.EXTERNAL_HOST

    os.makedirs(output_dir, exist_ok=True)
    # output directory should be empty initially
    if os.listdir(output_dir):
        raise Exception("Output directory should be empty!")

    # Read data from the rocketchat file
    realm, avatar_list, user_map, stream_map, private_stream_map, zerver_recipient = \
        rocketchat_workspace_to_realm(domain_name, realm_subdomain)
    subscriber_map = make_subscriber_map(
        zerver_subscription=realm['zerver_subscription'],
    )

    # For user mentions
    user_short_name_to_full_name = {}
    for userprofile in realm['zerver_userprofile']:
        full_name = userprofile['full_name']
        user_short_name_to_full_name[userprofile['short_name']] = full_name
    zerver_attachment, attachment_rec = convert_rocketchat_workspace_messages(
        output_dir, subscriber_map, user_map, stream_map, private_stream_map,
        zerver_recipient, user_short_name_to_full_name)
    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)
    # avatar_records = process_avatars(avatar_list, avatar_folder, realm_id, 8)
    attachment: Dict[str, List[Any]] = {"zerver_attachment": zerver_attachment}

    # IO realm.json
    create_converted_data_files(realm, output_dir, '/realm.json')
    # IO emoji records
    create_converted_data_files([], output_dir, '/emoji/records.json')
    # IO avatar records
    create_converted_data_files(avatar_list, output_dir,
                                '/avatars/records.json')
    # IO uploads records
    create_converted_data_files(attachment_rec, output_dir,
                                '/uploads/records.json')
    # IO attachments records
    create_converted_data_files(attachment, output_dir, '/attachment.json')

    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz',
                           output_dir, '-P'])

    logging.info('######### DATA CONVERSION FINISHED #########\n')
    logging.info("Zulip data dump created at %s", output_dir)


def write_data_to_file(output_file: str, data: Any) -> None:
    with open(output_file, "w") as f:
        f.write(ujson.dumps(data, indent=4))
