#!/usr/bin/python

from django.core.management.base import BaseCommand

from zerver.lib.utils import generate_random_token
from zerver.models import Stream

class Command(BaseCommand):
    help = """Set a token for all streams that don't have one."""

    def handle(self, **options):
        streams_needing_tokens = Stream.objects.filter(email_token=None)
        for stream in streams_needing_tokens:
            stream.email_token = generate_random_token(32)
            stream.save()
