#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

import argparse
import os
import sys
import pip

def provision_bot(path_to_bot, force):
    # type: (str, bool) -> None
    req_path = os.path.join(path_to_bot, 'requirements.txt')
    install_path = os.path.join(path_to_bot, 'bot_dependencies')
    if os.path.isfile(req_path):
        print('Installing dependencies...')
        if not os.path.isdir(install_path):
            os.makedirs(install_path)
        # pip install -r $BASEDIR/requirements.txt -t $BASEDIR/bot_dependencies --quiet
        rcode = pip.main(['install', '-r', req_path, '-t', install_path, '--quiet'])
        if not rcode == 0:
            print('Error. Check output of `pip install` above for details.')
            if not force:
                print('Use --force to try running anyway.')
                sys.exit(rcode)  # Use pip's exit code
        else:
            print('Installed.')
        sys.path.insert(0, install_path)

def dir_join(dir1, dir2):
    # type: (str, str) -> str
    return os.path.abspath(os.path.join(dir1, dir2))

def run():
    # type: () -> None
    usage = '''
        Installs dependencies of bots in api/bots directory. Add a
        reuirements.txt file in a bot's folder before provisioning.

        To provision all bots, use:
        ./provision.py

        To provision specific bots, use:
        ./provision.py [names of bots]
        Example: ./provision.py helloworld xkcd wikipedia

        '''

    bots_dir = dir_join(os.path.dirname(os.path.abspath(__file__)), '../bots')
    available_bots = [b for b in os.listdir(bots_dir) if os.path.isdir(dir_join(bots_dir, b))]

    parser = argparse.ArgumentParser(usage=usage)
    parser.add_argument('bots_to_provision',
                        metavar='bots',
                        nargs='*',
                        default=available_bots,
                        help='specific bots to provision (default is all)')
    parser.add_argument('--force',
                        default=False,
                        action="store_true",
                        help='Continue installation despite pip errors.')
    options = parser.parse_args()
    for bot in options.bots_to_provision:
        provision_bot(os.path.join(dir_join(bots_dir, bot)), options.force)

if __name__ == '__main__':
    run()
