import base64
import dateutil
import glob
import logging
import os
import shutil
import subprocess
import ujson

from typing import Any, Callable, Dict, List, Optional, Set

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.lib.utils import (
    process_list_in_batches,
)

from zerver.models import (
    RealmEmoji,
    Recipient,
    UserProfile,
)

from zerver.data_import.import_util import (
    build_message,
    build_realm,
    build_realm_emoji,
    build_recipients,
    build_stream,
    build_subscription,
    build_user,
    build_user_message,
    build_zerver_realm,
    create_converted_data_files,
    write_avatar_png,
)

from zerver.data_import.hipchat_attachment import AttachmentHandler
from zerver.data_import.hipchat_user import UserHandler
from zerver.data_import.sequencer import sequencer

# Create one sequencer for our entire conversion.
NEXT_ID = sequencer()

# stubs
ZerverFieldsT = Dict[str, Any]

def str_date_to_float(date_str: str) -> float:
    '''
        Dates look like this:

        "2018-08-08T14:23:54Z 626267"
    '''

    parts = date_str.split(' ')
    time_str = parts[0].replace('T', ' ')
    date_time = dateutil.parser.parse(time_str)
    timestamp = date_time.timestamp()
    if len(parts) == 2:
        microseconds = int(parts[1])
        timestamp += microseconds / 1000000.0
    return timestamp

def untar_input_file(tar_file: str) -> str:
    data_dir = tar_file.replace('.tar', '')
    data_dir = os.path.abspath(data_dir)

    if os.path.exists(data_dir):
        logging.info('input data was already untarred to %s, we will use it' % (data_dir,))
        return data_dir

    os.makedirs(data_dir)

    subprocess.check_call(['tar', '-xf', tar_file, '-C', data_dir])

    logging.info('input data was untarred to %s' % (data_dir,))

    return data_dir

def read_user_data(data_dir: str) -> List[ZerverFieldsT]:
    fn = 'users.json'
    data_file = os.path.join(data_dir, fn)
    with open(data_file, "r") as fp:
        return ujson.load(fp)

def convert_user_data(user_handler: UserHandler,
                      raw_data: List[ZerverFieldsT],
                      realm_id: int) -> None:
    flat_data = [
        d['User']
        for d in raw_data
    ]

    def process(in_dict: ZerverFieldsT) -> ZerverFieldsT:
        delivery_email = in_dict['email']
        email = in_dict['email']
        full_name = in_dict['name']
        id = in_dict['id']
        is_realm_admin = in_dict['account_type'] == 'admin'
        is_guest = in_dict['account_type'] == 'guest'
        is_mirror_dummy = False
        short_name = in_dict['mention_name']
        timezone = in_dict['timezone']

        if not email:
            # Hipchat guest users don't have emails, so
            # we just fake them.
            try:
                assert(is_guest)
            except:
                print(id)
                exit(1)
            email = 'guest-{id}@example.com'.format(id=id)
            delivery_email = email

        date_joined = int(timezone_now().timestamp())
        is_active = not in_dict['is_deleted']

        # unmapped fields:
        #    title - Developer, Project Manager, etc.
        #    rooms - no good sample data
        #    created - we just use "now"
        #    roles - we just use account_type

        if in_dict.get('avatar'):
            avatar_source = 'U'
        else:
            avatar_source = 'G'

        return build_user(
            avatar_source=avatar_source,
            date_joined=date_joined,
            delivery_email=delivery_email,
            email=email,
            full_name=full_name,
            id=id,
            is_active=is_active,
            is_realm_admin=is_realm_admin,
            is_guest=is_guest,
            is_mirror_dummy=is_mirror_dummy,
            realm_id=realm_id,
            short_name=short_name,
            timezone=timezone,
        )

    for raw_item in flat_data:
        user = process(raw_item)
        user_handler.add_user(user)

def convert_avatar_data(avatar_folder: str,
                        raw_data: List[ZerverFieldsT],
                        realm_id: int) -> List[ZerverFieldsT]:
    '''
    This code is pretty specific to how Hipchat sends us data.
    They give us the avatar payloads in base64 in users.json.

    We process avatars in our own pass of that data, rather
    than doing it while we're getting other user data.  I
    chose to keep this separate, as otherwise you have a lot
    of extraneous data getting passed around.

    This code has MAJOR SIDE EFFECTS--namely writing a bunch
    of files to the avatars directory.
    '''

    flat_data = [
        d['User']
        for d in raw_data
        if d.get('avatar')
    ]

    def process(raw_user: ZerverFieldsT) -> ZerverFieldsT:
        avatar_payload = raw_user['avatar']
        bits = base64.b64decode(avatar_payload)
        user_id = raw_user['id']

        metadata = write_avatar_png(
            avatar_folder=avatar_folder,
            realm_id=realm_id,
            user_id=user_id,
            bits=bits,
        )
        return metadata

    avatar_records = list(map(process, flat_data))
    return avatar_records

