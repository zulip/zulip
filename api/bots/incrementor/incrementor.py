# See readme.md for instructions on running this code.


class IncrementorHandler(object):

    def usage(self):
        return '''
        This is a boilerplate bot that makes use of the
        update_message function. For the first @-mention, it initially
        replies with one message containing a `1`. Every time the bot
        is @-mentioned, this number will be incremented in the same message.
        '''

    def handle_message(self, message, bot_handler, state_handler):
        with state_handler.state({'number': 0, 'message_id': None}) as state:
            state['number'] += 1
            if state['message_id'] is None:
                result = bot_handler.send_reply(message, str(state['number']))
                state['message_id'] = result['id']
            else:
                bot_handler.update_message(dict(
                    message_id = state['message_id'],
                    content = str(state['number'])
                ))


handler_class = IncrementorHandler
