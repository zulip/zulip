class ManagerHandler(object):
    '''
    This plugin facilitates managing bots when
    you are using Zulip.

    In this example, we write commands to a private chat with the
    gamebot.
    '''
    wiki = False
    conv = False
    dic = False
    enter = False
    username = ''

    def send_message(self, message_to_send, sender):
        self.client.send_message(dict(
            type='private',
            to=sender,
            content=message_to_send,
        ))

    def botmanager(command):
        """
        Manages the bot calling process
        """
        if command.message['content'] == 'converter' or command.conv:
            command.conv = True
            command.enter = True
            command.send_message('@convert ' + command.message['content'],
                'converter-bot@zulip.com')
        elif command.message['content'] == 'dictionary' or command.dic:
            command.dic = True
            command.enter = True
            command.send_message('@define ' + command.message['content'],
                'define-bot@zulip.com')
        elif command.message['content'] == 'wikipedia' or command.wiki:
            command.wiki = True
            command.enter = True
            command.send_message('@wiki ' + command.message['content'],
                'wiki-bot@zulip.com')

    def controller(command):
        """
        Controls the command input
        """
        command.username = command.message['sender_email']
        showbots = 'List of bots\n \
        converter -> Making conversions between units\n \
        dictionary -> Defining specific one word definitions\n \
        wikipedia -> Shows the wikipedia article'
        bots = ['converter', 'dictionary', 'wikipedia', 'exit']
        if (command.message['content'] in bots) or command.enter == True:
            if command.message['content'] == 'converter':
                command.send_message(
                    "This plugin allows users to make conversions between \
                    various units, e.g. Celsius to Fahrenheit, or \
                    kilobytes to gigabytes. It looks for messages of the \
                    format '<number> <unit_from> <unit_to>' The message \
                    'help' posts a short description of how to use the \
                    plugin, along with a list of all supported units.",
                        command.message['sender_email'])
            elif command.message['content'] == 'dictionary':
                command.send_message(
                    "This plugin define a word that the user inputs.",
                    command.message['sender_email'])
            elif command.message['content'] == 'wikipedia':
                command.send_message(
                    "This plugin facilitates searching Wikipedia for a \
                    specific key term and returns the top article from the \
                    search.", command.message['sender_email'])
            if command.message['content'] != 'exit':
                msg = ''
                command.botmanager()
            else:
                msg = 'bot exited'
                command.wiki = False
                command.dic = False
                command.enter = False
                command.conv = False
        elif command.message['content'] == 'list bots':
            msg = showbots
        elif command.message['content'] == 'list commands':
            msg = 'Hello These are the list of commands I can run\n \
            list bots - Shows the available bots.\n \
            Entering the name of the bot will start the bot for you\n \
            Enter `exit` to exit the current bot'
        else:
            msg = 'Invalid command try `list commands` for listing \
            the valid commands'
        return msg

    def usage(self):
        return '''
            This plugin will allow users to use bots
            using simple messages. Users should send a private message to
            the manager bot.

            Make sure to send the message to manager bot in private
            '''

    def triage_message(self, message, client):
        if message['type'] == 'private':
            return client.full_name != message['sender_full_name']
        is_manager = (message['type'] == 'private')
        return is_manager

    def handle_message(self, message, client, state_handler):
        self.client = client
        self.message = message
        bot_email = ['define-bot@zulip.com', 'converter-bot@zulip.com',
            'wiki-bot@zulip.com']

        if message['sender_email'] in bot_email:
            client.send_message(dict(
                type='private',
                to=self.username,
                content=message['content'],
            ))
        else:
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=self.controller(),
            ))

handler_class = ManagerHandler
