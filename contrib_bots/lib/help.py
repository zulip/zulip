# See readme.md for instructions on running this code.

class HelpHandler(object):
    def usage(self):
        return '''
            This plugin will give info about Zulip to
            any user that types a message saying "help".

            This is example code; ideally, you would flesh
            this out for more useful help pertaining to
            your Zulip instance.
            '''

    def triage_message(self, message):
        # return True if we think the message may be of interest
        original_content = message['content']

        if message['type'] != 'stream':
            return True

        if original_content.lower().strip() != 'help':
            return False

        return True

    def handle_message(self, message, client):
        help_content = '''
            Info on Zulip can be found here:
            https://github.com/zulip/zulip
            '''.strip()

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=help_content,
        ))

handler_class = HelpHandler
