# -*- coding: utf-8 -*-
# See https://zulip.readthedocs.io/en/latest/subsystems/thumbnailing.html
import base64
import os
import sys
import urllib
from django.conf import settings
from libthumbor import CryptoURL

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath('__file__'))))
sys.path.append(ZULIP_PATH)

from zthumbor.loaders.helpers import (
    THUMBOR_S3_TYPE, THUMBOR_LOCAL_FILE_TYPE, THUMBOR_EXTERNAL_TYPE
)
from zerver.lib.camo import get_camo_url

def is_thumbor_enabled() -> bool:
    return settings.THUMBOR_URL != ''

def user_uploads_or_external(url: str) -> bool:
    return url.startswith('http') or url.lstrip('/').startswith('user_uploads/')

def get_source_type(url: str) -> str:
    if not url.startswith('/user_uploads/'):
        return THUMBOR_EXTERNAL_TYPE

    local_uploads_dir = settings.LOCAL_UPLOADS_DIR
    if local_uploads_dir:
        return THUMBOR_LOCAL_FILE_TYPE
    return THUMBOR_S3_TYPE

def generate_thumbnail_url(path: str,
                           size: str='0x0',
                           is_camo_url: bool=False) -> str:
    if not (path.startswith('https://') or path.startswith('http://')):
        path = '/' + path

    if not is_thumbor_enabled():
        if path.startswith('http://'):
            return get_camo_url(path)
        return path

    if not user_uploads_or_external(path):
        return path

    source_type = get_source_type(path)
    safe_url = base64.urlsafe_b64encode(path.encode()).decode('utf-8')
    image_url = '%s/source_type/%s' % (safe_url, source_type)
    width, height = map(int, size.split('x'))
    crypto = CryptoURL(key=settings.THUMBOR_KEY)

    smart_crop_enabled = True
    apply_filters = ['no_upscale()']
    if is_camo_url:
        smart_crop_enabled = False
        apply_filters.append('quality(100)')
    if size != '0x0':
        apply_filters.append('sharpen(0.5,0.2,true)')

    encrypted_url = crypto.generate(
        width=width,
        height=height,
        smart=smart_crop_enabled,
        filters=apply_filters,
        image_url=image_url
    )

    if settings.THUMBOR_URL == 'http://127.0.0.1:9995':
        # If THUMBOR_URL is the default then thumbor is hosted on same machine
        # as the Zulip server and we should serve a relative URL.
        # We add a /thumbor in front of the relative url because we make
        # use of a proxy pass to redirect request internally in Nginx to 9995
        # port where thumbor is running.
        thumbnail_url = '/thumbor' + encrypted_url
    else:
        thumbnail_url = urllib.parse.urljoin(settings.THUMBOR_URL, encrypted_url)
    return thumbnail_url
