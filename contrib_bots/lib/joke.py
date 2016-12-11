import requests, ast
# See readme.md for instructions on running this code.
class JokeHandler(object):
    '''
    This plugin facilitates creating follow-up tasks when
    you are using Zulip to conduct a virtual meeting.  It
    looks for messages starting with '@lol' or "@joke".

    In this example, we write follow up items to a special
    Zulip stream called "followup," but this code could
    be adapted to write follow up items to some kind of
    external issue tracker as well.
    '''

    def usage(self):
        return '''
            This plugin will allow users to enjoy some jokes.
            Users should preface messages with "@lol" or "@joke".

            Before running this, make sure to create a stream
            called "followup" that your API user can send to.
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        if message['display_recipient'] == 'links':
            return False
        is_link = (original_content.startswith('@lol') or
                  original_content.startswith('@joke'))

        return is_link

    def handle_message(self, message, client, state_handler):
        joke = list(ast.literal_eval(requests.get('http://tambal.azurewebsites.net/joke/random').text).values())[0]
        original_sender = message['sender_email']

        client.send_message(dict(
            type='private',
            to=original_sender,
            content=joke,
        ))

handler_class = JokeHandler
