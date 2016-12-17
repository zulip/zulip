# See readme.md for instructions on running this code.
import json
import requests

class DefineHandler(object):
    '''
    This plugin facilitates creating define tasks when
    you are using Zulip to conduct a virtual meeting.  It
    looks for messages starting with '@define'.

    In this example, we write define items to a special
    Zulip stream called "define", but this code could
    be adapted to write define items to some kind of
    external issue tracker as well.
    '''

    def usage(self):
        return '''
            This plugin will allow users to flag messages
            as being define items.  Users should preface
            messages with "@define".

            Before running this, make sure to create a stream
            called "define" that your API user can send to.
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        
        is_define = original_content.startswith('@define')

        return is_define

    def _handle_definition(self, original_content):
        error_message = 'Definition not available.'

        # Remove '@define' from the message and extract the rest of the message, the
        # word/phrase to define.
        split_content = original_content.split(' ')
        to_define = ' '.join(split_content[1:])

        # No word was entered.
        if not to_define:
            return 'Please enter a word/phrase to define.'
        else:
            response = '**%s**:\n' % (to_define)

            # Some error occured with requests.get()
            try:
                # Use OwlBot API to fetch definition.
                api_result = requests.get('https://owlbot.info/api/v1/dictionary/%s?format=json' % (to_define))
                # Convert API result from string to JSON format.
                definitions = json.loads(api_result.text)

                # Could not fetch definitions for the given word/phrase.
                if not definitions:
                    response += error_message
                else: # Definitions available.
                    # Show definitions line by line.
                    response += '\n'.join('({}) {}'.format(d['type'], d['defenition']) for d in definitions)
            except Exception as e:
                response += error_message
            
            return response

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']

        response = self._handle_definition(original_content)        

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['sender_email'],
            content=response
        ))

handler_class = DefineHandler
