import os
import subprocess
from argparse import ArgumentParser
from typing import Any

import requests
from django.conf import settings
from django.core.management.base import CommandError
from django.utils.crypto import get_random_string
from requests.models import Response
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, check_config
from zerver.lib.remote_server import (
    PushBouncerSession,
    send_json_to_push_bouncer,
    send_server_data_to_push_bouncer,
)

if settings.DEVELOPMENT:
    SECRETS_FILENAME = "zproject/dev-secrets.conf"
else:
    SECRETS_FILENAME = "/etc/zulip/zulip-secrets.conf"


class Command(ZulipBaseCommand):
    help = """Register a remote Zulip server for push notifications."""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--agree_to_terms_of_service",
            action="store_true",
            help="Agree to the Zulipchat Terms of Service: https://zulip.com/policies/terms.",
        )
        action = parser.add_mutually_exclusive_group()
        action.add_argument(
            "--rotate-key",
            action="store_true",
            help="Automatically rotate your server's zulip_org_key",
        )
        action.add_argument(
            "--deactivate",
            action="store_true",
            help="Deregister the server; this will stop mobile push notifications",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEVELOPMENT:
            check_config()

        if not settings.ZULIP_ORG_ID:
            raise CommandError(
                "Missing zulip_org_id; run scripts/setup/generate_secrets.py to generate."
            )
        if not settings.ZULIP_ORG_KEY:
            raise CommandError(
                "Missing zulip_org_key; run scripts/setup/generate_secrets.py to generate."
            )
        if not settings.ZULIP_SERVICES_URL:
            raise CommandError(
                "ZULIP_SERVICES_URL is not set; was the default incorrectly overridden in /etc/zulip/settings.py?"
            )
        if not settings.ZULIP_SERVICE_PUSH_NOTIFICATIONS:
            raise CommandError(
                "Please set ZULIP_SERVICE_PUSH_NOTIFICATIONS to True in /etc/zulip/settings.py"
            )

        if options["deactivate"]:
            send_json_to_push_bouncer("POST", "server/deactivate", {})
            print("Mobile Push Notification Service registration successfully deactivated!")
            return

        request = {
            "zulip_org_id": settings.ZULIP_ORG_ID,
            "zulip_org_key": settings.ZULIP_ORG_KEY,
            "hostname": settings.EXTERNAL_HOST,
            "contact_email": settings.ZULIP_ADMINISTRATOR,
        }
        if options["rotate_key"]:
            if not os.access(SECRETS_FILENAME, os.W_OK):
                raise CommandError(f"{SECRETS_FILENAME} is not writable by the current user.")
            request["new_org_key"] = get_random_string(64)

        print(
            "This command registers your server for the Mobile Push Notifications Service.\n"
            "Doing so will share basic metadata with the service's maintainers:\n\n"
            f"* This server's configured hostname: {request['hostname']}\n"
            f"* This server's configured contact email address: {request['contact_email']}\n"
            "* Metadata about each organization hosted by the server; see:\n\n"
            "    <https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#uploading-basic-metadata>\n\n"
            "Use of this service is governed by the Zulip Terms of Service:\n\n"
            "    <https://zulip.com/policies/terms>\n"
        )

        if not options["agree_to_terms_of_service"] and not options["rotate_key"]:
            tos_prompt = input(
                "Do you want to agree to the Zulip Terms of Service and proceed? [Y/n] "
            )
            print()
            if not (
                tos_prompt.lower() == "y" or tos_prompt.lower() == "" or tos_prompt.lower() == "yes"
            ):
                # Exit without registering; no need to print anything
                # special, as the "n" reply to the query is clear
                # enough about what happened.
                return

        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/register", request
        )

        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        if response.json()["created"]:
            print(
                "Your server is now registered for the Mobile Push Notification Service!\n"
                "Return to the documentation for next steps."
            )
        else:
            if options["rotate_key"]:
                print(f"Success! Updating {SECRETS_FILENAME} with the new key...")
                subprocess.check_call(
                    [
                        "crudini",
                        "--inplace",
                        "--set",
                        SECRETS_FILENAME,
                        "secrets",
                        "zulip_org_key",
                        request["new_org_key"],
                    ]
                )
            print("Mobile Push Notification Service registration successfully updated!")

    def _request_push_notification_bouncer_url(self, url: str, params: dict[str, Any]) -> Response:
        assert settings.ZULIP_SERVICES_URL is not None
        registration_url = settings.ZULIP_SERVICES_URL + url
        session = PushBouncerSession()
        try:
            response = session.post(registration_url, data=params)
        except requests.RequestException:
            raise CommandError(
                "Network error connecting to push notifications service "
                f"({settings.ZULIP_SERVICES_URL})",
            )
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            # Report nice errors from the Zulip API if possible.
            try:
                content_dict = response.json()
            except Exception:
                raise e

            raise CommandError("Error: " + content_dict["msg"])

        return response
