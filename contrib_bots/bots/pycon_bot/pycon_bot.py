
class HelpHandler(object):
    def usage(self):
        return '''
            The bot will return the city that the next Pycon
            North America will be held in.              
            '''

    def triage_message(self, message, client):
        # return True if we think the message may be of interest
        original_content = message['content']

        if message['type'] != 'stream':
            return True

        if original_content.lower().strip() != 'help':
            return False

        return True

    def handle_message(self, message, client, state_handler):
        help_content = '''
            Next year Pycon will be in:
            Cleveland, OH
            '''.strip()

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=help_content,
        ))

handler_class = HelpHandler
