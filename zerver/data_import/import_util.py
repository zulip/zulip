import random
import requests
import shutil
import logging

from typing import List, Dict, Any
from django.forms.models import model_to_dict

from zerver.models import Realm
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
    subscription = dict(
        recipient=recipient_id,
        color=random.choice(stream_colors),
        audible_notifications=True,
        push_notifications=False,
        email_notifications=False,
        desktop_notifications=True,
        pin_to_top=False,
        in_home_view=True,
        active=True,
        user_profile=user_id,
        id=subscription_id)
    return subscription

def build_recipient(type_id: int, recipient_id: int, type: int) -> ZerverFieldsT:
    recipient = dict(
        type_id=type_id,  # stream id
        id=recipient_id,
        type=type)
    return recipient

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
