from argparse import ArgumentParser
from typing import Any

from zerver.lib.actions import get_markdown_messages
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Get a list of messages in markdown format."""

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
