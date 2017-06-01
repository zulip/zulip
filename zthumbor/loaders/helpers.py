import os
import hmac
import time
import base64
from hashlib import sha1
from urlparse import urlparse, parse_qs
import six.moves.configparser
from typing import Any, AnyStr, Dict, List, Optional, Text

THUMBOR_EXTERNAL_TYPE = 'external'
THUMBOR_S3_TYPE = 's3'
THUMBOR_LOCAL_FILE_TYPE = 'local_file'

config_file = six.moves.configparser.RawConfigParser()
config_file.read("/etc/zulip/zulip.conf")

PRODUCTION = config_file.has_option('machine', 'deploy_type')
DEPLOY_ROOT = os.path.join(os.path.realpath(os.path.dirname(__file__)), '..', '..')

secrets_file = six.moves.configparser.RawConfigParser()
if PRODUCTION:
    secrets_file.read("/etc/zulip/zulip-secrets.conf")
else:
    secrets_file.read(os.path.join(DEPLOY_ROOT, "zproject/dev-secrets.conf"))


def get_secret(key):
    # type: (str) -> Any
    if secrets_file.has_option('secrets', key):
        return secrets_file.get('secrets', key)
    return None


def get_sign_hash(raw, key):
    # type: (AnyStr, str) -> Text
    hashed = hmac.new(key.encode('utf-8'), raw.encode('utf-8'), sha1)
    return base64.b64encode(hashed.digest()).decode()


def get_param_value(data, param_name):
    # type: (Dict[str, List[str]], str) -> Optional[str]
    value = data.get(param_name, [])
    if value:
        retval = value[0]
    else:
        retval = None
    return retval


def get_url_params(url):
    # type: (Text) -> Dict[str, Any]
    data = parse_qs(urlparse(url).query)
    return {k: v[0] for k, v in data.items() if v}

# TODO: Set context to reflect the Contect object?
def sign_is_valid(url, context):
    # type: (str, Any) -> Any
    size = '{0}x{1}'.format(context.request.width, context.request.height)
    data = parse_qs(urlparse(url).query)
    expired = get_param_value(data, 'expired')
    sign = get_param_value(data, 'sign')
    if not expired or not sign:
        return False
    url_path = url.rsplit('?', 1)[0]
    raw = u'_'.join([url_path, expired, size])
    if sign == get_sign_hash(raw, get_secret('thumbor_sign_key')):
        if int(expired) > time.time() or int(expired) == 0:
            return True
    return False


def is_external_url(url):
    # type: (str) -> bool
    return url.startswith('http')
