from __future__ import absolute_import

import os
import sys
import hmac
import time
import base64
from hashlib import sha1
from six.moves.urllib.parse import urlparse, parse_qs
from typing import Any, AnyStr, Dict, List, Optional, Text, Union

if False:
    from thumbor.context import Context

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath('__file__'))))
sys.path.append(ZULIP_PATH)

# Piece of code below relating to secrets conf has been duplicated with that of
# django settings in zproject/settings.py
import six.moves.configparser

DEPLOY_ROOT = os.path.join(os.path.realpath(os.path.dirname(__file__)), '..', '..')

config_file = six.moves.configparser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

# Whether this instance of Zulip is running in a production environment.
PRODUCTION = config_file.has_option('machine', 'deploy_type')
DEVELOPMENT = not PRODUCTION

secrets_file = six.moves.configparser.RawConfigParser()
if PRODUCTION:
    secrets_file.read("/etc/zulip/zulip-secrets.conf")
else:
    secrets_file.read(os.path.join(DEPLOY_ROOT, "zproject/dev-secrets.conf"))

def get_secret(key):
    # type: (str) -> Optional[Text]
    if secrets_file.has_option('secrets', key):
        return secrets_file.get('secrets', key)
    return None

THUMBOR_EXTERNAL_TYPE = 'external'
THUMBOR_S3_TYPE = 's3'
THUMBOR_LOCAL_FILE_TYPE = 'local_file'

def force_text(s, encoding='utf-8'):
    # type: (Union[Text, bytes], str) -> Text
    """converts a string to a text string"""
    if isinstance(s, Text):
        return s
    elif isinstance(s, bytes):
        return s.decode(encoding)
    else:
        raise TypeError("force_text expects a string type")

def get_sign_hash(raw, key):
    # type: (Text, Text) -> Text
    hashed = hmac.new(key.encode('utf-8'), raw.encode('utf-8'), sha1)
    return base64.b64encode(hashed.digest()).decode()

def get_url_params(url):
    # type: (Text) -> Dict[str, Any]
    data = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in data.items() if v}

def sign_is_valid(url, context):
    # type: (str, Context) -> bool
    size = '{0}x{1}'.format(context.request.width, context.request.height)
    data = parse_qs(urlparse(url).query)
    source_type = data.get('source_type', [''])[0]
    sign = data.get('sign', [''])[0]
    if not source_type or not sign:
        return False
    url_path = url.rsplit('?', 1)[0]
    if url_path.startswith('files/'):
        url_path = url_path.split('/', 1)[1]
    raw = u'_'.join([
        force_text(url_path),
        force_text(size),
        force_text(source_type),
    ])
    secret_key = get_secret('thumbor_key')
    if secret_key is None or sign != get_sign_hash(raw, secret_key):
        return False
    return True
