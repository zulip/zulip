import argparse
import os
import tempfile
import logging
from getpass import getpass
from typing import Any
from base64 import b64encode

from django.core.management.base import BaseCommand, CommandError, CommandParser

from zerver.data_import.ryver import do_convert_data


class Command(BaseCommand):
    help = """Fetch Ryver data from api then convert into Zulip data format."""

    def add_arguments(self, parser: CommandParser) -> None:        
        # API Parameters
        parser.add_argument('--account-base64', dest='base64', action='store', default=None, help='Ryver username:password in base64, skips --account-user')
        parser.add_argument('--account-user', dest='account_user', action='store', default=None, help='Valid Ryver username/email used to typically login. Please use base64 method instead')
        parser.add_argument('--api-endpoint', dest='api_endpoint', action='store', default=None, help='Endpoint to access the Ryver api Eg https://yourorg.ryver.com/api/1/odata.svc')
        
        # Convert Parameters
        parser.add_argument('--output', dest='output_dir',
                            action="store", default=None,
                            help='Directory to write exported data to.')
        
        parser.add_argument('--threads',
                            dest='threads',
                            action="store",
                            default=6,
                            help='Threads to download avatars and attachments faster')

        parser.formatter_class = argparse.RawTextHelpFormatter

    def handle(self, *args: Any, **options: Any) -> None:
        output_dir = options["output_dir"]
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="converted-ryver-data-")
        else:
            output_dir = os.path.realpath(output_dir)
        
        num_threads = int(options['threads'])
        if num_threads < 1:
            raise CommandError('You must have at least one thread.')
    
        logging.info("==Ryver Data Handler - Parsing Extraction Args==")
        api_endpoint = options["api_endpoint"]
        if api_endpoint is None or api_endpoint == '':
            raise CommandError('You must enter a valid Ryver API endpoint in order to extract. See -h for example')
        # Strip tailing / if provided
        if api_endpoint[-1] == '/':
            api_endpoint = api_endpoint[:-1]

        base64 = options["base64"]
        if base64 is None or base64 == '':
            account_user = options["account_user"]
            if account_user is None or account_user == '':
                raise CommandError('If no base64 encoding for account was included, you must enter a valid --acount-user in order to extract')
            else:
                print('Please Input password for account: {}'.format(account_user))
                # grab secure password from command line next
                account_password = getpass()
                if account_password == '':
                    raise CommandError('No input was given for password. Restart command to try again.')
                else:
                    base64 = b64encode(str.encode('{username}:{password}'.format(username=account_user, password=account_password))).decode('utf-8')
        
        logging.info("==Ryver Data Handler - Performing Ryver extraction and conversion==")
        do_convert_data(base64=base64, api_endpoint=options["api_endpoint"], output_dir=output_dir, threads=num_threads)
        logging.info("==Ryver Data Handler - Extract and convert finished==")
        logging.info("==Ryver Data Handler - Finished==")
