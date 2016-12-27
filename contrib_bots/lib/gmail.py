#instructions to install googleapiclient can be found in this bot's readme file.
from __future__ import print_function
import base64
import httplib2
import logging
import mimetypes
import os
import re

if os.path.isfile(os.path.join(os.path.expanduser('~'),
                               '.google-credentials.json')):
    from googleapiclient import discovery, errors
else:
    logging.error("Couldn't find authorized credentials for a Google account."
                  " Please, run the google.py script from this directory first.")

from email.mime.text import MIMEText
from oauth2client.file import Storage

class GmailHandler(object):
    '''
    This plugin facilitates sending emails from a Gmail account
    from within Zulip. It looks for messages starting with '@gmail'.
    '''

    def __init__(self):
        self.parse_regex_with_label = re.compile('@gmail (.*?) "(.*?)" "(.*?)" --label (.*?)\Z')
        self.parse_regex = re.compile('@gmail (.*?) "(.*?)" "(.*?)"\Z')

    def usage(self):
        return '''
            This plugin will allow users to send emails from a
            personal gmail account. Users should preface
            messages with "@gmail".

            Enter messages in the following format:
            '@gmail <recipient_email> "<subject>" "<body>" --label <label>'
            The --label tag is optional and can be left out.
            '''

    def help(self, client, message):
        content = ("This plugin will allow users to send emails from a"
                   "personal gmail account. Users should preface"
                   "messages with '@gmail'."

                   "Enter messages in the following format:"
                   '@gmail <recipient_email> "<subject>" "<body>" --label <label>'
                   "The --label tag is optional and can be left out. Note the quotation"
                   " marks around the subject and body.")

        client.send_message(dict(
            type = 'private',
            to = message['sender_email'],
            sender = self.bot_email,
            content = content
        ))

    def triage_message(self, message, client):
        # return True if we want to (possibly) response to this message

        original_content = message['content']
        self.bot_email = client.email

        # This next line of code is defensive
        if message['display_recipient'] == 'gmail':
            return False

        if original_content.startswith('@gmail') and 'help' in original_content:
            help(client, message)
            return False

        return original_content.startswith('@gmail')

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']

        try:
            recipient, subject, body, label = self.parse_input(original_content)
        except TypeError:
            content = ("The input format used was incorrect. The correct format is: "
                       '@gmail <recipient> "<subject>" "<body>"')

            client.send_message(dict(
                type = 'private',
                to = original_sender,
                sender = self.bot_email,
                content = content
            ))

            return False

        service = get_service()
        email = create_message(body, subject, recipient)
        result = send_message(service, email)

        label_result = False
        if label:
            create_label(service, label)
            label_id = get_label_id(service, label)
            label_result = add_label(service, label_id, result['id'])

        if 'SENT' in result['labelIds']:
            content = 'Email sent to {}'.format(recipient)
            if label_result:  # Enters this block if the label couldn't be added
                              # or if there was no label
                content += ' without label.'
            else:
                content += '.'
        else:
            content = 'Could not send email to {}. Please try again.'.format(recipient)

        client.send_message(dict(
            type = 'private',
            to = original_sender,
            sender = self.bot_email,
            content = content
        ))

    def parse_input(self, user_input):
        # Input is of the following format: (--label flag is optional)
        # @gmail <recipient_email> "<subject>" "<body>" --label <label>
        regex = self.parse_regex
        if '--label' in user_input:
            regex = self.parse_regex_with_label

        match = re.match(regex, user_input)
        if match:
            return match.groups() + (None,)
        else:
            return False

def create_message(body, subject, recipient):
    message = MIMEText(body)
    message['to'] = recipient
    message['from'] = 'me'
    message['subject'] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes())
    return {'raw': raw.decode()}


def send_message(service, email):
    try:
        result = service.users().messages().send(userId='me', body=email).execute()
        return result
    except errors.HttpError:
        logging.exception('An error occured while sending the email.')
        return False


def create_label(service, label):
    # Creates the label if it doesn't already exist
    label_object = {'name': label}
    labels = service.users().labels().list(userId='me').execute()
    labels = labels['labels']

    if label not in [l['name'] for l in labels]:
        service.users().labels().create(userId='me',
                                        body=label_object).execute()

def get_label_id(service, label_name):
    labels = service.users().labels().list(userId='me').execute()

    for l in labels['labels']:
        if label_name == l['name']:
            return l['id']

def add_label(service, label_Id, msg_Id):
    try:
        label_object = {'addLabelIds': [label_Id]}
        service.users().messages().modify(userId='me', id=msg_Id,
                                          body=label_object).execute()
        return True
    except errors.HttpError:
        logging.exception('Encountered an error while adding the label to the message')
        return False

def get_service():
    try:
        credential_path = os.path.join(os.path.expanduser('~'),
                                       '.google-credentials.json')

        store = Storage(credential_path)
        credentials = store.get()
        creds = credentials.authorize(httplib2.Http())

    except AttributeError:
        logging.error("Couldn't find authorized credentials for a Google account."
                      " Please, run the google.py script from this directory first.")

    try:
        service = discovery.build('gmail', 'v1', http=creds)
    except ImportError:
        logging.exception('Error with imports within the googleapiclient')
    return service

handler_class = GmailHandler
