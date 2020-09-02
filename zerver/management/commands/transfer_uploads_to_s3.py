from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.lib.transfer import transfer_uploads_to_s3


class Command(BaseCommand):
    help = """Transfer uploads to S3 """

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--processes',
                            default=settings.DEFAULT_DATA_EXPORT_IMPORT_PARALLELISM,
                            help='Processes to use for exporting uploads in parallel')

    def handle(self, *args: Any, **options: Any) -> None:
        num_processes = int(options['processes'])
        if num_processes < 1:
            raise CommandError('You must have at least one process.')

        if not settings.LOCAL_UPLOADS_DIR:
            raise CommandError('Please set the value of LOCAL_UPLOADS_DIR.')

        transfer_uploads_to_s3(num_processes)
        print("Transfer to S3 completed successfully.")
