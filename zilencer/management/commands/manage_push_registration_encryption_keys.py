import configparser
import json
from argparse import ArgumentParser
from typing import Any

from django.conf import settings
from nacl.encoding import Base64Encoder
from nacl.public import PrivateKey
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """
Add or remove a key pair from the `push_registration_encryption_keys` map.

Usage:
./manage.py manage_push_registration_encryption_keys --add
./manage.py manage_push_registration_encryption_keys --remove-key <public-key>
"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--add",
            action="store_true",
            help="Add a new key pair to the `push_registration_encryption_keys` map.",
        )
        parser.add_argument(
            "--remove-key",
            type=str,
            metavar="PUBLIC_KEY",
            help="Remove the key pair associated with the given public key from the `push_registration_encryption_keys` map.",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not options["add"] and options["remove_key"] is None:
            print("Error: Please provide either --add or --remove-key <public-key>.")
            return

        if settings.DEVELOPMENT:
            SECRETS_FILENAME = "zproject/dev-secrets.conf"
        else:
            SECRETS_FILENAME = "/etc/zulip/zulip-secrets.conf"

        config = configparser.ConfigParser()
        config.read(SECRETS_FILENAME)
        push_registration_encryption_keys: dict[str, str] = json.loads(
            config.get("secrets", "push_registration_encryption_keys", fallback="{}")
        )

        added_key_pair: tuple[str, str] | None = None
        if options["add"]:
            # Generate a new key-pair and store.
            private_key = PrivateKey.generate()
            private_key_str = Base64Encoder.encode(bytes(private_key)).decode("utf-8")
            public_key_str = Base64Encoder.encode(bytes(private_key.public_key)).decode("utf-8")
            push_registration_encryption_keys[public_key_str] = private_key_str
            added_key_pair = (public_key_str, private_key_str)

        if options["remove_key"] is not None:
            # Remove the key-pair for the given public key.
            remove_key = options["remove_key"]
            if remove_key not in push_registration_encryption_keys:
                print("Error: No key pair found for the given public key.")
                return

            del push_registration_encryption_keys[remove_key]

        config.set(
            "secrets",
            "push_registration_encryption_keys",
            json.dumps(push_registration_encryption_keys),
        )
        with open(SECRETS_FILENAME, "w") as secrets_file:
            config.write(secrets_file)

        if added_key_pair is not None:
            public_key_str, private_key_str = added_key_pair
            print("Added a new key pair:")
            print(f"- Public key:  {public_key_str}")
            print(f"- Private key: {private_key_str}")

        if options["remove_key"] is not None:
            print(f"Removed the key pair for public key: {options['remove_key']}")