def read_room_data(data_dir: str) -> List[ZerverFieldsT]:
    fn = 'rooms.json'
    data_file = os.path.join(data_dir, fn)
    with open(data_file) as f:
        data = ujson.load(f)
    return data

def convert_room_data(raw_data: List[ZerverFieldsT], realm_id: int) -> List[ZerverFieldsT]:
    flat_data = [
        d['Room']
        for d in raw_data
    ]

    def invite_only(v: str) -> bool:
        if v == 'public':
            return False
        elif v == 'private':
            return True
        else:
            raise Exception('unexpected value')

    def process(in_dict: ZerverFieldsT) -> ZerverFieldsT:
        now = int(timezone_now().timestamp())
        out_dict = build_stream(
            date_created=now,
            realm_id=realm_id,
            name=in_dict['name'],
            description=in_dict['topic'],
            stream_id=in_dict['id'],
            deactivated=in_dict['is_archived'],
            invite_only=invite_only(in_dict['privacy']),
        )

        # unmapped fields:
        #    guest_access_url: no Zulip equivalent
        #    created: we just use "now"
        #    members: no good sample data
        #    owners: no good sample data
        #    participants: no good sample data
        return out_dict

    return list(map(process, flat_data))

def make_realm(realm_id: int) -> ZerverFieldsT:
    NOW = float(timezone_now().timestamp())
    domain_name = settings.EXTERNAL_HOST
    realm_subdomain = ""
    zerver_realm = build_zerver_realm(realm_id, realm_subdomain, NOW, 'HipChat')
    realm = build_realm(zerver_realm, realm_id, domain_name)

    # We may override these later.
    realm['zerver_defaultstream'] = []

    return realm

def write_avatar_data(raw_user_data: List[ZerverFieldsT],
                      output_dir: str,
                      realm_id: int) -> None:
    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)

    avatar_records = convert_avatar_data(
        avatar_folder=avatar_folder,
        raw_data=raw_user_data,
        realm_id=realm_id,
    )

    create_converted_data_files(avatar_records, output_dir, '/avatars/records.json')

def write_emoticon_data(realm_id: int,
                        data_dir: str,
                        output_dir: str) -> List[ZerverFieldsT]:
    '''
    This function does most of the work for processing emoticons, the bulk
    of which is copying files.  We also write a json file with metadata.
    Finally, we return a list of RealmEmoji dicts to our caller.

    In our data_dir we have a pretty simple setup:

        emoticons.json - has very simple metadata on emojis:

          {
            "Emoticon": {
              "id": 9875487,
              "path": "emoticons/yasss.jpg",
              "shortcut": "yasss"
            }
          },
          {
            "Emoticon": {
              "id": 718017,
              "path": "emoticons/yayyyyy.gif",
              "shortcut": "yayyyyy"
            }
          }

        emoticons/ - contains a bunch of image files:

            slytherinsnake.gif
            spanishinquisition.jpg
            sparkle.png
            spiderman.gif
            stableparrot.gif
            stalkerparrot.gif
            supergirl.png
            superman.png

    We move all the relevant files to Zulip's more nested
    directory structure.
    '''

    logging.info('Starting to process emoticons')

    fn = 'emoticons.json'
    data_file = os.path.join(data_dir, fn)
    with open(data_file) as f:
        data = ujson.load(f)

    flat_data = [
        dict(
            path=d['Emoticon']['path'],
            name=d['Emoticon']['shortcut'],
        )
        for d in data
    ]

    emoji_folder = os.path.join(output_dir, 'emoji')
    os.makedirs(emoji_folder, exist_ok=True)

    def process(data: ZerverFieldsT) -> ZerverFieldsT:
        source_sub_path = data['path']
        source_fn = os.path.basename(source_sub_path)
        source_path = os.path.join(data_dir, source_sub_path)

        # Use our template from RealmEmoji
        # PATH_ID_TEMPLATE = "{realm_id}/emoji/images/{emoji_file_name}"
        target_fn = source_fn
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
            file_name=target_fn,
            realm_id=realm_id,
            name=data['name'],
        )

    emoji_records = list(map(process, flat_data))
    create_converted_data_files(emoji_records, output_dir, '/emoji/records.json')

    realmemoji = [
        build_realm_emoji(
            realm_id=realm_id,
            name=rec['name'],
            id=NEXT_ID('realmemoji'),
            file_name=rec['file_name'],
        )
        for rec in emoji_records
    ]
    logging.info('Done processing emoticons')

    return realmemoji

