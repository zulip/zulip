# Allows a mentor to ssh into a Digital Ocean droplet. This is designed to be
# executed on the target machine.
#
# This script takes the username of the mentor as an argument:
#
# $ python3 add_mentor.py <mentor's username>
#
# Alternatively you can pass in --remove to remove their ssh key from the
# machine:
#
# $ python3 add_mentor.py --remove <mentor's username>

import os
import sys
from argparse import ArgumentParser
from typing import List
import socket
import re

import requests

parser = ArgumentParser(description='Give a mentor ssh access to this machine.')
parser.add_argument('username', help='Github username of the mentor.')
parser.add_argument('--remove', help='Remove his/her key from the machine.',
                    action='store_true', default=False)

# Wrap keys with line comments for easier key removal.
append_key = """\
#<{username}>{{{{
{key}
#}}}}<{username}>
"""

def get_mentor_keys(username: str) -> List[str]:
    url = 'https://api.github.com/users/{}/keys'.format(username)

    r = requests.get(url)
    if r.status_code != 200:
        print('Cannot connect to Github...')
        sys.exit(1)

    keys = r.json()
    if not keys:
        print('Mentor "{}" has no public key.'.format(username))
        sys.exit(1)

    return [key['key'] for key in keys]


if __name__ == '__main__':
    args = parser.parse_args()
    authorized_keys = os.path.expanduser('~/.ssh/authorized_keys')

    if args.remove:
        remove_re = re.compile('#<{0}>{{{{.+}}}}<{0}>(\n)?'.format(args.username),
                               re.DOTALL | re.MULTILINE)

        with open(authorized_keys, 'r+') as f:
            old_content = f.read()
            new_content = re.sub(remove_re, '', old_content)
            f.seek(0)
            f.write(new_content)
            f.truncate()

        print('Successfully removed {}\' SSH key!'.format(args.username))

    else:
        keys = get_mentor_keys(args.username)
        with open(authorized_keys, 'a') as f:
            for key in keys:
                f.write(append_key.format(username=args.username, key=key))

        print('Successfully added {}\'s SSH key!'.format(args.username))
        print('Can you let your mentor know that they can connect to this machine with:\n')
        print('    $ ssh zulipdev@{}\n'.format(socket.gethostname()))
