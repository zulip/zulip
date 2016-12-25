import re
import os
import sys
import logging
import six.moves.configparser

import requests

class GithubHandler(object):
    '''
    This bot provides details on github issues and pull requests when they're
    referenced in the chat.
    '''

    CONFIG_PATH = os.path.expanduser('~/.contrib_bots/github_detail.ini')
    GITHUB_ISSUE_URL_TEMPLATE = 'https://api.github.com/repos/{owner}/{repo}/issues/{id}'
    GITHUB_PULL_URL_TEMPLATE = 'https://api.github.com/repos/{owner}/{repo}/pulls/{id}'
    HANDLE_MESSAGE_REGEX = re.compile("(?:([\w-]+)\/)?([\w-]+)?#(\d+)")
    MAX_LENGTH_OF_MESSAGE = 200

    def __init__(self):
        config = six.moves.configparser.ConfigParser()
        with open(self.CONFIG_PATH) as config_file:
            config.readfp(config_file)
        if config.get('GitHub', 'owner'):
            self.owner = config.get('GitHub', 'owner')
        else:
            # Allowing undefined default repos would require multiple triage_message regexs.
            # It's simpler to require them to be defined.
            sys.exit('Default owner not defined')

        if config.get('GitHub', 'repo'):
            self.repo = config.get('GitHub', 'repo')
        else:
            sys.exit('Default repo not defined')

    def usage(self):
        # type: () -> None
        return ("This plugin displays details on github issues and pull requests. "
                "To reference an issue or pull request usename mention the bot then "
                "anytime in the message type its id, for example:\n"
                "@**Github detail** #3212 zulip/#3212 zulip/zulip#3212\n"
                "The default owner is {} and the default repo is {}.".format(self.owner, self.repo))

    def triage_message(self, message, client):
        # type: () -> bool
        # Check the message contains a username mention, an issue idi
        # or 'help', and that we're not replying to another bot.
        regex = "(?:@(?:\*\*){}).+?(?:#\d+)|(?:help)".format(re.escape(client.full_name))
        return re.search(regex, message['content']) and not message['sender_email'].endswith('-bot@zulip.com')

    def format_message(self, details):
        # type: (Dict[Text, Union[Text, int, bool]]) -> Text
        number = details['number']
        title = details['title']
        link = details['html_url']
        # Truncate if longer than 200 characters.
        ellipsis = '...'

        if len(details['body']) > self.MAX_LENGTH_OF_MESSAGE + len(ellipsis):
            description = "{}{}".format(details['body'][:self.MAX_LENGTH_OF_MESSAGE], ellipsis)
        else:
            description = details['body']
        status = details['state'].title()

        return '**[{id} | {title}]({link})** - **{status}**\n```quote\n{description}\n```'\
            .format(id=number, title=title, link=link, status=status, description=description)

    def get_details_from_github(self, owner, repo, number):
        # type: (Text, Text, Text) -> Dict[Text, Union[Text, Int, Bool]]
        # Gets the details of an issues or pull request

        # Try to get an issue, try to get a pull if that fails
        try:
            r = requests.get(
                self.GITHUB_ISSUE_URL_TEMPLATE.format(owner=owner, repo=repo, id=number))
        except requests.exceptions.RequestException as e:
            logging.exception(e)
            return

        if r.status_code == 404:
            try:
                r = requests.get(
                    self.GITHUB_PULL_URL_TEMPLATE.format(owner=owner, repo=repo, id=number))
            except requests.exceptions.RequestException as e:
                logging.exception(e)
                return

        if r.status_code != requests.codes.ok:
            return

        return r.json()

    def get_owner_and_repo(self, issue_pr):
        owner = issue_pr.group(1)
        repo = issue_pr.group(2)
        if owner is None:
            owner = self.owner
            if repo is None:
                repo = self.repo
        return (owner, repo)

    def handle_message(self, message, client, state_handler):
        # type: () -> None
        # Send help message
        if message['content'] == '@**{}** help'.format(client.full_name):
            client.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=self.usage(),
            ))

        # Capture owner, repo, id
        issue_prs = re.finditer(
            self.HANDLE_MESSAGE_REGEX, message['content'])

        bot_messages = []
        for issue_pr in issue_prs:
            owner, repo = self.get_owner_and_repo(issue_pr)
            details = self.get_details_from_github(owner, repo, issue_pr.group(3))
            if details is not None:
                bot_messages.append(self.format_message(details))
            else:
                bot_messages.append("Failed to find issue/pr: {owner}/{repo}#{id}".format(owner=owner, repo=repo, id=issue_pr.group(3)))
        bot_message = '\n'.join(bot_messages)

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=bot_message,
        ))

handler_class = GithubHandler
