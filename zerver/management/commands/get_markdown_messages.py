from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import get_markdown_messages
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Get a list of messages in markdown format.

It helps to export an specific list of messages in another stream/topic
by a markdown text.
It can be useful to check the visibility of the messages before doing a copy of them.

Usage examples:

./manage.py get_markdown_messages -e aaron@zulip.com -m 80,81 > file.txt
./manage.py get_markdown_messages --email aaron@zulip.com --messages 80,81 > file.txt

Result:
2020-02-15 15:39:35 @**Polonius**:

 >Such a claim might seem unexpected but fell in line with ...

2020-02-16 16:16:03 @**Prospero from The Tempest**:

 In our research we concentrate our efforts on confirming ...
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser)
        parser.add_argument('-e', '--email', type=str, required=True,
                            help='user email address')
        parser.add_argument(
            '-m', '--messages',
            dest='messages',
            type=str,
            required=True,
            help='A comma-separated list of message ids.')

    def handle(self, *args: Any, **options: str) -> None:
        email = options['email']
        messages = options['messages']
        message_ids = set([int(msg.strip()) for msg in messages.split(",")])

        realm = self.get_realm(options)
        user_profile = self.get_user(email, realm)

        markdown = get_markdown_messages(user_profile, list(message_ids))
        print(markdown)
