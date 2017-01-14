from . import github
import os
import requests
import urllib.error
import urllib.parse
import urllib.request

class IssueHandler(object):
    '''
    This plugin facilitates sending issues to github, when
    an item is prefixed with '@issue'
    It will also write items to the issues stream, as well
    as reporting it to github
    '''
    CHARACTER_LIMIT = 70

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
            Check ~/.github/github.conf, and make sure there are
            github_repo   (The name of the repo to post to)
            github_repo_owner   (The owner of the repo to post to)
            github_username   (The username of the github bot)
            github_token    (The personal access token for the github bot)
            '''

    def triage_message(self, message):
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

        gh = github.Github()
        # signs into github using the provided username and password
        gh.auth()

        # Gets rid of the @issue in the issue title
        issue_title = message['content'].replace('@issue', '').strip()
        github_issue_title = ''
        github_issue_content = ''
        new_issue_title = []
        new_issue_content = []
        title_length = 0

        for part_of_title in issue_title.split(' '):
            if title_length < IssueHandler.CHARACTER_LIMIT:
                new_issue_title.extend([part_of_title])
                title_length += len(part_of_title)
            else:
                new_issue_content.extend([part_of_title])

        github_issue_content = ' '.join(new_issue_content).strip()
        github_issue_title = ' '.join(new_issue_title).strip()

        if github_issue_content:
            github_issue_title += '...'

        # Creates the issue json, that is transmitted to the github api servers
        issue = {
                 'title': github_issue_title,
                 'body': '{} **Sent by [{}](https://chat.zulip.org/#) from zulip**'.format(github_issue_content, original_sender),
                 'assignee': '',
                 'milestone': 'none',
                 'labels': [''],
                }
        # Sends the HTTP post request
        r = gh.post(gh.base_url + '/issues', issue)

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
