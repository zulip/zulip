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
    prepare_for_registration_transfer_challenge,
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
            "--agree-to-terms-of-service",
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
            "--registration-transfer",
            action="store_true",
            help="""\
If your server uses a publicly verifiable SSL certificate for a
hostname that is already registered for Zulip services, transfers the
registration to this server by changing the zulip_org_key secret for
that registration and saving the updated secret in
/etc/zulip/zulip-secrets.conf.""",
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

        hostname = settings.EXTERNAL_HOST
        request: dict[str, object] = {
            "zulip_org_id": settings.ZULIP_ORG_ID,
            "zulip_org_key": settings.ZULIP_ORG_KEY,
            "hostname": hostname,
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
            "    <https://zulip.com/doc-permalinks/basic-metadata>\n\n"
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

        if options["registration_transfer"]:
            org_id, org_key = self.do_registration_transfer_flow(hostname)
            # We still want to proceed with a regular request to the registration endpoint,
            # as it'll update the registration with new information such as the contact email.
            request["zulip_org_id"] = org_id
            request["zulip_org_key"] = org_key
            settings.ZULIP_ORG_ID = org_id
            settings.ZULIP_ORG_KEY = org_key
            print()
            print("Proceeding to update the registration with current metadata...")

        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/register", request
        )

        send_server_data_to_push_bouncer(consider_usage_statistics=False, raise_on_error=True)

        if response.json()["created"]:
            print(
                "Your server is now registered for the Mobile Push Notification Service!\n"
                "Return to the documentation for next steps."
            )
        else:
            if options["rotate_key"]:
                print(f"Success! Updating {SECRETS_FILENAME} with the new key...")
                new_org_key = request["new_org_key"]
                assert isinstance(new_org_key, str)
                subprocess.check_call(
                    [
                        "crudini",
                        "--inplace",
                        "--set",
                        SECRETS_FILENAME,
                        "secrets",
                        "zulip_org_key",
                        new_org_key,
                    ]
                )
            print("Mobile Push Notification Service registration successfully updated!")

        if options["registration_transfer"]:
            print()
            print(
                "Make sure to restart the server next by running /home/zulip/deployments/current/scripts/restart-server "
                "so that the new credentials are reloaded."
            )

    def do_registration_transfer_flow(self, hostname: str) -> tuple[str, str]:
        params = {"hostname": hostname}
        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/register/transfer", params
        )
        verification_secret = response.json()["verification_secret"]

        print(
            "Received a verification secret from the service. Preparing to serve it at the verification URL."
        )
        token_for_push_bouncer = prepare_for_registration_transfer_challenge(verification_secret)

        print("Sending ACK to the service and awaiting completion of verification...")
        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/register/verify_challenge",
            dict(hostname=params["hostname"], access_token=token_for_push_bouncer),
        )

        org_id = response.json()["zulip_org_id"]
        org_key = response.json()["zulip_org_key"]
        # Update the secrets file.
        print("Success! Updating secrets file with received credentials.")
        subprocess.check_call(
            [
                "crudini",
                "--inplace",
                "--set",
                SECRETS_FILENAME,
                "secrets",
                "zulip_org_id",
                org_id,
            ]
        )
        subprocess.check_call(
            [
                "crudini",
                "--inplace",
                "--set",
                SECRETS_FILENAME,
                "secrets",
                "zulip_org_key",
                org_key,
            ]
        )
        print("Mobile Push Notification Service registration successfully transferred.")
        return org_id, org_key

    def _request_push_notification_bouncer_url(self, url: str, params: dict[str, Any]) -> Response:
        assert settings.ZULIP_SERVICES_URL is not None
        request_url = settings.ZULIP_SERVICES_URL + url
        session = PushBouncerSession()
        try:
            response = session.post(request_url, data=params)
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

            if (
                "code" in content_dict
                and content_dict["code"] == "HOSTNAME_ALREADY_IN_USE_BOUNCER_ERROR"
            ):
                print(
                    "--------------------------------\n"
                    "The hostname is already in use by another server. If you control the hostname \n"
                    "and want to transfer the registration to this server, you can run manage.py register_server \n"
                    "with the --registration-transfer flag.\n"
                    "Note that this will invalidate old credentials if another server is still using them.\n"
                    "\n"
                    "For more information, see: \n"
                    "\n"
                    "<https://zulip.com/doc-permalinks/registration-transfer>"
                )
                raise CommandError

            error_message = content_dict["msg"]
            raise CommandError(
                f'Error received from the push notification service: "{error_message}"'
            )

        return response
