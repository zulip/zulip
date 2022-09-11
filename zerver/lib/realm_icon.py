import base64

import requests
from django.conf import settings

from zerver.lib.avatar_hash import gravatar_hash
from zerver.lib.upload import upload_backend
from zerver.models import Realm


def realm_icon_url(realm: Realm) -> str:
    return get_realm_icon_url(realm)


def get_realm_icon_data_url(realm: Realm) -> str:
    if realm.icon_source == "U":
        icon_file = upload_backend.get_realm_icon(realm.id)
    elif settings.ENABLE_GRAVATAR:
        hash_key = gravatar_hash(realm.string_id)
        url = f"https://secure.gravatar.com/avatar/{hash_key}?d=identicon"
        icon_file = requests.get(url).content
    else:
        with open(settings.DEFAULT_AVATAR_URI, "rb") as f:
            icon_file = f.read()
    # base64.b64encode returns a bytes instance, so it's necessary to call decode to get a str
    encoded_img = base64.b64encode(icon_file).decode("ascii")
    return f"data:image/png;base64,{encoded_img}"


def get_realm_icon_url(realm: Realm) -> str:
    if realm.icon_source == "U":
        return upload_backend.get_realm_icon_url(realm.id, realm.icon_version)
    elif settings.ENABLE_GRAVATAR:
        hash_key = gravatar_hash(realm.string_id)
        return f"https://secure.gravatar.com/avatar/{hash_key}?d=identicon"
    else:
        return settings.DEFAULT_AVATAR_URI + "?version=0"
