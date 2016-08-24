from __future__ import print_function

import importlib
import logging
import optparse
import os
import sys

our_dir = os.path.dirname(os.path.abspath(__file__))

# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '../api/zulip')):
    sys.path.append('../api')

from zulip import Client

class RestrictedClient(object):
    def __init__(self, client):
        # Only expose a subset of our Client's functionality
        self.send_message = client.send_message

def get_lib_module(lib_fn):
    lib_fn = os.path.abspath(lib_fn)
    if os.path.dirname(lib_fn) != os.path.join(our_dir, 'lib'):
        print('Sorry, we will only import code from contrib_bots/lib.')
        sys.exit(1)

    if not lib_fn.endswith('.py'):
        print('Please use a .py extension for library files.')
        sys.exit(1)

    sys.path.append('lib')
    base_lib_fn = os.path.basename(os.path.splitext(lib_fn)[0])
    module_name = 'lib.' + base_lib_fn
    module = importlib.import_module(module_name)
    return module

def run_message_handler_for_bot(lib_module, quiet, config_file):
    # Make sure you set up your ~/.zuliprc
    client = Client(config_file=config_file)
    restricted_client = RestrictedClient(client)

    message_handler = lib_module.handler_class()

    if not quiet:
        print(message_handler.usage())

    def handle_message(message):
        logging.info('waiting for next message')
        if message_handler.triage_message(message=message):
            message_handler.handle_message(
                message=message,
                client=restricted_client)

    logging.info('starting message handling...')
    client.call_on_each_message(handle_message)

def run():
    usage = '''
        python run.py <lib file>

        Example: python run.py lib/followup.py

        (This program loads bot-related code from the
        library code and then runs a message loop,
        feeding messages to the library code to handle.)

        Please make sure you have a current ~/.zuliprc
        file with the credentials you want to use for
        this bot.

        See lib/readme.md for more context.
        '''

    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--quiet', '-q',
        action='store_true',
        help='Turn off logging output.')
    parser.add_option('--config-file',
        action='store',
        help='(alternate config file to ~/.zuliprc)')
    (options, args) = parser.parse_args()

    if len(args) == 0:
        print('You must specify a library!')
        sys.exit(1)

    lib_module = get_lib_module(lib_fn=args[0])

    if not options.quiet:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    run_message_handler_for_bot(
        lib_module=lib_module,
        config_file=options.config_file,
        quiet=options.quiet
    )

if __name__ == '__main__':
    run()
