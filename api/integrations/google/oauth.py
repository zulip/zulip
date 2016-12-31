#!/usr/bin/env python
from __future__ import print_function
import argparse
import httplib2
import os

# Uses Google's Client Library
#   pip install --upgrade google-api-python-client
from oauth2client import client, tools
from oauth2client.file import Storage

# Before running this, make sure to register a new
# project in the Google Developers Console
# (https://console.developers.google.com/start)
# and download the "client secret" JSON file.
#
# You'll have to specify its location with --secret-path.
#
# The "-s, --scopes" argument specifies the Google Accounts permissions your
# application needs to run (e.g. viewing your contacts).
# You can find a full list of the accepted scopes here:
# https://developers.google.com/identity/protocols/googlescopes
#
# If you're using this script to set a bot or integration up, look at its
# documentation. The developer probably specified the scopes required for that
# specific application.
#
# The script supports the addition of multiple scopes. Also, if you added some
# scopes in the past, you can add more without overwriting the already existing
# ones.

# This parent argparser is used because it already contains
# the arguments that Google's Client Library method "tools.run_flow"
# supports.
parent = tools.argparser

parent.add_argument('-p', '--secret_path',
                    default='~/.client_secret.json',
                    type=str,
                    help='Path where the file with the secret is (filename included).')
parent.add_argument('-c', '--credential_path',
                    default='~/.google_credentials.json',
                    type=str,
                    help='Path to save the credentials (filename included).')
parent.add_argument('-s', '--scopes',
                    nargs='+',
                    type=str,
                    required=True,
                    help='Scopes to use in the authentication (separated with spaces).')

flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()

APPLICATION_NAME = 'Zulip'

def get_credentials():
    # type: () -> client.Credentials
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    scopes = flags.scopes

    credential_path = os.path.expanduser(flags.credential_path)
    secret_path = os.path.expanduser(flags.secret_path)

    # Try to read the previous credentials file (if any)
    store = Storage(credential_path)
    credentials = store.get()

    # There are no previous credentials, they aren't valid, or don't contain
    # some of the requested scopes
    if not credentials or credentials.invalid or not credentials.has_scopes(scopes):
        if credentials:
            # Check which scopes already exist
            http = credentials.authorize(httplib2.Http())
            old_scopes = list(credentials.retrieve_scopes(http))
            scopes += old_scopes

        # Prepare the OAuth flow with the specified configuration
        flow = client.flow_from_clientsecrets(secret_path, scopes)
        flow.user_agent = APPLICATION_NAME

        # Run the OAuth process
        credentials = tools.run_flow(flow, store, flags)
    else:
        print('Credentials already exist!')

get_credentials()
