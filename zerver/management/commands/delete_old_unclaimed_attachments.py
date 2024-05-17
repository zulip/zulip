from argparse import ArgumentParser
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.uploads import do_delete_old_unclaimed_attachments
from zerver.lib.attachments import get_old_unclaimed_attachments
from zerver.lib.management import abort_unless_locked
from zerver.lib.upload import all_message_attachments, delete_message_attachments
from zerver.models import ArchivedAttachment, Attachment


class Command(BaseCommand):
    help = """Remove unclaimed attachments from storage older than a supplied
              numerical value indicating the limit of how old the attachment can be.
              The default is five weeks."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "-w",
            "--weeks",
            dest="delta_weeks",
            default=5,
            type=int,
            help="How long unattached attachments are preserved; defaults to 5 weeks.",
        )

        parser.add_argument(
            "-f",
            "--for-real",
            action="store_true",
            help="Actually remove the files from the storage.",
        )

        parser.add_argument(
            "-C",
            "--clean-up-storage",
            action="store_true",
            help="Examine all attachments in storage (local disk or S3) and remove "
            "any files which are not in the database. This may take a very long time!",
        )

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        delta_weeks = options["delta_weeks"]
        print(f"Deleting unclaimed attached files older than {delta_weeks} weeks")

        # print the list of files that are going to be removed
        old_attachments, old_archived_attachments = get_old_unclaimed_attachments(delta_weeks)
        for old_attachment in old_attachments:
            print(f"* {old_attachment.file_name} created at {old_attachment.create_time}")
        for old_archived_attachment in old_archived_attachments:
            print(
                f"* {old_archived_attachment.file_name} created at {old_archived_attachment.create_time}"
            )

        if options["for_real"]:
            do_delete_old_unclaimed_attachments(delta_weeks)
            print("")
            print("Unclaimed files deleted.")

        if options["clean_up_storage"]:
            print("")
            self.clean_attachment_upload_backend(dry_run=not options["for_real"])

        if not options["for_real"]:
            print("")
            raise CommandError("This was a dry run. Pass -f to actually delete.")

    def clean_attachment_upload_backend(self, dry_run: bool = True) -> None:
        cutoff = timezone_now() - timedelta(minutes=5)
        print(f"Removing extra files in storage black-end older than {cutoff.isoformat()}")
        to_delete = []
        for path_id, modified_at in all_message_attachments():
            if Attachment.objects.filter(path_id=path_id).exists():
                continue
            if ArchivedAttachment.objects.filter(path_id=path_id).exists():
                continue
            if modified_at > cutoff:
                # We upload files to the backend storage and _then_
                # make the database entry, so must give some leeway to
                # recently-added files which do not have DB rows.
                continue
            print(f"* {path_id} modified at {modified_at}")
            if dry_run:
                continue
            to_delete.append(path_id)
            if len(to_delete) > 1000:
                delete_message_attachments(to_delete)
                to_delete = []
        if not dry_run and len(to_delete) > 0:
            delete_message_attachments(to_delete)
