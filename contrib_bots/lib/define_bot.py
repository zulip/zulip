# See readme.md for instructions on running this code.
import logging
import json
import requests
import html2text

class DefineHandler(object):
    '''
    This plugin define a word that the user inputs. It
    looks for messages starting with '@define'.
    '''

    DEFINITION_API_URL = 'https://owlbot.info/api/v1/dictionary/{}?format=json'
    REQUEST_ERROR_MESSAGE = 'Definition not available.'
    EMPTY_WORD_REQUEST_ERROR_MESSAGE = 'Please enter a word to define.'
    PHRASE_ERROR_MESSAGE = 'Definitions for phrases are not available.'

    def usage(DefineHandler):
        return '''
            This plugin will allow users to define a word. Users should preface
            messages with "@define".
            '''

    def triage_message(DefineHandler, message, client):
        # return True if we want to (possibly) response to this message
        original_content = message['content']
        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting follow
        # ups for own follow ups!
        is_define = original_content.startswith('@define')

        return is_define

    def _handle_definition(DefineHandler, original_content):
        # Remove '@define' from the message and extract the rest of the message, the
        # word to define.
        split_content = original_content.split(' ')

        # If there are more than one word (a phrase)
        if len(split_content) > 2:
            return DefineHandler.PHRASE_ERROR_MESSAGE

        to_define = split_content[1].strip()
        to_define_lower = to_define.lower()

        # No word was entered.
        if not to_define_lower:
            return DefineHandler.EMPTY_WORD_REQUEST_ERROR_MESSAGE
        else:
            response = '**{}**:\n'.format(to_define)

            try:
                # Use OwlBot API to fetch definition.
                api_result = requests.get(DefineHandler.DEFINITION_API_URL.format(to_define_lower))
                # Convert API result from string to JSON format.
                definitions = api_result.json()

                # Could not fetch definitions for the given word.
                if not definitions:
                    response += DefineHandler.REQUEST_ERROR_MESSAGE
                else: # Definitions available.
                    # Show definitions line by line.
                    for d in definitions:
                        example = d['example'] if d['example'] else '*No example available.*'
                        response += '\n' + '* (**{}**) {}\n&nbsp;&nbsp;{}'.format(d['type'], d['defenition'], html2text.html2text(example))

            except Exception as e:
                response += DefineHandler.REQUEST_ERROR_MESSAGE
                logging.exception(e)

            return response

    def handle_message(DefineHandler, message, client, state_handler):
        original_content = message['content']

        response = DefineHandler._handle_definition(original_content)

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['sender_email'],
            content=response
        ))

handler_class = DefineHandler
