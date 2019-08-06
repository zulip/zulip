from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from zproject.backends import query_ldap

class Command(BaseCommand):
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('email', metavar='<email>', type=str,
                            help="email of user to query")

    def handle(self, *args: Any, **options: str) -> None:
        email = options['email']
        values = query_ldap(email)
        for value in values:
            print(value)
