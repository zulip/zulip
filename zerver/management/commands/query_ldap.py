from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand
from typing_extensions import override

from zproject.backends import query_ldap


class Command(BaseCommand):
    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("email", metavar="<email>", help="email of user to query")

    @override
    def handle(self, *args: Any, **options: str) -> None:
        email = options["email"]
        values = query_ldap(email)
        for value in values:
            print(value)
