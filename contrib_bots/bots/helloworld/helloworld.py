# See readme.md for instructions on running this code.


class HelloWorldHandler(object):
    def usage(self):
        return '''
        This is a boilerplate bot that writes to the stream "Hello World!"

        (Or just "beep boop")

        This bot (along with Help) can be used as a template for other,
        more sophisticated bots.
        '''

    def handle_message(self, message, client, state_handler):
        content = 'beep boop'

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=content,
        ))

handler_class = HelloWorldHandler
