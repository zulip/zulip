import random
import requests
import shutil
import logging
import os

from typing import List, Dict, Any, Optional
from django.forms.models import model_to_dict

from zerver.models import Realm, RealmEmoji, Subscription, Recipient, \
    Attachment, Stream, Message
from zerver.lib.actions import STREAM_ASSIGNMENT_COLORS as stream_colors
from zerver.lib.avatar_hash import user_avatar_path_from_ids
from zerver.lib.parallel import run_parallel

# stubs
ZerverFieldsT = Dict[str, Any]

def build_zerver_realm(realm_id: int, realm_subdomain: str, time: float,
                       other_product: str) -> List[ZerverFieldsT]:
    realm = Realm(id=realm_id, date_created=time,
                  name=realm_subdomain, string_id=realm_subdomain,
                  description=("Organization imported from %s!" % (other_product)))
    auth_methods = [[flag[0], flag[1]] for flag in realm.authentication_methods]
    realm_dict = model_to_dict(realm, exclude='authentication_methods')
    realm_dict['authentication_methods'] = auth_methods
    return[realm_dict]

def build_avatar(zulip_user_id: int, realm_id: int, email: str, avatar_url: str,
                 timestamp: Any, avatar_list: List[ZerverFieldsT]) -> None:
    avatar = dict(
        path=avatar_url,  # Save original avatar url here, which is downloaded later
        realm_id=realm_id,
        content_type=None,
        user_profile_id=zulip_user_id,
        last_modified=timestamp,
        user_profile_email=email,
        s3_path="",
        size="")
    avatar_list.append(avatar)

def build_subscription(recipient_id: int, user_id: int,
                       subscription_id: int) -> ZerverFieldsT:
    subscription = Subscription(
        color=random.choice(stream_colors),
        id=subscription_id)
    subscription_dict = model_to_dict(subscription, exclude=['user_profile', 'recipient_id'])
    subscription_dict['user_profile'] = user_id
    subscription_dict['recipient'] = recipient_id
    return subscription_dict

def build_recipient(type_id: int, recipient_id: int, type: int) -> ZerverFieldsT:
    recipient = Recipient(
        type_id=type_id,  # stream id
        id=recipient_id,
        type=type)
    recipient_dict = model_to_dict(recipient)
    return recipient_dict

