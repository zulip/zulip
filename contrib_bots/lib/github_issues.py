from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from . import github
import json
import os
import requests
import six.moves.configparser
import urllib.request, urllib.error, urllib.parse

class IssueHandler(object):
    '''
    This plugin facilitates sending issues to github, when
    an item is prefixed with '@issue' or '@bug'

    It will also write items to the issues stream, as well
    as reporting it to github
    '''

    URL = 'https://api.github.com/repos/{}/{}/issues'
    CHARACTER_LIMIT = 70
    CONFIG_FILE = '~/.github-auth.conf'

    def __init__(self):
        self.repo_name = github.get_repo()
        self.repo_owner = github.get_repo_owner()

    def usage(self):
        return '''
            This plugin will allow users to flag messages
            as being issues with Zulip by using te prefix '@issue'

            Before running this, make sure to create a stream
            called "issues" that your API user can send to.

            Also, make sure that the credentials of the github bot have
            been typed in correctly, that there is a personal access token
            with access to public repositories ONLY,
            and that the repository name is entered correctly.

            Check ~/.github-auth.conf, and make sure there are
            github_repo = <repo_name>  (The name of the repo to post to)
            github_repo_owner = <repo_owner>  (The owner of the repo to post to)
            github_username = <username>  (The username of the GitHub bot)
            github_token = <oauth_token>   (The personal access token for the GitHub bot)
            '''

    def triage_message(self, message, client):
        # return True if we want to (possibly) respond to this message
        original_content = message['content']
        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        if message['display_recipient'] == 'issue':
            return False
        is_issue = original_content.startswith('@issue')
        return is_issue

    def handle_message(self, message, client, state_handler):

        original_content = message['content']
        original_sender = message['sender_email']

        new_content = original_content.replace('@issue', 'by {}:'.format(original_sender,))
        # gets the repo url
        url_new = self.URL.format(self.REPO_OWNER, self.REPO_NAME)

        # signs into github using the provided username and password
        session = github.auth()

        # Gets rid of the @issue in the issue title
        issue_title = message['content'].replace('@issue', '').strip()
        issue_content = ''
        new_issue_title = ''
        for part_of_title in issue_title.split():
            if len(new_issue_title) < self.CHARACTER_LIMIT:
                new_issue_title += '{} '.format(part_of_title)
            else:
                issue_content += '{} '.format(part_of_title)

        new_issue_title = new_issue_title.strip()
        issue_content = issue_content.strip()
        new_issue_title += '...'

        # Creates the issue json, that is transmitted to the github api servers
        issue = {
                 'title': new_issue_title,
                 'body': '{} **Sent by [{}](https://chat.zulip.org/#) from zulip**'.format(issue_content, original_sender),
                 'assignee': '',
                 'milestone': 'none',
                 'labels': [''],
                }
        # Sends the HTTP post request
        r = session.post(url_new, json.dumps(issue))

        if r.ok:
            # sends the message onto the 'issues' stream so it can be seen by zulip users
            client.send_message(dict(
                type='stream',
                to='issues',
                subject=message['sender_email'],
                # Adds a check mark so that the user can verify if it has been sent
                content='{} :heavy_check_mark:'.format(new_content),
            ))
            return
            # This means that the issue has not been sent
            # sends the message onto the 'issues' stream so it can be seen by zulip users
            client.send_message(dict(
                type='stream',
                to='issues',
                subject=message['sender_email'],
                # Adds a cross so that the user can see that it has failed, and provides a link to a
                # google search that can (hopefully) direct them to the error
                content='{} :x: Code: [{}](https://www.google.com/search?q=Github HTTP {} Error {})'
                        .format(new_content, r.status_code, r.status_code, r.content),
            ))

handler_class = IssueHandler
