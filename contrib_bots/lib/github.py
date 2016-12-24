#!/usr/bin/env python

# The purpose of this file is to handle all requests
# to the Github API, which will make sure that all
# requests are to the same account, and that all requests
# authenticated correctly and securely
# The sole purpose of this is to authenticate, and it will
# return the requests session that is properly authenticated
import logging
import os
import requests
import six.moves.configparser


# This file contains the oauth token for a github user, their username, and optionally, a repository
# name and owner. All in the format:
# github_repo
# github_repo_owner
# github_username
# github_token
CONFIG_FILE = '~/.github-auth.conf'

global config
config = six.moves.configparser.ConfigParser()  # Sets up the configParser to read the .conf file
config.read([os.path.expanduser(CONFIG_FILE)])  # Reads the config file


def auth():
    # Creates and authorises a requests session
    session = requests.session()
    session.auth = (get_username(), get_oauth_token())

    return session


def get_oauth_token():
    _get_data('token')


def get_username():
    _get_data('username')


def get_repo():
    _get_data('repo')


def get_repo_owner():
    _get_data('repo_owner')


def _get_data(key):
    try:
        return config.get('github', 'github_%s' % (key))
    except Exception:
        logging.exception('GitHub %s not supplied in ~/.github-auth.conf.' % (key))
