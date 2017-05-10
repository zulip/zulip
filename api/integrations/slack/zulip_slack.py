#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#
# slacker is a dependency for this script.
#

from __future__ import absolute_import
from __future__ import print_function

import sys
import string
import random
from six.moves import range
from typing import List, Dict

import zulip
from slacker import Slacker, Response, Error as SlackError

import zulip_slack_config as config


client = zulip.Client(email=config.ZULIP_USER, api_key=config.ZULIP_API_KEY, site=config.ZULIP_SITE)


class FromSlackImporter(object):
    def __init__(self, slack_token, get_archived_channels=True):
        # type: (str, bool) -> None
        self.slack = Slacker(slack_token)
        self.get_archived_channels = get_archived_channels

        self._check_slack_token()

    def get_slack_users_email(self):
        # type: () -> Dict[str, Dict[str, str]]

        r = self.slack.users.list()
        self._check_if_response_is_successful(r)
        results_dict = {}
        for user in r.body['members']:
            if user['profile'].get('email') and user.get('deleted') is False:
                results_dict[user['id']] = {'email': user['profile']['email'], 'name': user['profile']['real_name']}
        return results_dict

    def get_slack_public_channels_names(self):
        # type: () -> List[Dict[str, str]]

        r = self.slack.channels.list()
        self._check_if_response_is_successful(r)
        return [{'name': channel['name'], 'members': channel['members']} for channel in r.body['channels']]

    def get_slack_private_channels_names(self):
        # type: () -> List[str]

        r = self.slack.groups.list()
        self._check_if_response_is_successful(r)
        return [
            channel['name'] for channel in r.body['groups']
            if not channel['is_archived'] or self.get_archived_channels
        ]

    def _check_slack_token(self):
        # type: () -> None
        try:
            r = self.slack.api.test()
            self._check_if_response_is_successful(r)
        except SlackError as e:
            print(e)
            sys.exit(1)
        except Exception as e:
            print(e)
            sys.exit(1)

    def _check_if_response_is_successful(self, response):
        # type: (Response) -> None
        print(response)
        if not response.successful:
            print(response.error)
            sys.exit(1)

def _generate_random_password(size=10):
    # type: (int) -> str
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(size))

def get_and_add_users(slack_importer):
    # type: (Slacker) -> Dict[str, Dict[str, str]]
    users = slack_importer.get_slack_users_email()
    added_users = {}
    print('######### IMPORTING USERS STARTED #########\n')
    for user_id, user in users.items():
        r = client.create_user({
            'email': user['email'],
            'full_name': user['name'],
            'short_name': user['name']
        })
        if not r.get('msg'):
            added_users[user_id] = user
            print(u"{} -> {}\nCreated\n".format(user['name'], user['email']))
        else:
            print(u"{} -> {}\n{}\n".format(user['name'], user['email'], r.get('msg')))
    print('######### IMPORTING USERS FINISHED #########\n')
    return added_users

def create_streams_and_add_subscribers(slack_importer, added_users):
    # type: (Slacker, Dict[str, Dict[str, str]]) -> None
    channels_list = slack_importer.get_slack_public_channels_names()
    print('######### IMPORTING STREAMS STARTED #########\n')
    for stream in channels_list:
        subscribed_users = [added_users[member]['email'] for member in stream['members'] if member in added_users.keys()]
        if subscribed_users:
            r = client.add_subscriptions([{"name": stream['name']}], principals=subscribed_users)
            if not r.get('msg'):
                print(u"{} -> created\n".format(stream['name']))
            else:
                print(u"{} -> {}\n".format(stream['name'], r.get('msg')))
        else:
            print(u"{} -> wasn't created\nNo subscribers\n".format(stream['name']))
    print('######### IMPORTING STREAMS FINISHED #########\n')

def main():
    # type: () -> None
    importer = FromSlackImporter(config.SLACK_TOKEN)
    added_users = get_and_add_users(importer)
    create_streams_and_add_subscribers(importer, added_users)

if __name__ == '__main__':
    main()
