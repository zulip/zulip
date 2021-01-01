from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from zerver.lib.actions import do_delete_old_unclaimed_attachments
from zerver.models import get_old_unclaimed_attachments


class Command(BaseCommand):
    help = """Remove unclaimed attachments from storage older than a supplied
              numerical value indicating the limit of how old the attachment can be.
              One week is taken as the default value."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-w', '--weeks',
                            dest='delta_weeks',
                            default=5,
                            type=int,
                            help="Limiting value of how old the file can be.")

        parser.add_argument('-f', '--for-real',
                            action='store_true',
                            help="Actually remove the files from the storage.")

    def handle(self, *args: Any, **options: Any) -> None:
        delta_weeks = options['delta_weeks']
        print(f"Deleting unclaimed attached files older than {delta_weeks} weeks")

        # print the list of files that are going to be removed
        old_attachments = get_old_unclaimed_attachments(delta_weeks)
        for old_attachment in old_attachments:
            print(f"* {old_attachment.file_name} created at {old_attachment.create_time}")

        print("")
        if not options["for_real"]:
            raise CommandError("This was a dry run. Pass -f to actually delete.")

        do_delete_old_unclaimed_attachments(delta_weeks)
        print("")
        print("Unclaimed files deleted.")
