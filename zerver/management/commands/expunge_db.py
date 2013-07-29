from __future__ import absolute_import

from django.core.management.base import BaseCommand
from zerver.retention_policy     import get_UserMessages_to_expunge
from zerver.models               import Message

class Command(BaseCommand):
    help = ('Expunge old UserMessages and Messages from the database, '
            + 'according to the retention policy.')

    def handle(self, *args, **kwargs):
        get_UserMessages_to_expunge().delete()
        Message.remove_unreachable()
