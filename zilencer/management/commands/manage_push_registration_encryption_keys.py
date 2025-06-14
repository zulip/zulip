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
    help = """Add or remove a key pair to push_registration_encryption_keys map."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--add",
            action="store_true",
            help="",
        )
        parser.add_argument(
            "--remove-key",
            type=str,
            help="",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if settings.DEVELOPMENT:
            SECRETS_FILENAME = "zproject/dev-secrets.conf"
        else:
            SECRETS_FILENAME = "/etc/zulip/zulip-secrets.conf"

        config = configparser.ConfigParser()
        config.read(SECRETS_FILENAME)
        push_registration_encryption_keys: dict[str, str] = json.loads(
            config.get("secrets", "push_registration_encryption_keys", fallback="{}")
        )

        if options["add"]:
            # Generate a new key-pair and store.
            private_key = PrivateKey.generate()
            private_key_str = Base64Encoder.encode(bytes(private_key)).decode("utf-8")
            public_key_str = Base64Encoder.encode(bytes(private_key.public_key)).decode("utf-8")
            push_registration_encryption_keys[public_key_str] = private_key_str

        if options["remove_key"] is not None:
            # Remove the key-pair for the given public key.
            remove_key = options["remove_key"]
            if remove_key not in push_registration_encryption_keys:
                return

            del push_registration_encryption_keys[remove_key]

        config.set(
            "secrets",
            "push_registration_encryption_keys",
            json.dumps(push_registration_encryption_keys),
        )
        with open(SECRETS_FILENAME, "w") as secrets_file:
            config.write(secrets_file)
