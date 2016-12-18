# See readme.md for instructions on running this code.

class LinksHandler(object):
    '''
    This plugin facilitates creating a list of resources
    you want to save while using zulip. It looks for messages
    starting with "@link" or "@resource".

    In this example, we send resources to private messages.
    '''

    def usage(self):
        return '''
            This plugin will allow users to flag messages as
            being resources and store them in private messages
            with the bot.

            Users should preface with "@link" or "@resource".
            '''

    def triage_message(self, message):
        # return True if we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting resources.
        if message['display_recipient'] == 'links':
            return False
        is_link = (original_content.startswith('@link') or
                   original_content.startswith('@resource'))

        return is_link

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        if original_content.startswith('@link'):
            new_content = original_content.replace('@link',
                                                   'from %s:' % (original_sender,))
        else:
            new_content = original_content.replace('@resource',
                                                   'from %s:' % (original_sender,))
            
        client.send_message(dict(
            type='private',
            to=original_sender,
            content=new_content,
        ))

handler_class = LinksHandler
