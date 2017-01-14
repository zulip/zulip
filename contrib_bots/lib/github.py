# The purpose of this file is to handle all requests
# to the Github API, which will make sure that all
# requests are to the same account, and that all requests
# authenticated correctly and securely
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
import json
import os
import requests
import six.moves.configparser
import urllib.error
import urllib.parse
import urllib.request
import logging

class Github(object):
    '''
    Before use, check ~/.github/github.conf, and make sure there are
    github_repo   (The name of the repo to post to)
    github_repo_owner   (The owner of the repo to post to)
    github_username   (The username of the github bot)
    github_token    (The personal access token for the github bot)
    '''

    CONFIG_FILE = '~/.github/github.conf'

    def __init__(self):
        self.session = requests.session()
        self.base_url = ''
        self.authed = False

    def auth(self):
        if self.authed:
            return
        # Sets up the configParser to read the .conf file
        config = six.moves.configparser.ConfigParser()
        # Reads the config file
        config.read([os.path.expanduser(Github.CONFIG_FILE)])
        # Gets the properties from the config file
        oauth_token = config.get('github', 'github_token')
        username = config.get('github', 'github_username')
        self.base_url = 'https://api.github.com/repos/{}/{}'.format(config.get('github', 'github_repo_owner'), config.get('github', 'github_repo'))
        # authorises the requests session
        self.session.auth = (username, oauth_token)
        # Returns the session
        self.authed = True
        return

    def post(self, url, params):
        # If it is not authenticated, authenticate
        if not self.authed:
            self.auth()
        logging.info('Sending POST request to {}'.format(url))
        # Sends the request
        r = self.session.post(url, json.dumps(params))
        if not r.ok:
            logging.debug(r.content)
        return r

    def get(self, url):
        # If it is not authenticated, authenticate
        if not self.authed:
            self.auth()
        logging.info('Sending GET request to {}'.format(url))
        # Sends the request
        r = self.session.get(url)
        if not r.ok:
            logging.debug(r.content)
        return r
