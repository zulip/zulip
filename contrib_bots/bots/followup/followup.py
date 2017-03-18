# See readme.md for instructions on running this code.

class FollowupHandler(object):
    '''
    This plugin facilitates creating follow-up tasks when
    you are using Zulip to conduct a virtual meeting.  It
    looks for messages starting with '@mention-bot'.

    In this example, we write follow up items to a special
    Zulip stream called "followup," but this code could
    be adapted to write follow up items to some kind of
    external issue tracker as well.
    '''

    def usage(self):
        return '''
            This plugin will allow users to flag messages
            as being follow-up items.  Users should preface
            messages with "@mention-bot".

            Before running this, make sure to create a stream
            called "followup" that your API user can send to.
            '''

    def handle_message(self, message, client, state_handler):
        bot_response = self.get_bot_followup_response(message)
        client.send_message(dict(
            type='stream',
            to='followup',
            subject=message['sender_email'],
            content=bot_response,
        ))

    def get_bot_followup_response(self, message):
        original_content = message['content']
        original_sender = message['sender_email']
        temp_content = 'from %s:' % (original_sender,)
        new_content = temp_content + original_content

        return new_content

handler_class = FollowupHandler
