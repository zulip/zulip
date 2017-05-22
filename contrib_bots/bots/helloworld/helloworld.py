# See readme.md for instructions on running this code.

class HelloWorldHandler(object):
    def usage(self):
        return '''
        This is a boilerplate bot that writes to the stream "Hello World!"

        (Or just "beep boop")

        This bot (along with Help) can be used as a template for other,
        more sophisticated bots.
        '''

    def triage_message(self, message, client):
        # return True if we think the message may be of interest
        original_content = message['content']

        if message['type'] != 'stream':
            return True

        if original_content.lower().strip() != 'help':
            return False

        return True

    def handle_message(self, message, client, state_handler):
        help_content = '''
            beep boop
            '''.strip()

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=help_content,
        ))

handler_class = HelloWorldHandler
