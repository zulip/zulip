"""Client for communicating with nodl-backend API for video meetings."""

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.models import UserProfile

logger = logging.getLogger(__name__)


class NodlBackendSession(OutgoingSession):
    def __init__(self) -> None:
        super().__init__(role="nodl_backend", timeout=10)


@dataclass
class MeetingCredentials:
    room_name: str
    jwt: str
    domain: str
    join_url: str


class NodlBackendError(JsonableError):
    def __init__(self, message: str = "Failed to communicate with meeting service") -> None:
        super().__init__(message)


class NodlBackendService:
    """Client for nodl-backend video meeting API."""

    def __init__(self) -> None:
        self.base_url = getattr(settings, "NODL_BACKEND_URL", "")
        self.api_key = getattr(settings, "NODL_BACKEND_API_KEY", "")

    def _get_headers(self, user: UserProfile) -> dict[str, str]:
        """Build headers for nodl-backend API requests."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        user: UserProfile,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request to nodl-backend."""
        if not self.base_url:
            raise NodlBackendError("Video meetings are not configured")

        url = f"{self.base_url.rstrip('/')}{endpoint}"
        headers = self._get_headers(user)

        try:
            session = NodlBackendSession()
            if method == "POST":
                response = session.post(url, json=data, headers=headers)
            else:
                response = session.get(url, headers=headers)

            if not response.ok:
                logger.error(
                    "nodl-backend request failed: %s %s -> %d",
                    method,
                    endpoint,
                    response.status_code,
                )
                raise NodlBackendError("Failed to create meeting")

            return response.json()
        except Exception as e:
            if isinstance(e, NodlBackendError):
                raise
            logger.exception("nodl-backend request error")
            raise NodlBackendError("Failed to connect to meeting service") from e

    def create_instant_meeting(
        self,
        workspace_id: str,
        user: UserProfile,
    ) -> MeetingCredentials:
        """Create an instant video meeting via nodl-backend JaaS integration.

        Args:
            workspace_id: The workspace UUID
            user: The user creating the meeting

        Returns:
            MeetingCredentials with room_name, jwt, domain, and join_url
        """
        endpoint = f"/api/v1/workspaces/{workspace_id}/meetings/instant"
        result = self._make_request("POST", endpoint, user)

        room_name = result["room_name"]
        domain = result["domain"]
        jwt = result["jwt"]
        jaas_app_id = getattr(settings, "JAAS_APP_ID", "")

        # Build the join URL
        join_url = f"https://{domain}/{jaas_app_id}/{room_name}?jwt={jwt}"

        return MeetingCredentials(
            room_name=room_name,
            jwt=jwt,
            domain=domain,
            join_url=join_url,
        )

    def get_join_token(
        self,
        workspace_id: str,
        room_name: str,
        user: UserProfile,
    ) -> MeetingCredentials:
        """Get a JWT token to join an existing meeting.

        Args:
            workspace_id: The workspace UUID
            room_name: The meeting room identifier
            user: The user joining the meeting

        Returns:
            MeetingCredentials with room_name, jwt, domain, and join_url
        """
        endpoint = f"/api/v1/workspaces/{workspace_id}/meetings/join/{room_name}"
        result = self._make_request("POST", endpoint, user)

        domain = result["domain"]
        jwt = result["jwt"]
        jaas_app_id = getattr(settings, "JAAS_APP_ID", "")

        # Build the join URL
        join_url = f"https://{domain}/{jaas_app_id}/{room_name}?jwt={jwt}"

        return MeetingCredentials(
            room_name=room_name,
            jwt=jwt,
            domain=domain,
            join_url=join_url,
        )
