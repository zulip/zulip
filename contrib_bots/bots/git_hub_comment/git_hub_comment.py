# See readme.md for instructions on running this code.
from __future__ import absolute_import
from __future__ import print_function
from . import github
import json
import logging
import os
import requests


class InputError(IndexError):
    '''raise this when there is an error with the information the user has entered'''


class GitHubHandler(object):
    '''
    This plugin allows you to comment on a GitHub issue, under a certain repository.
    It looks for messages starting with '@mention-bot'.
    '''

    def usage(self):
        return '''
            This bot will allow users to comment on a GitHub issue.
            Users should preface messages with '@mention-bot'.
            You will need to have a GitHub account.

            Before running this, make sure to get a GitHub OAuth token.
            The token will need to be authorized for the following scopes:
            'gist, public_repo, user'.
            Store it in the '~/.github_auth.conf' file, along with your username, in the format:
            github_repo = <repo_name>  (The name of the repo to post to)
            github_repo_owner = <repo_owner>  (The owner of the repo to post to)
            github_username = <username>  (The username of the GitHub bot)
            github_token = <oauth_token>   (The personal access token for the GitHub bot)

            Leave the first two options blank.

            Please use this format in your message to the bot:
            '<repository_owner>/<repository>/<issue_number>/<your_comment>'.
            '''

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']

        handle_input(client, original_content, original_sender)

handler_class = GitHubHandler


def send_to_github(repo_owner, repo, issue, comment_body):
    session = github.auth()
    comment = {
        'body': comment_body
    }
    r = session.post('https://api.github.com/repos/%s/%s/issues/%s/comments' % (repo_owner, repo, issue),
                     json.dumps(comment))

    return r.status_code


def get_values_message(original_content):
    # gets rid of whitespace around the edges, so that they aren't a problem in the future
    message_content = original_content.strip()
    # splits message by '/' which will work if the information was entered correctly
    message_content = message_content.split('/')
    try:
        # this will work if the information was entered correctly
        user = github.get_username()
        repo_owner = message_content[2]
        repo = message_content[3]
        issue = message_content[4]
        comment_body = message_content[5]

        return dict(user=user, repo_owner=repo_owner, repo=repo, issue=issue, comment_body=comment_body)
    except IndexError:
        raise InputError


def handle_input(client, original_content, original_sender):
    try:
        params = get_values_message(original_content)

        status_code = send_to_github(params['repo_owner'], params['repo'],
                                     params['issue'], params['comment_body'])

        if status_code == 201:
            # sending info to github was successful!
            reply_message = "You commented on issue number " + params['issue'] + " under " + \
                            params['repo_owner'] + "'s repository " + params['repo'] + "!"

            send_message(client, reply_message, original_sender)

        elif status_code == 404:
            # this error could be from an error with the OAuth token
            reply_message = "Error code: " + str(status_code) + " :( There was a problem commenting on issue number " \
                            + params['issue'] + " under " + \
                            params['repo_owner'] + "'s repository " + params['repo'] + \
                            ". Do you have the right OAuth token?"

            send_message(client, reply_message, original_sender)

        else:
            # sending info to github did not work
            reply_message = "Error code: " + str(status_code) +\
                            " :( There was a problem commenting on issue number " \
                            + params['issue'] + " under " + \
                            params['repo_owner'] + "'s repository " + params['repo'] + \
                            ". Did you enter the information in the correct format?"

            send_message(client, reply_message, original_sender)
    except InputError:
            message = "It doesn't look like the information was entered in the correct format." \
                      " Did you input it like this? " \
                      "'/<username>/<repository_owner>/<repository>/<issue_number>/<your_comment>'."
            send_message(client, message, original_sender)
            logging.error('there was an error with the information you entered')


def send_message(client, message, original_sender):
    # function for sending a message
    client.send_message(dict(
        type='private',
        to=original_sender,
        content=message,
    ))