def write_message_data(realm_id: int,
                       message_key: str,
                       zerver_recipient: List[ZerverFieldsT],
                       zerver_subscription: List[ZerverFieldsT],
                       data_dir: str,
                       output_dir: str,
                       user_handler: UserHandler,
                       attachment_handler: AttachmentHandler) -> None:

    stream_id_to_recipient_id = {
        d['type_id']: d['id']
        for d in zerver_recipient
        if d['type'] == Recipient.STREAM
    }

    user_id_to_recipient_id = {
        d['type_id']: d['id']
        for d in zerver_recipient
        if d['type'] == Recipient.PERSONAL
    }

    def get_stream_recipient_id(raw_message: ZerverFieldsT) -> int:
        fn_id = raw_message['fn_id']
        recipient_id = stream_id_to_recipient_id[fn_id]
        return recipient_id

    def get_pm_recipient_id(raw_message: ZerverFieldsT) -> int:
        user_id = raw_message['receiver_id']
        assert(user_id)
        recipient_id = user_id_to_recipient_id[user_id]
        return recipient_id

    if message_key in ['UserMessage', 'NotificationMessage']:
        dir_glob = os.path.join(data_dir, 'rooms', '*', 'history.json')
        get_recipient_id = get_stream_recipient_id
        get_files_dir = lambda fn_id: os.path.join(data_dir, 'rooms', str(fn_id), 'files')

    elif message_key == 'PrivateUserMessage':
        dir_glob = os.path.join(data_dir, 'users', '*', 'history.json')
        get_recipient_id = get_pm_recipient_id
        get_files_dir = lambda fn_id: os.path.join(data_dir, 'users', 'files')

    else:
        raise Exception('programming error: invalid message_key: ' + message_key)

    history_files = glob.glob(dir_glob)
    for fn in history_files:
        dir = os.path.dirname(fn)
        fn_id = int(os.path.basename(dir))
        files_dir = get_files_dir(fn_id)

        process_message_file(
            realm_id=realm_id,
            fn=fn,
            fn_id=fn_id,
            files_dir=files_dir,
            get_recipient_id=get_recipient_id,
            message_key=message_key,
            zerver_subscription=zerver_subscription,
            data_dir=data_dir,
            output_dir=output_dir,
            user_handler=user_handler,
            attachment_handler=attachment_handler,
        )

def process_message_file(realm_id: int,
                         fn: str,
                         fn_id: int,
                         files_dir: str,
                         get_recipient_id: Callable[[ZerverFieldsT], int],
                         message_key: str,
                         zerver_subscription: List[ZerverFieldsT],
                         data_dir: str,
                         output_dir: str,
                         user_handler: UserHandler,
                         attachment_handler: AttachmentHandler) -> None:

    def get_raw_messages(fn: str) -> List[ZerverFieldsT]:
        with open(fn) as f:
            data = ujson.load(f)

        flat_data = [
            d[message_key]
            for d in data
            if message_key in d
        ]

        def get_raw_message(d: Dict[str, Any]) -> ZerverFieldsT:
            if isinstance(d['sender'], str):
                # Some Hipchat instances just give us a person's
                # name in the sender field for NotificationMessage.
                # We turn them into a mirror user.
                mirror_user = user_handler.get_mirror_user(
                    realm_id=realm_id,
                    name=d['sender'],
                )
                sender_id = mirror_user['id']
            else:
                sender_id = d['sender']['id']

            return dict(
                fn_id=fn_id,
                sender_id=sender_id,
                receiver_id=d.get('receiver', {}).get('id'),
                content=d['message'],
                mention_user_ids=d.get('mentions', []),
                pub_date=str_date_to_float(d['timestamp']),
                attachment=d.get('attachment'),
                files_dir=files_dir,
            )

        raw_messages = []

        for d in flat_data:
            raw_message = get_raw_message(d)
            raw_messages.append(raw_message)

        return raw_messages

    raw_messages = get_raw_messages(fn)

    def process_batch(lst: List[Any]) -> None:
        process_raw_message_batch(
            realm_id=realm_id,
            raw_messages=lst,
            zerver_subscription=zerver_subscription,
            user_handler=user_handler,
            attachment_handler=attachment_handler,
            get_recipient_id=get_recipient_id,
            output_dir=output_dir,
        )

    chunk_size = 1000

    process_list_in_batches(
        lst=raw_messages,
        chunk_size=chunk_size,
        process_batch=process_batch,
    )

