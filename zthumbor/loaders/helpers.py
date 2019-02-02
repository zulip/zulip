# This file is used by both Python 2.7 (thumbor) and 3 (zulip).
from __future__ import absolute_import

import os
import re
import sys
from typing import Any, Text, Tuple, Optional

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

def get_secret(key, default_value=None, development_only=False):
    # type: (str, Optional[Any], bool) -> Optional[Any]
    if development_only and PRODUCTION:
        return default_value
    if secrets_file.has_option('secrets', key):
        return secrets_file.get('secrets', key)
    return default_value

THUMBOR_EXTERNAL_TYPE = 'external'
THUMBOR_S3_TYPE = 's3'
THUMBOR_LOCAL_FILE_TYPE = 'local_file'

def separate_url_and_source_type(url):
    # type: (Text) -> Tuple[Text, Text]
    THUMBNAIL_URL_PATT = re.compile('^(?P<actual_url>.+)/source_type/(?P<source_type>.+)')
    matches = THUMBNAIL_URL_PATT.match(url)
    return (matches.group('source_type'), matches.group('actual_url'))
