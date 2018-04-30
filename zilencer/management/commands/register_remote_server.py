from argparse import ArgumentParser
import requests
from typing import Any

from django.conf import settings

from zerver.lib.management import ZulipBaseCommand
from zilencer.models import RemoteZulipServer

class Command(ZulipBaseCommand):
    help = """Register a remote Zulip server for push notifications."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--agree_to_terms_of_service',
                            dest='agree_to_terms_of_service',
                            action='store_true',
                            default=False,
                            help="Agree to the Zulipchat Terms of Service: https://zulipchat.com/terms/.")

    def handle(self, **options: Any) -> None:
        if not options['agree_to_terms_of_service']:
            print("You must agree to the Zulipchat Terms of Service: https://zulipchat.com/terms/.")
            print("Run as")
            print("python manage.py register_remote_server --agree_to_terms_of_service")
            exit(1)

        zulip_org_id = settings.get('ZULIP_ORG_ID', '')
        if zulip_org_id is '':
            print("zulip_org_id is not set.")
            exit(1)
        zulip_org_key = settings.get('ZULIP_ORG_KEY', '')
        if zulip_org_key is '':
            print("zulip_org_key is not set.")
            exit(1)
        external_host = settings.get('EXTERNAL_HOST', '')
        if external_host is '':
            print("EXTERNAL_HOST is not set. You can set it in /etc/zulip/settings.py.")
            exit(1)
        zulip_administrator = settings.get('ZULIP_ADMINISTRATOR', '')
        if zulip_administrator is '':
            print("ZULIP_ADMINISTRATOR is not set. You can set it in /etc/zulip/settings.py.")
            exit(1)

        response = requests.post("https://zulipchat.com/remotes/server/register",
                                 params={"zulip_org_id": zulip_org_id,
                                         "zulip_org_key": zulip_org_key,
                                         "hostname": external_host,
                                         "contact_email": zulip_administrator})

        # TODO
        # try:
            # response.raise_for_status()
        # except:
            # print the error message
            # print that you can run the script again
        # if response.json()['created']:
        #     print("Server successfully registered.")
        # else:
        #     print("Server successfully updated.")