def build_realm(zerver_realm: List[ZerverFieldsT], realm_id: int,
                domain_name: str) -> ZerverFieldsT:
    realm = dict(zerver_client=[{"name": "populate_db", "id": 1},
                                {"name": "website", "id": 2},
                                {"name": "API", "id": 3}],
                 zerver_customprofilefield=[],
                 zerver_customprofilefieldvalue=[],
                 zerver_userpresence=[],  # shows last logged in data, which is not available
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
    return realm

def build_usermessages(zerver_usermessage: List[ZerverFieldsT], usermessage_id: int,
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

def build_defaultstream(realm_id: int, stream_id: int,
                        defaultstream_id: int) -> ZerverFieldsT:
    defaultstream = dict(
        stream=stream_id,
        realm=realm_id,
        id=defaultstream_id)
    return defaultstream

def build_stream(date_created: Any, realm_id: int, name: str,
                 description: str, stream_id: int, deactivated: bool=False,
                 invite_only: bool=False) -> ZerverFieldsT:
    stream = Stream(
        name=name,
        deactivated=deactivated,
        description=description,
        date_created=date_created,
        invite_only=invite_only,
        id=stream_id)
    stream_dict = model_to_dict(stream,
                                exclude=['realm'])
    stream_dict['realm'] = realm_id
    return stream_dict

def build_message(subject: str, pub_date: float, message_id: int, content: str,
                  rendered_content: Optional[str], user_id: int, recipient_id: int,
                  has_image: bool=False, has_link: bool=False,
                  has_attachment: bool=True) -> ZerverFieldsT:
    zulip_message = Message(
        rendered_content_version=1,  # this is Zulip specific
        subject=subject,
        pub_date=pub_date,
        id=message_id,
        content=content,
        rendered_content=rendered_content,
        has_image=has_image,
        has_attachment=has_attachment,
        has_link=has_link)
    zulip_message_dict = model_to_dict(zulip_message,
                                       exclude=['recipient', 'sender', 'sending_client'])
    zulip_message_dict['sender'] = user_id
    zulip_message_dict['sending_client'] = 1
    zulip_message_dict['recipient'] = recipient_id

    return zulip_message_dict

def build_attachment(realm_id: int, message_id: int, attachment_id: int,
                     user_id: int, fileinfo: ZerverFieldsT, s3_path: str,
                     zerver_attachment: List[ZerverFieldsT]) -> None:
    """
    This function should be passed a 'fileinfo' dictionary, which contains
    information about 'size', 'created' (created time) and ['name'] (filename).
    """
    attachment = Attachment(
        id=attachment_id,
        size=fileinfo['size'],
        create_time=fileinfo['created'],
        is_realm_public=True,
        path_id=s3_path,
        file_name=fileinfo['name'])

    attachment_dict = model_to_dict(attachment,
                                    exclude=['owner', 'messages', 'realm'])
    attachment_dict['owner'] = user_id
    attachment_dict['messages'] = [message_id]
    attachment_dict['realm'] = realm_id

    zerver_attachment.append(attachment_dict)

def process_avatars(avatar_list: List[ZerverFieldsT], avatar_dir: str, realm_id: int,
                    threads: int, size_url_suffix: str='') -> List[ZerverFieldsT]:
    """
    This function gets the avatar of the user and saves it in the
    user's avatar directory with both the extensions '.png' and '.original'
    Required parameters:

    1. avatar_list: List of avatars to be mapped in avatars records.json file
    2. avatar_dir: Folder where the downloaded avatars are saved
    3. realm_id: Realm ID.
    """

    def get_avatar(avatar_upload_list: List[str]) -> int:
        avatar_url = avatar_upload_list[0]
        image_path = avatar_upload_list[1]
        original_image_path = avatar_upload_list[2]
        response = requests.get(avatar_url + size_url_suffix, stream=True)
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
        avatar_url = avatar['path']
        avatar_original = dict(avatar)

        image_path = ('%s/%s.png' % (avatar_dir, avatar_hash))
        original_image_path = ('%s/%s.original' % (avatar_dir, avatar_hash))

        avatar_upload_list.append([avatar_url, image_path, original_image_path])
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
    This function downloads the uploads and saves it in the realm's upload directory.
    Required parameters:

    1. upload_list: List of uploads to be mapped in uploads records.json file
    2. upload_dir: Folder where the downloaded uploads are saved
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

def process_emojis(zerver_realmemoji: List[ZerverFieldsT], emoji_dir: str,
                   emoji_url_map: ZerverFieldsT, threads: int) -> List[ZerverFieldsT]:
    """
    This function downloads the custom emojis and saves in the output emoji folder.
    Required parameters:

    1. zerver_realmemoji: List of all RealmEmoji objects to be imported
    2. emoji_dir: Folder where the downloaded emojis are saved
    3. emoji_url_map: Maps emoji name to its url
    """
    def get_emojis(upload: List[str]) -> int:
        emoji_url = upload[0]
        emoji_path = upload[1]
        upload_emoji_path = os.path.join(emoji_dir, emoji_path)

        response = requests.get(emoji_url, stream=True)
        os.makedirs(os.path.dirname(upload_emoji_path), exist_ok=True)
        with open(upload_emoji_path, 'wb') as emoji_file:
            shutil.copyfileobj(response.raw, emoji_file)
        return 0

    emoji_records = []
    upload_emoji_list = []
    logging.info('######### GETTING EMOJIS #########\n')
    logging.info('DOWNLOADING EMOJIS .......\n')
    for emoji in zerver_realmemoji:
        emoji_url = emoji_url_map[emoji['name']]
        emoji_path = RealmEmoji.PATH_ID_TEMPLATE.format(
            realm_id=emoji['realm'],
            emoji_file_name=emoji['name'])

        upload_emoji_list.append([emoji_url, emoji_path])

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
