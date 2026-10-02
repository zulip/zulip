from typing import Any
from uuid import uuid4

import responses
from django.utils.timezone import now as timezone_now
from requests.exceptions import ConnectionError
from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase
from zilencer.lib.communities_directory import (
    get_remote_realms_asking_to_be_advertised,
    probe_remote_realms_for_communities_directory,
)
from zilencer.models import RemoteRealm, RemoteZulipServer

logger_string = "zilencer.lib.communities_directory"


class ProbeRemoteRealmsForCommunitiesDirectoryTest(ZulipTestCase):
    SERVER_SETTINGS_URL = "https://community.example.com/api/v1/server_settings"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.server = RemoteZulipServer.objects.create(
            uuid=uuid4(),
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=timezone_now(),
        )
        self.remote_realm = RemoteRealm.objects.create(
            server=self.server,
            uuid=uuid4(),
            uuid_owner_secret="dummy-secret",
            host="community.example.com",
            realm_date_created=timezone_now(),
            asks_to_advertise_in_communities_directory=True,
            description="A place to talk about Zulip",
            invite_required=False,
        )

    def recorded_as_reachable(self, **response_kwargs: Any) -> bool:
        responses.reset()
        responses.add(responses.GET, self.SERVER_SETTINGS_URL, **response_kwargs)

        probe_remote_realms_for_communities_directory()
        self.remote_realm.refresh_from_db()
        reached = self.remote_realm.last_reachable_datetime is not None

        # reset
        self.remote_realm.last_reachable_datetime = None
        self.remote_realm.save(update_fields=["last_reachable_datetime"])

        return reached

    @responses.activate
    def test_remote_realm_reachability(self) -> None:
        with self.assertLogs(logger_string, level="INFO") as m:
            self.assertTrue(self.recorded_as_reachable(json={"zulip_version": "11.0"}, status=200))

            self.assertFalse(self.recorded_as_reachable(status=500))
            self.assertFalse(self.recorded_as_reachable(body="not json", status=200))
            # Something answered, but it is not a Zulip server.
            self.assertFalse(self.recorded_as_reachable(json={}, status=200))
            # Valid JSON that is not an object at all.
            self.assertFalse(self.recorded_as_reachable(body="null", status=200))
            self.assertFalse(self.recorded_as_reachable(body=ConnectionError("unreachable")))

        host = self.remote_realm.host
        self.assertEqual(
            m.output,
            [
                f"INFO:{logger_string}:Probed 1 organizations, reached 1",
                f"INFO:{logger_string}:Probe for {host} returned status 500",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} did not return valid JSON",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} did not answer as a Zulip realm",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} did not answer as a Zulip realm",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
                f"INFO:{logger_string}:Probe for {host} failed: unreachable",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
            ],
        )

    @responses.activate
    def test_invalid_host(self) -> None:
        # The host is whatever the organization's server uploaded.
        self.remote_realm.host = "["
        self.remote_realm.save(update_fields=["host"])

        with self.assertLogs(logger_string, level="INFO") as m:
            probe_remote_realms_for_communities_directory()

        self.assertEqual(
            m.output,
            [
                f"INFO:{logger_string}:Probe for [ failed: Invalid IPv6 URL",
                f"INFO:{logger_string}:Probed 1 organizations, reached 0",
            ],
        )
        self.assert_length(responses.calls, 0)
        self.remote_realm.refresh_from_db()
        self.assertIsNone(self.remote_realm.last_reachable_datetime)

    @responses.activate
    def test_organization_not_meeting_base_criteria_is_not_probed(self) -> None:
        self.remote_realm.description = ""
        self.remote_realm.save(update_fields=["description"])

        with self.assertLogs(logger_string, level="INFO") as m:
            probe_remote_realms_for_communities_directory()

        self.assertEqual(m.output, [f"INFO:{logger_string}:Probed 0 organizations, reached 0"])
        self.assert_length(responses.calls, 0)
        self.remote_realm.refresh_from_db()
        self.assertIsNone(self.remote_realm.last_reachable_datetime)

    def test_get_remote_realms_asking_to_be_advertised(self) -> None:
        self.assertEqual(list(get_remote_realms_asking_to_be_advertised()), [self.remote_realm])

        for attr_name in ["registration_deactivated", "realm_deactivated", "realm_locally_deleted"]:
            setattr(self.remote_realm, attr_name, True)
            self.remote_realm.save(update_fields=[attr_name])
            self.assertEqual(list(get_remote_realms_asking_to_be_advertised()), [])
            setattr(self.remote_realm, attr_name, False)
            self.remote_realm.save(update_fields=[attr_name])

        self.remote_realm.asks_to_advertise_in_communities_directory = False
        self.remote_realm.save(update_fields=["asks_to_advertise_in_communities_directory"])
        self.assertEqual(list(get_remote_realms_asking_to_be_advertised()), [])
