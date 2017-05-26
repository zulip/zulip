# See readme.md for instructions on running this code.


class HelloWorldHandler(object):
    def usage(self):
        return '''
        This is a boilerplate bot that responds to a user query with
        "beep boop", which is robot for "Hello World".

        This bot can be used as a template for other, more
        sophisticated, bots.
        '''

    def handle_message(self, message, client, state_handler):
        content = 'beep boop'
        client.send_reply(message, content)

handler_class = HelloWorldHandler
