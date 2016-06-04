from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

from zerver.lib.actions import do_delete_old_unclaimed_attachments
from zerver.models import Attachment, get_old_unclaimed_attachments

class Command(BaseCommand):
    help = """Remove unclaimed attachments from storage older than a supplied
              numerical value indicating the limit of how old the attachment can be.
              One week is taken as the default value."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument('-w', '--weeks',
                            dest='delta_weeks',
                            default=1,
                            help="Limiting value of how old the file can be.")

        parser.add_argument('-f', '--for-real',
                            dest='for_real',
                            action='store_true',
                            default=False,
                            help="Actually remove the files from the storage.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        delta_weeks = options['delta_weeks']
        print("Deleting unclaimed attached files older than %s" % (delta_weeks,))
        print("")

        # print the list of files that are going to be removed
        old_attachments = get_old_unclaimed_attachments(delta_weeks)
        for old_attachment in old_attachments:
            print("%s created at %s" % (old_attachment.file_name, old_attachment.create_time))

        print("")
        if not options["for_real"]:
            print("This was a dry run. Pass -f to actually delete.")
            exit(1)

        do_delete_old_unclaimed_attachments(delta_weeks)
        print("")
        print("Unclaimed Files deleted.")
