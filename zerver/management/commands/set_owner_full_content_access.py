from argparse import ArgumentParser
from typing import Any

from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = (
        "Set the owner_full_content_access flag for a realm. The flag determines "
        "whether the organization's owner will have the ability to access private "
        "content in the organization in the Zulip UI."
    )

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        toggle_group = parser.add_mutually_exclusive_group(required=True)
        toggle_group.add_argument(
            "--enable",
            action="store_true",
            help="Set owner_full_content_access to True.",
        )
        toggle_group.add_argument(
            "--disable",
            action="store_false",
            help="Set owner_full_content_access to False.",
        )
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        owner_full_content_access = options["enable"]
        realm.owner_full_content_access = owner_full_content_access
        realm.save(update_fields=["owner_full_content_access"])

        print(
            f"owner_full_content_access set to {owner_full_content_access} for realm {realm.name} (id={realm.id})."
        )
