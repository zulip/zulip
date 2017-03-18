from random import randint

import logging
import requests

XKCD_TEMPLATE_URL = 'https://xkcd.com/%s/info.0.json'
LATEST_XKCD_URL = 'https://xkcd.com/info.0.json'

class XkcdHandler(object):
    '''
    This plugin provides several commands that can be used for fetch a comic
    strip from https://xkcd.com. The bot looks for messages starting with
    "@mention-bot" and responds with a message with the comic based on provided
    commands.
    '''

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

    def handle_message(self, message, client, state_handler):
        xkcd_bot_response = get_xkcd_bot_response(message)

        client.send_message(dict(
            type='stream',
            to=message['display_recipient'],
            subject=message['subject'],
            content=xkcd_bot_response,
        ))

class XkcdBotCommand(object):
    LATEST = 0
    RANDOM = 1
    COMIC_ID = 2

class XkcdNotFoundError(Exception):
    pass

class XkcdServerError(Exception):
    pass

def get_xkcd_bot_response(message):
    original_content = message['content'].strip()
    command = original_content.strip()

    commands_help = ("%s"
                     "\n* `@xkcd help` to show this help message."
                     "\n* `@xkcd latest` to fetch the latest comic strip from xkcd."
                     "\n* `@xkcd random` to fetch a random comic strip from xkcd."
                     "\n* `@xkcd <comic id>` to fetch a comic strip based on `<comic id>` "
                     "e.g `@xkcd 1234`.")

    try:
        if command == 'help':
            return commands_help % ('xkcd bot supports these commands:')
        elif command == 'latest':
            fetched = fetch_xkcd_query(XkcdBotCommand.LATEST)
        elif command == 'random':
            fetched = fetch_xkcd_query(XkcdBotCommand.RANDOM)
        elif command.isdigit():
            fetched = fetch_xkcd_query(XkcdBotCommand.COMIC_ID, command)
        else:
            return commands_help % ('xkcd bot only supports these commands:')
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
