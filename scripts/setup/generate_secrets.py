#!/usr/bin/env python3
# This tools generates /etc/zulip/zulip-secrets.conf

import sys
import os

from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
import scripts.lib.setup_path_on_import

os.environ['DJANGO_SETTINGS_MODULE'] = 'zproject.settings'

from django.utils.crypto import get_random_string
import argparse
import uuid
import configparser
from zerver.lib.utils import generate_random_token, generate_api_key

os.chdir(os.path.join(os.path.dirname(__file__), '..', '..'))

CAMO_CONFIG_FILENAME = '/etc/default/camo'

# Standard, 64-bit tokens
AUTOGENERATED_SETTINGS = [
    'avatar_salt',
    'initial_password_salt',
    'local_database_password',
    'rabbitmq_password',
    'shared_secret',
    'thumbor_key',
]

# TODO: We can eliminate this function if we refactor the install
# script to run generate_secrets before zulip-puppet-apply.
def generate_camo_config_file(camo_key):
    # type: (str) -> None
    camo_config = """ENABLED=yes
PORT=9292
CAMO_KEY=%s
""" % (camo_key,)
    with open(CAMO_CONFIG_FILENAME, 'w') as camo_file:
        camo_file.write(camo_config)
    print("Generated Camo config file %s" % (CAMO_CONFIG_FILENAME,))

def generate_django_secretkey():
    # type: () -> str
    """Secret key generation taken from Django's startproject.py"""
    chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    return get_random_string(50, chars)

def get_old_conf(output_filename):
    # type: (str) -> Dict[str, str]
    if not os.path.exists(output_filename) or os.path.getsize(output_filename) == 0:
        return {}

    secrets_file = configparser.RawConfigParser()
    secrets_file.read(output_filename)

    return dict(secrets_file.items("secrets"))

def generate_secrets(development=False):
    # type: (bool) -> None
    if development:
        OUTPUT_SETTINGS_FILENAME = "zproject/dev-secrets.conf"
    else:
        OUTPUT_SETTINGS_FILENAME = "/etc/zulip/zulip-secrets.conf"
    current_conf = get_old_conf(OUTPUT_SETTINGS_FILENAME)

    lines = []  # type: List[str]
    if len(current_conf) == 0:
        lines = ['[secrets]\n']

    def need_secret(name):
        # type: (str) -> bool
        return name not in current_conf

    def add_secret(name, value):
        # type: (str, str) -> None
        lines.append("%s = %s\n" % (name, value))
        current_conf[name] = value

    for name in AUTOGENERATED_SETTINGS:
        if need_secret(name):
            add_secret(name, generate_random_token(64))

    if need_secret('secret_key'):
        add_secret('secret_key', generate_django_secretkey())

    if need_secret('camo_key'):
        add_secret('camo_key', get_random_string(64))

    # zulip_org_key is generated using os.urandom().
    # zulip_org_id does not require a secure CPRNG,
    # it only needs to be unique.
    if need_secret('zulip_org_key'):
        add_secret('zulip_org_key', get_random_string(64))
    if need_secret('zulip_org_id'):
        add_secret('zulip_org_id', str(uuid.uuid4()))

    if need_secret('zulip_url_key'):
        add_secret('zulip_url_key',
                   # 16 is from RemoteZulipServer.URL_KEY_LENGTH
                   generate_api_key()[:16])

    if not development:
        # Write the Camo config file directly
        generate_camo_config_file(current_conf['camo_key'])

    if len(lines) == 0:
        print("generate_secrets: No new secrets to generate.")
        return

    with open(OUTPUT_SETTINGS_FILENAME, 'a') as f:
        # Write a newline at the start, in case there was no newline at
        # the end of the file due to human editing.
        f.write("\n" + "".join(lines))

    print("Generated new secrets in %s." % (OUTPUT_SETTINGS_FILENAME,))

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--development', action='store_true', dest='development',
                       help='For setting up the developer env for zulip')
    group.add_argument('--production', action='store_false', dest='development',
                       help='For setting up the production env for zulip')
    results = parser.parse_args()

    generate_secrets(results.development)
