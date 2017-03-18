#!/usr/bin/env python
from __future__ import print_function

import importlib
import logging
import optparse
import os
import sys

our_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, our_dir)

from bot_lib import run_message_handler_for_bot

def get_lib_module(bots_fn):
    bots_fn = os.path.abspath(bots_fn)
    if not os.path.dirname(bots_fn).startswith(os.path.join(our_dir, 'bots')):
        print('Sorry, we will only import code from contrib_bots/bots.')
        sys.exit(1)

    if not bots_fn.endswith('.py'):
        print('Please use a .py extension for library files.')
        sys.exit(1)
    base_bots_fn = os.path.basename(os.path.splitext(bots_fn)[0])
    sys.path.append('bots/{}'.format(base_bots_fn))
    module_name = base_bots_fn
    module = importlib.import_module(module_name)
    return module

def run():
    usage = '''
        ./run.py <lib file>
        Example: ./run.py lib/followup.py
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

    lib_module = get_lib_module(bots_fn=args[0])

    if not options.quiet:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    run_message_handler_for_bot(
        lib_module=lib_module,
        config_file=options.config_file,
        quiet=options.quiet
    )

if __name__ == '__main__':
    run()
