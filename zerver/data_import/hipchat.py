import base64
import json
import logging
import os
import shutil
import subprocess

from typing import Any, Dict, List

from django.conf import settings
from django.forms.models import model_to_dict
from django.utils.timezone import now as timezone_now

from zerver.models import (
    RealmEmoji,
    UserProfile,
)

from zerver.data_import.import_util import (
    build_realm,
    build_realm_emoji,
    build_recipients,
    build_stream,
    build_subscriptions,
    build_user,
    build_zerver_realm,
    write_avatar_png,
)

# stubs
ZerverFieldsT = Dict[str, Any]

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
    data = json.load(open(data_file))
    return data

def convert_user_data(raw_data: List[ZerverFieldsT], realm_id: int) -> List[ZerverFieldsT]:
    flat_data = [
        d['User']
        for d in raw_data
    ]

    def _is_realm_admin(v: str) -> bool:
        if v == 'user':
            return False
        elif v == 'admin':
            return True
        else:
            raise Exception('unexpected value')

    def process(in_dict: ZerverFieldsT) -> ZerverFieldsT:
        delivery_email = in_dict['email']
        email = in_dict['email']
        full_name = in_dict['name']
        id = in_dict['id']
        is_realm_admin = _is_realm_admin(in_dict['account_type'])
        short_name = in_dict['mention_name']
        timezone = in_dict['timezone']

        date_joined = int(timezone_now().timestamp())
        is_active = not in_dict['is_deleted']

        # unmapped fields:
        #    title - Developer, Project Manager, etc.
        #    rooms - no good sample data
        #    created - we just use "now"
        #    roles - we just use account_type
        return build_user(
            avatar_source='U',
            date_joined=date_joined,
            delivery_email=delivery_email,
            email=email,
            full_name=full_name,
            id=id,
            is_active=is_active,
            is_realm_admin=is_realm_admin,
            realm_id=realm_id,
            short_name=short_name,
            timezone=timezone,
        )

    return list(map(process, flat_data))

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
    data = json.load(open(data_file))
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

def write_upload_data(output_dir: str, realm_id: int) -> None:
    uploads_records = []  # type: List[ZerverFieldsT]
    uploads_folder = os.path.join(output_dir, 'uploads')
    os.makedirs(os.path.join(uploads_folder, str(realm_id)), exist_ok=True)

    attachments = []  # type: List[ZerverFieldsT]
    attachment = {"zerver_attachment": attachments}
    create_converted_data_files(uploads_records, output_dir, '/uploads/records.json')
    create_converted_data_files(attachment, output_dir, '/attachment.json')

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
    data = json.load(open(data_file))

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
            id=i+1,
            file_name=rec['file_name'],
        )
        for i, rec in enumerate(emoji_records)
    ]
    logging.info('Done processing emoticons')

    return realmemoji

def do_convert_data(input_tar_file: str, output_dir: str) -> None:
    input_data_dir = untar_input_file(input_tar_file)

    realm_id = 0
    realm = make_realm(realm_id=realm_id)

    # users.json -> UserProfile
    raw_user_data = read_user_data(data_dir=input_data_dir)
    zerver_userprofile = convert_user_data(
        raw_data=raw_user_data,
        realm_id=realm_id,
    )
    realm['zerver_userprofile'] = zerver_userprofile

    # streams.json -> Stream
    raw_stream_data = read_room_data(data_dir=input_data_dir)
    zerver_stream = convert_room_data(
        raw_data=raw_stream_data,
        realm_id=realm_id,
    )
    realm['zerver_stream'] = zerver_stream

    zerver_recipient = build_recipients(
        zerver_userprofile=zerver_userprofile,
        zerver_stream=zerver_stream,
    )
    realm['zerver_recipient'] = zerver_recipient

    zerver_subscription = build_subscriptions(
        zerver_userprofile=zerver_userprofile,
        zerver_recipient=zerver_recipient,
        zerver_stream=zerver_stream,
    )
    realm['zerver_subscription'] = zerver_subscription

    zerver_realmemoji = write_emoticon_data(
        realm_id=realm_id,
        data_dir=input_data_dir,
        output_dir=output_dir,
    )
    realm['zerver_realmemoji'] = zerver_realmemoji

    create_converted_data_files(realm, output_dir, '/realm.json')

    write_avatar_data(
        raw_user_data=raw_user_data,
        output_dir=output_dir,
        realm_id=realm_id,
    )

    write_upload_data(
        output_dir=output_dir,
        realm_id=realm_id,
    )

    subprocess.check_call(["tar", "-czf", output_dir + '.tar.gz', output_dir, '-P'])

# TODO: everything below is verbatim from slack.py

def create_converted_data_files(data: Any, output_dir: str, file_path: str) -> None:
    output_file = output_dir + file_path
    json.dump(data, open(output_file, 'w'), indent=4)
