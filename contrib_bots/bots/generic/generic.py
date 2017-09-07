class BotCommandRegistry(object):
    def __init__(self, about_text, just_mentioned=-1):
        # Note the values are empty, since they are handled elsewhere
        self._commands = \
            {'help'    : ('','output this help text'),
             'commands': ('','briefly list these supported commands'),
             'about'   : ('','tells you what this bot is intended to do'),
            }
        self._integer_command = None
        self._about_text = about_text
        self._just_mentioned = just_mentioned
      
    def usage(self):
        return '''
            This generic zulip bot is intended to be a simple extensible design
            which relies upon users simply adding in extra elements into a dict.
            '''

    def add_command(self, cmd, text_or_function, explanation):
        if cmd not in self._commands.keys():
            self._commands[cmd] = (text_or_function, explanation)
        else:
            print("WARNING: %s command already exists, so haven't added it." % cmd)

    def add_int_handler(self, text_or_function, explanation):
        self._integer_command = (text_or_function, explanation)
        self._commands["<id>"] = ('', explanation)

    def handle_message(self, message, client, state_handler):
        msg = self._about_text

        content = message['content']
        if len(content) == 0:
            if self._just_mentioned != -1:
                if not isinstance(self._just_mentioned, str):
                    msg = self._just_mentioned()
                else:
                    msg = self._just_mentioned
                content = "about" # Use pass-through below
            else:
                content = "help" # Default handling of just mentioning bot
            
        command = content.split()[0].strip()
        args = content.split()[1:]

        if self._integer_command is not None and command.isdigit():
            msg = self._integer_command[0](command,args)
        elif command == 'about':
            pass # defaults to about text
        elif command == 'help':
            for key, value in self._commands.items(): msg += "\n* " + key + " : " + value[1]
        elif command == 'commands':
            msg = "Commands: " + (" ".join(self._commands.keys()))
        elif command == '<id>' and self._integer_command is not None:
            msg = "This command is not intended to be used explicitly, but is a placeholder for a number; please check the help."
        elif command in self._commands.keys():
            if not isinstance(self._commands[command][0], str): 
                msg = self._commands[command][0](args)
            else:
                msg = self._commands[command][0]
        else:
            msg = "Sorry, I don't understand that command. Please try one of the following.\n"
            msg += "Commands: " + (" ".join(self._commands.keys()))

        client.send_reply(message, msg)


import time
class DemoHandler(BotCommandRegistry):
    def __init__(self):
        BotCommandRegistry.__init__(self, \
          'A Generic zulip bot that you can extend using a dictionary',
          'Try typing "commands" for the list of commands.'
#          -1 # Default => just mentioning leads to help text
          )

        # This will do nothing (help command already exists)
        self.add_command('help','help','help')

        # Examples of text, function, and function which uses arguments
        self.add_command('dance','/me dances','makes me dance!')
        self.add_command('go',lambda x : ("I live here!" if " ".join(x)=="away" else "where?"),"where should I go?")
        self.add_command('time',lambda x : time.time(),'time since the epoch')
p

from random import randint

import logging
import requests

XKCD_TEMPLATE_URL = 'https://xkcd.com/%s/info.0.json'
LATEST_XKCD_URL = 'https://xkcd.com/info.0.json'

class XkcdHandler(BotCommandRegistry):
    '''
    This plugin provides several commands that can be used for fetch a comic
    strip from https://xkcd.com. The bot looks for messages starting with
    "@mention-bot" and responds with a message with the comic based on provided
    commands.
    '''

    def __init__(self):
        BotCommandRegistry.__init__(self, \
          'This bot provides several commands for fetching a comic strip from https://xkcd.com', # about text
          'Try typing "commands" for the list of commands.'             # if just mentioned
          )

        self.add_command('latest', lambda x:get_xkcd_bot_response('latest'),\
                         'fetch the latest comic strip from xkcd')
        self.add_command('random', lambda x:get_xkcd_bot_response('random'),\
                         'fetch a random comic strip from xkcd')
        self.add_int_handler(lambda x,y:get_xkcd_bot_response(x),\
                         'fetch a comic strip based on the supplied id')

    def usage(self):
        return '''
            This plugin allows users to fetch a comic strip provided by
            https://xkcd.com. Users should preface the command with "@mention-bot".

            There are several commands to use this bot:
            - @mention-bot help -> To show all commands the bot supports.
            - @mention-bot latest -> To fetch the latest comic strip from xkcd.
            - @mention-bot random -> To fetch a random comic strip from xkcd.
            - @mention-bot <comic_id> -> To fetch a comic strip based on
            `<comic_id>`, e.g `@mention-bot 1234`.
            '''

class XkcdBotCommand(object):
    LATEST = 0
    RANDOM = 1
    COMIC_ID = 2

class XkcdNotFoundError(Exception):
    pass

class XkcdServerError(Exception):
    pass

def get_xkcd_bot_response(command): # v2
    try:
        if command == 'latest':
            fetched = fetch_xkcd_query(XkcdBotCommand.LATEST)
        elif command == 'random':
            fetched = fetch_xkcd_query(XkcdBotCommand.RANDOM)
        elif command.isdigit():
            fetched = fetch_xkcd_query(XkcdBotCommand.COMIC_ID, command)
        else:
            logging.exception('Unsupported command')
            return 'Unsupported command'
    except (requests.exceptions.ConnectionError, XkcdServerError):
        logging.exception('Connection error occurred when trying to connect to xkcd server')
        return 'Sorry, I cannot process your request right now, please try again later!'
    except XkcdNotFoundError:
        logging.exception('XKCD server responded 404 when trying to fetch comic with id %s'
                          % (command))
        return 'Sorry, there is likely no xkcd comic strip with id: #%s' % (command,)
    else:
        return ("#%s: **%s**\n[%s](%s)" % (fetched['num'],
                                           fetched['title'],
                                           fetched['alt'],
                                           fetched['img']))

def fetch_xkcd_query(mode, comic_id=None):
    try:
        if mode == XkcdBotCommand.LATEST:  # Fetch the latest comic strip.
            url = LATEST_XKCD_URL

        elif mode == XkcdBotCommand.RANDOM:  # Fetch a random comic strip.
            latest = requests.get(LATEST_XKCD_URL)

            if latest.status_code != 200:
                raise XkcdServerError()

            latest_id = latest.json()['num']
            random_id = randint(1, latest_id)
            url = XKCD_TEMPLATE_URL % (str(random_id))

        elif mode == XkcdBotCommand.COMIC_ID:  # Fetch specific comic strip by id number.
            if comic_id is None:
                raise Exception('Missing comic_id argument')
            url = XKCD_TEMPLATE_URL % (comic_id)

        fetched = requests.get(url)

        if fetched.status_code == 404:
            raise XkcdNotFoundError()
        elif fetched.status_code != 200:
            raise XkcdServerError()

        xkcd_json = fetched.json()
    except requests.exceptions.ConnectionError as e:
        logging.warning(e)
        raise

    return xkcd_json

handler_class = XkcdHandler
#handler_class = DemoHandler
