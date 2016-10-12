# See readme.md for instructions on running this code.

class FollowupHandler(object):
    '''
    This plugin facilitates creating follow-up tasks when
    you are using Zulip to conduct a virtual meeting.  It
    looks for messages starting with '@followup'.

    In this example, we write follow up items to a special
    Zulip stream called "followup," but this code could
    be adapted to write follow up items to some kind of
    external issue tracker as well.
    '''

    def usage(self):
        return '''
            This plugin will allow users to flag messages
            as being follow-up items.  Users should preface
            messages with "@followup".

            Before running this, make sure to create a stream
            called "followup" that your API user can send to.
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        if message['display_recipient'] == 'followup':
            return False
        is_follow_up = (original_content.startswith('@followup') or
                        original_content.startswith('@follow-up'))

        return is_follow_up

    def handle_message(self, message, client):
        original_content = message['content']
        original_sender = message['sender_email']
        new_content = original_content.replace('@followup',
                                               'from %s:' % (original_sender,))

        client.send_message(dict(
            type='stream',
            to='followup',
            subject=message['sender_email'],
            content=new_content,
        ))

handler_class = FollowupHandler
