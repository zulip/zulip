from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.lib.embedded_docs import import_markdown_directory
from zerver.lib.management import ZulipBaseCommand
from zerver.models import EmbeddedDocArticle

class Command(ZulipBaseCommand):
    help = """Load all of the templates in a markdown directory into the
    database. Useful for setting up Postgres-based search"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('template_directory',
                            metavar='<template_directory>',
                            type=str,
                            help='subdirectory of `templates` to load')

    def handle(self, *args: Any, **options: str) -> None:
        import_markdown_directory(options['template_directory'])
