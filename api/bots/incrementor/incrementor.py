# See readme.md for instructions on running this code.


class IncrementorHandler(object):

    def __init__(self):
        self.number = 0
        self.message_id = None

    def usage(self):
        return '''
        This is a boilerplate bot that makes use of the
        update_message function. For the first @-mention, it initially
        replies with one message containing a `1`. Every time the bot
        is @-mentioned, this number will be incremented in the same message.
        '''

    def handle_message(self, message, client, state_handler):
        self.number += 1
        if self.message_id is None:
            result = client.send_reply(message, str(self.number))
            self.message_id = result['id']
        else:
            client.update_message(dict(
                message_id=self.message_id,
                content=str(self.number),
            ))


handler_class = IncrementorHandler
