import base64
import dateutil
import glob
import hypchat
import logging
import os
import re
import shutil
import subprocess
import ujson

from typing import Any, Callable, Dict, List, Optional, Set

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.utils import (
    process_list_in_batches,
)

from zerver.models import (
    RealmEmoji,
    Recipient,
)

from zerver.data_import.import_util import (
    build_message,
    build_realm,
    build_realm_emoji,
    build_recipients,
    build_stream,
    build_personal_subscriptions,
    build_public_stream_subscriptions,
    build_stream_subscriptions,
    build_user_message,
    build_user_profile,
    build_zerver_realm,
    create_converted_data_files,
    make_subscriber_map,
    write_avatar_png,
)

from zerver.data_import.hipchat_attachment import AttachmentHandler
from zerver.data_import.hipchat_user import UserHandler
from zerver.data_import.hipchat_subscriber import SubscriberHandler
from zerver.data_import.sequencer import NEXT_ID, IdMapper

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
                      slim_mode: bool,
                      user_id_mapper: IdMapper,
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
        id = user_id_mapper.get(in_dict['id'])
        is_realm_admin = in_dict['account_type'] == 'admin'
        is_guest = in_dict['account_type'] == 'guest'
        is_mirror_dummy = False
        short_name = in_dict['mention_name']
        timezone = in_dict['timezone']

        date_joined = int(timezone_now().timestamp())
        is_active = not in_dict['is_deleted']

        if not email:
            if is_guest:
                # Hipchat guest users don't have emails, so
                # we just fake them.
                email = 'guest-{id}@example.com'.format(id=id)
                delivery_email = email
            else:
                # Hipchat sometimes doesn't export an email for deactivated users.
                assert not is_active
                email = delivery_email = "deactivated-{id}@example.com".format(id=id)

        # unmapped fields:
        #    title - Developer, Project Manager, etc.
        #    rooms - no good sample data
        #    created - we just use "now"
        #    roles - we just use account_type

        if in_dict.get('avatar'):
            avatar_source = 'U'
        else:
            avatar_source = 'G'

        return build_user_profile(
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
                        user_id_mapper: IdMapper,
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

    avatar_records = []

    for d in raw_data:
        raw_user = d['User']
        avatar_payload = raw_user.get('avatar')
        if not avatar_payload:
            continue

        bits = base64.b64decode(avatar_payload)

        raw_user_id = raw_user['id']
        if not user_id_mapper.has(raw_user_id):
            continue

        user_id = user_id_mapper.get(raw_user_id)

        metadata = write_avatar_png(
            avatar_folder=avatar_folder,
            realm_id=realm_id,
            user_id=user_id,
            bits=bits,
        )
        avatar_records.append(metadata)

    return avatar_records

def read_room_data(data_dir: str) -> List[ZerverFieldsT]:
    fn = 'rooms.json'
    data_file = os.path.join(data_dir, fn)
    with open(data_file) as f:
        data = ujson.load(f)
    return data

def convert_room_data(raw_data: List[ZerverFieldsT],
                      subscriber_handler: SubscriberHandler,
                      stream_id_mapper: IdMapper,
                      user_id_mapper: IdMapper,
                      realm_id: int,
                      api_token: Optional[str]=None) -> List[ZerverFieldsT]:
    flat_data = [
        d['Room']
        for d in raw_data
    ]

    def get_invite_only(v: str) -> bool:
        if v == 'public':
            return False
        elif v == 'private':
            return True
        else:
            raise Exception('unexpected value')

    streams = []

    for in_dict in flat_data:
        now = int(timezone_now().timestamp())
        stream_id = stream_id_mapper.get(in_dict['id'])

        invite_only = get_invite_only(in_dict['privacy'])

        stream = build_stream(
            date_created=now,
            realm_id=realm_id,
            name=in_dict['name'],
            description=in_dict['topic'],
            stream_id=stream_id,
            deactivated=in_dict['is_archived'],
            invite_only=invite_only,
        )

        if invite_only:
            users = {
                user_id_mapper.get(key)
                for key in in_dict['members']
                if user_id_mapper.has(key)
            }  # type: Set[int]

            if user_id_mapper.has(in_dict['owner']):
                owner = user_id_mapper.get(in_dict['owner'])
                users.add(owner)
        else:
            users = set()
            if api_token is not None:
                hc = hypchat.HypChat(api_token)
                room_data = hc.fromurl('{0}/v2/room/{1}/member'.format(hc.endpoint, in_dict['id']))

                for item in room_data['items']:
                    hipchat_user_id = item['id']
                    zulip_user_id = user_id_mapper.get(hipchat_user_id)
                    users.add(zulip_user_id)

        if users:
            subscriber_handler.set_info(
                stream_id=stream_id,
                users=users,
            )

        # unmapped fields:
        #    guest_access_url: no Zulip equivalent
        #    created: we just use "now"
        #    participants: no good sample data

        streams.append(stream)

    return streams

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
                      user_id_mapper: IdMapper,
                      realm_id: int) -> None:
    avatar_folder = os.path.join(output_dir, 'avatars')
    avatar_realm_folder = os.path.join(avatar_folder, str(realm_id))
    os.makedirs(avatar_realm_folder, exist_ok=True)

    avatar_records = convert_avatar_data(
        avatar_folder=avatar_folder,
        raw_data=raw_user_data,
        user_id_mapper=user_id_mapper,
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
    if not os.path.exists(data_file):
        logging.warning("HipChat export does not contain emoticons.json.")
        logging.warning("As a result, custom emoji cannot be imported.")
        return []

    with open(data_file) as f:
        data = ujson.load(f)

    if isinstance(data, dict) and 'Emoticons' in data:
        # Handle the hc-migrate export format for emoticons.json.
        flat_data = [
            dict(
                path=d['path'],
                name=d['shortcut'],
            )
            for d in data['Emoticons']
        ]
    else:
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
            s3_path=target_path,
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
                       slim_mode: bool,
                       message_key: str,
                       zerver_recipient: List[ZerverFieldsT],
                       subscriber_map: Dict[int, Set[int]],
                       data_dir: str,
                       output_dir: str,
                       masking_content: bool,
                       stream_id_mapper: IdMapper,
                       user_id_mapper: IdMapper,
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
        stream_id = stream_id_mapper.get(fn_id)
        recipient_id = stream_id_to_recipient_id[stream_id]
        return recipient_id

    def get_pm_recipient_id(raw_message: ZerverFieldsT) -> int:
        raw_user_id = raw_message['receiver_id']
        assert(raw_user_id)
        user_id = user_id_mapper.get(raw_user_id)
        recipient_id = user_id_to_recipient_id[user_id]
        return recipient_id

    if message_key in ['UserMessage', 'NotificationMessage']:
        is_pm_data = False
        dir_glob = os.path.join(data_dir, 'rooms', '*', 'history.json')
        get_recipient_id = get_stream_recipient_id
        get_files_dir = lambda fn_id: os.path.join(data_dir, 'rooms', str(fn_id), 'files')

    elif message_key == 'PrivateUserMessage':
        is_pm_data = True
        dir_glob = os.path.join(data_dir, 'users', '*', 'history.json')
        get_recipient_id = get_pm_recipient_id
        get_files_dir = lambda fn_id: os.path.join(data_dir, 'users', 'files')

    else:
        raise Exception('programming error: invalid message_key: ' + message_key)

    history_files = glob.glob(dir_glob)
    for fn in history_files:
        dir = os.path.dirname(fn)
        fn_id = os.path.basename(dir)
        files_dir = get_files_dir(fn_id)

        process_message_file(
            realm_id=realm_id,
            slim_mode=slim_mode,
            fn=fn,
            fn_id=fn_id,
            files_dir=files_dir,
            get_recipient_id=get_recipient_id,
            message_key=message_key,
            subscriber_map=subscriber_map,
            data_dir=data_dir,
            output_dir=output_dir,
            is_pm_data=is_pm_data,
            masking_content=masking_content,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
            attachment_handler=attachment_handler,
        )

def get_hipchat_sender_id(realm_id: int,
                          slim_mode: bool,
                          message_dict: Dict[str, Any],
                          user_id_mapper: IdMapper,
                          user_handler: UserHandler) -> Optional[int]:
    '''
    The HipChat export is inconsistent in how it renders
    senders, and sometimes we don't even get an id.
    '''
    if isinstance(message_dict['sender'], str):
        if slim_mode:
            return None
        # Some Hipchat instances just give us a person's
        # name in the sender field for NotificationMessage.
        # We turn them into a mirror user.
        mirror_user = user_handler.get_mirror_user(
            realm_id=realm_id,
            name=message_dict['sender'],
        )
        sender_id = mirror_user['id']
        return sender_id

    raw_sender_id = message_dict['sender']['id']

    if raw_sender_id == 0:
        if slim_mode:
            return None
        mirror_user = user_handler.get_mirror_user(
            realm_id=realm_id,
            name=message_dict['sender']['name']
        )
        sender_id = mirror_user['id']
        return sender_id

    if not user_id_mapper.has(raw_sender_id):
        if slim_mode:
            return None
        mirror_user = user_handler.get_mirror_user(
            realm_id=realm_id,
            name=message_dict['sender']['id']
        )
        sender_id = mirror_user['id']
        return sender_id

    # HAPPY PATH: Hipchat just gave us an ordinary
    # sender_id.
    sender_id = user_id_mapper.get(raw_sender_id)
    return sender_id

def process_message_file(realm_id: int,
                         slim_mode: bool,
                         fn: str,
                         fn_id: str,
                         files_dir: str,
                         get_recipient_id: Callable[[ZerverFieldsT], int],
                         message_key: str,
                         subscriber_map: Dict[int, Set[int]],
                         data_dir: str,
                         output_dir: str,
                         is_pm_data: bool,
                         masking_content: bool,
                         user_id_mapper: IdMapper,
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

        def get_raw_message(d: Dict[str, Any]) -> Optional[ZerverFieldsT]:
            sender_id = get_hipchat_sender_id(
                realm_id=realm_id,
                slim_mode=slim_mode,
                message_dict=d,
                user_id_mapper=user_id_mapper,
                user_handler=user_handler,
            )

            if sender_id is None:
                return None

            if is_pm_data:
                # We need to compare with str() on both sides here.
                # In Stride, user IDs are strings, but in HipChat,
                # they are integers, and fn_id is always a string.
                if str(sender_id) != str(fn_id):
                    # PMs are in multiple places in the Hipchat export,
                    # and we only use the copy from the sender
                    return None

            content = d['message']

            if masking_content:
                content = re.sub('[a-z]', 'x', content)
                content = re.sub('[A-Z]', 'X', content)

            return dict(
                fn_id=fn_id,
                sender_id=sender_id,
                receiver_id=d.get('receiver', {}).get('id'),
                content=content,
                mention_user_ids=d.get('mentions', []),
                pub_date=str_date_to_float(d['timestamp']),
                attachment=d.get('attachment'),
                files_dir=files_dir,
            )

        raw_messages = []

        for d in flat_data:
            raw_message = get_raw_message(d)
            if raw_message is not None:
                raw_messages.append(raw_message)

        return raw_messages

    raw_messages = get_raw_messages(fn)

    def process_batch(lst: List[Any]) -> None:
        process_raw_message_batch(
            realm_id=realm_id,
            raw_messages=lst,
            subscriber_map=subscriber_map,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
            attachment_handler=attachment_handler,
            get_recipient_id=get_recipient_id,
            is_pm_data=is_pm_data,
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
                              subscriber_map: Dict[int, Set[int]],
                              user_id_mapper: IdMapper,
                              user_handler: UserHandler,
                              attachment_handler: AttachmentHandler,
                              get_recipient_id: Callable[[ZerverFieldsT], int],
                              is_pm_data: bool,
                              output_dir: str) -> None:

    def fix_mentions(content: str,
                     mention_user_ids: Set[int]) -> str:
        for user_id in mention_user_ids:
            user = user_handler.get_user(user_id=user_id)
            hipchat_mention = '@{short_name}'.format(**user)
            zulip_mention = '@**{full_name}**'.format(**user)
            content = content.replace(hipchat_mention, zulip_mention)

        content = content.replace('@here', '@**all**')
        return content

    mention_map = dict()  # type: Dict[int, Set[int]]

    zerver_message = []

    import html2text
    h = html2text.HTML2Text()

    for raw_message in raw_messages:
        # One side effect here:

        message_id = NEXT_ID('message')
        mention_user_ids = {
            user_id_mapper.get(id)
            for id in set(raw_message['mention_user_ids'])
            if user_id_mapper.has(id)
        }
        mention_map[message_id] = mention_user_ids

        content = fix_mentions(
            content=raw_message['content'],
            mention_user_ids=mention_user_ids,
        )
        content = h.handle(content)

        if len(content) > 10000:
            logging.info('skipping too-long message of length %s' % (len(content),))
            continue

        pub_date = raw_message['pub_date']

        try:
            recipient_id = get_recipient_id(raw_message)
        except KeyError:
            logging.debug("Could not find recipient_id for a message, skipping.")
            continue

        rendered_content = None

        if is_pm_data:
            topic_name = ''
        else:
            topic_name = 'imported from hipchat'
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

        message = build_message(
            content=content,
            message_id=message_id,
            pub_date=pub_date,
            recipient_id=recipient_id,
            rendered_content=rendered_content,
            topic_name=topic_name,
            user_id=user_id,
            has_attachment=has_attachment,
        )
        zerver_message.append(message)

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

    dump_file_id = NEXT_ID('dump_file_id')
    message_file = "/messages-%06d.json" % (dump_file_id,)
    create_converted_data_files(message_json, output_dir, message_file)

def make_user_messages(zerver_message: List[ZerverFieldsT],
                       subscriber_map: Dict[int, Set[int]],
                       is_pm_data: bool,
                       mention_map: Dict[int, Set[int]]) -> List[ZerverFieldsT]:

    zerver_usermessage = []

    for message in zerver_message:
        message_id = message['id']
        recipient_id = message['recipient']
        sender_id = message['sender']
        mention_user_ids = mention_map[message_id]
        subscriber_ids = subscriber_map.get(recipient_id, set())
        user_ids = subscriber_ids | {sender_id}

        for user_id in user_ids:
            is_mentioned = user_id in mention_user_ids
            user_message = build_user_message(
                user_id=user_id,
                message_id=message_id,
                is_private=is_pm_data,
                is_mentioned=is_mentioned,
            )
            zerver_usermessage.append(user_message)

    return zerver_usermessage

def do_convert_data(input_tar_file: str,
                    output_dir: str,
                    masking_content: bool,
                    api_token: Optional[str]=None,
                    slim_mode: bool=False) -> None:
    input_data_dir = untar_input_file(input_tar_file)

    attachment_handler = AttachmentHandler()
    user_handler = UserHandler()
    subscriber_handler = SubscriberHandler()
    user_id_mapper = IdMapper()
    stream_id_mapper = IdMapper()

    realm_id = 0
    realm = make_realm(realm_id=realm_id)

    # users.json -> UserProfile
    raw_user_data = read_user_data(data_dir=input_data_dir)
    convert_user_data(
        user_handler=user_handler,
        slim_mode=slim_mode,
        user_id_mapper=user_id_mapper,
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
        subscriber_handler=subscriber_handler,
        stream_id_mapper=stream_id_mapper,
        user_id_mapper=user_id_mapper,
        realm_id=realm_id,
        api_token=api_token,
    )
    realm['zerver_stream'] = zerver_stream

    zerver_recipient = build_recipients(
        zerver_userprofile=normal_users,
        zerver_stream=zerver_stream,
    )
    realm['zerver_recipient'] = zerver_recipient

    if api_token is None:
        if slim_mode:
            public_stream_subscriptions = []  # type: List[ZerverFieldsT]
        else:
            public_stream_subscriptions = build_public_stream_subscriptions(
                zerver_userprofile=normal_users,
                zerver_recipient=zerver_recipient,
                zerver_stream=zerver_stream,
            )

        private_stream_subscriptions = build_stream_subscriptions(
            get_users=subscriber_handler.get_users,
            zerver_recipient=zerver_recipient,
            zerver_stream=[stream_dict for stream_dict in zerver_stream
                           if stream_dict['invite_only']],
        )
        stream_subscriptions = public_stream_subscriptions + private_stream_subscriptions
    else:
        stream_subscriptions = build_stream_subscriptions(
            get_users=subscriber_handler.get_users,
            zerver_recipient=zerver_recipient,
            zerver_stream=zerver_stream,
        )

    personal_subscriptions = build_personal_subscriptions(
        zerver_recipient=zerver_recipient,
    )
    zerver_subscription = personal_subscriptions + stream_subscriptions

    realm['zerver_subscription'] = zerver_subscription

    zerver_realmemoji = write_emoticon_data(
        realm_id=realm_id,
        data_dir=input_data_dir,
        output_dir=output_dir,
    )
    realm['zerver_realmemoji'] = zerver_realmemoji

    subscriber_map = make_subscriber_map(
        zerver_subscription=zerver_subscription,
    )

    logging.info('Start importing message data')
    for message_key in ['UserMessage',
                        'NotificationMessage',
                        'PrivateUserMessage']:
        write_message_data(
            realm_id=realm_id,
            slim_mode=slim_mode,
            message_key=message_key,
            zerver_recipient=zerver_recipient,
            subscriber_map=subscriber_map,
            data_dir=input_data_dir,
            output_dir=output_dir,
            masking_content=masking_content,
            stream_id_mapper=stream_id_mapper,
            user_id_mapper=user_id_mapper,
            user_handler=user_handler,
            attachment_handler=attachment_handler,
        )

    # Order is important here...don't write users until
    # we process everything else, since we may introduce
    # mirror users when processing messages.
    realm['zerver_userprofile'] = user_handler.get_all_users()
    realm['sort_by_date'] = True

    create_converted_data_files(realm, output_dir, '/realm.json')

    logging.info('Start importing avatar data')
    write_avatar_data(
        raw_user_data=raw_user_data,
        output_dir=output_dir,
        user_id_mapper=user_id_mapper,
        realm_id=realm_id,
    )

    attachment_handler.write_info(
        output_dir=output_dir,
        realm_id=realm_id,
    )

    logging.info('Start making tarball')
    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])
    logging.info('Done making tarball')