def process_raw_message_batch(realm_id: int,
                              raw_messages: List[Dict[str, Any]],
                              zerver_subscription: List[ZerverFieldsT],
                              user_handler: UserHandler,
                              attachment_handler: AttachmentHandler,
                              get_recipient_id: Callable[[ZerverFieldsT], int],
                              output_dir: str) -> None:

    def fix_mentions(content: str,
                     mention_user_ids: List[int]) -> str:
        for user_id in mention_user_ids:
            user = user_handler.get_user(user_id=user_id)
            hipchat_mention = '@{short_name}'.format(**user)
            zulip_mention = '@**{full_name}**'.format(**user)
            content = content.replace(hipchat_mention, zulip_mention)

        content = content.replace('@here', '@**all**')
        return content

    mention_map = dict()  # type: Dict[int, Set[int]]

    def make_message(message_id: int, raw_message: ZerverFieldsT) -> ZerverFieldsT:
        # One side effect here:
        mention_map[message_id] = set(raw_message['mention_user_ids'])

        content = fix_mentions(
            content=raw_message['content'],
            mention_user_ids=raw_message['mention_user_ids'],
        )
        pub_date = raw_message['pub_date']
        recipient_id = get_recipient_id(raw_message)
        rendered_content = None
        subject = 'archived'
        user_id = raw_message['sender_id']

        # Another side effect:
        extra_content = attachment_handler.handle_message_data(
            realm_id=realm_id,
            message_id=message_id,
            sender_id=user_id,
            attachment=raw_message['attachment'],
            files_dir=raw_message['files_dir'],
        )

        if extra_content:
            has_attachment = True
            content += '\n' + extra_content
        else:
            has_attachment = False

        return build_message(
            content=content,
            message_id=message_id,
            pub_date=pub_date,
            recipient_id=recipient_id,
            rendered_content=rendered_content,
            subject=subject,
            user_id=user_id,
            has_attachment=has_attachment,
        )

    zerver_message = [
        make_message(
            message_id=NEXT_ID('message'),
            raw_message=raw_message
        )
        for raw_message in raw_messages
    ]

    zerver_usermessage = make_user_messages(
        zerver_message=zerver_message,
        zerver_subscription=zerver_subscription,
        mention_map=mention_map,
    )

    message_json = dict(
        zerver_message=zerver_message,
        zerver_usermessage=zerver_usermessage,
    )

    dump_file_id = NEXT_ID('dump_file_id')
    message_file = "/messages-%06d.json" % (dump_file_id,)
    create_converted_data_files(message_json, output_dir, message_file)

def make_user_messages(zerver_message: List[ZerverFieldsT],
                       zerver_subscription: List[ZerverFieldsT],
                       mention_map: Dict[int, Set[int]]) -> List[ZerverFieldsT]:

    subscriber_map = dict()  # type: Dict[int, Set[int]]
    for sub in zerver_subscription:
        user_id = sub['user_profile']
        recipient_id = sub['recipient']
        if recipient_id not in subscriber_map:
            subscriber_map[recipient_id] = set()
        subscriber_map[recipient_id].add(user_id)

    zerver_usermessage = []

    for message in zerver_message:
        message_id = message['id']
        recipient_id = message['recipient']
        mention_user_ids = mention_map[message_id]
        user_ids = subscriber_map.get(recipient_id, set())
        for user_id in user_ids:
            is_mentioned = user_id in mention_user_ids
            user_message = build_user_message(
                id=NEXT_ID('user_message'),
                user_id=user_id,
                message_id=message_id,
                is_mentioned=is_mentioned,
            )
            zerver_usermessage.append(user_message)

    return zerver_usermessage

def do_build_dict_hipchat_user_by_id(data: [ZerverFieldsT]):
    users={}
    for d in data:
        users[d['User']['id']]=d['User']
    return users
