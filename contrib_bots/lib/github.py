# The purpose of this file is to handle all requests
# to the Github API, which will make sure that all
# requests are to the same account, and that all requests
# authenticated correctly and securely
# The sole purpose of this is to authenticate, and it will
# return the requests session that is properly authenticated
import os
import requests
import six.moves.configparser

CONFIG_FILE = '~/.github-issue-bot/github-issue-bot.conf'

def auth():
    # Sets up the configParser to read the .conf file
    config = six.moves.configparser.ConfigParser()
    # Reads the config file
    config.read([os.path.expanduser(CONFIG_FILE)])
    # Gets the properties from the config file
    oauth_token = config.get('github', 'github_token')
    username = config.get('github', 'github_username')
    # Creates and authorises a requests session
    session = requests.session()
    session.auth = (username, oauth_token)
    # Returns the session
    return session
