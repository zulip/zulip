import subprocess
from argparse import ArgumentParser
from typing import Any, Dict

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
    """Register a remote Zulip server for push notifications."""
    help = """Register a remote Zulip server for push notifications."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--agree_to_terms_of_service",
            action="store_true",
            help="Agree to the Zulipchat Terms of Service: https://zulip.com/policies/terms.",
        )
        parser.add_argument(
            "--rotate-key",
            action="store_true",
            help="Automatically rotate your server's zulip_org_key",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Handle command line arguments passed to a command.

        This method performs various checks and operations based on the provided options.

        Args:
            *args: Any additional positional arguments passed to the command.
            **options: Any additional keyword arguments passed to the command.

        Raises:
            CommandError: If `settings.ZULIP_ORG_ID` or `settings.ZULIP_ORG_KEY` are
            missing, or if `settings.PUSH_NOTIFICATION_BOUNCER_URL` is not set and
            `settings.DEVELOPMENT` is False, or if the user does not agree to the terms of
            service.
        """
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

        request = {
            "zulip_org_id": settings.ZULIP_ORG_ID,
            "zulip_org_key": settings.ZULIP_ORG_KEY,
            "hostname": settings.EXTERNAL_HOST,
            "contact_email": settings.ZULIP_ADMINISTRATOR,
        }
        if options["rotate_key"]:
            request["new_org_key"] = get_random_string(64)

        self._log_params(request)

        if not options["agree_to_terms_of_service"] and not options["rotate_key"]:
            print(
                "To register, you must agree to the Zulipchat Terms of Service: "
                "https://zulip.com/policies/terms"
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
            if options["rotate_key"]:
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

    def _request_push_notification_bouncer_url(self, url: str, params: Dict[str, Any]) -> Response:
        """
        Send a POST request to the push notification bouncer URL.

        This method sends a POST request to the push notification bouncer URL with the
        specified
        URL and parameters. It returns the response from the server.

        Args:
            url (str): The URL to send the request to.
            params (Dict[str, Any]): The parameters to include in the request.

        Returns:
            Response: The response from the server.

        Raises:
            CommandError: If there is a network error connecting to the push notifications service.
            CommandError: If there is an error reported by the push notifications service.
        """
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        registration_url = settings.PUSH_NOTIFICATION_BOUNCER_URL + url
        session = PushBouncerSession()
        try:
            response = session.post(registration_url, params=params)
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
        """
        Log the data that will be submitted to the push notification service.

        This method logs the data that will be submitted to the push notification service. It
        prints each parameter key and value to the console.

        Args:
            params (Dict[str, Any]): The parameters to log.
        """
        print("The following data will be submitted to the push notification service:")
        for key in sorted(params.keys()):
            print(f"  {key}: {params[key]}")
        print("")