def do_build_dict_zulip_user_by_email(data: [ZerverFieldsT]):
    users={}
    for d in data:
        users[d['email']] = d
    return users
def do_build_dict_zulip_stream_by_name(data: [ZerverFieldsT]):
    streams={}
    for d in data:
        streams[d['name']] = d
    return streams
def do_build_dict_recipient_by_type_id(data: [ZerverFieldsT]):
    recipients={}
    for d in data:
        if d['type'] == 2:
            recipients[d['type_id']] = d
    return recipients
    
def do_subscriptions(raw_data: List[ZerverFieldsT], zerver_stream: List[ZerverFieldsT], realm_id: int, realm: ZerverFieldsT, users: List[ZerverFieldsT], raw_user_data: List[ZerverFieldsT]) -> List[ZerverFieldsT]:
    from pprint import pprint
    users_hipchat = do_build_dict_hipchat_user_by_id(raw_user_data)
    users_zulip = do_build_dict_zulip_user_by_email(data=users)
    stream_zulip = do_build_dict_zulip_stream_by_name(zerver_stream)
    recipient_zulip = do_build_dict_recipient_by_type_id(realm['zerver_recipient'])
    subscriptions = []
    subscription_id = 1
    for d in raw_data:
        print(d['Room']['name'])
        print(stream_zulip[d['Room']['name']]['id'])
        for members in d['Room']['members']:
            print('-----' + str(users_zulip[users_hipchat[members]['email']]['id']) + '----' + users_zulip[users_hipchat[members]['email']]['email'])
            subscription = build_subscription(
                recipient_id=recipient_zulip[stream_zulip[d['Room']['name']]['id']],
                user_id=users_zulip[users_hipchat[members]['email']]['id'],
                subscription_id=subscription_id,
            )
            subscriptions.append(subscription)
            subscription_id +=1
    return subscriptions
def do_convert_data(input_tar_file: str, output_dir: str) -> None:
    input_data_dir = untar_input_file(input_tar_file)

    attachment_handler = AttachmentHandler()
    user_handler = UserHandler()

    realm_id = 0
    realm = make_realm(realm_id=realm_id)

    # users.json -> UserProfile
    raw_user_data = read_user_data(data_dir=input_data_dir)
    convert_user_data(
        user_handler=user_handler,
        raw_data=raw_user_data,
        realm_id=realm_id,
    )
    normal_users = user_handler.get_normal_users()
    # Don't write zerver_userprofile here, because we
    # may add more users later.

    # streams.json -> Stream
    raw_stream_data = read_room_data(data_dir=input_data_dir)
    zerver_stream = convert_room_data(
        raw_data=raw_stream_data,
        realm_id=realm_id,
    )
    realm['zerver_stream'] = zerver_stream

    zerver_recipient = build_recipients(
        zerver_userprofile=normal_users,
        zerver_stream=zerver_stream,    )
    realm['zerver_recipient'] = zerver_recipient
    zerver_subscription = do_subscriptions(
        raw_data=raw_stream_data,
        realm_id=realm_id,
        zerver_stream=zerver_stream,
        realm=realm,
        users=normal_users,
        raw_user_data=raw_user_data,
    )
    realm['zerver_subscription'] = zerver_subscription

    zerver_realmemoji = write_emoticon_data(
        realm_id=realm_id,
        data_dir=input_data_dir,
        output_dir=output_dir,
    )
    realm['zerver_realmemoji'] = zerver_realmemoji

    logging.info('Start importing message data')
    for message_key in ['UserMessage',
                        'NotificationMessage',
                        'PrivateUserMessage']:
        write_message_data(
            realm_id=realm_id,
            message_key=message_key,
            zerver_recipient=zerver_recipient,
            zerver_subscription=zerver_subscription,
            data_dir=input_data_dir,
            output_dir=output_dir,
            user_handler=user_handler,
            attachment_handler=attachment_handler,
        )

    # Order is important here...don't write users until
    # we process everything else, since we may introduce
    # mirror users when processing messages.
    realm['zerver_userprofile'] = user_handler.get_all_users()
    create_converted_data_files(realm, output_dir, '/realm.json')

    logging.info('Start importing avatar data')
    write_avatar_data(
        raw_user_data=raw_user_data,
        output_dir=output_dir,
        realm_id=realm_id,
    )

    attachment_handler.write_info(
        output_dir=output_dir,
        realm_id=realm_id,
    )

    logging.info('Start making tarball')
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])
    logging.info('Done making tarball')
