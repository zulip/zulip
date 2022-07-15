import base64
import subprocess
from argparse import ArgumentParser
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.core.management.base import CommandError
from django.utils.crypto import get_random_string
from requests.models import Response

from zerver.lib.management import ZulipBaseCommand, check_config
from zerver.lib.remote_server import PushBouncerSession

if settings.DEVELOPMENT:
    SECRETS_FILENAME = "zproject/dev-secrets.conf"
else:
    SECRETS_FILENAME = "/etc/zulip/zulip-secrets.conf"


class Command(ZulipBaseCommand):
    help = """Register a remote Zulip server for push notifications."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--register",
            action="store_true",
            help="Register your server for the Mobile Push Notification Service.",
        )
        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate your server's Mobile Push Notification Service registration.",
        )
        parser.add_argument(
            "--agree_to_terms_of_service",
            action="store_true",
            help="Agree to the Zulipchat Terms of Service: https://zulip.com/terms/.",
        )
        parser.add_argument(
            "--rotate-key",
            action="store_true",
            help="Automatically rotate your server's zulip_org_key",
        )

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
        if settings.PUSH_NOTIFICATION_BOUNCER_URL is None:
            if settings.DEVELOPMENT:
                settings.PUSH_NOTIFICATION_BOUNCER_URL = (
                    settings.EXTERNAL_URI_SCHEME + settings.EXTERNAL_HOST
                )
            else:
                raise CommandError(
                    "Please uncomment PUSH_NOTIFICATION_BOUNCER_URL "
                    "in /etc/zulip/settings.py (remove the '#')"
                )

        if options["register"]:
            self._handle_register_subcommand(*args, **options)
        elif options["rotate_key"]:
            self._handle_rotate_key_subcommand(*args, **options)
        elif options["deactivate"]:
            self._handle_deactivate_subcommand(*args, **options)

    def _handle_rotate_key_subcommand(self, *args: Any, **options: Any) -> None:
        request = {
            "zulip_org_id": settings.ZULIP_ORG_ID,
            "zulip_org_key": settings.ZULIP_ORG_KEY,
            "hostname": settings.EXTERNAL_HOST,
            "contact_email": settings.ZULIP_ADMINISTRATOR,
            "new_org_key": get_random_string(64),
        }
        self._log_params(request)

        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/register", request
        )

        assert response.json()["result"] == "success"
        print(f"Success! Updating {SECRETS_FILENAME} with the new key...")
        subprocess.check_call(
            [
                "crudini",
                "--set",
                SECRETS_FILENAME,
                "secrets",
                "zulip_org_key",
                request["new_org_key"],
            ]
        )
        print("Mobile Push Notification Service registration successfully updated!")

    def _handle_register_subcommand(self, *args: Any, **options: Any) -> None:
        request = {
            "zulip_org_id": settings.ZULIP_ORG_ID,
            "zulip_org_key": settings.ZULIP_ORG_KEY,
            "hostname": settings.EXTERNAL_HOST,
            "contact_email": settings.ZULIP_ADMINISTRATOR,
        }
        self._log_params(request)

        if not options["agree_to_terms_of_service"]:
            print(
                "To register, you must agree to the Zulipchat Terms of Service: "
                "https://zulip.com/terms/"
            )
            tos_prompt = input("Do you agree to the Terms of Service? [Y/n] ")
            print("")
            if not (
                tos_prompt.lower() == "y" or tos_prompt.lower() == "" or tos_prompt.lower() == "yes"
            ):
                raise CommandError("Aborting, since Terms of Service have not been accepted.")

        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/register", request
        )

        assert response.json()["result"] == "success"
        if response.json()["created"]:
            print(
                "You've successfully registered for the Mobile Push Notification Service!\n"
                "To finish setup for sending push notifications:"
            )
            print(
                "- Restart the server, using /home/zulip/deployments/current/scripts/restart-server"
            )
            print("- Return to the documentation to learn how to test push notifications")
        else:
            print("Mobile Push Notification Service registration successfully updated!")

    def _handle_deactivate_subcommand(self, *args: Any, **options: Any) -> None:
        credentials = "{}:{}".format(settings.ZULIP_ORG_ID, settings.ZULIP_ORG_KEY)
        basic_auth = "Basic " + base64.b64encode(credentials.encode()).decode()

        response = self._request_push_notification_bouncer_url(
            "/api/v1/remotes/server/deactivate", headers={"authorization": basic_auth}
        )

        assert response.json()["result"] == "success"
        print("Mobile Push Notification Service registration successfully deactivated!")

    def _request_push_notification_bouncer_url(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = {},
        headers: Optional[Dict[str, Any]] = {},
    ) -> Response:
        registration_url = settings.PUSH_NOTIFICATION_BOUNCER_URL + url
        session = PushBouncerSession()
        try:
            response = session.post(registration_url, params=params, headers=headers)
        except requests.RequestException:
            raise CommandError(
                "Network error connecting to push notifications service "
                f"({settings.PUSH_NOTIFICATION_BOUNCER_URL})",
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

    def _log_params(self, params: Dict[str, Any]) -> None:
        print("The following data will be submitted to the push notification service:")
        for key in sorted(params.keys()):
            print(f"  {key}: {params[key]}")
        print("")
