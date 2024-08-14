from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.realm_settings import do_set_realm_authentication_methods
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Enable or disable an authentication backend for a realm"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--enable",
            type=str,
            help="Name of the authentication backend to enable",
        )
        group.add_argument(
            "--disable",
            type=str,
            help="Name of the authentication backend to disable",
        )
        group.add_argument(
            "--show",
            action="store_true",
            help="Show current authentication backends for the realm",
        )

    @override
    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # Should be ensured by parser

        auth_methods = realm.authentication_methods_dict()

        if options["show"]:
            print("Current authentication backends for the realm:")
            print_auth_methods_dict(auth_methods)
            return

        if options["enable"]:
            backend_name = options["enable"]
            check_backend_name_valid(backend_name, auth_methods)

            auth_methods[backend_name] = True
            print(f"Enabling {backend_name} backend for realm {realm.name}")
        elif options["disable"]:
            backend_name = options["disable"]
            check_backend_name_valid(backend_name, auth_methods)

            auth_methods[backend_name] = False
            print(f"Disabling {backend_name} backend for realm {realm.name}")

        do_set_realm_authentication_methods(realm, auth_methods, acting_user=None)

        print("Updated authentication backends for the realm:")
        print_auth_methods_dict(realm.authentication_methods_dict())
        print("Done!")


def check_backend_name_valid(backend_name: str, auth_methods_dict: dict[str, bool]) -> None:
    if backend_name not in auth_methods_dict:
        raise CommandError(
            f"Backend {backend_name} is not a valid authentication backend. Valid backends: {list(auth_methods_dict.keys())}"
        )


def print_auth_methods_dict(auth_methods: dict[str, bool]) -> None:
    enabled_backends = [backend for backend, enabled in auth_methods.items() if enabled]
    disabled_backends = [backend for backend, enabled in auth_methods.items() if not enabled]

    if enabled_backends:
        print("Enabled backends:")
        for backend in enabled_backends:
            print(f"  {backend}")

    if disabled_backends:
        print("Disabled backends:")
        for backend in disabled_backends:
            print(f"  {backend}")
